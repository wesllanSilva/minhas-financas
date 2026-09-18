"""Lista de lançamentos do mês."""
from __future__ import annotations

import streamlit as st

from core import repo, ui
from core.forms import abrir_edicao_pendente, formulario_lancamento, pedir_edicao

competencia = ui.seletor_mes()
abrir_edicao_pendente()

st.title("Transações")
st.caption(repo.rotulo_mes(competencia))

resumo = repo.resumo_mes(competencia)
ui.painel(
    [
        ("Receitas", ui.brl(resumo["receitas"]), ui.VERDE, ""),
        ("Despesas", ui.brl(resumo["despesas"]), ui.VERMELHO, ""),
        ("Em aberto", ui.brl(resumo["a_pagar"]), ui.AMBAR, "Ainda não marcado como pago"),
        ("Balanço", ui.brl(resumo["balanco"]),
         ui.VERDE if resumo["balanco"] >= 0 else ui.VERMELHO, ""),
    ]
)

with st.expander("Novo lançamento", expanded=False):
    if formulario_lancamento("trans", data_padrao=competencia):
        st.success("Lançamento salvo.")
        st.rerun()

df = repo.transacoes(competencia)

if df.empty:
    ui.vazio(
        "Nenhum lançamento neste mês.",
        "Lance manualmente acima ou repita as contas fixas do mês passado em Planejamento.",
    )
    st.stop()

# --------------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------------- #
f1, f2, f3, f4 = st.columns([1.2, 1.4, 1.4, 2])
tipo_filtro = f1.selectbox("Tipo", ["Todos", "Despesas", "Receitas"])
cat_filtro = f2.multiselect("Categoria", sorted(df["categoria"].unique()))
pagamento_filtro = f3.selectbox(
    "Forma", ["Todas", "Conta/dinheiro"] + sorted(c for c in df["cartao"].unique() if c)
)
busca = f4.text_input("Buscar na descrição", "")

filtrado = df.copy()
if tipo_filtro != "Todos":
    filtrado = filtrado[filtrado.tipo == ("despesa" if tipo_filtro == "Despesas" else "receita")]
if cat_filtro:
    filtrado = filtrado[filtrado.categoria.isin(cat_filtro)]
if pagamento_filtro == "Conta/dinheiro":
    filtrado = filtrado[filtrado.cartao == ""]
elif pagamento_filtro != "Todas":
    filtrado = filtrado[filtrado.cartao == pagamento_filtro]
if busca.strip():
    filtrado = filtrado[filtrado.descricao.str.contains(busca.strip(), case=False, na=False)]

st.markdown(
    f"<div style='color:{ui.CINZA};font-size:.84rem;margin:6px 0 2px 0'>"
    f"{len(filtrado)} lançamento(s) · despesas {ui.brl(filtrado.loc[filtrado.tipo=='despesa','valor'].sum())}"
    f" · receitas {ui.brl(filtrado.loc[filtrado.tipo=='receita','valor'].sum())}</div>",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Lista
# --------------------------------------------------------------------------- #
for r in filtrado.itertuples():
    c1, c2, c3, c4, c5 = st.columns([0.5, 4, 2, 1.6, 0.9])

    c1.markdown(
        f"<div style='padding-top:8px;font-size:1.05rem'>{'✓' if r.pago else '○'}</div>",
        unsafe_allow_html=True,
    )
    parcela = f" · {r.parcela}" if r.parcela else ""
    c2.markdown(
        f"<div style='padding-top:4px'><b>{r.descricao}</b>"
        f"<div style='font-size:.76rem;color:{ui.CINZA}'>"
        f"{r.data.strftime('%d/%m/%Y')}{parcela}"
        f"{' · ' + r.cartao if r.cartao else (' · ' + r.conta if r.conta else '')}</div></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"<div style='padding-top:8px'><span class='tag' style='background:{r.cor}'>"
        f"{r.categoria}</span></div>",
        unsafe_allow_html=True,
    )
    sinal = "-" if r.tipo == "despesa" else "+"
    cor = ui.VERMELHO if r.tipo == "despesa" else ui.VERDE
    c4.markdown(
        f"<div class='dinheiro' style='padding-top:8px;text-align:right;"
        f"font-weight:600;color:{cor}'>{sinal} {ui.brl(r.valor)}</div>",
        unsafe_allow_html=True,
    )

    with c5.popover("⋯", width="stretch"):
        if st.button("Editar", key=f"ed{r.id}", width="stretch"):
            pedir_edicao(r.id)
            st.rerun()
        if st.button(
            "Marcar como pendente" if r.pago else "Marcar como pago",
            key=f"pg{r.id}", width="stretch",
        ):
            repo.alternar_pago(r.id)
            st.rerun()
        if st.button("Excluir", key=f"ex{r.id}", width="stretch"):
            repo.excluir_transacao(r.id)
            st.rerun()
        if r.grupo and st.button(
            "Excluir todas as parcelas/repetições", key=f"exg{r.id}", width="stretch"
        ):
            repo.excluir_transacao(r.id, grupo_inteiro=True)
            st.rerun()

    st.markdown(
        f"<hr style='margin:2px 0;border:none;border-top:1px solid {ui.LINHA}'>",
        unsafe_allow_html=True,
    )

with st.sidebar:
    csv = filtrado[["data", "descricao", "valor", "tipo", "categoria", "conta", "cartao", "pago"]]
    st.download_button(
        "Baixar este mês (CSV)",
        csv.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"transacoes-{competencia:%Y-%m}.csv",
        mime="text/csv",
        width="stretch",
    )
