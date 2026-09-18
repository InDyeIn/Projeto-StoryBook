"""Fichas: criação, edição por caminho e visibilidade."""

from __future__ import annotations

import pytest


@pytest.fixture
def mesa_com_jogador(fazer_usuario):
    mestre = fazer_usuario("mestra", "A Mestra")
    sala = mestre.post(
        "/api/salas", json={"name": "Mesa das Fichas", "system_id": "triangle-agency"}
    ).json()
    codigo = mestre.get(f"/api/salas/{sala['slug']}").json()["room"]["invite_code"]

    jogador = fazer_usuario("peao", "O Peão")
    jogador.post("/api/salas/entrar", json={"invite_code": codigo})
    return mestre, jogador, sala


def nova_ficha(sessao, sala, nome="Agente", **extra):
    resposta = sessao.post(
        "/api/fichas", json={"name": nome, "room_id": sala["id"], **extra}
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["character"]


def test_ficha_nasce_com_os_valores_do_sistema(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)

    assert ficha["system_id"] == "triangle-agency"
    assert ficha["data"]["competencias"]["burocracia"] == 2
    assert ficha["data"]["realidade"] == {"atual": 6, "max": 6}


def test_a_mesa_manda_no_sistema_da_ficha(fazer_usuario):
    """Quem cria a ficha não escolhe o sistema: quem manda é a mesa."""
    mestre = fazer_usuario("dono")
    sala = mestre.post("/api/salas", json={"name": "Só Genérico", "system_id": "generico"}).json()

    ficha = mestre.post(
        "/api/fichas",
        json={"name": "Intruso", "room_id": sala["id"], "system_id": "triangle-agency"},
    ).json()["character"]
    assert ficha["system_id"] == "generico"


def test_editar_campo_por_caminho(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)

    resposta = jogador.patch(
        f"/api/fichas/{ficha['id']}",
        json={
            "patch": {
                "competencias.burocracia": 5,
                "identidade.codinome": "Caneta Azul",
                "realidade.atual": 3,
            }
        },
    )
    assert resposta.status_code == 200
    dados = resposta.json()["character"]["data"]
    assert dados["competencias"]["burocracia"] == 5
    assert dados["identidade"]["codinome"] == "Caneta Azul"
    assert dados["realidade"] == {"atual": 3, "max": 6}


def test_edicao_persiste_entre_requisicoes(mesa_com_jogador):
    """Regressão: a cópia rasa do JSON fazia a gravação passar despercebida."""
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)

    jogador.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"competencias.fisico": 6}}
    )
    relido = jogador.get(f"/api/fichas/{ficha['id']}").json()["character"]
    assert relido["data"]["competencias"]["fisico"] == 6


def test_campo_inexistente_e_recusado(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    resposta = jogador.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"virei.admin": True}}
    )
    assert resposta.status_code == 400


def test_jogador_nao_escreve_em_campo_do_mestre(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    resposta = jogador.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"notas_mestre": "invadido"}}
    )
    assert resposta.status_code == 403


def test_mestre_escreve_em_campo_do_mestre(mesa_com_jogador):
    mestre, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    resposta = mestre.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"notas_mestre": "anotado"}}
    )
    assert resposta.status_code == 200


def test_jogador_nao_edita_ficha_alheia(mesa_com_jogador, fazer_usuario):
    mestre, jogador, sala = mesa_com_jogador
    codigo = mestre.get(f"/api/salas/{sala['slug']}").json()["room"]["invite_code"]
    outro = fazer_usuario("xereta")
    outro.post("/api/salas/entrar", json={"invite_code": codigo})

    ficha = nova_ficha(jogador, sala)
    resposta = outro.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"competencias.fisico": 6}}
    )
    assert resposta.status_code == 403


def test_ficha_privada_nao_aparece_para_os_outros(mesa_com_jogador, fazer_usuario):
    mestre, jogador, sala = mesa_com_jogador
    codigo = mestre.get(f"/api/salas/{sala['slug']}").json()["room"]["invite_code"]
    outro = fazer_usuario("curioso")
    outro.post("/api/salas/entrar", json={"invite_code": codigo})

    ficha = nova_ficha(jogador, sala, nome="Segredo")
    jogador.patch(f"/api/fichas/{ficha['id']}", json={"visibility": "PRIVATE"})

    assert outro.get(f"/api/fichas/{ficha['id']}").status_code == 403
    # O mestre continua enxergando — ele tem sheet.view.any.
    assert mestre.get(f"/api/fichas/{ficha['id']}").status_code == 200


def test_jogador_comum_nao_cria_npc(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    resposta = jogador.post(
        "/api/fichas", json={"name": "NPC Falso", "room_id": sala["id"], "is_npc": True}
    )
    assert resposta.status_code == 403


def test_rolar_usando_a_ficha_resolve_os_caminhos(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    jogador.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"competencias.investigacao": 4}}
    )

    resposta = jogador.post(
        f"/api/salas/{sala['slug']}/rolar",
        json={
            "formula": "{{competencias.investigacao}}d6>=4",
            "character_id": ficha["id"],
        },
    )
    assert resposta.status_code == 200
    assert resposta.json()["roll"]["formula"] == "4d6>=4"


def test_colocar_ficha_no_mapa_cria_token_vinculado(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala, nome="Teixeira")

    resposta = jogador.post(f"/api/fichas/{ficha['id']}/token")
    assert resposta.status_code == 200
    token = resposta.json()["token"]
    assert token["character_id"] == ficha["id"]
    assert token["name"] == "Teixeira"
    # As barras vêm da definição do sistema, lidas da ficha.
    assert [b["label"] for b in token["bars"]] == ["Realidade", "Confiança"]


def test_barra_do_token_acompanha_a_ficha(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    jogador.post(f"/api/fichas/{ficha['id']}/token")

    jogador.patch(f"/api/fichas/{ficha['id']}", json={"patch": {"realidade.atual": 3}})

    tokens = jogador.get(f"/api/salas/{sala['slug']}").json()["tokens"]
    realidade = next(b for b in tokens[0]["bars"] if b["label"] == "Realidade")
    assert realidade["current"] == 3
    assert realidade["ratio"] == 0.5


def test_apagar_a_propria_ficha(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    assert jogador.delete(f"/api/fichas/{ficha['id']}").status_code == 200
    assert jogador.get(f"/api/fichas/{ficha['id']}").status_code == 404
