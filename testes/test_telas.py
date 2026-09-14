"""Cada tela abre sem estourar exceção, com dados realistas na carteira.

Não verifica layout — verifica que nenhuma página quebra ao ser carregada, que
é o tipo de defeito que só aparece em produção quando ninguém testa a tela.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import escopo, repo

#: O AppTest resolve caminho relativo contra o arquivo que o chama, não contra
#: a raiz do projeto.
RAIZ = Path(__file__).resolve().parent.parent

TELAS = [
    "views/painel.py",
    "views/transacoes.py",
    "views/planejamento.py",
    "views/cartoes.py",
    "views/investimentos.py",
    "views/objetivos.py",
    "views/configuracoes.py",
]


@pytest.fixture
def carteira_povoada(base, usuario):
    """Dados no mês corrente — é o que as telas mostram por padrão."""
    hoje = dt.date.today()
    repo.salvar_transacao(
        data=hoje.replace(day=5), descricao="Salário", valor=7200, tipo="receita",
        categoria_id=base["cat_receita"], conta_id=base["conta"],
    )
    repo.salvar_transacao(
        data=hoje.replace(day=2), descricao="Aluguel", valor=1592, tipo="despesa",
        categoria_id=base["cat_despesa"], conta_id=base["conta"], repetir_meses=6,
    )
    repo.salvar_transacao(
        data=hoje.replace(day=9), descricao="Cadeira", valor=900, tipo="despesa",
        categoria_id=base["cat_despesa2"], cartao_id=base["cartao"], parcelas=3,
    )
    repo.definir_orcamento(repo.comp(hoje.year, hoje.month), base["cat_despesa2"], 1200)

    repo.salvar_investimento("Tesouro Selic 2029", "Renda fixa", "Nubank")
    inv = int(repo.listar_investimentos().iloc[0]["id"])
    repo.salvar_movimento_investimento(inv, hoje.replace(day=3), "aporte", 1500)
    repo.salvar_objetivo("Reserva de emergência", 30000, 9000, dt.date(hoje.year + 1, 12, 31))

    return base


def _abrir(tela: str, carteira: int, usuario_id: int) -> AppTest:
    """Carrega a página já logada.

    As telas rodam depois do login no app de verdade, então o teste precisa
    reproduzir o estado que `ui.exigir_login` deixa pronto: usuário na sessão e
    workspace no escopo.
    """
    at = AppTest.from_file(str(RAIZ / tela), default_timeout=60)
    at.session_state["_usuario"] = {
        "id": usuario_id,
        "nome": "Pessoa de Teste",
        "email": "pessoa@exemplo.test",
    }
    at.session_state[escopo.CHAVE] = carteira
    return at.run()


@pytest.mark.parametrize("tela", TELAS)
def test_tela_abre_sem_erro(tela, carteira_povoada, usuario):
    uid, _ = usuario
    at = _abrir(tela, carteira_povoada["workspace"], uid)
    assert not at.exception, [str(e.value) for e in at.exception]


@pytest.mark.parametrize("tela", TELAS)
def test_tela_vazia_tambem_abre(tela, carteira, usuario):
    """Carteira recém-criada: é o primeiro que a esposa vai ver ao entrar."""
    uid, _ = usuario
    at = _abrir(tela, carteira, uid)
    assert not at.exception, [str(e.value) for e in at.exception]


def test_painel_mostra_o_saldo(carteira_povoada, usuario):
    uid, _ = usuario
    at = _abrir("views/painel.py", carteira_povoada["workspace"], uid)
    texto = " ".join(m.value for m in at.markdown)
    assert "Saldo em conta" in texto
