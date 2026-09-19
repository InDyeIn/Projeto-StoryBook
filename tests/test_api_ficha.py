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
    # As nove Qualidades nascem zeradas; o jogador distribui as 9 GQs.
    assert len(ficha["data"]["qualidades"]) == 9
    assert ficha["data"]["qualidades"]["empatia"] == {"atual": 0, "max": 0}
    assert ficha["data"]["arc"]["anomalia"] == ""
    assert ficha["data"]["estado"]["burnout"] == 0


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
                "arc.anomalia": "sussurro",
                "identidade.nome": "Ruan Teixeira",
                "qualidades.empatia.max": 3,
                "qualidades.empatia.atual": 2,
            }
        },
    )
    assert resposta.status_code == 200
    dados = resposta.json()["character"]["data"]
    assert dados["arc"]["anomalia"] == "sussurro"
    assert dados["identidade"]["nome"] == "Ruan Teixeira"
    assert dados["qualidades"]["empatia"] == {"atual": 2, "max": 3}


def test_edicao_persiste_entre_requisicoes(mesa_com_jogador):
    """Regressão: a cópia rasa do JSON fazia a gravação passar despercebida."""
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)

    jogador.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"estado.burnout": 2}}
    )
    relido = jogador.get(f"/api/fichas/{ficha['id']}").json()["character"]
    assert relido["data"]["estado"]["burnout"] == 2


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
        f"/api/fichas/{ficha['id']}", json={"patch": {"notas_gm": "invadido"}}
    )
    assert resposta.status_code == 403


def test_mestre_escreve_em_campo_do_mestre(mesa_com_jogador):
    mestre, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    resposta = mestre.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"notas_gm": "anotado"}}
    )
    assert resposta.status_code == 200


def test_jogador_nao_edita_ficha_alheia(mesa_com_jogador, fazer_usuario):
    mestre, jogador, sala = mesa_com_jogador
    codigo = mestre.get(f"/api/salas/{sala['slug']}").json()["room"]["invite_code"]
    outro = fazer_usuario("xereta")
    outro.post("/api/salas/entrar", json={"invite_code": codigo})

    ficha = nova_ficha(jogador, sala)
    resposta = outro.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"estado.burnout": 6}}
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
    """Fórmulas com {{caminho}} leem os valores da ficha."""
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    jogador.patch(
        f"/api/fichas/{ficha['id']}", json={"patch": {"qualidades.sutileza.atual": 4}}
    )

    resposta = jogador.post(
        f"/api/salas/{sala['slug']}/rolar",
        json={
            "formula": "{{qualidades.sutileza}}d6>=4",
            "character_id": ficha["id"],
        },
    )
    assert resposta.status_code == 200
    assert resposta.json()["roll"]["formula"] == "4d6>=4"


def test_jogada_padrao_do_triangle_agency(mesa_com_jogador):
    """6d4 contando os 3s: sucesso, Caos gerado e Triscendência."""
    _, jogador, sala = mesa_com_jogador

    vistos = {"triscendencia": False, "normal": False}
    for _ in range(80):
        rolagem = jogador.post(
            f"/api/salas/{sala['slug']}/rolar", json={"formula": "6d4=3"}
        ).json()["roll"]

        assert rolagem["is_pool"] is True
        assert rolagem["formula"] == "6d4=3"
        assert rolagem["success_word"] == "3"
        assert rolagem["resource_name"] == "Caos"

        treses = rolagem["successes"]
        dados = rolagem["terms"][0]["dice"]
        assert len(dados) == 6
        assert treses == sum(1 for d in dados if d["value"] == 3)

        if treses == 3:
            # Triscendência: sucesso sem nenhum Caos.
            assert rolagem["highlight"] == "Triscendência"
            assert rolagem["resource_amount"] == 0
            vistos["triscendencia"] = True
        else:
            # Cada dado que não é 3 gera um Caos.
            assert "highlight" not in rolagem
            assert rolagem["resource_amount"] == 6 - treses
            vistos["normal"] = True

    assert vistos["normal"], "nenhuma jogada comum em 80 tentativas"
    assert vistos["triscendencia"], "nenhuma Triscendência em 80 tentativas"


def test_colocar_ficha_no_mapa_cria_token_vinculado(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala, nome="Teixeira")

    resposta = jogador.post(f"/api/fichas/{ficha['id']}/token")
    assert resposta.status_code == 200
    token = resposta.json()["token"]
    assert token["character_id"] == ficha["id"]
    assert token["name"] == "Teixeira"
    # O Triangle Agency não tem pontos de vida, então o token não ganha barras.
    assert token["bars"] == []


def test_barra_do_token_acompanha_a_ficha(fazer_usuario):
    """Sistemas com recurso (aqui o genérico) alimentam a barra sob o token."""
    mestre = fazer_usuario("dono")
    sala = mestre.post(
        "/api/salas", json={"name": "Mesa Genérica", "system_id": "generico"}
    ).json()

    ficha = mestre.post(
        "/api/fichas", json={"name": "Herói", "room_id": sala["id"]}
    ).json()["character"]
    mestre.post(f"/api/fichas/{ficha['id']}/token")

    mestre.patch(f"/api/fichas/{ficha['id']}", json={"patch": {"vida.atual": 5}})

    tokens = mestre.get(f"/api/salas/{sala['slug']}").json()["tokens"]
    vida = next(b for b in tokens[0]["bars"] if b["label"] == "Vida")
    assert vida["current"] == 5
    assert vida["ratio"] == 0.5


def test_apagar_a_propria_ficha(mesa_com_jogador):
    _, jogador, sala = mesa_com_jogador
    ficha = nova_ficha(jogador, sala)
    assert jogador.delete(f"/api/fichas/{ficha['id']}").status_code == 200
    assert jogador.get(f"/api/fichas/{ficha['id']}").status_code == 404
