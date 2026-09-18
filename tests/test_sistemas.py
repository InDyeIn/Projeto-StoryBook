"""Definições de sistema e resolução de fórmulas."""

from __future__ import annotations

from app.systems import (
    DEFAULT_SYSTEM_ID,
    SYSTEMS,
    apply_room_difficulty,
    get_path,
    get_system,
    initial_sheet_data,
    list_systems,
    resolve_formula,
    set_path,
)


def test_todos_os_sistemas_tem_id_unico():
    ids = [s.id for s in SYSTEMS]
    assert len(ids) == len(set(ids))


def test_sistema_desconhecido_cai_no_padrao():
    assert get_system("nao-existe").id == DEFAULT_SYSTEM_ID
    assert get_system(None).id == DEFAULT_SYSTEM_ID


def test_campos_da_ficha_tem_chave_unica_por_sistema():
    for sistema in SYSTEMS:
        chaves = [c.key for c in sistema.all_fields()]
        assert len(chaves) == len(set(chaves)), f"chave repetida em {sistema.id}"


def test_todo_campo_tem_valor_inicial():
    """Um campo sem valor padrão apareceria vazio e quebraria as fórmulas."""
    for sistema in SYSTEMS:
        dados = initial_sheet_data(sistema.id)
        for campo in sistema.all_fields():
            assert get_path(dados, campo.key) is not None, (
                f"{sistema.id}: campo '{campo.key}' sem valor inicial"
            )


def test_barras_do_token_apontam_para_campos_de_recurso():
    for sistema in SYSTEMS:
        for barra in sistema.token_bars:
            campo = sistema.field_by_key(barra.path)
            assert campo is not None, f"{sistema.id}: barra '{barra.path}' sem campo"
            assert campo.type == "resource"


def test_rolagens_rapidas_referenciam_caminhos_existentes():
    import re

    for sistema in SYSTEMS:
        dados = initial_sheet_data(sistema.id)
        for rapida in sistema.quick_rolls:
            for caminho in re.findall(r"\{\{([^}]+)\}\}", rapida.formula):
                assert get_path(dados, caminho.strip()) is not None, (
                    f"{sistema.id}: rolagem '{rapida.id}' usa '{caminho}' inexistente"
                )


def test_formula_resolve_valores_da_ficha():
    dados = initial_sheet_data("triangle-agency")
    set_path(dados, "competencias.burocracia", 5)
    assert resolve_formula("{{competencias.burocracia}}d6>=4", dados) == "5d6>=4"


def test_formula_com_recurso_usa_o_valor_atual():
    dados = {"vida": {"atual": 7, "max": 12}}
    assert resolve_formula("{{vida}}d6", dados) == "7d6"


def test_caminho_ausente_vira_zero_em_vez_de_quebrar():
    assert resolve_formula("{{nao.existe}}d6", {}) == "0d6"


def test_dificuldade_da_sala_substitui_o_alvo():
    assert apply_room_difficulty("5d6>=4", {"dificuldade_padrao": "5"}) == "5d6>=5"
    assert apply_room_difficulty("5d6>=4", {}) == "5d6>=4"
    assert apply_room_difficulty("2d6+3", {"dificuldade_padrao": "5"}) == "2d6+3"


def test_dificuldade_invalida_nao_quebra():
    assert apply_room_difficulty("5d6>=4", {"dificuldade_padrao": "abc"}) == "5d6>=4"


def test_set_path_cria_niveis_intermediarios():
    dados: dict = {}
    set_path(dados, "a.b.c", 1)
    assert dados == {"a": {"b": {"c": 1}}}


def test_ficha_do_generico_respeita_a_vida_da_sala():
    dados = initial_sheet_data("generico", {"vida_inicial": 25})
    assert dados["vida"] == {"atual": 25, "max": 25}


def test_resumo_dos_sistemas_tem_o_que_a_tela_precisa():
    for resumo in list_systems():
        assert {"id", "name", "tagline", "color", "status", "room_options"} <= set(resumo)
