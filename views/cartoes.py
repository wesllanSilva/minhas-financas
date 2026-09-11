"""Faturas dos cartões do mês, com comparação com o mês anterior."""
from __future__ import annotations

import streamlit as st

from core import repo, ui

competencia = ui.seletor_mes()
anterior = repo.somar_meses(competencia, -1)

st.title("Cartões")
st.caption(repo.rotulo_mes(competencia))

fat = repo.faturas(competencia)
fat_ant = repo.faturas(anterior)

if fat.empty:
    ui.vazio(
        "Nenhum cartão cadastrado ainda.",
        "Vá em Configurações → Cartões para cadastrar Nubank, Mercado Pago, Inter…",
    )
    st.stop()

total = float(fat["total"].sum())
total_ant = float(fat_ant["total"].sum()) if not fat_ant.empty else 0.0
diferenca = total - total_ant

ui.painel(
    [
        ("Total das faturas", ui.brl(total), ui.VERMELHO, repo.rotulo_mes(competencia)),
        ("Mês anterior", ui.brl(total_ant), ui.CINZA, repo.rotulo_mes(anterior)),
        ("Diferença", ui.brl(diferenca),
         ui.VERMELHO if diferenca > 0 else ui.VERDE,
         "gastou mais" if diferenca > 0 else "gastou menos"),
    ]
)

anteriores = (
    dict(zip(fat_ant["cartao"], fat_ant["total"])) if not fat_ant.empty else {}
)

for r in fat.itertuples():
    ant = float(anteriores.get(r.cartao, 0.0))
    delta = r.total - ant
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.markdown(
            f"**{r.cartao}**  \n<span style='color:{ui.CINZA};font-size:.8rem'>"
            f"{r.banco or 'sem banco informado'}</span>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div style='font-size:1.3rem;font-weight:600;font-variant-numeric:tabular-nums'>"
            f"{ui.brl(r.total)}</div>"
            f"<div style='font-size:.76rem;color:{ui.VERMELHO if delta > 0 else ui.VERDE}'>"
            f"{'+' if delta >= 0 else ''}{ui.brl(delta)} vs. mês anterior</div>",
            unsafe_allow_html=True,
        )
        if r.limite:
            c3.markdown(
                f"<div style='font-size:.78rem;color:{ui.CINZA};margin-bottom:4px'>"
                f"{r.uso:.0f}% de {ui.brl(r.limite)}</div>"
                + ui.barra(r.uso, ui.cor_do_uso(r.uso)),
                unsafe_allow_html=True,
            )
        else:
            c3.caption("Limite não informado")

        itens = repo.transacoes(competencia, tipo="despesa", cartao_id=int(r.cartao_id))
        with st.expander(f"Ver {len(itens)} lançamento(s)"):
            if itens.empty:
                st.caption("Nada lançado neste cartão no mês.")
            else:
                tabela = itens[["data", "descricao", "categoria", "parcela", "valor"]].copy()
                tabela["data"] = tabela["data"].map(lambda d: d.strftime("%d/%m"))
                tabela["valor"] = tabela["valor"].map(ui.brl)
                tabela.columns = ["Data", "Descrição", "Categoria", "Parcela", "Valor"]
                st.dataframe(tabela, hide_index=True, width="stretch")

st.caption(
    "A fatura de um mês reúne as compras feitas até o dia de fechamento do cartão. "
    "Ajuste esse dia em Configurações se os valores não baterem com o app do banco."
)
