"""Fichas de personagem.

A ficha guarda os valores num JSON cujas chaves vêm da definição do sistema
(``app/systems``). A edição é feita por *patch* de caminho — o cliente manda
``{"competencias.burocracia": 4}`` e só esse campo muda, o que evita que duas
pessoas editando a mesma ficha sobrescrevam o trabalho uma da outra.
"""

from __future__ import annotations

import copy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.deps import CurrentUser, DbDep, load_room, verify_csrf
from app.models import Character, CharacterVisibility, Room, Scene, Token, utcnow
from app.permissions import can
from app.realtime import manager
from app.schemas import CharacterCreateIn, CharacterUpdateIn
from app.services import (
    can_edit_character,
    ensure_active_scene,
    can_view_character,
    serialize_character,
    serialize_token,
)
from app.systems import get_system, initial_sheet_data, set_path

router = APIRouter(prefix="/api/fichas", tags=["fichas"])


def _load(db, character_id: str) -> Character:
    character = db.get(Character, character_id)
    if character is None:
        raise HTTPException(404, "Ficha não encontrada.")
    return character


def _member_for(db, character: Character, user):
    """Vínculo do usuário com a mesa da ficha (None para fichas soltas)."""
    if character.room_id is None:
        return None
    room = db.get(Room, character.room_id)
    return room.member_for(user.id) if room else None


@router.post("", dependencies=[Depends(verify_csrf)])
async def create_character(payload: CharacterCreateIn, user: CurrentUser, db: DbDep):
    room = None
    member = None
    system_id = payload.system_id
    config: dict = {}

    if payload.room_id:
        room = load_room(db, payload.room_id)
        member = room.member_for(user.id)
        if member is None:
            raise HTTPException(403, "Você não participa desta mesa.")
        if not can(member, "sheet.create"):
            raise HTTPException(403, "Você não pode criar fichas nesta mesa.")
        # A mesa manda no sistema: não adianta trazer ficha de outro jogo.
        system_id = room.system_id
        config = room.system_config or {}

    if payload.is_npc and member is not None and not can(member, "sheet.edit.any"):
        raise HTTPException(403, "Só o mestre cria NPCs.")

    system = get_system(system_id)
    character = Character(
        room_id=room.id if room else None,
        owner_id=user.id,
        system_id=system.id,
        name=payload.name,
        avatar_url=payload.avatar_url,
        is_npc=payload.is_npc,
        visibility=CharacterVisibility.PRIVATE if payload.is_npc else CharacterVisibility.PARTY,
        data=initial_sheet_data(system.id, config),
    )
    db.add(character)
    db.commit()
    db.refresh(character)

    data = serialize_character(character)
    if room:
        await manager.to_room(room.id, "character:created", data)
    return {"character": data}


@router.get("/{character_id}")
async def read_character(character_id: str, user: CurrentUser, db: DbDep):
    character = _load(db, character_id)
    member = _member_for(db, character, user)

    if not can_view_character(character, user.id, member):
        raise HTTPException(403, "Você não pode ver esta ficha.")

    system = get_system(character.system_id)
    room = db.get(Room, character.room_id) if character.room_id else None

    return {
        "character": serialize_character(character),
        "can_edit": can_edit_character(character, user.id, member),
        "is_gm": bool(member and can(member, "sheet.edit.any")),
        "system": system.full(),
        "room_config": (room.system_config if room else {}) or {},
    }


@router.patch("/{character_id}", dependencies=[Depends(verify_csrf)])
async def update_character(
    character_id: str, payload: CharacterUpdateIn, user: CurrentUser, db: DbDep
):
    character = _load(db, character_id)
    member = _member_for(db, character, user)

    if not can_edit_character(character, user.id, member):
        raise HTTPException(403, "Você não pode editar esta ficha.")

    data = payload.model_dump(exclude_unset=True)
    patch = data.pop("patch", None)

    if patch:
        system = get_system(character.system_id)
        e_mestre = bool(member and can(member, "sheet.edit.any"))
        # Cópia profunda: `set_path` altera dicionários aninhados, e mexer no
        # objeto que o SQLAlchemy carregou faria a mudança passar despercebida.
        valores = copy.deepcopy(character.data or {})

        for caminho, valor in patch.items():
            campo = system.field_by_key(caminho)
            # Campos do mestre não podem ser mexidos por quem não é mestre,
            # nem que o cliente mande o caminho na mão.
            if campo is not None and campo.gm_only and not e_mestre:
                raise HTTPException(403, f'O campo "{campo.label}" é só do mestre.')
            if campo is None and not _is_resource_path(system, caminho):
                raise HTTPException(400, f'Campo desconhecido: "{caminho}".')
            set_path(valores, caminho, valor)

        character.data = valores
        flag_modified(character, "data")

    if "visibility" in data and data["visibility"]:
        character.visibility = CharacterVisibility(data.pop("visibility"))

    for key, value in data.items():
        setattr(character, key, value)

    character.updated_at = utcnow()
    db.commit()
    db.refresh(character)

    payload_out = serialize_character(character)
    if character.room_id:
        await manager.to_room(
            character.room_id, "character:updated", payload_out, exclude_user=user.id
        )
        # As barras do token vêm da ficha: avisa quem estiver com o mapa aberto.
        for token in character.tokens:
            await manager.to_room(character.room_id, "token:updated", serialize_token(token))

    return {"character": payload_out}


def _is_resource_path(system, path: str) -> bool:
    """Aceita ``vida.atual`` / ``vida.max`` quando ``vida`` é um recurso."""
    if "." not in path:
        return False
    base, leaf = path.rsplit(".", 1)
    if leaf not in ("atual", "max"):
        return False
    campo = system.field_by_key(base)
    return campo is not None and campo.type == "resource"


@router.delete("/{character_id}", dependencies=[Depends(verify_csrf)])
async def delete_character(character_id: str, user: CurrentUser, db: DbDep):
    character = _load(db, character_id)
    member = _member_for(db, character, user)

    dono = character.owner_id == user.id
    if not (dono or (member and can(member, "sheet.edit.any"))):
        raise HTTPException(403, "Você não pode apagar esta ficha.")

    room_id = character.room_id
    db.delete(character)
    db.commit()

    if room_id:
        await manager.to_room(room_id, "character:deleted", {"character_id": character_id})
    return {"ok": True}


@router.post("/{character_id}/token", dependencies=[Depends(verify_csrf)])
async def spawn_token(character_id: str, user: CurrentUser, db: DbDep, scene_id: str = ""):
    """Coloca no mapa um token já vinculado a esta ficha."""
    character = _load(db, character_id)
    if character.room_id is None:
        raise HTTPException(400, "Esta ficha não pertence a nenhuma mesa.")

    room = db.get(Room, character.room_id)
    member = room.member_for(user.id)
    if member is None or not can(member, "token.create"):
        raise HTTPException(403, "Você não pode criar tokens nesta mesa.")

    scene = db.get(Scene, scene_id) if scene_id else None
    if scene is None or scene.room_id != room.id:
        scene = ensure_active_scene(db, room)

    token = Token(
        scene_id=scene.id,
        character_id=character.id,
        owner_id=character.owner_id,
        name=character.name,
        image_url=character.avatar_url,
        color=member.color,
        x=scene.grid_size * 2,
        y=scene.grid_size * 2,
        width=float(scene.grid_size),
        height=float(scene.grid_size),
        order=len(scene.tokens),
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    await manager.to_room(room.id, "token:created", serialize_token(token))
    return {"token": serialize_token(token)}


@router.get("")
async def my_characters(user: CurrentUser, db: DbDep):
    fichas = db.scalars(
        select(Character)
        .where(Character.owner_id == user.id)
        .order_by(Character.updated_at.desc())
    ).all()
    return {"characters": [serialize_character(f, include_data=False) for f in fichas]}
