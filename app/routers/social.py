"""Amizades e mensagens diretas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select

from app.deps import CurrentUser, DbDep, verify_csrf
from app.models import (
    Conversation,
    ConversationMember,
    DirectMessage,
    Friendship,
    FriendshipStatus,
    MessageKind,
    Room,
    RoomMember,
    User,
    utcnow,
)
from app.realtime import manager
from app.schemas import DirectMessageIn, FriendRequestIn
from app.services import (
    get_or_create_conversation,
    list_conversations,
    load_friendships,
    public_user,
    search_users,
    serialize_direct_message,
)

router = APIRouter(prefix="/api", tags=["social"])


# ---------------------------------------------------------------------------
#  Busca de pessoas
# ---------------------------------------------------------------------------


@router.get("/usuarios/busca")
async def find_users(user: CurrentUser, db: DbDep, q: str = ""):
    return {"users": search_users(db, q, exclude_id=user.id)}


# ---------------------------------------------------------------------------
#  Amizades
# ---------------------------------------------------------------------------


@router.get("/amigos")
async def my_friends(user: CurrentUser, db: DbDep):
    return load_friendships(db, user.id)


@router.post("/amigos", dependencies=[Depends(verify_csrf)])
async def request_friend(payload: FriendRequestIn, user: CurrentUser, db: DbDep):
    target = db.scalar(select(User).where(User.username == payload.username.lower()))
    if target is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if target.id == user.id:
        raise HTTPException(400, "Você já é seu próprio amigo.")

    existing = db.scalar(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == user.id) & (Friendship.addressee_id == target.id),
                (Friendship.requester_id == target.id) & (Friendship.addressee_id == user.id),
            )
        )
    )

    if existing:
        if existing.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(409, "Vocês já são amigos.")
        if existing.status == FriendshipStatus.BLOCKED:
            raise HTTPException(403, "Não foi possível enviar o pedido.")
        # A outra pessoa já tinha pedido: aceita na hora.
        if existing.addressee_id == user.id:
            existing.status = FriendshipStatus.ACCEPTED
            db.commit()
            await manager.to_user(
                target.id, "friend:accepted", {"id": existing.id, "user": public_user(user)}
            )
            return {"status": "ACCEPTED", "auto_accepted": True}
        raise HTTPException(409, "Pedido já enviado.")

    friendship = Friendship(requester_id=user.id, addressee_id=target.id)
    db.add(friendship)
    db.commit()

    await manager.to_user(
        target.id, "friend:request", {"id": friendship.id, "user": public_user(user)}
    )
    return {"status": "PENDING", "id": friendship.id}


@router.post("/amigos/{friendship_id}/aceitar", dependencies=[Depends(verify_csrf)])
async def accept_friend(friendship_id: str, user: CurrentUser, db: DbDep):
    friendship = db.get(Friendship, friendship_id)
    if friendship is None:
        raise HTTPException(404, "Pedido não encontrado.")
    if friendship.addressee_id != user.id:
        raise HTTPException(403, "Só quem recebeu o pedido pode aceitá-lo.")

    friendship.status = FriendshipStatus.ACCEPTED
    db.commit()

    await manager.to_user(
        friendship.requester_id,
        "friend:accepted",
        {"id": friendship.id, "user": public_user(user)},
    )
    return {"status": "ACCEPTED"}


@router.delete("/amigos/{friendship_id}", dependencies=[Depends(verify_csrf)])
async def remove_friend(friendship_id: str, user: CurrentUser, db: DbDep):
    friendship = db.get(Friendship, friendship_id)
    if friendship is None:
        raise HTTPException(404, "Pedido não encontrado.")
    if user.id not in (friendship.requester_id, friendship.addressee_id):
        raise HTTPException(403, "Este pedido não é seu.")

    other = (
        friendship.addressee_id if friendship.requester_id == user.id else friendship.requester_id
    )
    db.delete(friendship)
    db.commit()

    await manager.to_user(other, "friend:removed", {"id": friendship_id})
    return {"ok": True}


@router.post("/amigos/{friendship_id}/bloquear", dependencies=[Depends(verify_csrf)])
async def block_friend(friendship_id: str, user: CurrentUser, db: DbDep):
    friendship = db.get(Friendship, friendship_id)
    if friendship is None:
        raise HTTPException(404, "Pedido não encontrado.")
    if user.id not in (friendship.requester_id, friendship.addressee_id):
        raise HTTPException(403, "Este pedido não é seu.")

    friendship.status = FriendshipStatus.BLOCKED
    db.commit()
    return {"status": "BLOCKED"}


# ---------------------------------------------------------------------------
#  Conversas
# ---------------------------------------------------------------------------


@router.get("/conversas")
async def my_conversations(user: CurrentUser, db: DbDep):
    return {"conversations": list_conversations(db, user.id)}


@router.post("/conversas", dependencies=[Depends(verify_csrf)])
async def open_conversation(user: CurrentUser, db: DbDep, username: str = "", user_id: str = ""):
    if user_id:
        target = db.get(User, user_id)
    else:
        target = db.scalar(select(User).where(User.username == username.lower()))

    if target is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if target.id == user.id:
        raise HTTPException(400, "Não dá para conversar consigo mesmo.")

    conversation = get_or_create_conversation(db, user.id, target.id)
    return {"id": conversation.id, "redirect": f"/mensagens?c={conversation.id}"}


def _membership(db, conversation_id: str, user_id: str) -> ConversationMember:
    member = db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(403, "Você não participa desta conversa.")
    return member


@router.get("/conversas/{conversation_id}/mensagens")
async def conversation_messages(conversation_id: str, user: CurrentUser, db: DbDep):
    member = _membership(db, conversation_id, user.id)
    conversation = db.get(Conversation, conversation_id)

    messages = db.scalars(
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conversation_id)
        .order_by(DirectMessage.created_at.desc())
        .limit(80)
    ).all()[::-1]

    member.last_read_at = utcnow()
    db.commit()

    return {
        "messages": [serialize_direct_message(m) for m in messages],
        "participants": [
            public_user(m.user) for m in conversation.members if m.user_id != user.id
        ],
    }


@router.post("/conversas/{conversation_id}/mensagens", dependencies=[Depends(verify_csrf)])
async def send_direct_message(
    conversation_id: str, payload: DirectMessageIn, user: CurrentUser, db: DbDep
):
    _membership(db, conversation_id, user.id)
    conversation = db.get(Conversation, conversation_id)

    extra = None
    kind = MessageKind.TEXT

    if payload.kind == "ROOM_INVITE":
        # Só convida para uma mesa da qual você realmente participa.
        room = db.scalar(
            select(Room)
            .join(RoomMember)
            .where(Room.id == payload.room_id, RoomMember.user_id == user.id)
        )
        if room is None:
            raise HTTPException(403, "Você não participa dessa mesa.")
        kind = MessageKind.ROOM_INVITE
        extra = {
            "room_id": room.id,
            "room_name": room.name,
            "slug": room.slug,
            "invite_code": room.invite_code,
        }

    message = DirectMessage(
        conversation_id=conversation_id,
        author_id=user.id,
        kind=kind,
        body=payload.body,
        payload=extra,
    )
    db.add(message)
    conversation.updated_at = utcnow()
    db.commit()
    db.refresh(message)

    data = serialize_direct_message(message)
    for member in conversation.members:
        await manager.to_user(
            member.user_id,
            "dm:message",
            {"conversation_id": conversation_id, "message": data},
        )

    return {"message": data}
