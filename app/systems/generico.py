"""Sistema genérico — exemplo de como plugar um sistema novo.

Serve também de refúgio para mesas que ainda não decidiram as regras: seis
atributos, vida, defesa e espaço livre para anotar.
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

ATRIBUTOS = [
    ("forca", "Força"),
    ("destreza", "Destreza"),
    ("constituicao", "Constituição"),
    ("inteligencia", "Inteligência"),
    ("sabedoria", "Sabedoria"),
    ("carisma", "Carisma"),
]


generico = RpgSystem(
    id="generico",
    name="Sistema Genérico",
    short_name="GEN",
    tagline="Uma ficha simples de atributos e d20 para qualquer história.",
    description=(
        "Seis atributos, pontos de vida e espaço livre para anotar. Bom para "
        "one-shots e para testar a mesa antes de escolher um sistema definitivo."
    ),
    color="#7c5cff",
    status="stable",
    default_roll="d20",
    room_options=[
        SystemOption(
            key="dado_base",
            label="Dado base",
            type="select",
            default="d20",
            options=[Option("d20", "d20"), Option("2d6", "2d6"), Option("d100", "d100")],
        ),
        SystemOption(key="vida_inicial", label="Vida inicial", type="number", default=10),
        SystemOption(
            key="dificuldade_padrao",
            label="Alvo padrão das pools",
            hint=(
                "Vale para fórmulas que contam sucessos (ex.: 5d6>=4). "
                "Deixe em 4 se a mesa não usar pools."
            ),
            type="select",
            default="4",
            options=[
                Option("3", "3+ (generosa)"),
                Option("4", "4+ (padrão)"),
                Option("5", "5+ (dura)"),
            ],
        ),
    ],
    defaults={
        "conceito": "",
        "atributos": {key: 10 for key, _ in ATRIBUTOS},
        "vida": {"atual": 10, "max": 10},
        "defesa": 10,
        "inventario": [],
        "notas": "",
    },
    sections=[
        Section(
            id="basico",
            title="Personagem",
            columns=2,
            fields=[
                Field(key="conceito", label="Conceito", type="text", span=2),
                Field(key="vida", label="Vida", type="resource", max=999),
                Field(key="defesa", label="Defesa", type="number", min=0),
            ],
        ),
        Section(
            id="atributos",
            title="Atributos",
            columns=3,
            fields=[
                Field(
                    key=f"atributos.{key}",
                    label=label,
                    type="number",
                    min=1,
                    max=30,
                    roll=QuickRollDef(formula=f"d20+{{{{atributos.{key}}}}}", label=label),
                )
                for key, label in ATRIBUTOS
            ],
        ),
        Section(
            id="inventario",
            title="Inventário",
            columns=1,
            fields=[
                Field(
                    key="inventario",
                    label="Itens",
                    type="list",
                    span="full",
                    columns=[ListColumn("nome", "Item", "text"), ListColumn("qtd", "Qtd", "number")],
                )
            ],
        ),
        Section(
            id="notas",
            title="Anotações",
            columns=1,
            fields=[Field(key="notas", label="Notas", type="textarea", span="full")],
        ),
    ],
    token_bars=[TokenBar(label="Vida", path="vida", color="#5ce1e6")],
    quick_rolls=[
        QuickRoll(id="teste", label="Teste (d20)", formula="d20"),
        QuickRoll(id="vantagem", label="Com vantagem", formula="2d20kh1"),
        QuickRoll(id="desvantagem", label="Com desvantagem", formula="2d20kl1"),
    ],
)
