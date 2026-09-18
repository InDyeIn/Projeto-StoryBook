"""Canais WebSocket.

    /ws/mesa/{slug}   eventos da mesa (tokens, cenas, chat, membros, presença)
    /ws/usuario       eventos pessoais (mensagens diretas, convites, amizades)

Autenticação usa o mesmo cookie de sessão das páginas: não há token separado
para vazar. Quem não é membro da mesa é desconectado antes de receber qualquer
evento.
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import Presence, Room, Session, Token, User, utcnow
from app.permissions import can
from app.realtime import manager
from app.security import tokens_match, unsign_session
from app.services import public_user

logger = logging.getLogger("storybook.ws")
router = APIRouter()

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404


def _authenticate(websocket: WebSocket) -> User | None:
    """Resolve o usuário a partir do cookie. Usa sessão própria de banco."""
    raw = websocket.cookies.get(settings.session_cookie)
    if not raw:
        return None

    parsed = unsign_session(raw)
    if not parsed:
        return None

    session_id, token = parsed
    db = SessionLocal()
    try:
        session = db.get(Session, session_id)
        if session is None or not tokens_match(token, session.token_hash):
            return None
        if session.is_expired:
            return None
        db.expunge(session.user)
        return session.user
    finally:
        db.close()


#: Por quanto tempo o veredito de "pode mover este token" fica em cache.
#: Uma prévia de arrasto chega a cada ~45 ms; consultar o banco a cada evento
#: seria desperdício, e a resposta quase nunca muda no meio de um arrasto.
VEREDITO_TTL = 3.0


def _pode_arrastar(user_id: str, room_id: str, token_id: str) -> bool:
    """Confere no banco se este usuário pode mover este token.

    Roda numa thread (o SQLAlchemy aqui é síncrono) para não travar o laço de
    eventos enquanto alguém arrasta.
    """
    db = SessionLocal()
    try:
        token = db.get(Token, token_id)
        if token is None or token.scene.room_id != room_id:
            return False

        room = db.get(Room, room_id)
        membro = room.member_for(user_id) if room else None
        if membro is None:
            return False

        if token.is_locked and not can(membro, "token.move.any"):
            return False
        if can(membro, "token.move.any"):
            return True
        return token.owner_id == user_id and can(membro, "token.move.own")
    finally:
        db.close()


def _set_presence(user_id: str, presence: Presence) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is not None:
            user.presence = presence
            user.last_seen_at = utcnow()
            db.commit()
    finally:
        db.close()


@router.websocket("/ws/mesa/{slug}")
async def room_socket(websocket: WebSocket, slug: str):
    user = _authenticate(websocket)
    if user is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    db = SessionLocal()
    try:
        room = db.scalar(select(Room).where(Room.slug == slug))
        if room is None:
            await websocket.close(code=CLOSE_NOT_FOUND)
            return
        if room.member_for(user.id) is None:
            await websocket.close(code=CLOSE_FORBIDDEN)
            return
        room_id = room.id
    finally:
        db.close()

    await websocket.accept()
    channel = manager.room_channel(room_id)
    connection = await manager.join(channel, websocket, user.id)
    _set_presence(user.id, Presence.ONLINE)

    # Quem chega precisa saber quem já estava; quem estava precisa saber de quem chegou.
    await websocket.send_json({"event": "presence:list", "data": sorted(manager.members(channel))})
    await manager.broadcast(
        channel, "presence:joined", public_user(user), exclude_user=user.id
    )

    #: cache de "pode arrastar" por token, só para esta conexão
    vereditos: dict[str, tuple[bool, float]] = {}

    try:
        while True:
            payload = await websocket.receive_json()
            event = payload.get("event")

            if event == "ping":
                await websocket.send_json({"event": "pong"})

            elif event == "cursor":
                # Ponteiro do mouse no mapa: efêmero, nunca vai para o banco.
                await manager.broadcast(
                    channel,
                    "cursor",
                    {"user_id": user.id, **(payload.get("data") or {})},
                    exclude_user=user.id,
                )

            elif event == "token:dragging":
                # Prévia do arrasto. A posição definitiva é gravada pela API
                # REST, que faz a sua própria checagem — mas a prévia também
                # precisa ser verificada: sem isso, quem não tem permissão
                # conseguiria mexer o token na tela dos outros.
                dados = payload.get("data") or {}
                token_id = dados.get("token_id")
                if not isinstance(token_id, str):
                    continue

                agora = time.monotonic()
                veredito = vereditos.get(token_id)
                if veredito is None or veredito[1] < agora:
                    permitido = await asyncio.to_thread(
                        _pode_arrastar, user.id, room_id, token_id
                    )
                    vereditos[token_id] = (permitido, agora + VEREDITO_TTL)
                else:
                    permitido = veredito[0]

                if not permitido:
                    continue

                await manager.broadcast(
                    channel, "token:dragging", dados, exclude_user=user.id
                )

            elif event == "typing":
                await manager.broadcast(
                    channel,
                    "typing",
                    {"user_id": user.id, "display_name": user.display_name},
                    exclude_user=user.id,
                )

    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("erro no socket da mesa %s", slug)
    finally:
        await manager.leave(channel, connection)
        if user.id not in manager.members(channel):
            await manager.broadcast(channel, "presence:left", {"user_id": user.id})
        _set_presence(user.id, Presence.OFFLINE)


@router.websocket("/ws/usuario")
async def user_socket(websocket: WebSocket):
    user = _authenticate(websocket)
    if user is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    await websocket.accept()
    channel = manager.user_channel(user.id)
    connection = await manager.join(channel, websocket, user.id)
    _set_presence(user.id, Presence.ONLINE)

    try:
        while True:
            payload = await websocket.receive_json()
            if payload.get("event") == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("erro no socket pessoal de %s", user.username)
    finally:
        await manager.leave(channel, connection)
        if not manager.members(channel):
            _set_presence(user.id, Presence.OFFLINE)
