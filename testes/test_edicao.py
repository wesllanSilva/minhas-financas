"""Editar lançamentos (um ou o grupo inteiro) e categorias."""
from __future__ import annotations

import datetime as dt

import pytest

from core import escopo, repo

MARCO = dt.date(2026, 3, 1)
ABRIL = dt.date(2026, 4, 1)


def _parcelado(base, n=3, valor=900):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 12), descricao="Cadeira", valor=valor, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"], parcelas=n,
    )
    return int(repo.transacoes(MARCO).iloc[0]["id"])


# --------------------------------------------------------------------------- #
# Lançamento
# --------------------------------------------------------------------------- #


def test_obter_traz_tudo_que_o_formulario_precisa(base):
    id_ = _parcelado(base)
    lanc = repo.obter_transacao(id_)
    assert lanc["descricao"] == "Cadeira"
    assert lanc["valor"] == pytest.approx(300)
    assert lanc["cartao_id"] == base["cartao"]
    assert lanc["categoria_id"] == base["cat_despesa"]
    assert (lanc["parcela_num"], lanc["parcela_total"], lanc["tamanho_grupo"]) == (1, 3, 3)


def test_obter_de_lancamento_simples_nao_tem_grupo(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Pão", valor=8, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    lanc = repo.obter_transacao(int(repo.transacoes(MARCO).iloc[0]["id"]))
    assert lanc["grupo"] is None and lanc["tamanho_grupo"] == 1


def test_editar_so_um_deixa_as_outras_parcelas_em_paz(base):
    id_ = _parcelado(base)
    repo.salvar_transacao(
        id_=id_, data=dt.date(2026, 3, 12), descricao="Cadeira gamer", valor=300,
        tipo="despesa", categoria_id=base["cat_despesa2"], cartao_id=base["cartao"],
    )
    assert repo.transacoes(MARCO).iloc[0]["descricao"] == "Cadeira gamer"
    assert repo.transacoes(MARCO).iloc[0]["categoria_id"] == base["cat_despesa2"]
    abril = repo.transacoes(ABRIL).iloc[0]
    assert abril["descricao"] == "Cadeira"
    assert abril["categoria_id"] == base["cat_despesa"]


def test_editar_todos_muda_o_grupo_inteiro(base):
    id_ = _parcelado(base)
    n = repo.editar_grupo(
        id_, descricao="Cadeira gamer", valor=310, tipo="despesa",
        categoria_id=base["cat_despesa2"], conta_id=None, cartao_id=base["cartao"],
        observacao="troquei a categoria",
    )
    assert n == 3
    for comp in (MARCO, ABRIL, repo.comp(2026, 5)):
        linha = repo.transacoes(comp).iloc[0]
        assert linha["descricao"] == "Cadeira gamer"
        assert float(linha["valor"]) == pytest.approx(310)
        assert linha["categoria_id"] == base["cat_despesa2"]
        assert linha["observacao"] == "troquei a categoria"


def test_editar_todos_preserva_data_e_pago_de_cada_parcela(base):
    id_ = _parcelado(base)
    repo.editar_grupo(
        id_, descricao="Cadeira", valor=300, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=None, cartao_id=base["cartao"],
    )
    marco, abril = repo.transacoes(MARCO).iloc[0], repo.transacoes(ABRIL).iloc[0]
    assert (bool(marco["pago"]), bool(abril["pago"])) == (True, False)
    assert marco["data"] == dt.date(2026, 3, 12) and abril["data"] == dt.date(2026, 4, 12)


def test_trocar_cartao_recalcula_a_competencia_de_cada_parcela(base):
    """Cartão com fechamento dia 5: compra do dia 12 vai para a fatura seguinte."""
    repo.salvar_cartao("Outro", "Banco", 1000, 5, 15)
    outro = int(repo.listar_cartoes().query("nome == 'Outro'").iloc[0]["id"])
    id_ = _parcelado(base)
    repo.editar_grupo(
        id_, descricao="Cadeira", valor=300, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=None, cartao_id=outro,
    )
    assert repo.transacoes(MARCO).empty
    assert len(repo.transacoes(ABRIL)) == 1  # a parcela de março, agora em abril


def test_editar_grupo_de_lancamento_simples_muda_so_ele(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Pão", valor=8, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    id_ = int(repo.transacoes(MARCO).iloc[0]["id"])
    assert repo.editar_grupo(
        id_, descricao="Pão integral", valor=9, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], cartao_id=None,
    ) == 1


def test_nao_edita_grupo_de_outra_carteira(base, emails):
    from core import auth

    id_ = _parcelado(base)
    outro = auth.criar_usuario(emails(), "Outra", "senha-de-teste-123")
    with escopo.usando(auth.workspaces_de(outro)[0]["id"]):
        assert repo.obter_transacao(id_) is None
        assert repo.editar_grupo(
            id_, descricao="INVADIDO", valor=1, tipo="despesa",
            categoria_id=None, conta_id=None, cartao_id=None,
        ) == 0
    assert repo.transacoes(MARCO).iloc[0]["descricao"] == "Cadeira"


# --------------------------------------------------------------------------- #
# Categoria
# --------------------------------------------------------------------------- #


def test_renomear_categoria_reflete_nos_lancamentos(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Pão", valor=8, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    repo.salvar_categoria("Casa e lar", "despesa", "#123456", id_=base["cat_despesa"])
    linha = repo.transacoes(MARCO).iloc[0]
    assert linha["categoria"] == "Casa e lar"
    assert linha["cor"] == "#123456"


def test_renomear_para_nome_que_ja_existe_e_recusado(carteira):
    cats = repo.listar_categorias(tipo="despesa")
    a, b = int(cats.iloc[0]["id"]), cats.iloc[1]["nome"]
    with pytest.raises(repo.NomeRepetido):
        repo.salvar_categoria(b.upper(), "despesa", "#000000", id_=a)


def test_salvar_com_o_proprio_nome_nao_e_repeticao(carteira):
    cat = repo.listar_categorias(tipo="despesa").iloc[0]
    repo.salvar_categoria(cat["nome"], "despesa", "#abcdef", id_=int(cat["id"]))
    assert repo.listar_categorias().query("id == @cat.id").iloc[0]["cor"] == "#abcdef"


def test_nome_vazio_e_recusado(carteira):
    with pytest.raises(ValueError):
        repo.salvar_categoria("   ", "despesa", "#000000")


# --------------------------------------------------------------------------- #
# Conta, cartão, carteira
# --------------------------------------------------------------------------- #


def test_editar_conta_reflete_nos_lancamentos_e_no_saldo(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Salário", valor=100, tipo="receita",
        categoria_id=base["cat_receita"], conta_id=base["conta"],
    )
    repo.salvar_conta("Nubank", "Conta corrente", 50, id_=base["conta"])
    assert repo.transacoes(MARCO).iloc[0]["conta"] == "Nubank"
    assert repo.saldo_total() == pytest.approx(150)


def test_conta_com_nome_repetido_e_recusada(carteira):
    repo.salvar_conta("Inter", "Conta corrente", 0)
    with pytest.raises(repo.NomeRepetido):
        repo.salvar_conta("inter", "Poupança", 0)


def test_arquivar_conta_esconde_mas_mantem_os_lancamentos(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 5), descricao="Pão", valor=8, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"],
    )
    repo.arquivar_conta(base["conta"])
    assert repo.listar_contas().empty
    assert len(repo.transacoes(MARCO)) == 1


def test_editar_cartao_renomeia_nas_faturas(base):
    repo.salvar_transacao(
        data=dt.date(2026, 3, 10), descricao="Jantar", valor=200, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"],
    )
    repo.salvar_cartao("Nubank Roxinho", "Nubank", 6000, 25, 5, id_=base["cartao"])
    assert repo.faturas(MARCO).iloc[0]["cartao"] == "Nubank Roxinho"
    assert float(repo.faturas(MARCO).iloc[0]["limite"]) == pytest.approx(6000)


def test_mudar_fechamento_do_cartao_move_a_compra_de_fatura(base):
    """Fechava dia 25: compra do dia 12 é de março. Passa a fechar dia 5: vira abril."""
    repo.salvar_transacao(
        data=dt.date(2026, 3, 12), descricao="Jantar", valor=200, tipo="despesa",
        categoria_id=base["cat_despesa"], cartao_id=base["cartao"],
    )
    assert len(repo.transacoes(MARCO)) == 1
    repo.salvar_cartao("Nubank Teste", "Nubank", 5000, 5, 15, id_=base["cartao"])
    assert repo.transacoes(MARCO).empty
    assert repo.transacoes(ABRIL).iloc[0]["descricao"] == "Jantar"


def test_cartao_com_nome_repetido_e_recusado(base):
    with pytest.raises(repo.NomeRepetido):
        repo.salvar_cartao("NUBANK TESTE", "x", 0, 1, 10)


def test_renomear_carteira_so_pelo_dono(usuario, emails):
    from core import auth

    uid, ws = usuario
    auth.renomear_workspace(ws, "Casa", uid)
    assert auth.workspaces_de(uid)[0]["nome"] == "Casa"

    outro = auth.criar_usuario(emails(), "Outra", "senha-de-teste-123")
    with pytest.raises(auth.ErroDeAuth):
        auth.renomear_workspace(ws, "Invadida", outro)
    assert auth.workspaces_de(uid)[0]["nome"] == "Casa"
