"""Cadastros, importação da planilha e backup."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core import db, repo, ui

st.title("Configurações")

aba_contas, aba_cartoes, aba_cats, aba_dados = st.tabs(
    ["Contas", "Cartões", "Categorias", "Importar e exportar"]
)

# --------------------------------------------------------------------------- #
with aba_contas:
    contas = repo.listar_contas()
    if not contas.empty:
        tabela = contas.copy()
        tabela["saldo_inicial"] = tabela["saldo_inicial"].map(ui.brl)
        tabela = tabela[["nome", "tipo", "saldo_inicial"]]
        tabela.columns = ["Nome", "Tipo", "Saldo inicial"]
        st.dataframe(tabela, hide_index=True, width="stretch")

    with st.form("nova_conta", clear_on_submit=True):
        st.markdown("**Nova conta**")
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Nome", placeholder="Nubank, Inter, Carteira…")
        tipo = c2.selectbox("Tipo", ["Conta corrente", "Poupança", "Carteira", "Investimento"])
        saldo = c3.number_input("Saldo inicial (R$)", step=100.0, format="%.2f")
        if st.form_submit_button("Salvar conta", type="primary"):
            if nome.strip():
                repo.salvar_conta(nome, tipo, float(saldo))
                st.success("Conta salva.")
                st.rerun()
            else:
                st.error("Dê um nome à conta.")

    st.caption(
        "O saldo inicial é quanto havia na conta quando você começou a usar o app. "
        "A partir daí o saldo se atualiza sozinho com os lançamentos pagos."
    )

# --------------------------------------------------------------------------- #
with aba_cartoes:
    cartoes = repo.listar_cartoes()
    if not cartoes.empty:
        for r in cartoes.itertuples():
            c1, c2, c3, c4 = st.columns([2, 2, 2, 0.8])
            c1.write(f"**{r.nome}**")
            c2.write(r.banco or "—")
            c3.write(
                f"Limite {ui.brl(r.limite)} · fecha dia {r.dia_fechamento} · "
                f"vence dia {r.dia_vencimento}"
            )
            if c4.button("Remover", key=f"delcard{r.id}"):
                repo.excluir_cartao(r.id)
                st.rerun()

    with st.form("novo_cartao", clear_on_submit=True):
        st.markdown("**Novo cartão**")
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Apelido", placeholder="Nubank, Nubank PJ, Mercado Pago…")
        banco = c2.text_input("Banco", placeholder="Nubank")
        limite = c3.number_input("Limite (R$)", min_value=0.0, step=500.0, format="%.2f")
        c4, c5 = st.columns(2)
        fechamento = c4.number_input("Dia do fechamento", 1, 31, 1)
        vencimento = c5.number_input("Dia do vencimento", 1, 31, 10)
        if st.form_submit_button("Salvar cartão", type="primary"):
            if nome.strip():
                repo.salvar_cartao(
                    nome, banco, float(limite), int(fechamento), int(vencimento)
                )
                st.success("Cartão salvo.")
                st.rerun()
            else:
                st.error("Dê um apelido ao cartão.")

# --------------------------------------------------------------------------- #
with aba_cats:
    c_desp, c_rec = st.columns(2)
    for coluna, tipo, titulo in ((c_desp, "despesa", "Despesas"), (c_rec, "receita", "Receitas")):
        with coluna:
            st.markdown(f"**{titulo}**")
            cats = repo.listar_categorias(tipo)
            for r in cats.itertuples():
                a, b = st.columns([4, 1])
                a.markdown(
                    f"<span class='tag' style='background:{r.cor}'>{r.nome}</span>",
                    unsafe_allow_html=True,
                )
                if b.button("✕", key=f"delcat{r.id}"):
                    repo.arquivar_categoria(r.id)
                    st.rerun()

    st.divider()
    with st.form("nova_categoria", clear_on_submit=True):
        st.markdown("**Nova categoria**")
        c1, c2, c3 = st.columns([2, 1, 1])
        nome = c1.text_input("Nome", placeholder="Pet, Escola, Academia…")
        tipo = c2.selectbox(
            "Tipo", ["despesa", "receita"], format_func=lambda t: t.capitalize()
        )
        cor = c3.color_picker("Cor", "#5B7A86")
        if st.form_submit_button("Criar categoria", type="primary"):
            if nome.strip():
                repo.salvar_categoria(nome, tipo, cor)
                st.success("Categoria criada.")
                st.rerun()
            else:
                st.error("Dê um nome à categoria.")

    st.caption("Remover uma categoria só a esconde: os lançamentos antigos continuam intactos.")

# --------------------------------------------------------------------------- #
with aba_dados:
    st.subheader("Importar da planilha")
    st.markdown(
        "No Google Sheets, use **Arquivo → Fazer download → CSV** para cada aba e "
        "envie o arquivo aqui. Depois é só dizer qual coluna é qual."
    )

    arquivo = st.file_uploader("Arquivo CSV", type=["csv"])
    if arquivo is not None:
        try:
            bruto = pd.read_csv(arquivo, dtype=str, keep_default_na=False)
        except Exception:
            arquivo.seek(0)
            bruto = pd.read_csv(arquivo, dtype=str, sep=";", keep_default_na=False)

        st.caption(f"{len(bruto)} linha(s) encontradas. Confira o começo do arquivo:")
        st.dataframe(bruto.head(5), width="stretch")

        colunas = ["— não tenho —"] + list(bruto.columns)
        st.markdown("**De qual coluna vem cada informação?**")
        m1, m2, m3, m4 = st.columns(4)
        col_data = m1.selectbox("Data", colunas, index=min(1, len(colunas) - 1))
        col_valor = m2.selectbox("Valor", colunas, index=min(2, len(colunas) - 1))
        col_desc = m3.selectbox("Descrição", colunas, index=min(3, len(colunas) - 1))
        col_cat = m4.selectbox("Categoria", colunas, index=min(4, len(colunas) - 1))
        m5, m6, m7 = st.columns(3)
        col_conta = m5.selectbox("Conta", colunas, index=0)
        col_cartao = m6.selectbox("Cartão", colunas, index=0)
        tipo_fixo = m7.selectbox("Essas linhas são", ["Despesas", "Receitas"])

        if st.button("Importar", type="primary"):
            def pega(coluna):
                return bruto[coluna] if coluna in bruto.columns else ""

            preparado = pd.DataFrame(
                {
                    "data": pega(col_data),
                    "valor": pega(col_valor),
                    "descricao": pega(col_desc),
                    "categoria": pega(col_cat),
                    "conta": pega(col_conta),
                    "cartao": pega(col_cartao),
                }
            )
            preparado["tipo"] = "despesa" if tipo_fixo == "Despesas" else "receita"
            preparado = preparado[preparado["data"].astype(str).str.strip() != ""]

            inseridos, erros = repo.importar_transacoes(preparado)
            st.success(f"{inseridos} lançamento(s) importado(s).")
            if erros:
                with st.expander(f"{len(erros)} linha(s) ignorada(s)"):
                    st.write("\n".join(erros[:50]))

    st.divider()
    st.subheader("Backup")
    tudo = repo.exportar_tudo()
    st.download_button(
        "Baixar todos os lançamentos (CSV)",
        tudo.to_csv(index=False).encode("utf-8-sig"),
        file_name="minhas-financas-backup.csv",
        mime="text/csv",
        disabled=tudo.empty,
    )

    modelo = io.StringIO()
    pd.DataFrame(
        [
            {
                "data": "20/04/2026", "valor": "1592,00", "descricao": "Aluguel",
                "categoria": "Aluguel", "conta": "Nubank", "cartao": "",
            }
        ]
    ).to_csv(modelo, index=False)
    st.download_button(
        "Baixar modelo de CSV", modelo.getvalue().encode("utf-8-sig"),
        file_name="modelo-importacao.csv", mime="text/csv",
    )

    st.divider()
    st.subheader("Onde seus dados estão")
    if db.usando_sqlite():
        st.warning(
            "Rodando em **SQLite local** (arquivo `data/financas.db`). Ótimo para testar no seu "
            "computador, mas na nuvem os dados somem a cada reinício. Configure `DATABASE_URL` "
            "com um Postgres gratuito (Supabase ou Neon) antes de usar para valer."
        )
    else:
        st.success("Conectado a um banco Postgres. Seus dados continuam lá entre os deploys.")
