"""Salas: criação, membros, permissões, cenas, tokens, chat e rolagens."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.deps import (
    CurrentUser,
    DbDep,
    load_room,
    require_membership,
    require_permission,
    verify_csrf,
)
from app.dice import DiceError, describe, parse_roll_command, roll
from app.models import (
    Character,
    GridType,
    MessageKind,
    Room,
    RoomMember,
    RoomMessage,
    RoomRole,
    Scene,
    Token,
    TokenLayer,
    User,
    utcnow,
)
from app.permissions import ALL_PERMISSIONS, can
from app.realtime import manager
from app.schemas import (
    InviteIn,
    JoinIn,
    MemberUpdateIn,
    RoomCreateIn,
    RoomMessageIn,
    RoomUpdateIn,
    RollIn,
    SceneIn,
    SceneUpdateIn,
    TokenCreateIn,
    TokenUpdateIn,
)
from app.services import (
    build_room_state,
    can_view_character,
    ensure_active_scene,
    get_or_create_conversation,
    public_user,
    serialize_member,
    serialize_room_message,
    serialize_scene,
    serialize_token,
    unique_slug,
)
from app.systems import apply_room_difficulty, get_system, resolve_formula

router = APIRouter(prefix="/api/salas", tags=["salas"])


# ===========================================================================
#  Sala
# ===========================================================================


@router.post("", dependencies=[Depends(verify_csrf)])
async def create_room(payload: RoomCreateIn, user: CurrentUser, db: DbDep):
    system = get_system(payload.system_id)

    # Completa as opções do sistema que o mestre não informou.
    config: dict = {}
    for option in system.room_options:
        raw = payload.system_config.get(option.key, option.default)
        if option.type == "boolean":
            config[option.key] = raw in (True, "true", "on", "1", 1)
        elif option.type == "number":
            try:
                config[option.key] = int(raw)
            except (TypeError, ValueError):
                config[option.key] = option.default
        else:
            config[option.key] = str(raw)

    room = Room(
        name=payload.name,
        description=payload.description or None,
        system_id=system.id,
        system_config=config,
        is_public=payload.is_public,
        max_players=payload.max_players,
        owner_id=user.id,
        slug=unique_slug(db, payload.name),
    )
    room.members = [RoomMember(user_id=user.id, role=RoomRole.GM)]
    room.scenes = [Scene(name="Cena inicial", is_active=True, order=0)]
    db.add(room)
    db.commit()
    db.refresh(room)

    db.add(
        RoomMessage(
            room_id=room.id,
            kind=MessageKind.SYSTEM,
            body=f"Mesa aberta com o sistema {system.name}. Boa sessão.",
        )
    )
    db.commit()

    return {"id": room.id, "slug": room.slug, "redirect": f"/mesa/{room.slug}"}


@router.post("/entrar", dependencies=[Depends(verify_csrf)])
async def join_room(payload: JoinIn, user: CurrentUser, db: DbDep):
    code = payload.invite_code.strip().upper()
    room = db.scalar(select(Room).where(Room.invite_code == code))
    if room is None:
        raise HTTPException(404, "Convite inválido ou expirado.")

    if room.member_for(user.id):
        return {"slug": room.slug, "redirect": f"/mesa/{room.slug}", "already": True}

    if len(room.members) >= room.max_players + 1:
        raise HTTPException(409, "Esta mesa já está cheia.")

    member = RoomMember(room_id=room.id, user_id=user.id, role=RoomRole.PLAYER)
    db.add(member)
    message = RoomMessage(
        room_id=room.id,
        kind=MessageKind.SYSTEM,
        body=f"{user.display_name} entrou na mesa.",
    )
    db.add(message)
    db.commit()
    db.refresh(member)
    db.refresh(message)

    await manager.to_room(room.id, "member:joined", serialize_member(member))
    await manager.to_room(room.id, "chat:message", serialize_room_message(message))

    return {"slug": room.slug, "redirect": f"/mesa/{room.slug}"}


@router.get("/{slug}")
async def room_state(slug: str, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    require_membership(db, room, user)
    return build_room_state(db, room, user)


@router.patch("/{slug}", dependencies=[Depends(verify_csrf)])
async def update_room(slug: str, payload: RoomUpdateIn, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "room.edit")

    data = payload.model_dump(exclude_unset=True)
    if "system_config" in data and data["system_config"] is not None:
        # Mescla: o mestre pode mudar uma opção sem reenviar todas.
        merged = dict(room.system_config or {})
        merged.update(data.pop("system_config"))
        room.system_config = merged

    for key, value in data.items():
        setattr(room, key, value)
    room.updated_at = utcnow()
    db.commit()

    await manager.to_room(
        room.id,
        "room:updated",
        {
            "name": room.name,
            "description": room.description,
            "banner_url": room.banner_url,
            "system_config": room.system_config,
            "is_public": room.is_public,
            "max_players": room.max_players,
        },
    )
    return {"ok": True}


@router.delete("/{slug}", dependencies=[Depends(verify_csrf)])
async def delete_room(slug: str, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    if room.owner_id != user.id:
        raise HTTPException(403, "Só o dono pode apagar a mesa.")

    room_id = room.id
    await manager.to_room(room_id, "room:deleted", {"room_id": room_id})
    db.delete(room)
    db.commit()
    return {"ok": True, "redirect": "/painel"}


@router.post("/{slug}/novo-convite", dependencies=[Depends(verify_csrf)])
async def rotate_invite(slug: str, user: CurrentUser, db: DbDep):
    """Gera um código novo — invalida convites antigos que vazaram."""
    from app.models import invite_code as make_code

    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "room.invite")

    room.invite_code = make_code()
    db.commit()
    return {"invite_code": room.invite_code}


# ===========================================================================
#  Membros e permissões
# ===========================================================================


@router.post("/{slug}/convidar", dependencies=[Depends(verify_csrf)])
async def invite_member(slug: str, payload: InviteIn, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "room.invite")

    target = db.scalar(select(User).where(User.username == payload.username.lower()))
    if target is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if room.member_for(target.id):
        raise HTTPException(409, "Esta pessoa já está na mesa.")

    # O convite sempre chega pelo chat — a pessoa acha a mesa sem sair do site.
    from app.models import DirectMessage

    conversation = get_or_create_conversation(db, user.id, target.id)
    invite = DirectMessage(
        conversation_id=conversation.id,
        author_id=user.id,
        kind=MessageKind.ROOM_INVITE,
        body=f'{user.display_name} te convidou para a mesa "{room.name}".',
        payload={
            "room_id": room.id,
            "room_name": room.name,
            "slug": room.slug,
            "invite_code": room.invite_code,
        },
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    from app.services import serialize_direct_message

    await manager.to_user(
        target.id,
        "dm:message",
        {"conversation_id": conversation.id, "message": serialize_direct_message(invite)},
    )

    if not payload.add_directly:
        return {"invited": True, "conversation_id": conversation.id}

    created = RoomMember(room_id=room.id, user_id=target.id, role=RoomRole(payload.role))
    db.add(created)
    db.commit()
    db.refresh(created)

    await manager.to_room(room.id, "member:joined", serialize_member(created))
    return {"invited": True, "added": True, "member": serialize_member(created)}


@router.patch("/{slug}/membros/{member_id}", dependencies=[Depends(verify_csrf)])
async def update_member(
    slug: str, member_id: str, payload: MemberUpdateIn, user: CurrentUser, db: DbDep
):
    room = load_room(db, slug)
    me = require_membership(db, room, user)

    target = next((m for m in room.members if m.id == member_id), None)
    if target is None:
        raise HTTPException(404, "Membro não encontrado.")

    data = payload.model_dump(exclude_unset=True)
    cosmetic_only = not ({"role", "permissions"} & data.keys())

    # Mudar a própria cor ou apelido não exige permissão especial.
    if not (cosmetic_only and target.user_id == user.id):
        require_permission(me, "room.permissions")

    if target.user_id == room.owner_id and data.get("role") not in (None, "GM"):
        raise HTTPException(400, "O dono da mesa não pode deixar de ser mestre.")

    if "permissions" in data and data["permissions"] is not None:
        unknown = set(data["permissions"]) - set(ALL_PERMISSIONS)
        if unknown:
            raise HTTPException(400, f"Permissão desconhecida: {', '.join(sorted(unknown))}")
        target.permissions = data.pop("permissions")

    if "role" in data and data["role"] is not None:
        target.role = RoomRole(data.pop("role"))

    for key, value in data.items():
        setattr(target, key, value)

    db.commit()
    db.refresh(target)

    payload_out = serialize_member(target)
    await manager.to_room(room.id, "member:updated", payload_out)
    return {"member": payload_out}


@router.delete("/{slug}/membros/{member_id}", dependencies=[Depends(verify_csrf)])
async def remove_member(slug: str, member_id: str, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    me = require_membership(db, room, user)

    target = next((m for m in room.members if m.id == member_id), None)
    if target is None:
        raise HTTPException(404, "Membro não encontrado.")
    if target.user_id == room.owner_id:
        raise HTTPException(400, "O dono da mesa não pode ser removido.")

    saindo = target.user_id == user.id
    if not saindo:
        require_permission(me, "room.kick")

    nome = target.user.display_name
    target_user_id = target.user_id
    db.delete(target)
    message = RoomMessage(
        room_id=room.id,
        kind=MessageKind.SYSTEM,
        body=f"{nome} saiu da mesa." if saindo else f"{nome} foi removido da mesa.",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    await manager.to_room(
        room.id, "member:left", {"member_id": member_id, "user_id": target_user_id}
    )
    await manager.to_room(room.id, "chat:message", serialize_room_message(message))
    return {"ok": True, "redirect": "/painel" if saindo else None}


# ===========================================================================
#  Cenas
# ===========================================================================


@router.post("/{slug}/cenas", dependencies=[Depends(verify_csrf)])
async def create_scene(slug: str, payload: SceneIn, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "scene.create")

    data = payload.model_dump(exclude_unset=True)
    if "grid_type" in data and data["grid_type"]:
        data["grid_type"] = GridType(data["grid_type"])

    scene = Scene(room_id=room.id, order=len(room.scenes), **data)
    db.add(scene)
    db.commit()
    db.refresh(scene)

    await manager.to_room(room.id, "scene:created", serialize_scene(scene))
    return {"scene": serialize_scene(scene)}


@router.patch("/{slug}/cenas/{scene_id}", dependencies=[Depends(verify_csrf)])
async def update_scene(
    slug: str, scene_id: str, payload: SceneUpdateIn, user: CurrentUser, db: DbDep
):
    room = load_room(db, slug)
    member = require_membership(db, room, user)

    scene = db.get(Scene, scene_id)
    if scene is None or scene.room_id != room.id:
        raise HTTPException(404, "Cena não encontrada.")

    data = payload.model_dump(exclude_unset=True)
    tornar_ativa = data.pop("is_active", None)

    if data:
        require_permission(member, "scene.edit")
        if "grid_type" in data and data["grid_type"]:
            data["grid_type"] = GridType(data["grid_type"])
        for key, value in data.items():
            setattr(scene, key, value)

    if tornar_ativa:
        require_permission(member, "scene.switch")
        for other in room.scenes:
            other.is_active = other.id == scene.id

    db.commit()
    db.refresh(scene)

    if tornar_ativa:
        # Todo mundo precisa recarregar a mesa: mudou o mapa e os tokens.
        await manager.to_room(room.id, "scene:switched", {"scene_id": scene.id})
    else:
        await manager.to_room(room.id, "scene:updated", serialize_scene(scene))

    return {"scene": serialize_scene(scene)}


@router.delete("/{slug}/cenas/{scene_id}", dependencies=[Depends(verify_csrf)])
async def delete_scene(slug: str, scene_id: str, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "scene.create")

    scene = db.get(Scene, scene_id)
    if scene is None or scene.room_id != room.id:
        raise HTTPException(404, "Cena não encontrada.")
    if len(room.scenes) <= 1:
        raise HTTPException(400, "A mesa precisa de pelo menos uma cena.")

    era_ativa = scene.is_active
    db.delete(scene)
    db.commit()
    db.refresh(room)

    if era_ativa:
        ensure_active_scene(db, room)
        await manager.to_room(room.id, "scene:switched", {"scene_id": room.active_scene.id})
    else:
        await manager.to_room(room.id, "scene:deleted", {"scene_id": scene_id})

    return {"ok": True}


# ===========================================================================
#  Tokens
# ===========================================================================


def _token_or_404(db, room: Room, token_id: str) -> Token:
    token = db.get(Token, token_id)
    if token is None or token.scene.room_id != room.id:
        raise HTTPException(404, "Token não encontrado.")
    return token


@router.post("/{slug}/tokens", dependencies=[Depends(verify_csrf)])
async def create_token(slug: str, payload: TokenCreateIn, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "token.create")

    scene = db.get(Scene, payload.scene_id)
    if scene is None or scene.room_id != room.id:
        raise HTTPException(404, "Cena não encontrada.")

    if payload.layer == "GM_ONLY":
        require_permission(member, "token.reveal")

    data = payload.model_dump(exclude_unset=True, exclude={"scene_id", "layer"})
    data.setdefault("color", member.color)

    token = Token(
        scene_id=scene.id,
        owner_id=user.id,
        layer=TokenLayer(payload.layer),
        order=len(scene.tokens),
        **data,
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    await manager.to_room(room.id, "token:created", serialize_token(token))
    return {"token": serialize_token(token)}


@router.patch("/{slug}/tokens/{token_id}", dependencies=[Depends(verify_csrf)])
async def update_token(
    slug: str, token_id: str, payload: TokenUpdateIn, user: CurrentUser, db: DbDep
):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    token = _token_or_404(db, room, token_id)

    data = payload.model_dump(exclude_unset=True)
    apenas_posicao = set(data) <= {"x", "y", "rotation"}
    meu = token.owner_id == user.id

    if apenas_posicao:
        if token.is_locked and not can(member, "token.move.any"):
            raise HTTPException(403, "Este token está travado.")
        if not (can(member, "token.move.any") or (meu and can(member, "token.move.own"))):
            raise HTTPException(403, "Você não pode mover este token.")
    else:
        # Alterar nome, camada, visibilidade ou tamanho é edição, não movimento.
        if not (can(member, "token.move.any") or (meu and can(member, "token.create"))):
            raise HTTPException(403, "Você não pode editar este token.")
        if data.get("layer") == "GM_ONLY":
            require_permission(member, "token.reveal")

    if "layer" in data and data["layer"]:
        token.layer = TokenLayer(data.pop("layer"))
    for key, value in data.items():
        setattr(token, key, value)

    db.commit()
    db.refresh(token)

    await manager.to_room(
        room.id, "token:updated", serialize_token(token), exclude_user=user.id
    )
    return {"token": serialize_token(token)}


@router.delete("/{slug}/tokens/{token_id}", dependencies=[Depends(verify_csrf)])
async def delete_token(slug: str, token_id: str, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    token = _token_or_404(db, room, token_id)

    meu = token.owner_id == user.id
    if not (can(member, "token.delete.any") or (meu and can(member, "token.create"))):
        raise HTTPException(403, "Você não pode apagar este token.")

    db.delete(token)
    db.commit()

    await manager.to_room(room.id, "token:deleted", {"token_id": token_id})
    return {"ok": True}


# ===========================================================================
#  Chat e rolagens
# ===========================================================================


async def _publish(db, room: Room, message: RoomMessage) -> dict:
    db.add(message)
    db.commit()
    db.refresh(message)
    data = serialize_room_message(message)

    if message.whisper_to:
        # Sussurro: só o destinatário e o autor recebem.
        for user_id in {message.whisper_to, message.author_id}:
            if user_id:
                await manager.to_room(room.id, "chat:message", data, only_user=user_id)
    else:
        await manager.to_room(room.id, "chat:message", data)
    return data


@router.get("/{slug}/mensagens")
async def room_messages(slug: str, user: CurrentUser, db: DbDep, limite: int = 80):
    room = load_room(db, slug)
    require_membership(db, room, user)
    estado = build_room_state(db, room, user)
    return {"messages": estado["messages"][-min(limite, 200):]}


@router.post("/{slug}/mensagens", dependencies=[Depends(verify_csrf)])
async def send_message(slug: str, payload: RoomMessageIn, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "chat.send")

    texto = payload.body.strip()

    # "/r 2d6+1 ataque" vira uma rolagem de verdade em vez de texto solto.
    comando = parse_roll_command(texto)
    if comando:
        formula, rotulo = comando
        return await _roll_and_publish(
            db, room, member, user, formula, rotulo, private=payload.private
        )

    destino = payload.whisper_to
    if destino and not room.member_for(destino):
        raise HTTPException(400, "Essa pessoa não está na mesa.")

    message = RoomMessage(
        room_id=room.id,
        author_id=user.id,
        kind=MessageKind.OOC if texto.startswith("((") else MessageKind.TEXT,
        body=texto,
        whisper_to=destino,
    )
    return {"message": await _publish(db, room, message)}


@router.post("/{slug}/rolar", dependencies=[Depends(verify_csrf)])
async def roll_dice(slug: str, payload: RollIn, user: CurrentUser, db: DbDep):
    room = load_room(db, slug)
    member = require_membership(db, room, user)
    require_permission(member, "chat.send")

    formula = payload.formula
    rotulo = payload.label

    # Fórmula vinda da ficha: resolve {{caminhos}} com os valores do personagem.
    if payload.character_id:
        character = db.get(Character, payload.character_id)
        if character is None or character.room_id != room.id:
            raise HTTPException(404, "Ficha não encontrada.")
        if not can_view_character(character, user.id, member):
            raise HTTPException(403, "Você não pode usar esta ficha.")
        formula = resolve_formula(formula, character.data or {})
        rotulo = rotulo or character.name

    return await _roll_and_publish(
        db, room, member, user, formula, rotulo, private=payload.private
    )


async def _roll_and_publish(db, room, member, user, formula: str, rotulo, *, private: bool):
    formula = apply_room_difficulty(formula, room.system_config)

    try:
        resultado = roll(formula, rotulo)
    except DiceError as erro:
        raise HTTPException(400, str(erro))

    if private and not can(member, "roll.private"):
        raise HTTPException(403, "Você não pode rolar em segredo nesta mesa.")

    message = RoomMessage(
        room_id=room.id,
        author_id=user.id,
        kind=MessageKind.ROLL,
        body=describe(resultado),
        payload=resultado.to_dict(),
        whisper_to=user.id if private else None,
    )
    data = await _publish(db, room, message)
    return {"message": data, "roll": resultado.to_dict()}
