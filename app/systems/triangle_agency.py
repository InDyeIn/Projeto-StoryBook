"""Triangle Agency — ficha baseada no livro (1ª edição, Haunted Table).

Implementa as MECÂNICAS do sistema; os textos descritivos de cada peça de ARC
continuam no livro, que cada jogador consulta para preencher a ficha.

Resumo do que está implementado
-------------------------------
* Jogada-padrão: sempre **6d4**, conta quantos dados saem **3**.
  - pelo menos um 3 → sucesso;
  - nenhum 3 → fracasso;
  - cada dado que NÃO é 3 gera 1 de **Caos** para a reserva do GM;
  - exatamente três 3s (antes de ajustes) → **Triscendência**: sucesso sem Caos
    e um efeito extra à escolha.
* **Qualidades** (9) com **Garantias de Qualidade** gastáveis: cada GQ gasta
  ajusta a face de um dado. O Agente começa com 9 GQs distribuídas em 3
  Qualidades.
* **Burnout**: usar uma Qualidade sem GQ restante queima um 3 e soma 1 de Caos.
* **ARC**: Anomalia (3 Habilidades Anômalas) + Realidade (Gatilho e Alívio de
  Burnout, mais 3 Relacionamentos) + Competência (Diretriz Primária,
  Comportamentos Sancionados e Requisição Inicial).
* **Ferimento** como escala de gravidade — 1 já é o bastante para matar um
  humano comum; não é barra de vida.

O que ficou de fora de propósito
--------------------------------
A reserva de **Caos** é do GM e vale para a mesa inteira, não para uma ficha.
A rolagem mostra quanto Caos gerou; quem anota o total é o GM. Se virar campo
de mesa no futuro, é aqui que a contagem já sai pronta.
"""

from __future__ import annotations

from app.systems.base import (
    Field,
    ListColumn,
    Option,
    PoolRules,
    QuickRoll,
    RpgSystem,
    Section,
    SystemOption,
)

# As nove Qualidades, com um lembrete curto do que cada uma cobre.
QUALIDADES: list[tuple[str, str, str]] = [
    ("atencao", "Atenção", "Reparar em detalhes, entender o complicado, achar o que esconderam."),
    ("duplicidade", "Duplicidade", "Mentir, convencer sem acreditar, apoiar por fora discordando por dentro."),
    ("dinamismo", "Dinamismo", "Impor-se, dominar, usar a força para fazer valer o seu ponto."),
    ("empatia", "Empatia", "Conectar-se, demonstrar cuidado, enxergar o ponto fraco de alguém."),
    ("iniciativa", "Iniciativa", "Antecipar-se, agir rápido, resolver antes de virar problema."),
    ("persistencia", "Persistência", "Não ceder, insistir, incomodar até obter resposta."),
    ("presenca", "Presença", "Destacar-se, liderar, inspirar e intimidar."),
    ("profissionalismo", "Profissionalismo", "Manter a calma sob pressão e resistir a distrações."),
    ("sutileza", "Sutileza", "Agir em silêncio, sem chamar atenção, com precisão."),
]

ANOMALIAS = [
    "Sussurro", "Catálogo", "Drenagem", "Cronometria", "Crescimento",
    "Arma", "Sonho", "Emaranhado", "Ausência",
]

REALIDADES = [
    "Cuidador", "Sobrecarregado", "Perseguido", "Estrela", "Endividado",
    "Recém-Nascido", "Romântico", "Mandachuva", "Criatura",
]

COMPETENCIAS = [
    "RP", "P&D", "Barista", "CEO", "Estagiário",
    "Coveiro", "Recepção", "Atendimento", "Palhaço",
]


def _opcoes(nomes: list[str]) -> list[Option]:
    opcoes = [Option("", "— escolher —")]
    opcoes += [Option(n.lower().replace(" ", "-"), n) for n in nomes]
    return opcoes


triangle_agency = RpgSystem(
    id="triangle-agency",
    name="Triangle Agency",
    short_name="TA",
    tagline="Bata o ponto. Salve o mundo.",
    description=(
        "Você é um Agente de Campo da Agência Triangular, com uma Anomalia "
        "alojada no corpo e um cargo corporativo a cumprir. Seis dados de quatro "
        "faces, e só o 3 interessa. Todo o resto vira Caos."
    ),
    color="#ff6b9d",
    publisher="Haunted Table Games",
    status="stable",

    # Jogada-padrão do sistema: 6d4 contando os 3s.
    default_roll="6d4=3",
    pool_rules=PoolRules(
        resource_per_failure="Caos",
        highlight_at=3,
        highlight_name="Triscendência",
        highlight_clears_resource=True,
        success_word="3",
        failure_note="Sem nenhum 3: malsucedido.",
    ),

    room_options=[
        SystemOption(
            key="caos_inicial",
            label="Caos inicial na reserva",
            hint="O GM anota a reserva de Caos da mesa; isto é só o ponto de partida.",
            type="number",
            default=0,
        ),
        SystemOption(
            key="gqs_iniciais",
            label="GQs iniciais por Agente",
            hint="O padrão do livro são 9, distribuídas em 3 Qualidades.",
            type="number",
            default=9,
        ),
        SystemOption(
            key="anomalias_visiveis",
            label="Agentes veem as Habilidades Anômalas uns dos outros",
            type="boolean",
            default=True,
        ),
    ],

    defaults={
        "identidade": {
            "nome": "",
            "pronomes": "",
            "aparencia": "",
            "questionario": "",
        },
        "arc": {
            "anomalia": "",
            "realidade": "",
            "competencia": "",
            "gatilho_realidade": "",
            "alivio_burnout": "",
            "diretriz_primaria": "",
            "comportamentos": "",
        },
        "habilidades": [],
        "relacionamentos": [],
        "qualidades": {chave: {"atual": 0, "max": 0} for chave, _, _ in QUALIDADES},
        "estado": {"burnout": 0, "ferimento": 0, "meritos": 0, "demeritos": 0},
        "requisicoes": [],
        "pontas_soltas": "",
        "notas": "",
        "notas_gm": "",
    },

    sections=[
        # ------------------------------------------------------------------
        Section(
            id="identidade",
            title="Registro do Agente",
            description="Preencha em letra de forma. A Agência não aceita rasuras.",
            columns=2,
            fields=[
                Field(key="identidade.nome", label="Nome do Agente", type="text", span=2),
                Field(key="identidade.pronomes", label="Pronomes", type="text"),
                Field(
                    key="estado.ferimento",
                    label="Ferimento",
                    type="number",
                    min=0,
                    max=9,
                    hint="1 já mata um humano comum. 2+ deixa marca do Anômalo.",
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
        # ------------------------------------------------------------------
        Section(
            id="arc",
            title="ARC",
            description="Anomalia, Realidade e Competência — as três peças do seu Agente.",
            columns=3,
            fields=[
                Field(
                    key="arc.anomalia",
                    label="A — Anomalia",
                    type="select",
                    options=_opcoes(ANOMALIAS),
                    hint="O que se alojou em você.",
                ),
                Field(
                    key="arc.realidade",
                    label="R — Realidade",
                    type="select",
                    options=_opcoes(REALIDADES),
                    hint="Sua vida fora do expediente.",
                ),
                Field(
                    key="arc.competencia",
                    label="C — Competência",
                    type="select",
                    options=_opcoes(COMPETENCIAS),
                    hint="Seu cargo na Agência.",
                ),
                Field(
                    key="arc.gatilho_realidade",
                    label="Gatilho de Realidade",
                    type="textarea",
                    span="full",
                ),
                Field(
                    key="arc.alivio_burnout",
                    label="Alívio de Burnout",
                    type="textarea",
                    span="full",
                ),
                Field(
                    key="arc.diretriz_primaria",
                    label="Diretriz Primária",
                    type="textarea",
                    span="full",
                ),
                Field(
                    key="arc.comportamentos",
                    label="Comportamentos Sancionados",
                    type="textarea",
                    span="full",
                ),
            ],
        ),
        # ------------------------------------------------------------------
        Section(
            id="habilidades",
            title="Habilidades Anômalas",
            description="As três que a sua Anomalia concede. Usá-las exige a jogada de 6d4.",
            columns=1,
            fields=[
                Field(
                    key="habilidades",
                    label="Habilidades",
                    type="list",
                    span="full",
                    columns=[
                        ListColumn("nome", "Habilidade", "text"),
                        ListColumn("sucesso", "Sendo bem-sucedido", "text"),
                        ListColumn("fracasso", "Sendo malsucedido", "text"),
                    ],
                ),
            ],
        ),
        # ------------------------------------------------------------------
        Section(
            id="qualidades",
            title="Qualidades e Garantias de Qualidade",
            description=(
                "Cada GQ gasta ajusta a face de um dado. Começa com 9 GQs "
                "distribuídas em 3 Qualidades. Usar uma Qualidade sem GQ causa Burnout."
            ),
            columns=3,
            fields=[
                Field(
                    key=f"qualidades.{chave}",
                    label=rotulo,
                    type="resource",
                    max=9,
                    hint=dica,
                )
                for chave, rotulo, dica in QUALIDADES
            ],
        ),
        # ------------------------------------------------------------------
        Section(
            id="estado",
            title="Situação funcional",
            columns=3,
            fields=[
                Field(
                    key="estado.burnout",
                    label="Burnout",
                    type="number",
                    min=0,
                    max=9,
                    hint="Cada Burnout queima um 3 e soma 1 de Caos.",
                ),
                Field(key="estado.meritos", label="Méritos", type="number", min=0),
                Field(key="estado.demeritos", label="Deméritos", type="number", min=0),
            ],
        ),
        # ------------------------------------------------------------------
        Section(
            id="relacionamentos",
            title="Relacionamentos",
            description="Três pessoas da sua Realidade, interpretadas pelo GM ou por outro Agente.",
            columns=1,
            fields=[
                Field(
                    key="relacionamentos",
                    label="Relacionamentos",
                    type="list",
                    span="full",
                    columns=[
                        ListColumn("nome", "Nome", "text"),
                        ListColumn("relacao", "Quem é", "text"),
                        ListColumn("estado", "Como vai", "text"),
                    ],
                ),
            ],
        ),
        # ------------------------------------------------------------------
        Section(
            id="requisicoes",
            title="Requisições e Benefícios",
            columns=1,
            fields=[
                Field(
                    key="requisicoes",
                    label="Requisições",
                    type="list",
                    span="full",
                    columns=[
                        ListColumn("item", "Item", "text"),
                        ListColumn("custo", "Custo", "text"),
                        ListColumn("usado", "Usado", "checkbox"),
                    ],
                ),
            ],
        ),
        # ------------------------------------------------------------------
        Section(
            id="notas",
            title="Anotações",
            columns=1,
            fields=[
                Field(
                    key="pontas_soltas",
                    label="Pontas Soltas",
                    type="textarea",
                    span="full",
                    hint="O que ficou para trás e pode voltar a aparecer.",
                ),
                Field(key="notas", label="Notas do Agente", type="textarea", span="full"),
                Field(
                    key="notas_gm",
                    label="Arquivo da Agência (somente GM)",
                    type="textarea",
                    span="full",
                    gm_only=True,
                ),
            ],
        ),
    ],

    # O sistema não tem pontos de vida: Ferimento é escala de gravidade, e as
    # GQs variam de Agente para Agente. Nenhuma barra faz sentido sob o token.
    token_bars=[],

    quick_rolls=[
        QuickRoll(
            id="agencia",
            label="Jogada da Agência",
            formula="6d4=3",
            description="Seis dados de quatro faces. Só o 3 conta. O resto vira Caos.",
        ),
    ],
)
