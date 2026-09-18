"""Regras de negócio: competência, parcelas, orçamento, fatura, importação."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from core import repo
from core.db import get_session
from core.models import Cartao

MARCO = dt.date(2026, 3, 1)
ABRIL = dt.date(2026, 4, 1)


# --------------------------------------------------------------------------- #
# Datas
# --------------------------------------------------------------------------- #


def test_somar_meses_encolhe_o_dia_quando_o_mes_e_curto():
    """31 de janeiro + 1 mês não existe. Vira o último dia de fevereiro."""
    assert repo.somar_meses(dt.date(2026, 1, 31), 1) == dt.date(2026, 2, 28)
    assert repo.somar_meses(dt.date(2028, 1, 31), 1) == dt.date(2028, 2, 29)


def test_somar_meses_atravessa_o_ano():
    assert repo.somar_meses(dt.date(2026, 12, 15), 1) == dt.date(2027, 1, 15)
    assert repo.somar_meses(dt.date(2026, 1, 15), -1) == dt.date(2025, 12, 15)


def test_competencia_sem_cartao_e_o_mes_da_data():
    assert repo.competencia_de(dt.date(2026, 3, 26), None) == MARCO


def test_compra_depois_do_fechamento_cai_na_fatura_seguinte(base):
    with get_session() as s:
        cartao = s.get(Cartao, base["cartao"])  # fechamento dia 25
        assert repo.competencia_de(dt.date(2026, 3, 20), cartao) == MARCO
        assert repo.competencia_de(dt.date(2026, 3, 26), cartao) == ABRIL


# --------------------------------------------------------------------------- #
# Lançamentos
# --------------------------------------------------------------------------- #


def test_parcelamento_divide_o_valor_e_espalha_pelos_meses(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 12), descricao="Cadeira", valor=600, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"], parcelas=3,
    )
    marco = repo.transacoes(MARCO)
    parcela = marco[marco.descricao == "Cadeira"]
    assert float(parcela.iloc[0]["valor"]) == pytest.approx(200)
    assert parcela.iloc[0]["parcela"] == "1/3"

    assert len(repo.transacoes(ABRIL)) == 1
    assert len(repo.transacoes(repo.comp(2026, 5))) == 1
    assert len(repo.transacoes(repo.comp(2026, 6))) == 0


def test_repeticao_mantem_o_valor_cheio_e_para_no_fim(base):
    """Conta fixa: 12 meses de aluguel, e nada no décimo terceiro."""
    repo.salvar_transacao(
        data=dt.date(2026, 3, 1), descricao="Aluguel", valor=2000, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
        repetir_meses=12, pago=False,
    )
    assert float(repo.transacoes(ABRIL).iloc[0]["valor"]) == pytest.approx(2000)
    assert len(repo.transacoes(repo.comp(2027, 2))) == 1
    assert len(repo.transacoes(repo.comp(2027, 3))) == 0


def test_so_a_primeira_parcela_nasce_paga(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 12), descricao="TV", valor=900, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"], parcelas=3, pago=True,
    )
    assert bool(repo.transacoes(MARCO).iloc[0]["pago"]) is True
    assert bool(repo.transacoes(ABRIL).iloc[0]["pago"]) is False


def test_excluir_grupo_apaga_todas_as_parcelas(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 12), descricao="Notebook", valor=3000, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"], parcelas=3,
    )
    alvo = int(repo.transacoes(MARCO).iloc[0]["id"])
    repo.excluir_transacao(alvo, grupo_inteiro=True)
    assert len(repo.transacoes(MARCO)) == 0
    assert len(repo.transacoes(ABRIL)) == 0


def test_alternar_pago_vai_e_volta(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Mercado", valor=850.55, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], pago=False,
    )
    alvo = int(repo.transacoes(MARCO).iloc[0]["id"])
    repo.alternar_pago(alvo)
    assert bool(repo.transacoes(MARCO).iloc[0]["pago"]) is True
    repo.alternar_pago(alvo)
    assert bool(repo.transacoes(MARCO).iloc[0]["pago"]) is False


# --------------------------------------------------------------------------- #
# Resumos
# --------------------------------------------------------------------------- #


def test_resumo_do_mes_separa_pago_de_a_pagar(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Salário", valor=6000, tipo="receita",
        categoria_id=base["cat_receita"], conta_id=base["conta"],
    )
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Mercado", valor=850.55, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], pago=True,
    )
    repo.salvar_transacao(
        data=dt.date(2026, 3, 11), descricao="Luz", valor=149.45, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], pago=False,
    )
    r = repo.resumo_mes(MARCO)
    assert r["receitas"] == pytest.approx(6000)
    assert r["despesas"] == pytest.approx(1000)
    assert r["despesas_pagas"] == pytest.approx(850.55)
    assert r["a_pagar"] == pytest.approx(149.45)
    assert r["balanco"] == pytest.approx(5000)


def test_saldo_ignora_despesa_no_cartao(base):
    """Gasto no cartão só sai da conta quando a fatura é paga, não na compra."""
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Salário", valor=5000, tipo="receita",
        categoria_id=base["cat_receita"], conta_id=base["conta"], pago=True,
    )
    repo.salvar_transacao(
        data=dt.date(2026, 3, 6), descricao="Jantar", valor=200, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"], pago=True,
    )
    assert repo.saldo_total() == pytest.approx(5000)


def test_serie_mensal_devolve_uma_linha_por_mes(base):
    serie = repo.serie_mensal(12, ate=MARCO)
    assert len(serie) == 12
    assert list(serie.columns) >= ["competencia", "receitas", "despesas", "saldo", "mes"]


def test_fatura_soma_so_o_que_e_daquele_cartao(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Jantar", valor=200, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"],
    )
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Padaria", valor=50, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    fatura = repo.faturas(MARCO)
    assert float(fatura.iloc[0]["total"]) == pytest.approx(200)


# --------------------------------------------------------------------------- #
# Orçamento
# --------------------------------------------------------------------------- #


def test_meta_confronta_planejado_com_gasto(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Mercado", valor=1800, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    repo.definir_orcamento(MARCO, base["cat_despesa"], 1500)
    linha = repo.orcamento_mes(MARCO).iloc[0]
    assert float(linha["planejado"]) == pytest.approx(1500)
    assert float(linha["gasto"]) == pytest.approx(1800)
    assert float(linha["restante"]) == pytest.approx(-300)
    assert float(linha["uso"]) == pytest.approx(120)


def test_meta_zerada_e_apagada(base):
    repo.definir_orcamento(MARCO, base["cat_despesa"], 1500)
    repo.definir_orcamento(MARCO, base["cat_despesa"], 0)
    assert repo.orcamento_mes(MARCO).empty


def test_copiar_orcamento_nao_duplica_o_que_ja_existe(base):
    repo.definir_orcamento(MARCO, base["cat_despesa"], 1500)
    assert repo.copiar_orcamento(MARCO, ABRIL) == 1
    assert repo.copiar_orcamento(MARCO, ABRIL) == 0


def test_lancamento_copiado_nasce_em_aberto(base):
    """Copiar a conta fixa do mês passado não quer dizer que ela já foi paga."""
    repo.salvar_transacao(
        data=dt.date(2026, 3, 1), descricao="Internet", valor=120, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], pago=True,
    )
    assert repo.copiar_lancamentos(MARCO, ABRIL) == 1
    copiado = repo.transacoes(ABRIL).iloc[0]
    assert copiado["descricao"] == "Internet"
    assert bool(copiado["pago"]) is False


# --------------------------------------------------------------------------- #
# Investimentos e objetivos
# --------------------------------------------------------------------------- #


def test_saldo_do_investimento_soma_aporte_e_rendimento(carteira):
    repo.salvar_investimento("Tesouro Selic 2029", "Renda fixa", "Nubank")
    inv_id = int(repo.listar_investimentos().iloc[0]["id"])
    repo.salvar_movimento_investimento(inv_id, dt.date(2026, 3, 15), "aporte", 1000)
    repo.salvar_movimento_investimento(inv_id, dt.date(2026, 4, 15), "rendimento", 12.5)
    repo.salvar_movimento_investimento(inv_id, dt.date(2026, 5, 15), "resgate", 200)

    linha = repo.listar_investimentos().iloc[0]
    assert float(linha["saldo"]) == pytest.approx(812.5)
    assert float(linha["aportado"]) == pytest.approx(800)
    assert float(linha["rendimento"]) == pytest.approx(12.5)


def test_objetivo_calcula_progresso_e_conclusao(carteira):
    repo.salvar_objetivo("Viagem", 10000, 2500, dt.date(2026, 12, 31))
    assert float(repo.listar_objetivos().iloc[0]["progresso"]) == pytest.approx(25)

    alvo = int(repo.listar_objetivos().iloc[0]["id"])
    repo.salvar_objetivo("Viagem", 10000, 10000, None, id_=alvo)
    assert bool(repo.listar_objetivos().iloc[0]["concluido"]) is True


# --------------------------------------------------------------------------- #
# Importação
# --------------------------------------------------------------------------- #


def test_importacao_cria_categoria_e_conta_que_faltam(carteira):
    df = pd.DataFrame(
        {
            "data": ["01/06/2026", "02/06/2026"],
            "descricao": ["Padaria", "Farmácia"],
            "valor": ["R$ 1.592,00", "45,90"],
            "categoria": ["Mercearia", "Categoria Nova XPTO"],
            "conta": ["Conta corrente", "Conta Nova XPTO"],
            "cartao": ["", ""],
            "tipo": ["despesa", "despesa"],
        }
    )
    inseridos, erros = repo.importar_transacoes(df)
    assert (inseridos, erros) == (2, [])

    junho = repo.transacoes(repo.comp(2026, 6))
    padaria = junho[junho.descricao == "Padaria"].iloc[0]
    assert float(padaria["valor"]) == pytest.approx(1592)
    assert "Categoria Nova XPTO" in set(repo.listar_categorias()["nome"])
    assert "Conta Nova XPTO" in set(repo.listar_contas()["nome"])


def test_importacao_relata_a_linha_ruim_e_segue(carteira):
    df = pd.DataFrame(
        {
            "data": ["01/06/2026", "data inválida"],
            "descricao": ["Boa", "Ruim"],
            "valor": ["10,00", "10,00"],
            "tipo": ["despesa", "despesa"],
        }
    )
    inseridos, erros = repo.importar_transacoes(df)
    assert inseridos == 1
    assert len(erros) == 1
    assert "linha 3" in erros[0]


def test_exportar_traz_as_colunas_da_planilha(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Mercado", valor=100, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    export = repo.exportar_tudo()
    assert list(export.columns) == [
        "data", "competencia", "descricao", "valor", "tipo",
        "categoria", "conta", "cartao", "pago", "parcela",
    ]
    assert len(export) == 1


# --------------------------------------------------------------------------- #
# Detalhes do painel
# --------------------------------------------------------------------------- #


def test_saldo_por_conta_abre_o_total_e_mostra_negativo(base):
    repo.salvar_conta("Itaú", "Conta corrente", 100)
    itau = int(repo.listar_contas().query("nome == 'Itaú'").iloc[0]["id"])
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Salário", valor=3000, tipo="receita",
        categoria_id=base["cat_receita"], conta_id=base["conta"],
    )
    repo.salvar_transacao(
        data=dt.date(2026, 3, 6), descricao="Conta de luz", valor=250, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=itau,
    )
    df = repo.saldo_por_conta().set_index("nome")
    assert df.loc["Conta corrente", "saldo"] == pytest.approx(3000)
    assert df.loc["Itaú", "saldo"] == pytest.approx(-150)
    assert repo.saldo_total() == pytest.approx(float(df["saldo"].sum()))


def test_lancamento_pago_sem_conta_aparece_como_sem_conta(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Achado", valor=50, tipo="receita",
        categoria_id=base["cat_receita"],
    )
    df = repo.saldo_por_conta().set_index("nome")
    assert df.loc["Sem conta", "saldo"] == pytest.approx(50)


def test_por_categoria_separa_pago_de_pendente(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="A", valor=100, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], pago=True,
    )
    repo.salvar_transacao(
        data=dt.date(2026, 3, 6), descricao="B", valor=40, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], pago=False,
    )
    linha = repo.por_categoria(MARCO, "despesa").iloc[0]
    assert (linha["total"], linha["pago"], linha["pendente"], linha["itens"]) == (140, 100, 40, 2)
    assert repo.por_categoria(MARCO, "receita").empty
