"""Triangle Agency — definição PROVISÓRIA da ficha.

=============================================================================
 ATENÇÃO — ESTE ARQUIVO FOI ESCRITO ANTES DO PDF DO LIVRO SER ANEXADO.
=============================================================================

A ESTRUTURA está pronta e funcionando: pool de d6 contando sucessos, seções,
trilhas, barras no token e rolagens rápidas. Os NOMES e NÚMEROS abaixo são
marcadores e precisam ser conferidos contra o livro.

CONFERIR NO PDF:
    [ ] Nome e quantidade exatos das Competências (aqui: 4, escala 0-6)
    [ ] Alvo do pool de d6 (aqui: sucesso em 4+) e regra de crítico/falha
    [ ] Nome e escala das trilhas de Realidade e Confiança
    [ ] Estrutura da Anomalia (manifestação, custo, cargas)
    [ ] Lista real de Divisões/Departamentos
    [ ] Regra de Comissões / promoção corporativa

COMO CORRIGIR: edite apenas este arquivo. A ficha, as barras do token, o chat
e a tela de criação de sala se readaptam sozinhos — nenhuma tela precisa mudar.
"""

from __future__ import annotations

from app.systems.base import (
    Field,
    ListColumn,
    Option,
    QuickRoll,
    QuickRollDef,
    RpgSystem,
    Section,
    SystemOption,
    TokenBar,
)

COMPETENCIAS = [
    ("burocracia", "Burocracia"),
    ("investigacao", "Investigação"),
    ("fisico", "Físico"),
    ("intuicao", "Intuição"),
]


triangle_agency = RpgSystem(
    id="triangle-agency",
    name="Triangle Agency",
    short_name="TA",
    tagline="Agentes corporativos gerenciando anomalias da realidade.",
    description=(
        "Você é um Agente da Triangle Agency. A realidade tem defeitos, e o seu "
        "trabalho é arquivá-los antes que o prazo vire um incidente. "
        "Traga o relatório preenchido."
    ),
    color="#ff6b9d",
    publisher="Haunted Table Games",
    status="draft",
    draft_note=(
        "Ficha provisória. A estrutura funciona, mas os nomes de Competências, "
        "trilhas e Divisões ainda precisam ser conferidos com o livro. "
        "Edite app/systems/triangle_agency.py."
    ),
    default_roll="3d6>=4",
    room_options=[
        SystemOption(
            key="dificuldade_padrao",
            label="Alvo padrão do dado",
            hint="Valor mínimo em cada d6 para contar como sucesso.",
            type="select",
            default="4",
            options=[
                Option("3", "3+ (mesa generosa)"),
                Option("4", "4+ (padrão)"),
                Option("5", "5+ (burocracia hostil)"),
            ],
        ),
        SystemOption(
            key="anomalias_visiveis",
            label="Jogadores veem as Anomalias uns dos outros",
            type="boolean",
            default=False,
        ),
        SystemOption(
            key="usar_comissoes",
            label="Usar o sistema de Comissões",
            hint="Liga a seção de progressão corporativa na ficha.",
            type="boolean",
            default=True,
        ),
        SystemOption(
            key="tamanho_equipe",
            label="Tamanho da equipe",
            type="number",
            default=4,
        ),
    ],
    defaults={
        "identidade": {
            "nome_agente": "",
            "codinome": "",
            "divisao": "campo",
            "pronomes": "",
            "aparencia": "",
        },
        "competencias": {key: 2 for key, _ in COMPETENCIAS},
        "realidade": {"atual": 6, "max": 6},
        "confianca": {"atual": 3, "max": 6},
        "anomalia": {
            "nome": "",
            "descricao": "",
            "manifestacao": "",
            "consequencia": "",
            "cargas": 3,
        },
        "comissoes": {"nivel": 1, "pontos": 0},
        "equipamento": [],
        "contatos": [],
        "notas": "",
        "notas_mestre": "",
    },
    sections=[
        Section(
            id="identidade",
            title="Registro do Agente",
            description="Preencha em letra de forma. A Agência não aceita rasuras.",
            columns=2,
            fields=[
                Field(key="identidade.nome_agente", label="Nome do Agente", type="text", span=2),
                Field(key="identidade.codinome", label="Codinome", type="text"),
                Field(key="identidade.pronomes", label="Pronomes", type="text"),
                Field(
                    key="identidade.divisao",
                    label="Divisão",
                    type="select",
                    options=[
                        Option("campo", "Operações de Campo"),
                        Option("arquivo", "Arquivo e Documentação"),
                        Option("contencao", "Contenção"),
                        Option("analise", "Análise de Padrões"),
                        Option("relacoes", "Relações Públicas"),
                    ],
                ),
                Field(
                    key="identidade.aparencia",
                    label="Aparência",
                    type="textarea",
                    span="full",
                    placeholder="Como os civis descrevem você no depoimento.",
                ),
            ],
        ),
        Section(
            id="competencias",
            title="Competências",
            description=(
                "Role um pool de d6 igual à competência. "
                "Cada dado no alvo da mesa conta como um sucesso."
            ),
            columns=2,
            fields=[
                Field(
                    key=f"competencias.{key}",
                    label=label,
                    type="dots",
                    min=0,
                    max=6,
                    roll=QuickRollDef(formula=f"{{{{competencias.{key}}}}}d6>=4", label=label),
                )
                for key, label in COMPETENCIAS
            ],
        ),
        Section(
            id="trilhas",
            title="Trilhas",
            columns=2,
            fields=[
                Field(key="realidade", label="Realidade", type="resource", max=12),
                Field(key="confianca", label="Confiança da Agência", type="resource", max=12),
            ],
        ),
        Section(
            id="anomalia",
            title="Anomalia",
            description="O defeito que você carrega. Não é um poder. É um passivo.",
            columns=2,
            fields=[
                Field(key="anomalia.nome", label="Designação", type="text", span=2),
                Field(key="anomalia.descricao", label="O que ela faz", type="textarea", span="full"),
                Field(
                    key="anomalia.manifestacao",
                    label="Como se manifesta",
                    type="textarea",
                    span="full",
                ),
                Field(
                    key="anomalia.consequencia",
                    label="Custo ao usar",
                    type="textarea",
                    span="full",
                ),
                Field(
                    key="anomalia.cargas",
                    label="Cargas",
                    type="dots",
                    min=0,
                    max=6,
                    roll=QuickRollDef(formula="{{anomalia.cargas}}d6>=4", label="Anomalia"),
                ),
            ],
        ),
        Section(
            id="comissoes",
            title="Comissões",
            columns=2,
            fields=[
                Field(key="comissoes.nivel", label="Nível corporativo", type="number", min=1, max=10),
                Field(key="comissoes.pontos", label="Pontos de comissão", type="number", min=0),
            ],
        ),
        Section(
            id="recursos",
            title="Equipamento e Contatos",
            columns=1,
            fields=[
                Field(
                    key="equipamento",
                    label="Equipamento autorizado",
                    type="list",
                    span="full",
                    columns=[
                        ListColumn("nome", "Item", "text"),
                        ListColumn("qtd", "Qtd", "number"),
                        ListColumn("notas", "Observações", "text"),
                    ],
                ),
                Field(
                    key="contatos",
                    label="Contatos",
                    type="list",
                    span="full",
                    columns=[
                        ListColumn("nome", "Nome", "text"),
                        ListColumn("relacao", "Relação", "text"),
                        ListColumn("queimado", "Queimado", "checkbox"),
                    ],
                ),
            ],
        ),
        Section(
            id="notas",
            title="Anotações",
            columns=1,
            fields=[
                Field(key="notas", label="Notas do agente", type="textarea", span="full"),
                Field(
                    key="notas_mestre",
                    label="Notas da Agência (somente mestre)",
                    type="textarea",
                    span="full",
                    gm_only=True,
                ),
            ],
        ),
    ],
    token_bars=[
        TokenBar(label="Realidade", path="realidade", color="#5ce1e6"),
        TokenBar(label="Confiança", path="confianca", color="#ff6b9d"),
    ],
    quick_rolls=[
        QuickRoll(
            id=key,
            label=label,
            formula=f"{{{{competencias.{key}}}}}d6>=4",
        )
        for key, label in COMPETENCIAS
    ]
    + [
        QuickRoll(
            id="anomalia",
            label="Usar Anomalia",
            formula="{{anomalia.cargas}}d6>=4",
            description="Gasta uma carga. A Agência vai perguntar sobre isso depois.",
        )
    ],
)
