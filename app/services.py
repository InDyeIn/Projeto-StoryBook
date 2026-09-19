"""Serialização e consultas compartilhadas entre as rotas HTTP e o WebSocket."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.models import (
    Character,
    CharacterVisibility,
    Conversation,
    ConversationMember,
    Friendship,
    FriendshipStatus,
    Room,
    RoomMember,
    RoomMessage,
    Scene,
    Token,
    TokenLayer,
    User,
)
from app.permissions import ROLE_LABELS, can, effective_permissions
from app.systems import get_path, get_system


# ---------------------------------------------------------------------------
#  Texto
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug[:48] or "mesa"


def unique_slug(db: DbSession, name: str) -> str:
    base = slugify(name)
    slug, attempt = base, 2
    while db.scalar(select(Room.id).where(Room.slug == slug)):
        slug = f"{base}-{attempt}"
        attempt += 1
    return slug


def time_ago(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    seconds = int((datetime.now(timezone.utc) - value).total_seconds())
    if seconds < 60:
        return "agora"
    if seconds < 3600:
        return f"{seconds // 60} min"
    if seconds < 86400:
        return f"{seconds // 3600} h"
    if seconds < 2592000:
        return f"{seconds // 86400} d"
    return value.strftime("%d/%m/%Y")


# ---------------------------------------------------------------------------
#  Serializadores
# ---------------------------------------------------------------------------


def public_user(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "accent_color": user.accent_color,
        "tagline": user.tagline,
        "presence": user.presence.value,
        "initials": user.initials,
    }


def serialize_member(member: RoomMember) -> dict:
    return {
        "id": member.id,
        "user_id": member.user_id,
        "role": member.role.value,
        "role_label": ROLE_LABELS.get(member.role, member.role.value),
        "color": member.color,
        "nickname": member.nickname,
        "overrides": member.permissions or {},
        "permissions": sorted(effective_permissions(member)),
        "joined_at": member.joined_at,
        "user": public_user(member.user),
    }


def serialize_scene(scene: Scene) -> dict:
    return {
        "id": scene.id,
        "name": scene.name,
        "background_url": scene.background_url,
        "background_color": scene.background_color,
        "background_fit": scene.background_fit.value,
        "units_per_cell": scene.units_per_cell,
        "unit_name": scene.unit_name,
        "distance_mode": scene.distance_mode.value,
        "grid_type": scene.grid_type.value,
        "grid_size": scene.grid_size,
        "grid_color": scene.grid_color,
        "grid_visible": scene.grid_visible,
        "snap_to_grid": scene.snap_to_grid,
        "width": scene.width,
        "height": scene.height,
        "is_active": scene.is_active,
        "order": scene.order,
    }


def token_bars(token: Token) -> list[dict]:
    """Barras exibidas sob o token, lidas da ficha vinculada."""
    if token.character is None:
        return []
    system = get_system(token.character.system_id)
    bars = []
    for bar in system.token_bars:
        value = get_path(token.character.data or {}, bar.path)
        if not isinstance(value, dict):
            continue
        try:
            current = float(value.get("atual", 0))
            maximum = float(value.get("max", 0))
        except (TypeError, ValueError):
            continue
        if maximum <= 0:
            continue
        bars.append(
            {
                "label": bar.label,
                "color": bar.color,
                "current": current,
                "max": maximum,
                "ratio": max(0.0, min(1.0, current / maximum)),
            }
        )
    return bars


def serialize_token(token: Token) -> dict:
    return {
        "id": token.id,
        "scene_id": token.scene_id,
        "character_id": token.character_id,
        "owner_id": token.owner_id,
        "name": token.name,
        "image_url": token.image_url,
        "color": token.color,
        "x": token.x,
        "y": token.y,
        "width": token.width,
        "height": token.height,
        "rotation": token.rotation,
        "layer": token.layer.value,
        "is_visible": token.is_visible,
        "is_locked": token.is_locked,
        "statuses": token.statuses or [],
        "order": token.order,
        "bars": token_bars(token),
    }


def serialize_character(character: Character, *, include_data: bool = True) -> dict:
    payload = {
        "id": character.id,
        "room_id": character.room_id,
        "owner_id": character.owner_id,
        "system_id": character.system_id,
        "name": character.name,
        "avatar_url": character.avatar_url,
        "is_npc": character.is_npc,
        "visibility": character.visibility.value,
        "owner": public_user(character.owner),
        "updated_at": character.updated_at,
    }
    if include_data:
        payload["data"] = character.data or {}
    return payload


def serialize_room_message(message: RoomMessage) -> dict:
    return {
        "id": message.id,
        "room_id": message.room_id,
        "kind": message.kind.value,
        "body": message.body,
        "payload": message.payload,
        "whisper_to": message.whisper_to,
        "created_at": message.created_at,
        "author": public_user(message.author),
    }


def serialize_direct_message(message) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "kind": message.kind.value,
        "body": message.body,
        "payload": message.payload,
        "created_at": message.created_at,
        "author": public_user(message.author),
    }


# ---------------------------------------------------------------------------
#  Visibilidade de ficha
# ---------------------------------------------------------------------------


def can_view_character(character: Character, viewer_id: str, member: RoomMember | None) -> bool:
    if character.owner_id == viewer_id:
        return True
    if can(member, "sheet.view.any"):
        return True
    return character.visibility in (CharacterVisibility.PARTY, CharacterVisibility.PUBLIC)


def can_edit_character(character: Character, viewer_id: str, member: RoomMember | None) -> bool:
    if character.owner_id == viewer_id:
        return member is None or can(member, "sheet.edit.own")
    return can(member, "sheet.edit.any")


# ---------------------------------------------------------------------------
#  Cenas
# ---------------------------------------------------------------------------


def ensure_active_scene(db: DbSession, room: Room) -> Scene:
    """Garante que a mesa sempre tenha uma cena ativa."""
    active = room.active_scene
    if active is not None:
        return active

    first = db.scalar(select(Scene).where(Scene.room_id == room.id).order_by(Scene.order))
    if first is not None:
        first.is_active = True
        db.commit()
        return first

    scene = Scene(room_id=room.id, name="Cena inicial", is_active=True, order=0)
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


# ---------------------------------------------------------------------------
#  Estado completo da mesa
# ---------------------------------------------------------------------------


def build_room_state(db: DbSession, room: Room, user: User) -> dict:
    """Tudo que o tabletop precisa, já filtrado pelo que este usuário pode ver."""
    member = room.member_for(user.id)
    if member is None:
        raise PermissionError("Você não participa desta mesa.")

    scene = ensure_active_scene(db, room)
    sees_gm_layer = can(member, "token.reveal")

    token_query = select(Token).where(Token.scene_id == scene.id).order_by(Token.order)
    if not sees_gm_layer:
        token_query = token_query.where(
            Token.layer != TokenLayer.GM_ONLY, Token.is_visible.is_(True)
        )
    tokens = list(db.scalars(token_query))

    characters = [
        character
        for character in db.scalars(
            select(Character).where(Character.room_id == room.id).order_by(Character.created_at)
        )
        if can_view_character(character, user.id, member)
    ]

    messages = list(
        db.scalars(
            select(RoomMessage)
            .where(
                RoomMessage.room_id == room.id,
                or_(
                    RoomMessage.whisper_to.is_(None),
                    RoomMessage.whisper_to == user.id,
                    RoomMessage.author_id == user.id,
                ),
            )
            .order_by(RoomMessage.created_at.desc())
            .limit(80)
        )
    )[::-1]

    system = get_system(room.system_id)

    return {
        "room": {
            "id": room.id,
            "slug": room.slug,
            "name": room.name,
            "description": room.description,
            "banner_url": room.banner_url,
            "system_id": room.system_id,
            "system_name": system.name,
            "system_config": room.system_config or {},
            "invite_code": room.invite_code if can(member, "room.invite") else None,
            "is_public": room.is_public,
            "max_players": room.max_players,
            "owner_id": room.owner_id,
        },
        "me": {
            "user_id": user.id,
            "member_id": member.id,
            "role": member.role.value,
            "color": member.color,
            "permissions": sorted(effective_permissions(member)),
        },
        "members": [serialize_member(m) for m in room.members],
        "scenes": [serialize_scene(s) for s in room.scenes],
        "scene": serialize_scene(scene),
        "tokens": [serialize_token(t) for t in tokens],
        "characters": [serialize_character(c) for c in characters],
        "messages": [serialize_room_message(m) for m in messages],
    }


# ---------------------------------------------------------------------------
#  Social
# ---------------------------------------------------------------------------


def load_friendships(db: DbSession, user_id: str) -> dict[str, list[dict]]:
    rows = list(
        db.scalars(
            select(Friendship)
            .where(or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id))
            .order_by(Friendship.updated_at.desc())
        )
    )

    buckets: dict[str, list[dict]] = {"friends": [], "incoming": [], "outgoing": [], "blocked": []}
    for row in rows:
        entry = {
            "id": row.id,
            "status": row.status.value,
            "user": public_user(row.other_side(user_id)),
            "created_at": row.created_at,
        }
        if row.status == FriendshipStatus.ACCEPTED:
            buckets["friends"].append(entry)
        elif row.status == FriendshipStatus.BLOCKED:
            buckets["blocked"].append(entry)
        elif row.addressee_id == user_id:
            buckets["incoming"].append(entry)
        else:
            buckets["outgoing"].append(entry)
    return buckets


def get_or_create_conversation(db: DbSession, user_a: str, user_b: str) -> Conversation:
    """Abre (ou reaproveita) a conversa direta entre duas pessoas."""
    existing = db.scalars(
        select(Conversation)
        .join(ConversationMember)
        .where(Conversation.is_group.is_(False), ConversationMember.user_id == user_a)
    ).all()

    for conversation in existing:
        member_ids = {m.user_id for m in conversation.members}
        if member_ids == {user_a, user_b}:
            return conversation

    conversation = Conversation(is_group=False)
    conversation.members = [
        ConversationMember(user_id=user_a),
        ConversationMember(user_id=user_b),
    ]
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: DbSession, user_id: str) -> list[dict]:
    conversations = db.scalars(
        select(Conversation)
        .join(ConversationMember)
        .where(ConversationMember.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    ).all()

    result = []
    for conversation in conversations:
        me = next((m for m in conversation.members if m.user_id == user_id), None)
        others = [m for m in conversation.members if m.user_id != user_id]
        last = max(conversation.messages, key=lambda m: m.created_at, default=None)
        result.append(
            {
                "id": conversation.id,
                "title": conversation.title
                or ", ".join(m.user.display_name for m in others)
                or "Conversa",
                "participants": [public_user(m.user) for m in others],
                "last_message": serialize_direct_message(last) if last else None,
                "unread": bool(
                    last
                    and me
                    and last.author_id != user_id
                    and last.created_at > me.last_read_at
                ),
                "updated_at": conversation.updated_at,
                "time_ago": time_ago(last.created_at if last else conversation.updated_at),
            }
        )
    return result


def search_users(db: DbSession, query: str, exclude_id: str, limit: int = 12) -> list[dict]:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    pattern = f"%{query.lower()}%"
    rows = db.scalars(
        select(User)
        .where(
            User.id != exclude_id,
            or_(
                User.username.ilike(pattern),
                User.display_name.ilike(pattern),
            ),
        )
        .limit(limit)
    ).all()
    return [public_user(user) for user in rows]
