"""Tipos que descrevem um sistema de RPG.

A ficha **não** é escrita em HTML: ela é descrita por estes objetos e desenhada
por um renderizador genérico (``app/templates/partials/sheet.html``). Para
adicionar um sistema novo basta criar um arquivo neste pacote e registrá-lo em
``app/systems/__init__.py`` — nenhuma tela precisa mudar.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

FieldType = Literal[
    "text",      # linha simples
    "textarea",  # texto longo
    "number",    # inteiro com min/max
    "resource",  # par atual/máximo — vira barra no token
    "select",    # lista fechada de opções
    "checkbox",  # sim/não
    "dots",      # trilha de N bolinhas (atributos, estresse)
    "list",      # tabela de linhas livres
    "derived",   # somente leitura, calculado por fórmula
]


@dataclass
class Option:
    value: str
    label: str


@dataclass
class ListColumn:
    key: str
    label: str
    type: Literal["text", "number", "checkbox"] = "text"


@dataclass
class QuickRollDef:
    """Botão de rolagem rápida que aparece ao lado de um campo."""

    formula: str
    label: str | None = None


@dataclass
class Field:
    #: Caminho dentro de ``Character.data``, ex.: "competencias.burocracia"
    key: str
    label: str
    type: FieldType = "text"
    hint: str | None = None
    placeholder: str | None = None
    min: int | None = None
    max: int | None = None
    step: int = 1
    options: list[Option] = field(default_factory=list)
    #: derived: expressão com {{caminhos}}, ex.: "{{atributos.forca}} + 2"
    formula: str | None = None
    #: list: colunas de cada linha
    columns: list[ListColumn] = field(default_factory=list)
    #: rolagem atrelada ao campo
    roll: QuickRollDef | None = None
    #: largura no grid da seção: 1, 2 ou "full"
    span: int | Literal["full"] = 1
    #: somente o mestre vê e edita
    gm_only: bool = False


@dataclass
class Section:
    id: str
    title: str
    fields: list[Field]
    description: str | None = None
    columns: int = 2


@dataclass
class SystemOption:
    """Opção que o mestre escolhe no momento de criar a sala."""

    key: str
    label: str
    type: Literal["boolean", "select", "number", "text"]
    default: Any
    hint: str | None = None
    options: list[Option] = field(default_factory=list)


@dataclass
class TokenBar:
    label: str
    #: caminho de um campo do tipo "resource" dentro de Character.data
    path: str
    color: str


@dataclass
class QuickRoll:
    id: str
    label: str
    formula: str
    description: str | None = None


@dataclass
class RpgSystem:
    id: str
    name: str
    short_name: str
    tagline: str
    description: str
    color: str
    sections: list[Section]
    defaults: dict[str, Any]
    token_bars: list[TokenBar] = field(default_factory=list)
    quick_rolls: list[QuickRoll] = field(default_factory=list)
    room_options: list[SystemOption] = field(default_factory=list)
    default_roll: str = "d20"
    #: "draft" faz a ficha exibir um aviso de que ainda falta conferir o livro
    status: Literal["draft", "stable"] = "stable"
    draft_note: str | None = None
    publisher: str | None = None

    def all_fields(self) -> list[Field]:
        return [f for section in self.sections for f in section.fields]

    def field_by_key(self, key: str) -> Field | None:
        return next((f for f in self.all_fields() if f.key == key), None)

    def full(self) -> dict:
        """Definição completa, incluindo as seções — alimenta o renderizador de ficha."""
        return {
            **self.summary(),
            "draft_note": self.draft_note,
            "default_roll": self.default_roll,
            "sections": [asdict(section) for section in self.sections],
            "token_bars": [asdict(bar) for bar in self.token_bars],
            "quick_rolls": [asdict(quick) for quick in self.quick_rolls],
        }

    def summary(self) -> dict:
        """Versão leve para listagens e para o seletor de sistema."""
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "tagline": self.tagline,
            "description": self.description,
            "color": self.color,
            "status": self.status,
            "publisher": self.publisher,
            "room_options": [asdict(option) for option in self.room_options],
        }
