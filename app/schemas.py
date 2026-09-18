"""Schemas de entrada da API (Pydantic v2).

Mensagens de erro em português — elas aparecem direto na tela para o usuário.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
USERNAME = re.compile(r"^[a-z0-9_]+$")


class Base(BaseModel):
    model_config = {"str_strip_whitespace": True}


def _check_color(value: str | None) -> str | None:
    if value is None:
        return None
    if not HEX_COLOR.match(value):
        raise ValueError("Use uma cor hexadecimal, ex.: #7c5cff")
    return value.lower()


# ---------------------------------------------------------------------------
#  Conta
# ---------------------------------------------------------------------------


class RegisterIn(Base):
    email: EmailStr
    username: str = Field(min_length=3, max_length=24)
    display_name: str = Field(min_length=2, max_length=48)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.lower()
        if not USERNAME.match(value):
            raise ValueError("Use apenas letras minúsculas, números e _")
        return value


class LoginIn(Base):
    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ShowcaseItem(Base):
    label: str = Field(max_length=80, default="")
    value: str = Field(max_length=400, default="")


class ShowcaseBlock(Base):
    id: str = Field(max_length=32)
    type: Literal["links", "text", "systems", "characters"]
    title: str = Field(max_length=60)
    items: list[ShowcaseItem] = Field(default_factory=list, max_length=12)


class ProfileIn(Base):
    display_name: str | None = Field(default=None, min_length=2, max_length=48)
    tagline: str | None = Field(default=None, max_length=140)
    bio: str | None = Field(default=None, max_length=4000)
    pronouns: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=64)
    accent_color: str | None = None
    avatar_url: str | None = Field(default=None, max_length=512)
    banner_url: str | None = Field(default=None, max_length=512)
    showcase: list[ShowcaseBlock] | None = Field(default=None, max_length=8)

    _color = field_validator("accent_color")(_check_color)


class PresenceIn(Base):
    presence: Literal["ONLINE", "AWAY", "BUSY", "OFFLINE"]


# ---------------------------------------------------------------------------
#  Salas
# ---------------------------------------------------------------------------


class RoomCreateIn(Base):
    name: str = Field(min_length=3, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    system_id: str = Field(min_length=1, max_length=48)
    is_public: bool = False
    max_players: int = Field(default=6, ge=1, le=32)
    system_config: dict[str, Any] = Field(default_factory=dict)


class RoomUpdateIn(Base):
    name: str | None = Field(default=None, min_length=3, max_length=64)
    description: str | None = Field(default=None, max_length=2000)
    banner_url: str | None = Field(default=None, max_length=512)
    is_public: bool | None = None
    max_players: int | None = Field(default=None, ge=1, le=32)
    system_config: dict[str, Any] | None = None


class JoinIn(Base):
    invite_code: str = Field(min_length=4, max_length=12)


class InviteIn(Base):
    username: str
    role: Literal["PLAYER", "SPECTATOR", "CO_GM"] = "PLAYER"
    add_directly: bool = False


class MemberUpdateIn(Base):
    role: Literal["GM", "CO_GM", "PLAYER", "SPECTATOR"] | None = None
    color: str | None = None
    nickname: str | None = Field(default=None, max_length=48)
    permissions: dict[str, bool] | None = None

    _color = field_validator("color")(_check_color)


# ---------------------------------------------------------------------------
#  Cenas e tokens
# ---------------------------------------------------------------------------


class SceneIn(Base):
    name: str = Field(min_length=1, max_length=64)
    background_url: str | None = Field(default=None, max_length=512)
    background_color: str | None = None
    grid_type: Literal["SQUARE", "HEX", "NONE"] | None = None
    grid_size: int | None = Field(default=None, ge=16, le=256)
    grid_color: str | None = None
    grid_visible: bool | None = None
    snap_to_grid: bool | None = None
    width: int | None = Field(default=None, ge=5, le=200)
    height: int | None = Field(default=None, ge=5, le=200)

    _bg = field_validator("background_color")(_check_color)
    _grid = field_validator("grid_color")(_check_color)


class SceneUpdateIn(SceneIn):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    is_active: bool | None = None


class TokenCreateIn(Base):
    scene_id: str
    name: str = Field(min_length=1, max_length=48)
    character_id: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    color: str | None = None
    x: float = 0
    y: float = 0
    width: float = Field(default=64, ge=8, le=2000)
    height: float = Field(default=64, ge=8, le=2000)
    layer: Literal["BACKGROUND", "TOKENS", "GM_ONLY"] = "TOKENS"

    _color = field_validator("color")(_check_color)


class TokenUpdateIn(Base):
    name: str | None = Field(default=None, min_length=1, max_length=48)
    character_id: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    color: str | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = Field(default=None, ge=8, le=2000)
    height: float | None = Field(default=None, ge=8, le=2000)
    rotation: float | None = None
    layer: Literal["BACKGROUND", "TOKENS", "GM_ONLY"] | None = None
    is_visible: bool | None = None
    is_locked: bool | None = None
    statuses: list[str] | None = Field(default=None, max_length=12)

    _color = field_validator("color")(_check_color)


# ---------------------------------------------------------------------------
#  Fichas
# ---------------------------------------------------------------------------


class CharacterCreateIn(Base):
    name: str = Field(min_length=1, max_length=64)
    system_id: str | None = None
    room_id: str | None = None
    is_npc: bool = False
    avatar_url: str | None = Field(default=None, max_length=512)


class CharacterUpdateIn(Base):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)
    visibility: Literal["PRIVATE", "PARTY", "PUBLIC"] | None = None
    is_npc: bool | None = None
    #: Patch por caminho: {"competencias.burocracia": 4}
    patch: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
#  Mensagens
# ---------------------------------------------------------------------------


class MessageIn(Base):
    body: str = Field(min_length=1, max_length=4000)


class DirectMessageIn(MessageIn):
    kind: Literal["TEXT", "ROOM_INVITE"] = "TEXT"
    room_id: str | None = None


class RoomMessageIn(MessageIn):
    whisper_to: str | None = None
    private: bool = False


class RollIn(Base):
    formula: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=80)
    character_id: str | None = None
    private: bool = False


class FriendRequestIn(Base):
    username: str
