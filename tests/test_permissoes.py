"""Permissões da mesa."""

from __future__ import annotations

from app.models import RoomMember, RoomRole
from app.permissions import ALL_PERMISSIONS, can, effective_permissions, is_game_master


def membro(role: RoomRole, overrides: dict | None = None) -> RoomMember:
    return RoomMember(role=role, permissions=overrides or {})


def test_mestre_tem_tudo():
    assert effective_permissions(membro(RoomRole.GM)) == set(ALL_PERMISSIONS)


def test_mestre_nao_perde_permissao_nem_com_override():
    # O dono não pode se trancar para fora da própria mesa.
    trancado = membro(RoomRole.GM, {"scene.edit": False, "chat.send": False})
    assert can(trancado, "scene.edit")
    assert can(trancado, "chat.send")


def test_jogador_tem_o_basico_e_nada_mais():
    jogador = membro(RoomRole.PLAYER)
    assert can(jogador, "token.move.own")
    assert can(jogador, "sheet.edit.own")
    assert not can(jogador, "token.move.any")
    assert not can(jogador, "room.kick")
    assert not can(jogador, "sheet.view.any")


def test_espectador_so_conversa():
    espectador = membro(RoomRole.SPECTATOR)
    assert can(espectador, "chat.send")
    assert not can(espectador, "token.create")
    assert not can(espectador, "sheet.create")


def test_override_concede_permissao_extra():
    jogador = membro(RoomRole.PLAYER, {"token.move.any": True})
    assert can(jogador, "token.move.any")


def test_override_revoga_permissao_do_cargo():
    jogador = membro(RoomRole.PLAYER, {"token.move.own": False})
    assert not can(jogador, "token.move.own")


def test_override_desconhecido_e_ignorado():
    jogador = membro(RoomRole.PLAYER, {"inventado.permissao": True})
    assert "inventado.permissao" not in effective_permissions(jogador)


def test_co_mestre_e_considerado_mestre():
    assert is_game_master(membro(RoomRole.CO_GM))
    assert is_game_master(membro(RoomRole.GM))
    assert not is_game_master(membro(RoomRole.PLAYER))
    assert not is_game_master(None)


def test_sem_membro_nao_pode_nada():
    assert not can(None, "chat.send")
    assert effective_permissions(None) == set()
