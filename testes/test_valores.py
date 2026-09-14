"""Leitura de valores monetários escritos de todo jeito.

É o ponto de entrada de tudo que vem de planilha, e onde um erro silencioso
custa caro: `1.592` lido como 1,592 não quebra nada — só deixa a conta errada.
"""
from __future__ import annotations

import pytest

from core import repo


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("R$ 1.592,00", 1592.0),
        ("45,90", 45.9),
        ("1592.00", 1592.0),
        ("1.234.567,89", 1234567.89),
        ("R$ 3.000", 3000.0),
        ("", 0.0),
        (2500, 2500.0),
        (None, 0.0),
        ("  R$ 10,50  ", 10.5),
    ],
)
def test_le_formatos_comuns(entrada, esperado):
    assert repo.parse_valor(entrada) == pytest.approx(esperado)


@pytest.mark.parametrize("entrada, esperado", [("-85,00", -85.0), ("(85,00)", -85.0)])
def test_negativos(entrada, esperado):
    """Extrato de banco marca saída com sinal; planilha de contador, com parênteses."""
    assert repo.parse_valor(entrada) == pytest.approx(esperado)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("1.592", 1592.0),      # grupo de 3 depois do ponto -> milhar
        ("1.592.300", 1592300.0),
        ("1592.00", 1592.0),    # grupo de 2 -> o ponto era decimal
        ("0.5", 0.5),
    ],
)
def test_ponto_sozinho_decide_por_tamanho_do_grupo(entrada, esperado):
    """Sem vírgula, o ponto é ambíguo. A regra: só é milhar se sobrar grupo de 3."""
    assert repo.parse_valor(entrada) == pytest.approx(esperado)


def test_texto_sem_numero_algum_reclama():
    with pytest.raises(ValueError):
        repo.parse_valor("abc.def")
