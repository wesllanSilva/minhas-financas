"""Leitura e escrita do cookie de sessão.

O Streamlit lê cookies de graça (`st.context.cookies`, populado com o que o
navegador mandou na requisição inicial) mas não escreve nenhum. Para escrever,
injetamos um `<script>` via `components.v1.html`.

Esse script roda dentro de um iframe, então ele mexe em `window.parent.document`
— o iframe do Streamlit vem com `allow-same-origin`, o que dá acesso ao
documento de cima. Sem isso o cookie seria gravado num contexto opaco e sumiria.

Consequência de o `st.context.cookies` refletir só a requisição inicial: um
cookie escrito agora não aparece na leitura deste mesmo rerun. Isso não
atrapalha — no login a sessão já é guardada em memória, e o cookie só precisa
existir no *próximo* carregamento da página, que é justamente o F5.
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

NOME_COOKIE = "financas_sessao"


def ler(nome: str = NOME_COOKIE) -> str | None:
    """Valor que o navegador mandou ao abrir a página, ou None.

    O tipo é conferido de propósito: esta é a fronteira por onde entra dado de
    fora, e nem todo ambiente devolve uma string aqui — sob o `AppTest` o
    `st.context` é um mock, e o valor sai como objeto truthy que quebraria mais
    adiante, longe da causa.
    """
    try:
        valor = st.context.cookies.get(nome)
    except Exception:
        # Fora de um runtime (scripts, testes do `core`) não há requisição.
        return None
    return valor if isinstance(valor, str) and valor else None


def gravar(valor: str, dias: int, nome: str = NOME_COOKIE) -> None:
    max_age = int(dias * 24 * 60 * 60)
    _executar(
        f"""
        const valor = {json.dumps(valor)};
        const seguro = window.parent.location.protocol === 'https:' ? '; Secure' : '';
        window.parent.document.cookie =
            {json.dumps(nome)} + '=' + encodeURIComponent(valor)
            + '; Max-Age={max_age}; Path=/; SameSite=Lax' + seguro;
        """
    )


def apagar(nome: str = NOME_COOKIE) -> None:
    _executar(
        f"""
        window.parent.document.cookie =
            {json.dumps(nome)} + '=; Max-Age=0; Path=/; SameSite=Lax';
        """
    )


def _executar(js: str) -> None:
    """Roda um trecho de JS sem ocupar espaço na tela."""
    components.html(f"<script>{js}</script>", height=0, width=0)
