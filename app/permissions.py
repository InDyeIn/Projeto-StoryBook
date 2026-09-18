"""Permissões granulares da mesa.

O cargo define o conjunto padrão; o mestre pode ligar/desligar permissões
jogador a jogador em ``RoomMember.permissions``.
"""

from __future__ import annotations

from app.models import RoomMember, RoomRole

PERMISSIONS: dict[str, str] = {
    "room.edit": "Editar a sala (nome, descrição, opções do sistema)",
    "room.invite": "Convidar jogadores",
    "room.kick": "Remover jogadores",
    "room.permissions": "Alterar cargos e permissões",
    "scene.create": "Criar e apagar cenas",
    "scene.edit": "Editar a cena (mapa, grade, tamanho)",
    "scene.switch": "Trocar a cena ativa de todos",
    "token.create": "Criar tokens",
    "token.move.own": "Mover os próprios tokens",
    "token.move.any": "Mover qualquer token",
    "token.delete.any": "Apagar qualquer token",
    "token.reveal": "Enxergar a camada do mestre",
    "sheet.create": "Criar fichas",
    "sheet.edit.own": "Editar a própria ficha",
    "sheet.edit.any": "Editar qualquer ficha",
    "sheet.view.any": "Ver todas as fichas",
    "roll.private": "Rolar dados em segredo",
    "chat.send": "Escrever no chat da mesa",
}

ALL_PERMISSIONS: list[str] = list(PERMISSIONS)

#: Agrupamento usado na tela de configuração de permissões.
PERMISSION_GROUPS: dict[str, list[str]] = {
    "Sala": ["room.edit", "room.invite", "room.kick", "room.permissions"],
    "Cenas": ["scene.create", "scene.edit", "scene.switch"],
    "Tokens": [
        "token.create",
        "token.move.own",
        "token.move.any",
        "token.delete.any",
        "token.reveal",
    ],
    "Fichas": ["sheet.create", "sheet.edit.own", "sheet.edit.any", "sheet.view.any"],
    "Mesa": ["roll.private", "chat.send"],
}

CO_GM_DEFAULTS = [
    "room.invite",
    "scene.create",
    "scene.edit",
    "scene.switch",
    "token.create",
    "token.move.own",
    "token.move.any",
    "token.delete.any",
    "token.reveal",
    "sheet.create",
    "sheet.edit.own",
    "sheet.edit.any",
    "sheet.view.any",
    "roll.private",
    "chat.send",
]

PLAYER_DEFAULTS = [
    "token.create",
    "token.move.own",
    "sheet.create",
    "sheet.edit.own",
    "chat.send",
]

SPECTATOR_DEFAULTS = ["chat.send"]

ROLE_DEFAULTS: dict[RoomRole, list[str]] = {
    RoomRole.GM: ALL_PERMISSIONS,
    RoomRole.CO_GM: CO_GM_DEFAULTS,
    RoomRole.PLAYER: PLAYER_DEFAULTS,
    RoomRole.SPECTATOR: SPECTATOR_DEFAULTS,
}

ROLE_LABELS: dict[RoomRole, str] = {
    RoomRole.GM: "Mestre",
    RoomRole.CO_GM: "Co-mestre",
    RoomRole.PLAYER: "Jogador",
    RoomRole.SPECTATOR: "Espectador",
}


def effective_permissions(member: RoomMember | None) -> set[str]:
    """Padrão do cargo, com os ajustes explícitos do jogador aplicados por cima."""
    if member is None:
        return set()
    if member.role == RoomRole.GM:
        return set(ALL_PERMISSIONS)  # o mestre nunca se tranca para fora

    allowed = set(ROLE_DEFAULTS.get(member.role, []))
    for key, value in (member.permissions or {}).items():
        if key not in PERMISSIONS:
            continue
        if value:
            allowed.add(key)
        else:
            allowed.discard(key)
    return allowed


def can(member: RoomMember | None, permission: str) -> bool:
    return permission in effective_permissions(member)


def is_game_master(member: RoomMember | None) -> bool:
    return member is not None and member.role in (RoomRole.GM, RoomRole.CO_GM)
