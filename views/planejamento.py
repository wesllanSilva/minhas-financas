"""Metas de gasto por categoria — o coração de 'não refazer a planilha todo mês'."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import repo, ui

competencia = ui.seletor_mes()
anterior = repo.somar_meses(competencia, -1)

st.title("Planejamento")
st.caption(repo.rotulo_mes(competencia))

orc = repo.orcamento_mes(competencia)
planejado = float(orc["planejado"].sum()) if not orc.empty else 0.0
gasto = float(orc["gasto"].sum()) if not orc.empty else 0.0
receitas = repo.resumo_mes(competencia)["receitas"]

ui.painel(
    [
        ("Planejado", ui.brl(planejado), ui.TINTA, "Soma das metas"),
        ("Gasto até agora", ui.brl(gasto), ui.cor_do_uso((gasto / planejado * 100) if planejado else 0),
         f"{(gasto / planejado * 100) if planejado else 0:.0f}% do planejado"),
        ("Restante", ui.brl(planejado - gasto),
         ui.VERDE if planejado - gasto >= 0 else ui.VERMELHO, "Do que foi planejado"),
        ("Sobra prevista", ui.brl(receitas - planejado),
         ui.VERDE if receitas - planejado >= 0 else ui.VERMELHO, "Receitas menos metas"),
    ]
)

# --------------------------------------------------------------------------- #
# Repetir o mês anterior
# --------------------------------------------------------------------------- #
st.subheader("Começar o mês")
st.caption(
    "Em vez de copiar a planilha, traga o que se repete de "
    f"{repo.rotulo_mes(anterior).lower()} para cá."
)

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Copiar as metas**")
    st.caption("Traz os valores planejados por categoria. Não duplica o que já existe aqui.")
    if st.button("Copiar metas do mês anterior", width="stretch"):
        n = repo.copiar_orcamento(anterior, competencia)
        st.success(f"{n} meta(s) copiada(s).") if n else st.info("Nada novo para copiar.")
        st.rerun()

with c2:
    st.markdown("**Repetir contas fixas**")
    st.caption("Escolha os lançamentos do mês anterior que acontecem todo mês.")
    antigos = repo.transacoes(anterior)
    if antigos.empty:
        st.info("Não há lançamentos no mês anterior.")
    else:
        rotulos = {
            f"{r.descricao} · {ui.brl(r.valor)} ({r.categoria})": r.id
            for r in antigos.itertuples()
        }
        escolhidos = st.multiselect("Lançamentos", list(rotulos), key="repetir")
        if st.button("Repetir neste mês", width="stretch", disabled=not escolhidos):
            n = repo.copiar_lancamentos(
                anterior, competencia, [rotulos[e] for e in escolhidos]
            )
            st.success(f"{n} lançamento(s) criado(s) como não pagos.")
            st.rerun()

st.divider()

# --------------------------------------------------------------------------- #
# Editar metas
# --------------------------------------------------------------------------- #
st.subheader("Metas por categoria")

categorias = repo.listar_categorias("despesa")
metas_atuais = {int(r.categoria_id): r.planejado for r in orc.itertuples()} if not orc.empty else {}

editor = pd.DataFrame(
    {
        "categoria_id": categorias["id"],
        "Categoria": categorias["nome"],
        "Meta (R$)": [float(metas_atuais.get(int(i), 0.0)) for i in categorias["id"]],
    }
)

editado = st.data_editor(
    editor,
    hide_index=True,
    width="stretch",
    column_config={
        "categoria_id": None,
        "Categoria": st.column_config.TextColumn(disabled=True),
        "Meta (R$)": st.column_config.NumberColumn(min_value=0.0, step=50.0, format="%.2f"),
    },
    key="editor_metas",
)

if st.button("Salvar metas", type="primary"):
    for _, r in editado.iterrows():
        cat_id = int(r["categoria_id"])
        atual = float(metas_atuais.get(cat_id, 0.0))
        novo = float(r["Meta (R$)"] or 0.0)
        if abs(novo - atual) > 0.005:
            repo.definir_orcamento(competencia, cat_id, novo)
    st.success("Metas atualizadas.")
    st.rerun()

# --------------------------------------------------------------------------- #
# Acompanhamento
# --------------------------------------------------------------------------- #
if not orc.empty:
    st.subheader("Como está indo")
    blocos = []
    for r in orc.sort_values("uso", ascending=False).itertuples():
        cor = ui.cor_do_uso(r.uso) if r.planejado else ui.CINZA
        if r.planejado:
            direita = (
                f"{ui.brl(r.gasto)} <span style='color:#98A29E'>de {ui.brl(r.planejado)}</span>"
            )
            nota = (
                f"restam {ui.brl(r.restante)}" if r.restante >= 0
                else f"passou {ui.brl(-r.restante)}"
            )
        else:
            direita = ui.brl(r.gasto)
            nota = "sem meta definida"
        blocos.append(
            f"<div style='padding:9px 0;border-bottom:1px solid #EDF1EF'>"
            f"<div style='display:flex;justify-content:space-between;font-size:.88rem'>"
            f"<span><span style='display:inline-block;width:8px;height:8px;border-radius:50%;"
            f"background:{r.cor};margin-right:7px'></span>{r.categoria}</span>"
            f"<span style='font-variant-numeric:tabular-nums'>{direita}</span></div>"
            f"{ui.barra(r.uso, cor) if r.planejado else ''}"
            f"<div style='font-size:.72rem;color:#98A29E;margin-top:3px'>{nota}</div></div>"
        )
    st.markdown(f"<div class='ficha'>{''.join(blocos)}</div>", unsafe_allow_html=True)
