"""Peças de interface reaproveitadas em todas as páginas."""
from __future__ import annotations

import datetime as dt
import os

import streamlit as st

from . import repo

VERDE = "#0F5D4A"
VERMELHO = "#A8352A"
AMBAR = "#B5852B"
TINTA = "#16241F"
CINZA = "#6B7A75"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, .stApp, button, input, textarea, select {
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
}

/* Os ícones do Streamlit são ligatures da fonte Material Symbols: o span
   contém o nome do ícone em texto puro. Se a fonte for trocada, a ligature
   não acontece e o nome ("dashboard", "settings") vaza por cima do rótulo. */
[data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded' !important;
}

.stApp { background: #F1F3F2; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #DFE5E2; }
[data-testid="stHeader"] { background: transparent; }

h1 { font-size: 1.9rem; font-weight: 600; letter-spacing: -0.02em; color: #16241F; }
h2 { font-size: 1.25rem; font-weight: 600; color: #16241F; }
h3 { font-size: 1.02rem; font-weight: 600; color: #16241F; }

.painel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 12px;
    margin: 4px 0 22px 0;
}
.ficha {
    background: #FFFFFF;
    border: 1px solid #E2E8E5;
    border-radius: 10px;
    padding: 14px 16px 15px 16px;
}
.ficha .rotulo { font-size: .78rem; color: #6B7A75; margin-bottom: 4px; }
.ficha .cifra {
    font-size: 1.5rem; font-weight: 600; letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}
.ficha .nota { font-size: .74rem; color: #8A9691; margin-top: 3px; }
.ficha.destaque { border-left: 3px solid #0F5D4A; }

.trilho { height: 6px; background: #E6EBE9; border-radius: 3px; overflow: hidden; }
.trilho > div { height: 100%; border-radius: 3px; }

.tag {
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: .74rem; font-weight: 500; color: #fff;
}

div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
.stDataFrame { font-variant-numeric: tabular-nums; }
footer, #MainMenu { visibility: hidden; }
</style>
"""


def brl(valor: float) -> str:
    negativo = valor < 0
    txt = f"{abs(valor):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{'-' if negativo else ''}R$ {txt}"


def configurar_pagina(titulo: str, icone: str = "💰") -> None:
    st.set_page_config(page_title=f"{titulo} · Minhas Finanças", page_icon=icone, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def checar_senha() -> bool:
    """Trava simples por senha. Se `app_password` não estiver nos secrets, libera."""
    senha_certa = os.environ.get("APP_PASSWORD")
    if not senha_certa:
        try:
            senha_certa = st.secrets.get("app_password")
        except Exception:
            senha_certa = None
    if not senha_certa:
        return True
    if st.session_state.get("_liberado"):
        return True

    st.title("Minhas Finanças")
    st.caption("Digite a senha para abrir seus dados.")
    with st.form("login"):
        digitada = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar"):
            if digitada == senha_certa:
                st.session_state["_liberado"] = True
                st.rerun()
            else:
                st.error("Senha incorreta. Tente de novo.")
    return False


def seletor_mes() -> dt.date:
    """Navegação de mês na barra lateral, compartilhada entre as páginas."""
    hoje = dt.date.today()
    if "competencia" not in st.session_state:
        st.session_state["competencia"] = repo.comp(hoje.year, hoje.month)

    atual: dt.date = st.session_state["competencia"]
    with st.sidebar:
        st.markdown("#### Mês")
        esq, meio, dir_ = st.columns([1, 3, 1])
        if esq.button("‹", width="stretch", key="mes_ant"):
            st.session_state["competencia"] = repo.somar_meses(atual, -1)
            st.rerun()
        meio.markdown(
            f"<div style='text-align:center;padding-top:6px;font-weight:600'>"
            f"{repo.rotulo_mes(atual)}</div>",
            unsafe_allow_html=True,
        )
        if dir_.button("›", width="stretch", key="mes_prox"):
            st.session_state["competencia"] = repo.somar_meses(atual, 1)
            st.rerun()
        if atual != repo.comp(hoje.year, hoje.month):
            if st.button("Voltar para o mês atual", width="stretch"):
                st.session_state["competencia"] = repo.comp(hoje.year, hoje.month)
                st.rerun()
        st.divider()
    return st.session_state["competencia"]


def painel(fichas: list[tuple[str, str, str, str]]) -> None:
    """Linha de cartões: (rótulo, valor, cor do valor, nota)."""
    blocos = "".join(
        f"<div class='ficha'><div class='rotulo'>{rotulo}</div>"
        f"<div class='cifra' style='color:{cor}'>{valor}</div>"
        f"<div class='nota'>{nota}</div></div>"
        for rotulo, valor, cor, nota in fichas
    )
    st.markdown(f"<div class='painel'>{blocos}</div>", unsafe_allow_html=True)


def barra(pct: float, cor: str = VERDE) -> str:
    pct = max(0.0, min(pct, 100.0))
    return f"<div class='trilho'><div style='width:{pct:.1f}%;background:{cor}'></div></div>"


def cor_do_uso(uso: float) -> str:
    if uso >= 100:
        return VERMELHO
    if uso >= 80:
        return AMBAR
    return VERDE


def vazio(mensagem: str, acao: str = "") -> None:
    st.markdown(
        f"<div class='ficha' style='text-align:center;padding:34px 16px'>"
        f"<div style='color:{CINZA}'>{mensagem}</div>"
        f"{f'<div style=\"margin-top:6px;font-size:.82rem;color:#8A9691\">{acao}</div>' if acao else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )
