"""Amizades, conversas e convites por mensagem."""

from __future__ import annotations


def test_pedido_e_aceite_de_amizade(fazer_usuario):
    ana = fazer_usuario("ana")
    beto = fazer_usuario("beto")

    assert ana.post("/api/amigos", json={"username": "beto"}).status_code == 200
    assert ana.get("/api/amigos").json()["outgoing"][0]["user"]["username"] == "beto"

    pendente = beto.get("/api/amigos").json()["incoming"][0]
    assert beto.post(f"/api/amigos/{pendente['id']}/aceitar").status_code == 200

    assert len(ana.get("/api/amigos").json()["friends"]) == 1
    assert len(beto.get("/api/amigos").json()["friends"]) == 1


def test_pedido_cruzado_vira_amizade_na_hora(fazer_usuario):
    ana = fazer_usuario("ana")
    beto = fazer_usuario("beto")

    ana.post("/api/amigos", json={"username": "beto"})
    resposta = beto.post("/api/amigos", json={"username": "ana"})
    assert resposta.json()["auto_accepted"] is True
    assert len(ana.get("/api/amigos").json()["friends"]) == 1


def test_nao_da_para_ser_amigo_de_si_mesmo(fazer_usuario):
    ana = fazer_usuario("ana")
    assert ana.post("/api/amigos", json={"username": "ana"}).status_code == 400


def test_pedido_duplicado_e_recusado(fazer_usuario):
    ana = fazer_usuario("ana")
    fazer_usuario("beto")
    ana.post("/api/amigos", json={"username": "beto"})
    assert ana.post("/api/amigos", json={"username": "beto"}).status_code == 409


def test_usuario_inexistente(fazer_usuario):
    ana = fazer_usuario("ana")
    assert ana.post("/api/amigos", json={"username": "ninguem"}).status_code == 404


def test_so_o_destinatario_aceita(fazer_usuario):
    ana = fazer_usuario("ana")
    fazer_usuario("beto")
    pedido = ana.post("/api/amigos", json={"username": "beto"}).json()
    assert ana.post(f"/api/amigos/{pedido['id']}/aceitar").status_code == 403


def test_busca_nao_retorna_a_si_mesmo(fazer_usuario):
    ana = fazer_usuario("ana")
    fazer_usuario("anabela")
    encontrados = [u["username"] for u in ana.get("/api/usuarios/busca?q=ana").json()["users"]]
    assert "anabela" in encontrados
    assert "ana" not in encontrados


def test_busca_exige_dois_caracteres(fazer_usuario):
    ana = fazer_usuario("ana")
    assert ana.get("/api/usuarios/busca?q=a").json()["users"] == []


def test_conversa_direta_e_reaproveitada(fazer_usuario):
    ana = fazer_usuario("ana")
    fazer_usuario("beto")

    primeira = ana.post("/api/conversas?username=beto").json()["id"]
    segunda = ana.post("/api/conversas?username=beto").json()["id"]
    assert primeira == segunda


def test_mensagem_chega_para_os_dois_lados(fazer_usuario):
    ana = fazer_usuario("ana")
    beto = fazer_usuario("beto")
    conversa = ana.post("/api/conversas?username=beto").json()["id"]

    ana.post(f"/api/conversas/{conversa}/mensagens", json={"body": "oi, joga hoje?"})
    recebidas = beto.get(f"/api/conversas/{conversa}/mensagens").json()["messages"]
    assert recebidas[-1]["body"] == "oi, joga hoje?"


def test_estranho_nao_le_conversa_alheia(fazer_usuario):
    ana = fazer_usuario("ana")
    fazer_usuario("beto")
    xereta = fazer_usuario("xereta")
    conversa = ana.post("/api/conversas?username=beto").json()["id"]

    assert xereta.get(f"/api/conversas/{conversa}/mensagens").status_code == 403
    assert xereta.post(
        f"/api/conversas/{conversa}/mensagens", json={"body": "intruso"}
    ).status_code == 403


def test_convite_de_mesa_pelo_chat(fazer_usuario):
    ana = fazer_usuario("ana")
    beto = fazer_usuario("beto")
    sala = ana.post("/api/salas", json={"name": "Mesa da Ana", "system_id": "generico"}).json()
    conversa = ana.post("/api/conversas?username=beto").json()["id"]

    resposta = ana.post(
        f"/api/conversas/{conversa}/mensagens",
        json={"body": "bora?", "kind": "ROOM_INVITE", "room_id": sala["id"]},
    )
    assert resposta.status_code == 200
    convite = resposta.json()["message"]
    assert convite["kind"] == "ROOM_INVITE"
    assert convite["payload"]["slug"] == sala["slug"]

    # O convite é suficiente para entrar.
    entrada = beto.post(
        "/api/salas/entrar", json={"invite_code": convite["payload"]["invite_code"]}
    )
    assert entrada.status_code == 200


def test_nao_da_para_convidar_para_mesa_alheia(fazer_usuario):
    ana = fazer_usuario("ana")
    fazer_usuario("beto")
    forasteira = fazer_usuario("forasteira")
    sala = ana.post("/api/salas", json={"name": "Mesa da Ana", "system_id": "generico"}).json()

    conversa = forasteira.post("/api/conversas?username=beto").json()["id"]
    resposta = forasteira.post(
        f"/api/conversas/{conversa}/mensagens",
        json={"body": "entra aí", "kind": "ROOM_INVITE", "room_id": sala["id"]},
    )
    assert resposta.status_code == 403


def test_convidar_pela_mesa_manda_mensagem_direta(fazer_usuario):
    ana = fazer_usuario("ana")
    beto = fazer_usuario("beto")
    sala = ana.post("/api/salas", json={"name": "Mesa da Ana", "system_id": "generico"}).json()

    assert ana.post(
        f"/api/salas/{sala['slug']}/convidar", json={"username": "beto"}
    ).status_code == 200

    conversas = beto.get("/api/conversas").json()["conversations"]
    assert conversas[0]["last_message"]["kind"] == "ROOM_INVITE"
