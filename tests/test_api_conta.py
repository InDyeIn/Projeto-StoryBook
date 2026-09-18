"""Cadastro, login e perfil."""

from __future__ import annotations


def test_cadastro_cria_sessao(cliente):
    resposta = cliente.post(
        "/api/cadastro",
        json={
            "email": "novo@teste.com",
            "username": "novo",
            "display_name": "Pessoa Nova",
            "password": "senhaforte123",
        },
    )
    assert resposta.status_code == 200
    assert resposta.json()["user"]["username"] == "novo"
    assert cliente.get("/api/eu").json()["user"]["username"] == "novo"


def test_username_e_normalizado_para_minusculas(cliente):
    resposta = cliente.post(
        "/api/cadastro",
        json={
            "email": "Maiusc@teste.com",
            "username": "MaiUsc",
            "display_name": "Maiúsculo",
            "password": "senhaforte123",
        },
    )
    assert resposta.json()["user"]["username"] == "maiusc"


def test_email_duplicado_e_recusado(cliente, fazer_usuario):
    fazer_usuario("primeiro")
    resposta = cliente.post(
        "/api/cadastro",
        json={
            "email": "primeiro@teste.com",
            "username": "outro",
            "display_name": "Outro",
            "password": "senhaforte123",
        },
    )
    assert resposta.status_code == 409


def test_username_duplicado_e_recusado(cliente, fazer_usuario):
    fazer_usuario("repetido")
    resposta = cliente.post(
        "/api/cadastro",
        json={
            "email": "diferente@teste.com",
            "username": "repetido",
            "display_name": "Outro",
            "password": "senhaforte123",
        },
    )
    assert resposta.status_code == 409


def test_senha_curta_e_recusada(cliente):
    resposta = cliente.post(
        "/api/cadastro",
        json={
            "email": "curta@teste.com",
            "username": "curta",
            "display_name": "Curta",
            "password": "1234",
        },
    )
    assert resposta.status_code == 422


def test_username_com_caractere_invalido(cliente):
    resposta = cliente.post(
        "/api/cadastro",
        json={
            "email": "ponto@teste.com",
            "username": "com ponto!",
            "display_name": "Ponto",
            "password": "senhaforte123",
        },
    )
    assert resposta.status_code == 422


def test_login_com_email_ou_usuario(cliente, fazer_usuario):
    fazer_usuario("logavel")

    por_usuario = cliente.post(
        "/api/entrar", json={"identifier": "logavel", "password": "senhaforte123"}
    )
    assert por_usuario.status_code == 200

    por_email = cliente.post(
        "/api/entrar",
        json={"identifier": "logavel@teste.com", "password": "senhaforte123"},
    )
    assert por_email.status_code == 200


def test_senha_errada_nao_revela_se_a_conta_existe(cliente, fazer_usuario):
    fazer_usuario("existente")

    existe = cliente.post(
        "/api/entrar", json={"identifier": "existente", "password": "errada"}
    )
    nao_existe = cliente.post(
        "/api/entrar", json={"identifier": "fantasma", "password": "errada"}
    )
    assert existe.status_code == nao_existe.status_code == 401
    assert existe.json()["detail"] == nao_existe.json()["detail"]


def test_rota_protegida_sem_sessao(cliente):
    assert cliente.get("/api/eu").status_code == 401
    assert cliente.get("/api/minhas-salas").status_code == 401


def test_csrf_e_obrigatorio_nas_escritas(fazer_usuario):
    sessao = fazer_usuario("protegido")

    # Autenticado, mas sem o cabeçalho de segurança: a escrita é barrada.
    sem_token = sessao.c.patch("/api/perfil", json={"display_name": "Invasor"})
    assert sem_token.status_code == 403

    com_token_errado = sessao.c.patch(
        "/api/perfil", json={"display_name": "Invasor"}, headers={"X-CSRF-Token": "lixo"}
    )
    assert com_token_errado.status_code == 403

    # Com o token correto, passa.
    assert sessao.patch("/api/perfil", json={"display_name": "Legítimo"}).status_code == 200


def test_atualizar_perfil(fazer_usuario):
    sessao = fazer_usuario("perfilzinho")
    resposta = sessao.patch(
        "/api/perfil",
        json={
            "display_name": "Nome Novo",
            "tagline": "Frase nova",
            "accent_color": "#ff6b9d",
        },
    )
    assert resposta.status_code == 200
    assert resposta.json()["user"]["display_name"] == "Nome Novo"


def test_cor_invalida_no_perfil(fazer_usuario):
    sessao = fazer_usuario("corzinha")
    assert sessao.patch("/api/perfil", json={"accent_color": "azul"}).status_code == 422
