"""Catálogo de sistemas de RPG."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import CurrentUser
from app.systems import get_system, list_systems

router = APIRouter(prefix="/api/sistemas", tags=["sistemas"])


@router.get("")
async def catalog():
    return {"systems": list_systems()}


@router.get("/{system_id}")
async def definition(system_id: str, user: CurrentUser):
    """Definição completa (seções, campos, rolagens) para montar a ficha."""
    return {"system": get_system(system_id).full()}
