"""Isolamento entre carteiras.

É o teste que mais importa neste app. Um erro aqui não trava nada e não aparece
na tela de quem escreveu o código — só faz uma pessoa ver o dinheiro da outra.
"""
from __future__ import annotations

import datetime as dt

import pytest

from core import auth, escopo, repo
from core.models import COM_ESCOPO

DIA = dt.date(2026, 3, 10)
MARCO = dt.date(2026, 3, 1)


@pytest.fixture
def duas_carteiras(emails):
    """Dois usuários independentes, cada um com um lançamento próprio."""
    dados = {}
    for quem, valor in (("ana", 100.0), ("bruno", 999.0)):
        uid = auth.criar_usuario(emails(quem), quem.title(), "senha-de-teste-123")
        ws = auth.workspaces_de(uid)[0]["id"]
        with escopo.usando(ws):
            cat = int(repo.listar_categorias(tipo="despesa").iloc[0]["id"])
            conta = int(repo.listar_contas().iloc[0]["id"])
            repo.salvar_transacao(
                data=DIA, descricao=f"Gasto de {quem}", valor=valor, tipo="despesa",
                categoria_id=cat, conta_id=conta,
            )
        dados[quem] = {"usuario": uid, "workspace": ws}
    return dados


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #


def test_cada_carteira_ve_apenas_os_proprios_lancamentos(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        ana = repo.transacoes(MARCO)
    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        bruno = repo.transacoes(MARCO)

    assert list(ana["descricao"]) == ["Gasto de ana"]
    assert list(bruno["descricao"]) == ["Gasto de bruno"]


def test_totais_nao_somam_o_dinheiro_alheio(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        assert repo.resumo_mes(MARCO)["despesas"] == pytest.approx(100.0)
        assert repo.saldo_total() == pytest.approx(-100.0)
        assert repo.serie_mensal(3, ate=MARCO)["despesas"].sum() == pytest.approx(100.0)


def test_cadastros_nao_se_misturam(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        repo.salvar_cartao("Cartão da Ana", "Banco", 1000, 10, 20)
        repo.salvar_investimento("CDB da Ana", "Renda fixa", "Banco")
        repo.salvar_objetivo("Meta da Ana", 500, 0, None)

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        assert repo.listar_cartoes().empty
        assert repo.listar_investimentos().empty
        assert repo.listar_objetivos().empty


def test_carteiras_diferentes_podem_repetir_nomes(duas_carteiras):
    """O unique de nome é por carteira: os dois podem ter um "Nubank"."""
    for quem in ("ana", "bruno"):
        with escopo.usando(duas_carteiras[quem]["workspace"]):
            repo.salvar_cartao("Nubank", "Nubank", 5000, 25, 5)
            assert len(repo.listar_cartoes()) == 1


# --------------------------------------------------------------------------- #
# Escrita — o id vem da tela e não é confiável
# --------------------------------------------------------------------------- #


def test_nao_da_para_editar_lancamento_de_outra_carteira(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        alvo = int(repo.transacoes(MARCO).iloc[0]["id"])

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        repo.salvar_transacao(
            data=DIA, descricao="INVADIDO", valor=1, tipo="despesa",
            categoria_id=None, id_=alvo,
        )

    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        intacto = repo.transacoes(MARCO).iloc[0]
        assert intacto["descricao"] == "Gasto de ana"
        assert float(intacto["valor"]) == pytest.approx(100.0)


def test_nao_da_para_excluir_lancamento_de_outra_carteira(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        alvo = int(repo.transacoes(MARCO).iloc[0]["id"])

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        repo.excluir_transacao(alvo)
        repo.alternar_pago(alvo)

    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        assert len(repo.transacoes(MARCO)) == 1


def test_nao_da_para_arquivar_categoria_de_outra_carteira(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        antes = len(repo.listar_categorias())
        alvo = int(repo.listar_categorias().iloc[0]["id"])

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        repo.arquivar_categoria(alvo)
        repo.salvar_categoria("Renomeada", "despesa", "#000000", id_=alvo)

    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        nomes = set(repo.listar_categorias()["nome"])
        assert len(repo.listar_categorias()) == antes
        assert "Renomeada" not in nomes


def test_lancamento_nao_aponta_para_categoria_de_outra_carteira(duas_carteiras):
    """Id estranho vira "sem categoria" em vez de criar um vínculo cruzado."""
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        cat_alheia = int(repo.listar_categorias().iloc[0]["id"])

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        repo.salvar_transacao(
            data=DIA, descricao="Tentativa", valor=10, tipo="despesa",
            categoria_id=cat_alheia,
        )
        criado = repo.transacoes(MARCO)
        linha = criado[criado.descricao == "Tentativa"].iloc[0]
        assert linha["categoria_id"] is None or pd_isna(linha["categoria_id"])


def pd_isna(v) -> bool:
    import pandas as pd

    return bool(pd.isna(v))


def test_meta_nao_cai_em_categoria_de_outra_carteira(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        cat_alheia = int(repo.listar_categorias().iloc[0]["id"])

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        repo.definir_orcamento(MARCO, cat_alheia, 500)
        # A carteira do Bruno tem gasto no mês, então `orcamento_mes` devolve
        # linha de qualquer jeito. O que se verifica é que nenhuma meta foi
        # gravada — e nenhuma linha aponta para a categoria da Ana.
        orcamento = repo.orcamento_mes(MARCO)
        assert orcamento["planejado"].sum() == 0
        assert cat_alheia not in set(orcamento["categoria_id"])

    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        assert repo.orcamento_mes(MARCO)["planejado"].sum() == 0


def test_copiar_so_alcanca_a_propria_carteira(duas_carteiras):
    with escopo.usando(duas_carteiras["ana"]["workspace"]):
        ids_alheios = [int(x) for x in repo.transacoes(MARCO)["id"]]

    with escopo.usando(duas_carteiras["bruno"]["workspace"]):
        repo.copiar_lancamentos(MARCO, repo.comp(2026, 4), apenas_ids=ids_alheios)
        assert repo.transacoes(repo.comp(2026, 4)).empty


# --------------------------------------------------------------------------- #
# Falha fechada
# --------------------------------------------------------------------------- #


def test_sem_workspace_a_consulta_nao_acontece():
    """O modo de falha é erro, nunca "devolve tudo"."""
    escopo.limpar()
    with pytest.raises(escopo.SemWorkspace):
        repo.transacoes()
    with pytest.raises(escopo.SemWorkspace):
        repo.saldo_total()
    with pytest.raises(escopo.SemWorkspace):
        repo.listar_categorias()


def test_usando_devolve_o_escopo_anterior_mesmo_com_erro(carteira):
    with pytest.raises(ZeroDivisionError):
        with escopo.usando(9999):
            1 / 0
    assert escopo.atual() == carteira


def test_toda_tabela_financeira_tem_workspace_id():
    """Guarda contra esquecimento: uma tabela nova sem escopo derruba este teste."""
    for modelo in COM_ESCOPO:
        assert "workspace_id" in modelo.__table__.columns, modelo.__name__
