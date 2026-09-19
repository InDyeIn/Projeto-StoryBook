"""Modelos do StoryBook.

Convenções:
  * ids são strings (uuid4 hex curto) — legíveis em URLs e estáveis entre bancos.
  * campos livres usam JSON (funciona em SQLite e Postgres).
  * tudo que pertence a uma sala cai junto com ela (ondelete CASCADE).
"""

from __future__ import annotations

import enum
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return uuid.uuid4().hex[:24]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


class Presence(str, enum.Enum):
    ONLINE = "ONLINE"
    AWAY = "AWAY"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


class FriendshipStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"


class RoomRole(str, enum.Enum):
    GM = "GM"
    CO_GM = "CO_GM"
    PLAYER = "PLAYER"
    SPECTATOR = "SPECTATOR"


class MessageKind(str, enum.Enum):
    TEXT = "TEXT"
    SYSTEM = "SYSTEM"
    ROLL = "ROLL"
    OOC = "OOC"
    ROOM_INVITE = "ROOM_INVITE"


class GridType(str, enum.Enum):
    SQUARE = "SQUARE"
    HEX = "HEX"
    NONE = "NONE"


class BackgroundFit(str, enum.Enum):
    """Como a imagem de fundo ocupa a cena."""

    CONTAIN = "CONTAIN"   # cabe inteira, sem distorcer (padrão)
    COVER = "COVER"       # preenche tudo, sem distorcer, cortando o excesso
    STRETCH = "STRETCH"   # estica até encaixar — distorce
    TILE = "TILE"         # repete lado a lado, no tamanho original
    ACTUAL = "ACTUAL"     # tamanho original, sem repetir


class DistanceMode(str, enum.Enum):
    """Como a régua conta a distância entre duas células."""

    GRID = "GRID"            # diagonal custa igual a reta (estilo 5e)
    EUCLIDEAN = "EUCLIDEAN"  # linha reta de verdade
    MANHATTAN = "MANHATTAN"  # só em cruz, sem diagonal


class TokenLayer(str, enum.Enum):
    BACKGROUND = "BACKGROUND"
    TOKENS = "TOKENS"
    GM_ONLY = "GM_ONLY"


class CharacterVisibility(str, enum.Enum):
    PRIVATE = "PRIVATE"   # só o dono e o mestre
    PARTY = "PARTY"       # todos na mesa
    PUBLIC = "PUBLIC"     # aparece no perfil público


# ===========================================================================
#  CONTAS E PERFIL
# ===========================================================================


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # --- Perfil customizável (inspiração Steam) ---
    display_name: Mapped[str] = mapped_column(String(64))
    tagline: Mapped[str | None] = mapped_column(String(140), default=None)
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)
    banner_url: Mapped[str | None] = mapped_column(String(512), default=None)
    accent_color: Mapped[str] = mapped_column(String(9), default="#7c5cff")
    pronouns: Mapped[str | None] = mapped_column(String(32), default=None)
    location: Mapped[str | None] = mapped_column(String(64), default=None)
    #: Blocos livres da vitrine do perfil — ver app/profile.py
    showcase: Mapped[list] = mapped_column(JSON, default=list)

    presence: Mapped[Presence] = mapped_column(Enum(Presence), default=Presence.OFFLINE)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["RoomMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    owned_rooms: Mapped[list["Room"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", foreign_keys="Room.owner_id"
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )

    @property
    def initials(self) -> str:
        parts = [p for p in self.display_name.split() if p][:2]
        return "".join(p[0].upper() for p in parts) or self.username[:2].upper()


class Session(Base):
    """Sessão de login. O cookie carrega o token; aqui guardamos só o hash."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="sessions")

    @property
    def is_expired(self) -> bool:
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires < utcnow()

    @staticmethod
    def default_expiry(days: int) -> datetime:
        return utcnow() + timedelta(days=days)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(128))
    mime_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))  # avatar | banner | token | scene
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ===========================================================================
#  SOCIAL — AMIZADES E MENSAGENS DIRETAS
# ===========================================================================


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    addressee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus), default=FriendshipStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    addressee: Mapped[User] = relationship(foreign_keys=[addressee_id])

    def other_side(self, user_id: str) -> User:
        return self.addressee if self.requester_id == user_id else self.requester


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    is_group: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[list["DirectMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conv_member"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[MessageKind] = mapped_column(Enum(MessageKind), default=MessageKind.TEXT)
    body: Mapped[str] = mapped_column(Text)
    #: Para ROOM_INVITE: {"room_id", "room_name", "slug", "invite_code"}
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    author: Mapped[User] = relationship()


# ===========================================================================
#  SALAS (MESAS)
# ===========================================================================


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    banner_url: Mapped[str | None] = mapped_column(String(512), default=None)
    #: id do sistema de RPG — ver app/systems/
    system_id: Mapped[str] = mapped_column(String(48), default="triangle-agency")
    #: opções que o mestre escolheu ao criar a sala
    system_config: Mapped[dict] = mapped_column(JSON, default=dict)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invite_code: Mapped[str] = mapped_column(String(12), unique=True, index=True, default=invite_code)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    max_players: Mapped[int] = mapped_column(Integer, default=6)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="owned_rooms", foreign_keys=[owner_id])
    members: Mapped[list["RoomMember"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="room", cascade="all, delete-orphan", order_by="Scene.order"
    )
    characters: Mapped[list["Character"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )
    messages: Mapped[list["RoomMessage"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )

    def member_for(self, user_id: str) -> "RoomMember | None":
        return next((m for m in self.members if m.user_id == user_id), None)

    @property
    def active_scene(self) -> "Scene | None":
        return next((s for s in self.scenes if s.is_active), None)


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_member"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[RoomRole] = mapped_column(Enum(RoomRole), default=RoomRole.PLAYER)
    #: Ajustes finos por jogador: {"token.move.any": true, "scene.edit": false}
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    color: Mapped[str] = mapped_column(String(9), default="#7c5cff")
    nickname: Mapped[str | None] = mapped_column(String(48), default=None)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    room: Mapped[Room] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


# ===========================================================================
#  TABLETOP — CENAS E TOKENS
# ===========================================================================


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    background_url: Mapped[str | None] = mapped_column(String(512), default=None)
    background_color: Mapped[str] = mapped_column(String(9), default="#0a0d1a")
    #: Enquadramento da imagem de fundo — evita o mapa esticado.
    background_fit: Mapped[BackgroundFit] = mapped_column(
        Enum(BackgroundFit), default=BackgroundFit.CONTAIN
    )
    grid_type: Mapped[GridType] = mapped_column(Enum(GridType), default=GridType.SQUARE)
    grid_size: Mapped[int] = mapped_column(Integer, default=64)   # px por célula
    grid_color: Mapped[str] = mapped_column(String(9), default="#2a3354")
    grid_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    snap_to_grid: Mapped[bool] = mapped_column(Boolean, default=True)
    width: Mapped[int] = mapped_column(Integer, default=40)       # em células
    height: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # --- Régua ---
    #: Quanto vale uma célula no mundo do jogo (1,5 m é o padrão de mesa).
    units_per_cell: Mapped[float] = mapped_column(Float, default=1.5)
    unit_name: Mapped[str] = mapped_column(String(12), default="m")
    distance_mode: Mapped[DistanceMode] = mapped_column(
        Enum(DistanceMode), default=DistanceMode.GRID
    )

    room: Mapped[Room] = relationship(back_populates="scenes")
    tokens: Mapped[list["Token"]] = relationship(
        back_populates="scene", cascade="all, delete-orphan", order_by="Token.order"
    )


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"), index=True)
    #: Vinculado a uma ficha: nome e barras acompanham a ficha automaticamente
    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), default=None, index=True
    )
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    name: Mapped[str] = mapped_column(String(64))
    image_url: Mapped[str | None] = mapped_column(String(512), default=None)
    color: Mapped[str] = mapped_column(String(9), default="#7c5cff")
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[float] = mapped_column(Float, default=64.0)
    height: Mapped[float] = mapped_column(Float, default=64.0)
    rotation: Mapped[float] = mapped_column(Float, default=0.0)
    layer: Mapped[TokenLayer] = mapped_column(Enum(TokenLayer), default=TokenLayer.TOKENS)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    #: marcadores de estado livres: ["atordoado", "anomalia"]
    statuses: Mapped[list] = mapped_column(JSON, default=list)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    scene: Mapped[Scene] = relationship(back_populates="tokens")
    character: Mapped["Character | None"] = relationship(back_populates="tokens")


# ===========================================================================
#  FICHAS
# ===========================================================================


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    room_id: Mapped[str | None] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), default=None, index=True
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    system_id: Mapped[str] = mapped_column(String(48), default="triangle-agency")
    name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(String(512), default=None)
    is_npc: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[CharacterVisibility] = mapped_column(
        Enum(CharacterVisibility), default=CharacterVisibility.PARTY
    )
    #: Valores da ficha; as chaves vêm da definição do sistema.
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    room: Mapped[Room | None] = relationship(back_populates="characters")
    owner: Mapped[User] = relationship(back_populates="characters")
    tokens: Mapped[list[Token]] = relationship(back_populates="character")


# ===========================================================================
#  CHAT DA MESA
# ===========================================================================


class RoomMessage(Base):
    __tablename__ = "room_messages"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    kind: Mapped[MessageKind] = mapped_column(Enum(MessageKind), default=MessageKind.TEXT)
    body: Mapped[str] = mapped_column(Text)
    #: Para ROLL: {"formula", "terms", "total", "successes", "label"}
    payload: Mapped[dict | None] = mapped_column(JSON, default=None)
    #: Sussurro destinado a um único jogador
    whisper_to: Mapped[str | None] = mapped_column(String(24), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    room: Mapped[Room] = relationship(back_populates="messages")
    author: Mapped[User | None] = relationship()
