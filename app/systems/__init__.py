"""Registro dos sistemas de RPG suportados."""

from __future__ import annotations

import copy
import re
from typing import Any

from app.systems.base import (  # noqa: F401 — reexportados para conveniência
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
from app.systems.generico import generico
from app.systems.triangle_agency import triangle_agency

#: Ordem aqui = ordem no seletor da tela de criação de sala.
SYSTEMS: list[RpgSystem] = [triangle_agency, generico]
SYSTEMS_BY_ID: dict[str, RpgSystem] = {system.id: system for system in SYSTEMS}

DEFAULT_SYSTEM_ID = triangle_agency.id

_PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")


def get_system(system_id: str | None) -> RpgSystem:
    """Sistema pelo id, caindo no padrão se o id for desconhecido."""
    return SYSTEMS_BY_ID.get(system_id or "", SYSTEMS_BY_ID[DEFAULT_SYSTEM_ID])


def list_systems() -> list[dict]:
    return [system.summary() for system in SYSTEMS]


def get_path(data: Any, path: str) -> Any:
    """Lê ``"a.b.c"`` dentro de dicionários aninhados sem estourar exceção."""
    cursor = data
    for key in path.split("."):
        if isinstance(cursor, dict):
            cursor = cursor.get(key)
        else:
            return None
    return cursor


def set_path(data: dict, path: str, value: Any) -> dict:
    """Escreve ``"a.b.c"`` criando os níveis intermediários que faltarem."""
    keys = path.split(".")
    cursor = data
    for key in keys[:-1]:
        nxt = cursor.get(key)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[key] = nxt
        cursor = nxt
    cursor[keys[-1]] = value
    return data


def initial_sheet_data(system_id: str, room_config: dict | None = None) -> dict:
    """Valores iniciais de uma ficha nova, respeitando as opções da sala."""
    system = get_system(system_id)
    data = copy.deepcopy(system.defaults)
    config = room_config or {}

    if system.id == "generico":
        try:
            vida = int(config.get("vida_inicial", 10))
        except (TypeError, ValueError):
            vida = 10
        data["vida"] = {"atual": vida, "max": vida}

    return data


def resolve_formula(formula: str, data: Any) -> str:
    """Troca ``{{caminho}}`` pelos valores da ficha.

    Caminhos ausentes viram ``0`` — uma ficha incompleta nunca quebra o chat.
    Um campo do tipo ``resource`` resolve para o valor **atual**.
    """

    def replace(match: re.Match[str]) -> str:
        value = get_path(data, match.group(1).strip())
        if isinstance(value, dict) and "atual" in value:
            value = value["atual"]
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return "0"

    return _PLACEHOLDER_RE.sub(replace, formula)


def apply_room_difficulty(formula: str, room_config: dict | None) -> str:
    """Aplica o alvo escolhido pelo mestre (ex.: 4+ vira 5+) nas fórmulas de pool."""
    target = (room_config or {}).get("dificuldade_padrao")
    if not target:
        return formula
    try:
        target_int = int(target)
    except (TypeError, ValueError):
        return formula
    return re.sub(r">=\d+", f">={target_int}", formula)
