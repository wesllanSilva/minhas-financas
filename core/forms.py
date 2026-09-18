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


# --------------------------------------------------------------------------- #
# Edição
# --------------------------------------------------------------------------- #

CHAVE_EDICAO = "_editando_lancamento"


def pedir_edicao(id_: int) -> None:
    """Marca um lançamento para edição. A tela abre o diálogo no próximo rerun."""
    st.session_state[CHAVE_EDICAO] = id_


def abrir_edicao_pendente() -> None:
    """Chame no topo da tela: se alguém pediu edição, abre o diálogo."""
    id_ = st.session_state.get(CHAVE_EDICAO)
    if id_:
        _dialogo_edicao(id_)


@st.dialog("Editar lançamento", width="large")
def _dialogo_edicao(id_: int) -> None:
    lanc = repo.obter_transacao(id_)
    if lanc is None:
        st.session_state.pop(CHAVE_EDICAO, None)
        st.error("Esse lançamento não existe mais.")
        return

    contas = repo.listar_contas()
    cartoes = repo.listar_cartoes()
    tipo = st.radio(
        "Tipo", ["despesa", "receita"], horizontal=True, key="ed_tipo",
        index=0 if lanc["tipo"] == "despesa" else 1,
        format_func=lambda t: "Despesa" if t == "despesa" else "Receita",
    )
    categorias = repo.listar_categorias(tipo)
    if categorias.empty:
        st.warning("Cadastre uma categoria em Configurações antes.")
        return

    em_grupo = lanc["tamanho_grupo"] > 1
    alcance = "um"
    if em_grupo:
        n = lanc["tamanho_grupo"]
        rotulo = "parcelas" if lanc["parcela_total"] > 1 else "repetições"
        alcance = st.radio(
            f"Este lançamento faz parte de {n} {rotulo}. Aplicar a mudança em:",
            ["um", "todos"],
            format_func=lambda a: "Só este" if a == "um" else f"Todos os {n}",
            horizontal=True,
            key="ed_alcance",
        )
        if alcance == "todos":
            st.caption(
                "Descrição, valor, categoria, conta, cartão e observação mudam em todos. "
                "A data e o pago/pendente continuam como estão em cada um."
            )

    with st.form("ed_form"):
        c1, c2, c3 = st.columns([2, 1, 1])
        descricao = c1.text_input("Descrição", value=lanc["descricao"])
        valor = c2.number_input(
            "Valor (R$)", min_value=0.0, step=10.0, format="%.2f", value=float(lanc["valor"])
        )
        data = c3.date_input(
            "Data", value=lanc["data"], format="DD/MM/YYYY", disabled=(alcance == "todos")
        )

        c4, c5, c6 = st.columns(3)
        nomes_cat = categorias["nome"].tolist()
        idx_cat = _indice(categorias, lanc["categoria_id"])
        cat_nome = c4.selectbox("Categoria", nomes_cat, index=idx_cat)

        pagamento_opcoes = ["Conta/dinheiro"] + [f"Cartão · {n}" for n in cartoes["nome"]]
        idx_pag = 0
        if lanc["cartao_id"] is not None and not cartoes.empty:
            achou = cartoes.index[cartoes["id"] == lanc["cartao_id"]].tolist()
            if achou:
                idx_pag = 1 + int(achou[0])
        pagamento = c5.selectbox(
            "Pago com" if tipo == "despesa" else "Entrou em",
            pagamento_opcoes if tipo == "despesa" else ["Conta/dinheiro"],
            index=idx_pag if tipo == "despesa" else 0,
        )
        nomes_conta = contas["nome"].tolist() if not contas.empty else ["—"]
        conta_nome = c6.selectbox("Conta", nomes_conta, index=_indice(contas, lanc["conta_id"]))

        c7, c8 = st.columns([3, 1])
        observacao = c7.text_input("Observação (opcional)", value=lanc["observacao"])
        pago = c8.checkbox(
            "Já foi pago/recebido", value=lanc["pago"], disabled=(alcance == "todos")
        )
        salvar = st.form_submit_button("Salvar alterações", type="primary", width="stretch")

    if not salvar:
        return
    if not descricao.strip():
        st.error("Escreva uma descrição para o lançamento.")
        return
    if valor <= 0:
        st.error("O valor precisa ser maior que zero.")
        return

    cartao_id = None
    if pagamento.startswith("Cartão · "):
        nome = pagamento.removeprefix("Cartão · ")
        cartao_id = int(cartoes.loc[cartoes.nome == nome, "id"].iloc[0])
    conta_id = None
    if not contas.empty and conta_nome != "—":
        conta_id = int(contas.loc[contas.nome == conta_nome, "id"].iloc[0])
    categoria_id = int(categorias.loc[categorias.nome == cat_nome, "id"].iloc[0])

    if alcance == "todos":
        n = repo.editar_grupo(
            id_, descricao=descricao, valor=float(valor), tipo=tipo,
            categoria_id=categoria_id, conta_id=conta_id, cartao_id=cartao_id,
            observacao=observacao,
        )
        st.toast(f"{n} lançamentos alterados.")
    else:
        repo.salvar_transacao(
            id_=id_, data=data, descricao=descricao, valor=float(valor), tipo=tipo,
            categoria_id=categoria_id, conta_id=conta_id, cartao_id=cartao_id,
            pago=bool(pago), observacao=observacao,
        )
        st.toast("Lançamento alterado.")
    st.session_state.pop(CHAVE_EDICAO, None)
    st.rerun()


def _indice(df, id_) -> int:
    """Posição de `id_` num DataFrame com coluna id; 0 se não estiver lá."""
    if df.empty or id_ is None:
        return 0
    achou = df.index[df["id"] == id_].tolist()
    return int(achou[0]) if achou else 0
