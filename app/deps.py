"""Dependências de requisição: usuário atual, CSRF e acesso a salas."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_db
from app.models import Room, RoomMember, Session, User, utcnow
from app.permissions import can
from app.security import csrf_valid, tokens_match, unsign_session

DbDep = Annotated[DbSession, Depends(get_db)]


def _load_session(request: Request, db: DbSession) -> Session | None:
    raw = request.cookies.get(settings.session_cookie)
    if not raw:
        return None

    parsed = unsign_session(raw)
    if not parsed:
        return None

    session_id, token = parsed
    session = db.get(Session, session_id)
    if session is None or not tokens_match(token, session.token_hash):
        return None
    if session.is_expired:
        db.delete(session)
        db.commit()
        return None
    return session


def get_optional_user(request: Request, db: DbDep) -> User | None:
    """Usuário da requisição, ou ``None``. Usado nas páginas públicas."""
    session = _load_session(request, db)
    if session is None:
        request.state.session_id = None
        request.state.user = None
        return None

    request.state.session_id = session.id
    user = session.user
    request.state.user = user
    # Marca presença sem escrever no banco a cada request.
    if (utcnow().replace(tzinfo=None) - session.user.last_seen_at.replace(tzinfo=None)).seconds > 300:
        user.last_seen_at = utcnow()
        db.commit()
    return user


def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    """Exige login. Rotas de página tratam o 401 redirecionando para /entrar."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Faça login para continuar.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


async def verify_csrf(request: Request) -> None:
    """Confere o token CSRF em toda requisição que altera estado."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    session_id = getattr(request.state, "session_id", None)
    if session_id is None:
        parsed = unsign_session(request.cookies.get(settings.session_cookie, ""))
        session_id = parsed[0] if parsed else None
    if session_id is None:
        return  # sem sessão não há o que proteger (login/cadastro)

    token = request.headers.get("x-csrf-token")
    if not token:
        content_type = request.headers.get("content-type", "")
        if "form" in content_type:
            form = await request.form()
            token = str(form.get("csrf_token") or "")

    if not csrf_valid(session_id, token or ""):
        raise HTTPException(status_code=403, detail="Token de segurança inválido. Recarregue a página.")


def load_room(db: DbSession, slug_or_id: str) -> Room:
    room = db.scalar(select(Room).where(Room.slug == slug_or_id))
    if room is None:
        room = db.get(Room, slug_or_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Sala não encontrada.")
    return room


def require_membership(db: DbSession, room: Room, user: User) -> RoomMember:
    member = room.member_for(user.id)
    if member is None:
        raise HTTPException(status_code=403, detail="Você não participa desta mesa.")
    return member


def require_permission(member: RoomMember, permission: str) -> None:
    if not can(member, permission):
        raise HTTPException(
            status_code=403, detail="Você não tem permissão para isso nesta mesa."
        )
