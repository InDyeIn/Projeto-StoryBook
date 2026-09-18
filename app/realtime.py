"""Hub de WebSocket.

O banco continua sendo a fonte da verdade — o WebSocket apenas avisa quem está
com a página aberta que algo mudou. Se a conexão cair, recarregar a página
reconstrói o estado inteiro.

Canais:
    room:<room_id>   eventos da mesa (tokens, cenas, chat, membros)
    user:<user_id>   eventos pessoais (DM, convites, pedidos de amizade)
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("storybook.realtime")


def _encode(value: Any) -> Any:
    """Serializa datas e enums que aparecem nos objetos do SQLAlchemy."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Não sei serializar {type(value)!r}")


@dataclass(frozen=True)
class Connection:
    websocket: WebSocket
    user_id: str


class ConnectionManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[Connection]] = defaultdict(set)
        self._lock = asyncio.Lock()

    @staticmethod
    def room_channel(room_id: str) -> str:
        return f"room:{room_id}"

    @staticmethod
    def user_channel(user_id: str) -> str:
        return f"user:{user_id}"

    async def join(self, channel: str, websocket: WebSocket, user_id: str) -> Connection:
        connection = Connection(websocket=websocket, user_id=user_id)
        async with self._lock:
            self._channels[channel].add(connection)
        return connection

    async def leave(self, channel: str, connection: Connection) -> None:
        async with self._lock:
            self._channels[channel].discard(connection)
            if not self._channels[channel]:
                self._channels.pop(channel, None)

    def members(self, channel: str) -> set[str]:
        """Ids de usuário com pelo menos uma aba aberta neste canal."""
        return {c.user_id for c in self._channels.get(channel, set())}

    async def broadcast(
        self,
        channel: str,
        event: str,
        payload: Any = None,
        *,
        exclude_user: str | None = None,
        only_user: str | None = None,
    ) -> None:
        connections = list(self._channels.get(channel, set()))
        if not connections:
            return

        message = json.dumps({"event": event, "data": payload}, default=_encode)
        dead: list[Connection] = []

        for connection in connections:
            if exclude_user and connection.user_id == exclude_user:
                continue
            if only_user and connection.user_id != only_user:
                continue
            try:
                await connection.websocket.send_text(message)
            except Exception:  # noqa: BLE001 — conexão morta, limpa depois
                dead.append(connection)

        if dead:
            async with self._lock:
                for connection in dead:
                    self._channels[channel].discard(connection)

    async def to_room(self, room_id: str, event: str, payload: Any = None, **kwargs) -> None:
        await self.broadcast(self.room_channel(room_id), event, payload, **kwargs)

    async def to_user(self, user_id: str, event: str, payload: Any = None) -> None:
        await self.broadcast(self.user_channel(user_id), event, payload)


manager = ConnectionManager()
