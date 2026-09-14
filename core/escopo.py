"""Qual workspace está ativo agora.

Existe para que `repo.py` não precise receber `workspace_id` em 38 assinaturas
e para que as telas não possam esquecer de passá-lo.

Duas regras de segurança guiam este módulo:

1. **Nunca adivinhar.** Sem workspace definido, `atual()` levanta erro em vez de
   devolver algo. Uma consulta sem filtro devolveria os dados de todo mundo, e
   esse é exatamente o acidente que o módulo existe para impedir.

2. **Dentro do Streamlit, só `st.session_state` vale.** O Streamlit reaproveita
   threads entre sessões de usuários diferentes, então um `ContextVar` deixado
   para trás por um request anterior poderia vazar o workspace de outra pessoa.
   O `ContextVar` só é consultado fora do Streamlit (testes, scripts).
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

CHAVE = "_workspace_id"

_fora_do_streamlit: ContextVar[int | None] = ContextVar("workspace_id", default=None)


class SemWorkspace(RuntimeError):
    """Nenhum workspace ativo. Consultar o banco agora seria consultar o de todos."""


def _sessao_streamlit():
    """Devolve o `st.session_state` se houver um runtime de verdade rodando.

    Fora do `streamlit run` (nos testes, por exemplo) devolve None em vez de
    estourar.
    """
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return None
    return st.session_state if get_script_run_ctx() is not None else None


def definir(workspace_id: int | None) -> None:
    sessao = _sessao_streamlit()
    if sessao is not None:
        if workspace_id is None:
            sessao.pop(CHAVE, None)
        else:
            sessao[CHAVE] = int(workspace_id)
        return
    _fora_do_streamlit.set(None if workspace_id is None else int(workspace_id))


def atual_ou_none() -> int | None:
    sessao = _sessao_streamlit()
    if sessao is not None:
        return sessao.get(CHAVE)
    return _fora_do_streamlit.get()


def atual() -> int:
    ws = atual_ou_none()
    if ws is None:
        raise SemWorkspace(
            "Nenhum workspace ativo. Faça login ou use escopo.usando(id) antes "
            "de consultar o banco."
        )
    return ws


def limpar() -> None:
    definir(None)


@contextmanager
def usando(workspace_id: int):
    """Roda um bloco com outro workspace ativo e devolve o anterior no fim.

    Útil em testes e em rotinas que precisam tocar mais de uma carteira.
    """
    anterior = atual_ou_none()
    definir(workspace_id)
    try:
        yield workspace_id
    finally:
        definir(anterior)
