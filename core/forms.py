"""Formulário de lançamento, usado no Dashboard e na página de Transações."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from . import repo


def formulario_lancamento(chave: str = "novo", data_padrao: dt.date | None = None) -> bool:
    """Desenha o formulário. Devolve True quando algo foi salvo."""
    contas = repo.listar_contas()
    cartoes = repo.listar_cartoes()

    tipo = st.radio(
        "Tipo", ["despesa", "receita"], horizontal=True, key=f"{chave}_tipo",
        format_func=lambda t: "Despesa" if t == "despesa" else "Receita",
    )
    categorias = repo.listar_categorias(tipo)

    if categorias.empty:
        st.warning("Cadastre uma categoria em Configurações antes de lançar.")
        return False

    with st.form(f"{chave}_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        descricao = c1.text_input("Descrição", placeholder="Mercado, aluguel, salário…")
        valor = c2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")
        data = c3.date_input("Data", value=data_padrao or dt.date.today(), format="DD/MM/YYYY")

        c4, c5, c6 = st.columns(3)
        cat_nome = c4.selectbox("Categoria", categorias["nome"].tolist())

        pagamento_opcoes = ["Conta/dinheiro"] + [f"Cartão · {n}" for n in cartoes["nome"]]
        pagamento = c5.selectbox(
            "Pago com" if tipo == "despesa" else "Entrou em",
            pagamento_opcoes if tipo == "despesa" else ["Conta/dinheiro"],
        )
        conta_nome = c6.selectbox(
            "Conta", contas["nome"].tolist() if not contas.empty else ["—"]
        )

        c7, c8, c9 = st.columns(3)
        parcelas = c7.number_input("Parcelas", min_value=1, max_value=48, value=1)
        repetir = c8.number_input(
            "Repetir por (meses)", min_value=1, max_value=36, value=1,
            help="Para contas fixas: cria o mesmo valor nos próximos meses.",
        )
        pago = c9.checkbox("Já foi pago/recebido", value=True)

        observacao = st.text_input("Observação (opcional)", "")
        salvar = st.form_submit_button(
            "Salvar lançamento", type="primary", width="stretch"
        )

    if salvar:
        if not descricao.strip():
            st.error("Escreva uma descrição para o lançamento.")
            return False
        if valor <= 0:
            st.error("O valor precisa ser maior que zero.")
            return False

        cartao_id = None
        if pagamento.startswith("Cartão · "):
            nome = pagamento.removeprefix("Cartão · ")
            cartao_id = int(cartoes.loc[cartoes.nome == nome, "id"].iloc[0])

        conta_id = None
        if not contas.empty and conta_nome != "—":
            conta_id = int(contas.loc[contas.nome == conta_nome, "id"].iloc[0])

        repo.salvar_transacao(
            data=data,
            descricao=descricao,
            valor=float(valor),
            tipo=tipo,
            categoria_id=int(categorias.loc[categorias.nome == cat_nome, "id"].iloc[0]),
            conta_id=conta_id,
            cartao_id=cartao_id,
            pago=bool(pago),
            observacao=observacao,
            parcelas=int(parcelas),
            repetir_meses=int(repetir),
        )
        return True
    return False
