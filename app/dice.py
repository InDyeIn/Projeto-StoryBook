"""Motor de dados do StoryBook.

Notação suportada::

    d20              um dado de 20
    2d6+3            soma com modificador
    4d6kh3 / 4d6kl1  mantém os N maiores / menores
    6d6>=5           conta sucessos (pool de dados, usado pelo Triangle Agency)
    2d6!             dado explosivo (relança no valor máximo)
    1d20+2d4-1       vários termos na mesma expressão
"""

from __future__ import annotations

import re
import secrets
from dataclasses import asdict, dataclass, field

MAX_DICE = 200
MAX_SIDES = 1000
MAX_EXPLOSIONS = 20

_TERM_RE = re.compile(
    r"""^
    (?P<count>\d*)d(?P<sides>\d+)
    (?P<explode>!)?
    (?:(?P<keep_mode>kh|kl)(?P<keep_count>\d+))?
    (?:(?P<cmp>>=|<=|>|<)(?P<target>\d+))?
    $""",
    re.IGNORECASE | re.VERBOSE,
)

_ROLL_COMMAND_RE = re.compile(r"^/(?:r|roll|rolar)\s+(.+)$", re.IGNORECASE)
_FORMULA_SPLIT_RE = re.compile(r"^([0-9dkhl!<>=+\-\s]+?)(?:\s+(.*))?$", re.IGNORECASE)


class DiceError(ValueError):
    """Fórmula inválida — mostrada ao jogador no chat, sem derrubar nada."""


@dataclass
class Die:
    sides: int
    value: int
    kept: bool = True
    exploded: bool = False
    success: bool | None = None


@dataclass
class Term:
    expression: str
    dice: list[Die] = field(default_factory=list)
    constant: int | None = None
    subtotal: int = 0
    successes: int | None = None


@dataclass
class RollResult:
    formula: str
    terms: list[Term]
    total: int
    is_pool: bool
    successes: int | None = None
    label: str | None = None

    def to_dict(self) -> dict:
        return {
            "formula": self.formula,
            "label": self.label,
            "total": self.total,
            "successes": self.successes,
            "is_pool": self.is_pool,
            "terms": [asdict(term) for term in self.terms],
            "summary": describe(self),
        }


def _roll_die(sides: int) -> int:
    """Usa `secrets` em vez de `random`: rolagem de mesa não deve ser previsível."""
    return 1 + secrets.randbelow(sides)


def _tokenize(formula: str) -> list[tuple[int, str]]:
    cleaned = re.sub(r"\s+", "", formula)
    tokens: list[tuple[int, str]] = []
    sign = 1
    buffer = ""

    for char in cleaned:
        if char in "+-":
            if buffer:
                tokens.append((sign, buffer))
                sign = -1 if char == "-" else 1
                buffer = ""
            elif char == "-":
                sign = -sign
        else:
            buffer += char

    if buffer:
        tokens.append((sign, buffer))
    return tokens


def roll(formula: str, label: str | None = None) -> RollResult:
    formula = (formula or "").strip()
    if not formula:
        raise DiceError("Fórmula vazia.")
    if len(formula) > 120:
        raise DiceError("Fórmula longa demais.")

    tokens = _tokenize(formula)
    if not tokens:
        raise DiceError(f'Não entendi a fórmula "{formula}".')

    terms: list[Term] = []
    total = 0
    successes = 0
    is_pool = False

    for sign, body in tokens:
        if body.isdigit():
            constant = int(body) * sign
            terms.append(Term(expression=body, constant=constant, subtotal=constant))
            total += constant
            continue

        match = _TERM_RE.match(body)
        if not match:
            raise DiceError(f'Termo inválido: "{body}".')

        count = int(match.group("count") or 1)
        sides = int(match.group("sides"))

        if count < 1:
            raise DiceError("A quantidade de dados precisa ser ao menos 1.")
        if count > MAX_DICE:
            raise DiceError(f"No máximo {MAX_DICE} dados por termo.")
        if sides < 2 or sides > MAX_SIDES:
            raise DiceError(f"Dado inválido: d{sides}.")

        dice: list[Die] = []
        for _ in range(count):
            value = _roll_die(sides)
            dice.append(Die(sides=sides, value=value))
            if match.group("explode"):
                explosions = 0
                while value == sides and explosions < MAX_EXPLOSIONS:
                    value = _roll_die(sides)
                    dice.append(Die(sides=sides, value=value, exploded=True))
                    explosions += 1

        keep_mode = (match.group("keep_mode") or "").lower()
        if keep_mode:
            keep_count = max(0, min(int(match.group("keep_count")), len(dice)))
            ordered = sorted(dice, key=lambda d: d.value, reverse=keep_mode == "kh")
            for index, die in enumerate(ordered):
                die.kept = index < keep_count

        term = Term(expression=body, dice=dice)

        if match.group("cmp"):
            is_pool = True
            target = int(match.group("target"))
            comparison = match.group("cmp")
            term_successes = 0
            for die in dice:
                if not die.kept:
                    continue
                die.success = {
                    ">=": die.value >= target,
                    "<=": die.value <= target,
                    ">": die.value > target,
                    "<": die.value < target,
                }[comparison]
                if die.success:
                    term_successes += 1
            term.successes = term_successes
            successes += term_successes * (-1 if sign < 0 else 1)
        else:
            term.subtotal = sum(d.value for d in dice if d.kept) * sign
            total += term.subtotal

        terms.append(term)

    return RollResult(
        formula=formula,
        terms=terms,
        total=total,
        is_pool=is_pool,
        successes=successes if is_pool else None,
        label=label,
    )


def describe(result: RollResult) -> str:
    """Resumo de uma linha para o chat: ``4d6kh3 [5, 4, 3, ~2] = 12``."""
    parts: list[str] = []
    for term in result.terms:
        if not term.dice:
            parts.append(str(term.constant))
            continue
        faces = []
        for die in term.dice:
            if not die.kept:
                faces.append(f"~{die.value}")
            elif die.success:
                faces.append(f"*{die.value}*")
            else:
                faces.append(str(die.value))
        parts.append(f"{term.expression} [{', '.join(faces)}]")

    if result.is_pool:
        count = result.successes or 0
        tail = f"{count} sucesso" if count == 1 else f"{count} sucessos"
    else:
        tail = str(result.total)
    return f"{' + '.join(parts)} = {tail}"


def parse_roll_command(text: str) -> tuple[str, str | None] | None:
    """Interpreta ``/r 2d6+1 ataque`` e devolve ``("2d6+1", "ataque")``."""
    match = _ROLL_COMMAND_RE.match((text or "").strip())
    if not match:
        return None
    rest = match.group(1).strip()
    split = _FORMULA_SPLIT_RE.match(rest)
    if not split:
        return rest, None
    return split.group(1).strip(), (split.group(2) or "").strip() or None
