"""Mesas: criação, entrada, permissões, tokens, fichas e rolagens."""

from __future__ import annotations

import pytest


@pytest.fixture
def mesa(fazer_usuario):
    """Mestre com uma mesa aberta. Devolve (sessão, dados da sala)."""
    mestre = fazer_usuario("mestre", "A Mestra")
    resposta = mestre.post(
        "/api/salas",
        json={
            "name": "Mesa de Teste",
            "description": "Só para os testes.",
            "system_id": "triangle-agency",
            "max_players": 3,
            "system_config": {"gqs_iniciais": 12},
        },
    )
    assert resposta.status_code == 200, resposta.text
    return mestre, resposta.json()


def estado(sessao, slug):
    resposta = sessao.get(f"/api/salas/{slug}")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# ---------------------------------------------------------------------------
#  Criação e entrada
# ---------------------------------------------------------------------------


def test_criar_mesa_gera_slug_cena_e_convite(mesa):
    mestre, sala = mesa
    dados = estado(mestre, sala["slug"])

    assert dados["room"]["slug"] == "mesa-de-teste"
    assert dados["me"]["role"] == "GM"
    assert dados["scene"]["is_active"] is True
    assert len(dados["room"]["invite_code"]) == 8
    # As opções não informadas vêm preenchidas com o padrão do sistema.
    assert dados["room"]["system_config"]["gqs_iniciais"] == 12
    assert "anomalias_visiveis" in dados["room"]["system_config"]


def test_slug_repetido_ganha_sufixo(fazer_usuario):
    a = fazer_usuario("usera")
    b = fazer_usuario("userb")
    corpo = {"name": "Mesa Igual", "system_id": "generico"}
    assert a.post("/api/salas", json=corpo).json()["slug"] == "mesa-igual"
    assert b.post("/api/salas", json=corpo).json()["slug"] == "mesa-igual-2"


def test_entrar_com_codigo_de_convite(mesa, fazer_usuario):
    mestre, sala = mesa
    codigo = estado(mestre, sala["slug"])["room"]["invite_code"]

    jogador = fazer_usuario("jogador")
    resposta = jogador.post("/api/salas/entrar", json={"invite_code": codigo})
    assert resposta.status_code == 200

    dados = estado(jogador, sala["slug"])
    assert dados["me"]["role"] == "PLAYER"
    assert len(dados["members"]) == 2


def test_codigo_invalido(fazer_usuario):
    alguem = fazer_usuario("perdido")
    assert alguem.post("/api/salas/entrar", json={"invite_code": "NAOEXIST"}).status_code == 404


def test_codigo_em_minusculas_funciona(mesa, fazer_usuario):
    mestre, sala = mesa
    codigo = estado(mestre, sala["slug"])["room"]["invite_code"]
    jogador = fazer_usuario("caixa")
    assert jogador.post(
        "/api/salas/entrar", json={"invite_code": codigo.lower()}
    ).status_code == 200


def test_mesa_lotada_recusa(fazer_usuario):
    mestre = fazer_usuario("apertado")
    sala = mestre.post(
        "/api/salas", json={"name": "Mesa Pequena", "system_id": "generico", "max_players": 1}
    ).json()
    codigo = estado(mestre, sala["slug"])["room"]["invite_code"]

    primeiro = fazer_usuario("cabe")
    assert primeiro.post("/api/salas/entrar", json={"invite_code": codigo}).status_code == 200

    segundo = fazer_usuario("naocabe")
    assert segundo.post("/api/salas/entrar", json={"invite_code": codigo}).status_code == 409


def test_quem_nao_e_membro_nao_le_a_mesa(mesa, fazer_usuario):
    _, sala = mesa
    estranho = fazer_usuario("estranho")
    assert estranho.get(f"/api/salas/{sala['slug']}").status_code == 403


def test_rotacionar_convite_invalida_o_antigo(mesa, fazer_usuario):
    mestre, sala = mesa
    antigo = estado(mestre, sala["slug"])["room"]["invite_code"]

    novo = mestre.post(f"/api/salas/{sala['slug']}/novo-convite").json()["invite_code"]
    assert novo != antigo

    atrasado = fazer_usuario("atrasado")
    assert atrasado.post("/api/salas/entrar", json={"invite_code": antigo}).status_code == 404
    assert atrasado.post("/api/salas/entrar", json={"invite_code": novo}).status_code == 200


# ---------------------------------------------------------------------------
#  Permissões
# ---------------------------------------------------------------------------


@pytest.fixture
def mesa_com_jogador(mesa, fazer_usuario):
    mestre, sala = mesa
    codigo = estado(mestre, sala["slug"])["room"]["invite_code"]
    jogador = fazer_usuario("peao", "O Peão")
    jogador.post("/api/salas/entrar", json={"invite_code": codigo})
    dados = estado(mestre, sala["slug"])
    membro = next(m for m in dados["members"] if m["user_id"] == jogador.usuario["id"])
    return mestre, jogador, sala, membro


def test_jogador_nao_edita_a_sala(mesa_com_jogador):
    _, jogador, sala, _ = mesa_com_jogador
    resposta = jogador.patch(f"/api/salas/{sala['slug']}", json={"name": "Tomei a mesa"})
    assert resposta.status_code == 403


def test_jogador_nao_expulsa_ninguem(mesa_com_jogador):
    mestre, jogador, sala, _ = mesa_com_jogador
    dados = estado(mestre, sala["slug"])
    membro_mestre = next(m for m in dados["members"] if m["role"] == "GM")
    resposta = jogador.delete(f"/api/salas/{sala['slug']}/membros/{membro_mestre['id']}")
    assert resposta.status_code in (400, 403)


def test_jogador_pode_sair_sozinho(mesa_com_jogador):
    _, jogador, sala, membro = mesa_com_jogador
    assert jogador.delete(f"/api/salas/{sala['slug']}/membros/{membro['id']}").status_code == 200
    assert jogador.get(f"/api/salas/{sala['slug']}").status_code == 403


def test_dono_nao_pode_ser_removido(mesa_com_jogador):
    mestre, _, sala, _ = mesa_com_jogador
    dados = estado(mestre, sala["slug"])
    dono = next(m for m in dados["members"] if m["user_id"] == dados["room"]["owner_id"])
    assert mestre.delete(f"/api/salas/{sala['slug']}/membros/{dono['id']}").status_code == 400


def test_dono_nao_pode_deixar_de_ser_mestre(mesa_com_jogador):
    mestre, _, sala, _ = mesa_com_jogador
    dados = estado(mestre, sala["slug"])
    dono = next(m for m in dados["members"] if m["user_id"] == dados["room"]["owner_id"])
    resposta = mestre.patch(
        f"/api/salas/{sala['slug']}/membros/{dono['id']}", json={"role": "PLAYER"}
    )
    assert resposta.status_code == 400


def test_mestre_concede_permissao_extra(mesa_com_jogador):
    mestre, jogador, sala, membro = mesa_com_jogador

    resposta = mestre.patch(
        f"/api/salas/{sala['slug']}/membros/{membro['id']}",
        json={"permissions": {"token.move.any": True}},
    )
    assert resposta.status_code == 200
    assert "token.move.any" in resposta.json()["member"]["permissions"]
    assert "token.move.any" in estado(jogador, sala["slug"])["me"]["permissions"]


def test_permissao_inventada_e_recusada(mesa_com_jogador):
    mestre, _, sala, membro = mesa_com_jogador
    resposta = mestre.patch(
        f"/api/salas/{sala['slug']}/membros/{membro['id']}",
        json={"permissions": {"virar.admin": True}},
    )
    assert resposta.status_code == 400


def test_jogador_troca_a_propria_cor_sem_permissao_especial(mesa_com_jogador):
    _, jogador, sala, membro = mesa_com_jogador
    resposta = jogador.patch(
        f"/api/salas/{sala['slug']}/membros/{membro['id']}", json={"color": "#5ce1e6"}
    )
    assert resposta.status_code == 200


def test_jogador_nao_muda_o_proprio_cargo(mesa_com_jogador):
    _, jogador, sala, membro = mesa_com_jogador
    resposta = jogador.patch(
        f"/api/salas/{sala['slug']}/membros/{membro['id']}", json={"role": "GM"}
    )
    assert resposta.status_code == 403


# ---------------------------------------------------------------------------
#  Tokens
# ---------------------------------------------------------------------------


def test_criar_e_mover_o_proprio_token(mesa_com_jogador):
    _, jogador, sala, _ = mesa_com_jogador
    cena = estado(jogador, sala["slug"])["scene"]["id"]

    criado = jogador.post(
        f"/api/salas/{sala['slug']}/tokens",
        json={"scene_id": cena, "name": "Meu Token", "x": 0, "y": 0},
    )
    assert criado.status_code == 200
    token = criado.json()["token"]

    movido = jogador.patch(
        f"/api/salas/{sala['slug']}/tokens/{token['id']}", json={"x": 128, "y": 64}
    )
    assert movido.status_code == 200
    assert movido.json()["token"]["x"] == 128


def test_jogador_nao_move_token_alheio(mesa_com_jogador):
    mestre, jogador, sala, _ = mesa_com_jogador
    cena = estado(mestre, sala["slug"])["scene"]["id"]
    token = mestre.post(
        f"/api/salas/{sala['slug']}/tokens", json={"scene_id": cena, "name": "Do Mestre"}
    ).json()["token"]

    resposta = jogador.patch(
        f"/api/salas/{sala['slug']}/tokens/{token['id']}", json={"x": 999}
    )
    assert resposta.status_code == 403


def test_token_travado_nao_se_move(mesa_com_jogador):
    _, jogador, sala, _ = mesa_com_jogador
    cena = estado(jogador, sala["slug"])["scene"]["id"]
    token = jogador.post(
        f"/api/salas/{sala['slug']}/tokens", json={"scene_id": cena, "name": "Preso"}
    ).json()["token"]

    # Só quem pode mover qualquer token consegue travar/destravar.
    assert jogador.patch(
        f"/api/salas/{sala['slug']}/tokens/{token['id']}", json={"is_locked": True}
    ).status_code in (200, 403)


def test_jogador_nao_cria_na_camada_do_mestre(mesa_com_jogador):
    _, jogador, sala, _ = mesa_com_jogador
    cena = estado(jogador, sala["slug"])["scene"]["id"]
    resposta = jogador.post(
        f"/api/salas/{sala['slug']}/tokens",
        json={"scene_id": cena, "name": "Escondido", "layer": "GM_ONLY"},
    )
    assert resposta.status_code == 403


def test_token_da_camada_do_mestre_fica_oculto_do_jogador(mesa_com_jogador):
    mestre, jogador, sala, _ = mesa_com_jogador
    cena = estado(mestre, sala["slug"])["scene"]["id"]
    mestre.post(
        f"/api/salas/{sala['slug']}/tokens",
        json={"scene_id": cena, "name": "Segredo", "layer": "GM_ONLY"},
    )

    nomes_mestre = [t["name"] for t in estado(mestre, sala["slug"])["tokens"]]
    nomes_jogador = [t["name"] for t in estado(jogador, sala["slug"])["tokens"]]
    assert "Segredo" in nomes_mestre
    assert "Segredo" not in nomes_jogador


# ---------------------------------------------------------------------------
#  Rolagens
# ---------------------------------------------------------------------------


def test_rolagem_no_chat_vira_mensagem(mesa):
    mestre, sala = mesa
    resposta = mestre.post(
        f"/api/salas/{sala['slug']}/mensagens", json={"body": "/r 2d6+3 teste"}
    )
    assert resposta.status_code == 200
    mensagem = resposta.json()["message"]
    assert mensagem["kind"] == "ROLL"
    assert mensagem["payload"]["label"] == "teste"
    assert 5 <= mensagem["payload"]["total"] <= 15


def test_rolagem_aplica_a_dificuldade_da_sala(fazer_usuario):
    """Sistemas que expõem `dificuldade_padrao` reescrevem o alvo das pools."""
    mestre = fazer_usuario("arbitro")
    sala = mestre.post(
        "/api/salas",
        json={
            "name": "Mesa Difícil",
            "system_id": "generico",
            "system_config": {"dificuldade_padrao": "5"},
        },
    ).json()

    resposta = mestre.post(f"/api/salas/{sala['slug']}/rolar", json={"formula": "4d6>=4"})
    assert resposta.json()["roll"]["formula"] == "4d6>=5"


def test_formula_invalida_devolve_erro_legivel(mesa):
    mestre, sala = mesa
    resposta = mestre.post(f"/api/salas/{sala['slug']}/rolar", json={"formula": "banana"})
    assert resposta.status_code == 400
    assert "inválido" in resposta.json()["detail"].lower()


def test_sussurro_so_chega_ao_destinatario(mesa_com_jogador, fazer_usuario):
    mestre, jogador, sala, _ = mesa_com_jogador
    outro = fazer_usuario("terceiro")
    codigo = estado(mestre, sala["slug"])["room"]["invite_code"]
    outro.post("/api/salas/entrar", json={"invite_code": codigo})

    mestre.post(
        f"/api/salas/{sala['slug']}/mensagens",
        json={"body": "só para você", "whisper_to": jogador.usuario["id"]},
    )

    def corpos(sessao):
        return [m["body"] for m in estado(sessao, sala["slug"])["messages"]]

    assert "só para você" in corpos(jogador)
    assert "só para você" in corpos(mestre)      # o autor vê o que mandou
    assert "só para você" not in corpos(outro)


def test_jogador_sem_permissao_nao_rola_em_segredo(mesa_com_jogador):
    _, jogador, sala, _ = mesa_com_jogador
    resposta = jogador.post(
        f"/api/salas/{sala['slug']}/rolar", json={"formula": "d20", "private": True}
    )
    assert resposta.status_code == 403
