#!/usr/bin/env python
"""Popula o banco com uma mesa de demonstração.

    python seed.py            # cria os dados (não duplica se já existirem)
    python seed.py --reset    # apaga o banco e recria do zero

Contas criadas (senha de todas: ``storybook123``):
    halima@exemplo.com   @halima   — mestra
    ruan@exemplo.com     @ruan     — jogador
    dani@exemplo.com     @dani     — jogadora
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine, init_db
from app.models import (
    Character,
    CharacterVisibility,
    Friendship,
    FriendshipStatus,
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
)
from app.security import hash_password
from app.services import get_or_create_conversation, unique_slug
from app.systems import get_system, initial_sheet_data, set_path

SENHA = "storybook123"


def criar_usuario(db, *, email, username, nome, tagline, bio, cor, pronomes=None):
    existente = db.scalar(select(User).where(User.username == username))
    if existente:
        return existente
    user = User(
        email=email,
        username=username,
        display_name=nome,
        password_hash=hash_password(SENHA),
        tagline=tagline,
        bio=bio,
        accent_color=cor,
        pronouns=pronomes,
    )
    db.add(user)
    db.flush()
    return user


def semear() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.scalar(select(Room).where(Room.slug.like("incidente-no-arquivo%"))):
            print("Os dados de demonstração já existem. Use --reset para recriar.")
            return

        # ---------------- Pessoas ----------------
        halima = criar_usuario(
            db,
            email="halima@exemplo.com",
            username="halima",
            nome="Halima Bastos",
            tagline="Mestra de mesas longas e prazos curtos.",
            bio=(
                "Mestro desde 2016, com queda por investigação e horror burocrático.\n"
                "Rodo mesas às terças, 20h. Aceito jogadores novos sem drama."
            ),
            cor="#ff6b9d",
            pronomes="ela/dela",
        )
        ruan = criar_usuario(
            db,
            email="ruan@exemplo.com",
            username="ruan",
            nome="Ruan Teixeira",
            tagline="Anota tudo. Nunca relê.",
            bio="Jogo desde a facul. Prefiro personagens que falam demais.",
            cor="#5ce1e6",
            pronomes="ele/dele",
        )
        dani = criar_usuario(
            db,
            email="dani@exemplo.com",
            username="dani",
            nome="Dani Moraes",
            tagline="Especialista em resolver o problema errado.",
            bio="Vim do tabletop físico. Ainda desenho os mapas no papel antes.",
            cor="#7c5cff",
        )
        db.flush()

        halima.showcase = [
            {
                "id": "b1",
                "type": "links",
                "title": "Onde me achar",
                "items": [
                    {"label": "Meu blog de mesas", "value": "https://exemplo.com/halima"},
                ],
            },
            {
                "id": "b2",
                "type": "text",
                "title": "Disponibilidade",
                "items": [
                    {"label": "Terças", "value": "20h — 23h"},
                    {"label": "Sábados", "value": "sob combinação"},
                ],
            },
        ]

        # ---------------- Amizades ----------------
        for outro in (ruan, dani):
            db.add(
                Friendship(
                    requester_id=halima.id,
                    addressee_id=outro.id,
                    status=FriendshipStatus.ACCEPTED,
                )
            )
        db.add(
            Friendship(
                requester_id=ruan.id, addressee_id=dani.id, status=FriendshipStatus.PENDING
            )
        )
        db.flush()

        # ---------------- Mesa ----------------
        sistema = get_system("triangle-agency")
        config = {opcao.key: opcao.default for opcao in sistema.room_options}

        sala = Room(
            name="Incidente no Arquivo Morto",
            description=(
                "Três agentes. Um arquivo que não deveria existir. Um prazo que "
                "já venceu.\n\nMesa de demonstração do StoryBook."
            ),
            system_id=sistema.id,
            system_config=config,
            owner_id=halima.id,
            slug=unique_slug(db, "Incidente no Arquivo Morto"),
            is_public=True,
            max_players=4,
        )
        sala.members = [
            RoomMember(user_id=halima.id, role=RoomRole.GM, color="#ff6b9d"),
            RoomMember(user_id=ruan.id, role=RoomRole.PLAYER, color="#5ce1e6"),
            RoomMember(user_id=dani.id, role=RoomRole.PLAYER, color="#7c5cff"),
        ]
        db.add(sala)
        db.flush()

        # ---------------- Cenas ----------------
        arquivo = Scene(
            room_id=sala.id,
            name="Subsolo do Arquivo",
            grid_type=GridType.SQUARE,
            grid_size=64,
            width=30,
            height=22,
            is_active=True,
            order=0,
            background_color="#0a0d1a",
            units_per_cell=1.5,
            unit_name="m",
        )
        escritorio = Scene(
            room_id=sala.id,
            name="Escritório Regional",
            grid_type=GridType.SQUARE,
            grid_size=64,
            width=24,
            height=18,
            order=1,
            background_color="#0d1122",
        )
        db.add_all([arquivo, escritorio])
        db.flush()

        # ---------------- Fichas ----------------
        def nova_ficha(dono, nome, ajustes, *, npc=False, visibilidade=CharacterVisibility.PARTY):
            dados = initial_sheet_data(sistema.id, config)
            for caminho, valor in ajustes.items():
                set_path(dados, caminho, valor)
            ficha = Character(
                room_id=sala.id,
                owner_id=dono.id,
                system_id=sistema.id,
                name=nome,
                is_npc=npc,
                visibility=visibilidade,
                data=dados,
            )
            db.add(ficha)
            db.flush()
            return ficha

        # As 9 GQs iniciais ficam em 3 Qualidades, como manda o livro.
        ficha_ruan = nova_ficha(
            ruan,
            "Agente Teixeira",
            {
                "identidade.nome": "Ruan Teixeira",
                "identidade.pronomes": "ele/dele",
                "identidade.aparencia": "Camisa amassada, crachá sempre virado do lado errado.",
                "arc.anomalia": "catalogo",
                "arc.realidade": "endividado",
                "arc.competencia": "p&d",
                "arc.gatilho_realidade": "Quando alguém menciona uma dívida perto dele.",
                "arc.alivio_burnout": "Organizar alguma coisa que ninguém pediu para organizar.",
                "arc.diretriz_primaria": "Documentar antes de agir.",
                "arc.comportamentos": "Catalogar, medir, conferir duas vezes.",
                "qualidades.atencao": {"atual": 4, "max": 4},
                "qualidades.profissionalismo": {"atual": 2, "max": 3},
                "qualidades.persistencia": {"atual": 2, "max": 2},
                "habilidades": [
                    {
                        "nome": "Índice Vivo",
                        "sucesso": "Você sabe onde está o objeto que procura.",
                        "fracasso": "Você sabe onde ele estava. Alguém moveu.",
                    },
                    {
                        "nome": "Nota de Rodapé",
                        "sucesso": "Um documento ganha uma linha verdadeira que ninguém escreveu.",
                        "fracasso": "A linha aparece. É sobre você.",
                    },
                ],
                "relacionamentos": [
                    {"nome": "Sra. Antunes", "relacao": "Credora", "estado": "Paciente, por enquanto."},
                    {"nome": "Léo", "relacao": "Irmão mais novo", "estado": "Não sabe do emprego."},
                ],
                "estado.meritos": 2,
                "notas": "Perguntar à Halima sobre a caixa 14-B.",
            },
        )

        nova_ficha(
            dani,
            "Agente Moraes",
            {
                "identidade.nome": "Dani Moraes",
                "identidade.pronomes": "ela/dela",
                "arc.anomalia": "emaranhado",
                "arc.realidade": "sobrecarregado",
                "arc.competencia": "coveiro",
                "arc.gatilho_realidade": "Quando precisa escolher entre duas obrigações.",
                "arc.alivio_burnout": "Terminar alguma coisa, qualquer coisa, até o fim.",
                "qualidades.dinamismo": {"atual": 4, "max": 4},
                "qualidades.sutileza": {"atual": 3, "max": 3},
                "qualidades.iniciativa": {"atual": 1, "max": 2},
                "habilidades": [
                    {
                        "nome": "Porta Extra",
                        "sucesso": "O corredor ganha uma saída que não estava na planta.",
                        "fracasso": "Ganha. Alguém já saiu por ela.",
                    },
                ],
                "estado.burnout": 1,
            },
        )

        npc = nova_ficha(
            halima,
            "Supervisor Krell",
            {
                "identidade.nome": "Krell",
                "arc.competencia": "rp",
                "qualidades.duplicidade": {"atual": 6, "max": 6},
                "notas_gm": "Krell já morreu. Ninguém no escritório notou ainda.",
            },
            npc=True,
            visibilidade=CharacterVisibility.PRIVATE,
        )

        # ---------------- Tokens ----------------
        db.add_all(
            [
                Token(
                    scene_id=arquivo.id, character_id=ficha_ruan.id, owner_id=ruan.id,
                    name="Teixeira", color="#5ce1e6",
                    x=384, y=448, width=64, height=64, order=0,
                ),
                Token(
                    scene_id=arquivo.id, owner_id=dani.id,
                    name="Moraes", color="#7c5cff",
                    x=512, y=448, width=64, height=64, order=1,
                ),
                Token(
                    scene_id=arquivo.id, character_id=npc.id, owner_id=halima.id,
                    name="Krell", color="#ffc46b",
                    x=896, y=320, width=64, height=64, order=2,
                    layer=TokenLayer.GM_ONLY, is_visible=False,
                ),
            ]
        )

        # ---------------- Conversa ----------------
        conversa = get_or_create_conversation(db, halima.id, ruan.id)
        from app.models import DirectMessage

        db.add_all(
            [
                DirectMessage(
                    conversation_id=conversa.id, author_id=halima.id,
                    body="Terça às 20h fecha pra você?",
                ),
                DirectMessage(
                    conversation_id=conversa.id, author_id=ruan.id,
                    body="Fecha. Já preenchi a ficha inteira, inclusive a parte que ninguém lê.",
                ),
                DirectMessage(
                    conversation_id=conversa.id, author_id=halima.id,
                    kind=MessageKind.ROOM_INVITE,
                    body=f'Halima Bastos te convidou para a mesa "{sala.name}".',
                    payload={
                        "room_id": sala.id,
                        "room_name": sala.name,
                        "slug": sala.slug,
                        "invite_code": sala.invite_code,
                    },
                ),
            ]
        )

        # ---------------- Chat da mesa ----------------
        db.add_all(
            [
                RoomMessage(
                    room_id=sala.id, kind=MessageKind.SYSTEM,
                    body=f"Mesa aberta com o sistema {sistema.name}. Boa sessão.",
                ),
                RoomMessage(
                    room_id=sala.id, author_id=halima.id,
                    body="A luz do subsolo funciona em dois dos seis corredores. Escolham.",
                ),
                RoomMessage(
                    room_id=sala.id, author_id=ruan.id,
                    body="Vou conferir o índice antes. Alguém traz a lanterna.",
                ),
            ]
        )

        db.commit()

        print("\n  Dados de demonstração criados.\n")
        print(f"  Mesa:    {sala.name}")
        print(f"  Endereço: /mesa/{sala.slug}")
        print(f"  Convite:  {sala.invite_code}\n")
        print("  Contas (senha: storybook123)")
        print("    @halima  — mestra")
        print("    @ruan    — jogador")
        print("    @dani    — jogadora\n")

    finally:
        db.close()


def resetar() -> None:
    Base.metadata.drop_all(bind=engine)

    if settings.is_sqlite:
        # Fecha as conexões ANTES de apagar o arquivo. No Linux, um arquivo
        # apagado continua vivo enquanto alguém o mantém aberto — sem este
        # dispose(), as tabelas seriam recriadas no arquivo fantasma e o
        # storybook.db no disco ficaria vazio.
        engine.dispose()

        caminho = settings.database_url.split("///")[-1]
        for sufixo in ("", "-wal", "-shm"):
            arquivo = Path(caminho + sufixo)
            if arquivo.exists():
                arquivo.unlink()

    print("Banco apagado.")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        resetar()
    semear()
