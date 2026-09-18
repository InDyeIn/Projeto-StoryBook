"""Listagens do próprio usuário usadas por telas fora do painel."""

from __future__ import annotations

from sqlalchemy import select

from fastapi import APIRouter

from app.deps import CurrentUser, DbDep
from app.models import RoomMember
from app.permissions import ROLE_LABELS
from app.systems import get_system

router = APIRouter(prefix="/api", tags=["conta"])


@router.get("/minhas-salas")
async def my_rooms(user: CurrentUser, db: DbDep):
    """Mesas das quais o usuário participa — alimenta o convite pelo chat."""
    memberships = db.scalars(
        select(RoomMember).where(RoomMember.user_id == user.id)
    ).all()

    return {
        "rooms": [
            {
                "id": m.room.id,
                "slug": m.room.slug,
                "name": m.room.name,
                "system_name": get_system(m.room.system_id).name,
                "role": m.role.value,
                "role_label": ROLE_LABELS.get(m.role, m.role.value),
                "members": len(m.room.members),
            }
            for m in memberships
        ]
    }
