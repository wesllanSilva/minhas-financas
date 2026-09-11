"""Objetivos de médio prazo: viagem, reserva, troca de carro."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from core import repo, ui

st.title("Objetivos")
st.caption("Quanto falta para cada meta que você quer alcançar.")

with st.expander("Novo objetivo", expanded=False):
    with st.form("novo_objetivo", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2.2, 1.2, 1.2, 1.2])
        nome = c1.text_input("Objetivo", placeholder="Reserva de emergência, viagem…")
        alvo = c2.number_input("Quanto quero juntar", min_value=0.0, step=500.0, format="%.2f")
        atual = c3.number_input("Já tenho", min_value=0.0, step=100.0, format="%.2f")
        prazo = c4.date_input("Até quando", value=None, format="DD/MM/YYYY")
        if st.form_submit_button("Criar objetivo", type="primary"):
            if not nome.strip() or alvo <= 0:
                st.error("Informe o nome e um valor maior que zero.")
            else:
                repo.salvar_objetivo(nome, float(alvo), float(atual), prazo)
                st.success("Objetivo criado.")
                st.rerun()

objs = repo.listar_objetivos()
if objs.empty:
    ui.vazio("Nenhum objetivo por enquanto.", "Crie o primeiro no formulário acima.")
    st.stop()

for r in objs.itertuples():
    falta = max(r.valor_alvo - r.valor_atual, 0)
    with st.container(border=True):
        c1, c2 = st.columns([3, 1.4])
        c1.markdown(f"**{r.nome}**")
        c1.markdown(
            ui.barra(r.progresso, ui.VERDE if not r.concluido else ui.VERDE)
            + f"<div style='font-size:.8rem;color:{ui.CINZA};margin-top:5px'>"
            f"{ui.brl(r.valor_atual)} de {ui.brl(r.valor_alvo)} · {r.progresso:.0f}%"
            + (f" · faltam {ui.brl(falta)}" if falta else " · alcançado")
            + (f" · até {r.data_alvo.strftime('%d/%m/%Y')}" if r.data_alvo else "")
            + "</div>",
            unsafe_allow_html=True,
        )

        with c2:
            deposito = st.number_input(
                "Guardar agora", min_value=0.0, step=100.0, format="%.2f", key=f"dep{r.id}"
            )
            b1, b2 = st.columns(2)
            if b1.button("Somar", key=f"add{r.id}", width="stretch"):
                repo.salvar_objetivo(
                    r.nome, r.valor_alvo, r.valor_atual + float(deposito), r.data_alvo, r.id
                )
                st.rerun()
            if b2.button("Excluir", key=f"delobj{r.id}", width="stretch"):
                repo.excluir_objetivo(r.id)
                st.rerun()

        if r.data_alvo and falta:
            meses = max(
                (r.data_alvo.year - dt.date.today().year) * 12
                + (r.data_alvo.month - dt.date.today().month),
                1,
            )
            st.caption(
                f"Para chegar lá no prazo, guarde cerca de {ui.brl(falta / meses)} por mês."
            )
