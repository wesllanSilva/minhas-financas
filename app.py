"""Minhas Finanças — ponto de entrada.

Rode local com:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from core import ui

ui.configurar_pagina("Minhas Finanças", "💰")

# Precisa vir antes da navegação: é aqui que o workspace ativo é definido, e
# nenhuma página pode consultar o banco sem ele.
if not ui.exigir_login():
    st.stop()

ui.barra_lateral_conta()

navegacao = st.navigation(
    {
        "Mês a mês": [
            st.Page("views/painel.py", title="Painel", icon=":material/dashboard:", default=True),
            st.Page("views/transacoes.py", title="Transações", icon=":material/receipt_long:"),
            st.Page("views/planejamento.py", title="Planejamento", icon=":material/flag:"),
            st.Page("views/cartoes.py", title="Cartões", icon=":material/credit_card:"),
        ],
        "Longo prazo": [
            st.Page("views/investimentos.py", title="Investimentos", icon=":material/trending_up:"),
            st.Page("views/objetivos.py", title="Objetivos", icon=":material/savings:"),
        ],
        "Ajustes": [
            st.Page("views/configuracoes.py", title="Configurações", icon=":material/settings:"),
        ],
    }
)
navegacao.run()
