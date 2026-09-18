"""Rotas que devolvem páginas HTML.

Todo dado pesado (tokens, mensagens, fichas) é carregado pela API ou pelo
WebSocket — aqui só montamos o esqueleto da página.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.deps import CurrentUser, DbDep, OptionalUser, load_room
from app.models import Character, CharacterVisibility, Room, RoomMember, User
from app.permissions import can, effective_permissions
from app.services import (
    build_room_state,
    list_conversations,
    load_friendships,
    public_user,
    serialize_character,
)
from app.systems import get_system, list_systems
from app.templating import render

router = APIRouter(include_in_schema=False)


@router.get("/")
async def landing(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/painel", status_code=303)
    return render(request, "index.html")


# ---------------------------------------------------------------------------
#  Entrar / cadastrar
# ---------------------------------------------------------------------------


@router.get("/entrar")
async def login_page(request: Request, user: OptionalUser, proximo: str = "/painel"):
    if user:
        return RedirectResponse(proximo, status_code=303)
    return render(request, "auth/entrar.html", {"proximo": proximo})


@router.get("/cadastro")
async def register_page(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/painel", status_code=303)
    return render(request, "auth/cadastro.html")


# ---------------------------------------------------------------------------
#  Painel
# ---------------------------------------------------------------------------


@router.get("/painel")
async def dashboard(request: Request, user: CurrentUser, db: DbDep):
    memberships = db.scalars(
        select(RoomMember)
        .where(RoomMember.user_id == user.id)
        .order_by(RoomMember.joined_at.desc())
    ).all()

    salas = []
    for membership in memberships:
        room = membership.room
        system = get_system(room.system_id)
        salas.append(
            {
                "id": room.id,
                "slug": room.slug,
                "name": room.name,
                "description": room.description,
                "banner_url": room.banner_url,
                "system_name": system.name,
                "system_color": system.color,
                "system_status": system.status,
                "role": membership.role.value,
                "members": len(room.members),
                "max_players": room.max_players,
                "owner": public_user(room.owner),
                "updated_at": room.updated_at,
            }
        )

    fichas = db.scalars(
        select(Character)
        .where(Character.owner_id == user.id)
        .order_by(Character.updated_at.desc())
        .limit(8)
    ).all()

    amizades = load_friendships(db, user.id)

    return render(
        request,
        "painel.html",
        {
            "active": "painel",
            "salas": salas,
            "fichas": [serialize_character(f, include_data=False) for f in fichas],
            "amizades": amizades,
            "sistemas": list_systems(),
        },
    )


# ---------------------------------------------------------------------------
#  Perfil
# ---------------------------------------------------------------------------


@router.get("/u/{username}")
async def profile_page(request: Request, username: str, user: OptionalUser, db: DbDep):
    perfil = db.scalar(select(User).where(User.username == username.lower()))
    if perfil is None:
        raise HTTPException(404, "Perfil não encontrado.")

    e_meu = bool(user and user.id == perfil.id)

    fichas = db.scalars(
        select(Character)
        .where(
            Character.owner_id == perfil.id,
            Character.visibility == CharacterVisibility.PUBLIC,
        )
        .order_by(Character.updated_at.desc())
        .limit(12)
    ).all()

    mesas = [
        m.room
        for m in perfil.memberships
        if m.room.is_public or e_meu
    ][:6]

    relacao = None
    if user and not e_meu:
        amizades = load_friendships(db, user.id)
        for bucket, rows in amizades.items():
            if any(row["user"]["id"] == perfil.id for row in rows):
                relacao = bucket
                break

    return render(
        request,
        "perfil.html",
        {
            "active": "perfil",
            "perfil": perfil,
            "e_meu": e_meu,
            "fichas": [serialize_character(f, include_data=False) for f in fichas],
            "mesas": mesas,
            "relacao": relacao,
            "showcase": perfil.showcase or [],
        },
    )


@router.get("/configuracoes")
async def settings_page(request: Request, user: CurrentUser):
    return render(request, "configuracoes.html", {"active": "perfil"})


# ---------------------------------------------------------------------------
#  Social
# ---------------------------------------------------------------------------


@router.get("/amigos")
async def friends_page(request: Request, user: CurrentUser, db: DbDep):
    return render(
        request,
        "amigos.html",
        {"active": "amigos", "amizades": load_friendships(db, user.id)},
    )


@router.get("/mensagens")
async def messages_page(request: Request, user: CurrentUser, db: DbDep, c: str | None = None):
    conversas = list_conversations(db, user.id)
    return render(
        request,
        "mensagens.html",
        {"active": "mensagens", "conversas": conversas, "conversa_ativa": c},
    )


# ---------------------------------------------------------------------------
#  Mesa (tabletop)
# ---------------------------------------------------------------------------


@router.get("/mesa/{slug}")
async def room_page(request: Request, slug: str, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = room.member_for(user.id)

    if member is None:
        # Não é membro: oferece entrar se a sala for pública.
        if not room.is_public:
            raise HTTPException(403, "Você não participa desta mesa.")
        return render(
            request,
            "mesa_convite.html",
            {"room": room, "system": get_system(room.system_id)},
        )

    estado = build_room_state(db, room, user)
    system = get_system(room.system_id)

    return render(
        request,
        "mesa.html",
        {
            "body_class": "mesa-page",
            "room": room,
            "system": system,
            "system_def": system.full(),
            "estado": estado,
            "minhas_permissoes": sorted(effective_permissions(member)),
            "sou_mestre": can(member, "scene.edit"),
        },
    )


@router.get("/entrar-na-mesa")
async def join_page(request: Request, user: CurrentUser, codigo: str = ""):
    return render(request, "entrar_mesa.html", {"active": "painel", "codigo": codigo})


@router.get("/ficha/{character_id}")
async def character_page(request: Request, character_id: str, user: CurrentUser, db: DbDep):
    from app.services import can_view_character

    ficha = db.get(Character, character_id)
    if ficha is None:
        raise HTTPException(404, "Ficha não encontrada.")

    sala = db.get(Room, ficha.room_id) if ficha.room_id else None
    membro = sala.member_for(user.id) if sala else None
    if not can_view_character(ficha, user.id, membro):
        raise HTTPException(403, "Você não pode ver esta ficha.")

    return render(request, "ficha.html", {"active": "painel", "ficha": ficha, "sala": sala})
