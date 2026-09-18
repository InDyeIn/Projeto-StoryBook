"""Motor de dados."""

from __future__ import annotations

import pytest

from app.dice import DiceError, describe, parse_roll_command, roll


def test_dado_simples_fica_no_intervalo():
    for _ in range(200):
        assert 1 <= roll("d20").total <= 20


def test_soma_com_modificador():
    resultado = roll("2d6+3")
    assert 5 <= resultado.total <= 15
    assert len(resultado.terms) == 2


def test_subtracao():
    resultado = roll("1d4-10")
    assert -9 <= resultado.total <= -6


def test_manter_os_maiores_descarta_o_resto():
    resultado = roll("4d6kh3")
    dados = resultado.terms[0].dice
    assert len(dados) == 4
    assert sum(1 for d in dados if d.kept) == 3
    descartado = next(d for d in dados if not d.kept)
    mantidos = [d.value for d in dados if d.kept]
    assert descartado.value <= min(mantidos)
    assert resultado.total == sum(mantidos)


def test_manter_os_menores():
    resultado = roll("4d6kl1")
    dados = resultado.terms[0].dice
    mantido = next(d for d in dados if d.kept)
    assert mantido.value == min(d.value for d in dados)


def test_pool_conta_sucessos_e_nao_soma():
    resultado = roll("6d6>=4")
    assert resultado.is_pool
    assert resultado.total == 0
    esperado = sum(1 for d in resultado.terms[0].dice if d.value >= 4)
    assert resultado.successes == esperado


def test_pool_com_operadores_variados():
    maior = roll("5d6>3")
    assert maior.is_pool
    assert maior.successes == sum(1 for d in maior.terms[0].dice if d.value > 3)

    menor_igual = roll("5d6<=2")
    assert menor_igual.successes == sum(
        1 for d in menor_igual.terms[0].dice if d.value <= 2
    )


def test_dado_explosivo_gera_dados_extras():
    # d2 explode com frequência: em muitas tentativas alguma deve explodir.
    houve_explosao = any(
        any(d.exploded for d in roll("3d2!").terms[0].dice) for _ in range(60)
    )
    assert houve_explosao


def test_varios_termos():
    resultado = roll("1d20+2d4-1")
    assert len(resultado.terms) == 3
    assert 1 + 2 - 1 <= resultado.total <= 20 + 8 - 1


def test_constante_pura():
    assert roll("10").total == 10


@pytest.mark.parametrize(
    "formula",
    ["banana", "", "d1", "300d6", "2d", "d0", "   "],
)
def test_formulas_invalidas_sao_recusadas(formula):
    with pytest.raises(DiceError):
        roll(formula)


def test_limite_de_tamanho_da_formula():
    with pytest.raises(DiceError):
        roll("1d6+" * 40 + "1d6")


def test_descricao_marca_descartados_e_sucessos():
    texto = describe(roll("4d6kh3"))
    assert "~" in texto and "=" in texto
    assert "sucesso" in describe(roll("4d6>=1"))


def test_comando_de_chat():
    assert parse_roll_command("/r 2d6+1 ataque") == ("2d6+1", "ataque")
    assert parse_roll_command("/rolar d20") == ("d20", None)
    assert parse_roll_command("/roll 3d6>=4 perícia") == ("3d6>=4", "perícia")
    assert parse_roll_command("bom dia") is None
