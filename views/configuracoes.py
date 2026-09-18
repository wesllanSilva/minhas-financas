"""Cadastros, carteiras, importação da planilha e backup."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core import auth, db, escopo, repo, ui

st.title("Configurações")

aba_contas, aba_cartoes, aba_cats, aba_carteiras, aba_dados = st.tabs(
    ["Contas", "Cartões", "Categorias", "Carteiras e acesso", "Importar e exportar"]
)

# --------------------------------------------------------------------------- #
with aba_contas:
    TIPOS_CONTA = ["Conta corrente", "Poupança", "Carteira", "Investimento"]
    contas = repo.listar_contas()
    for r in contas.itertuples():
        c1, c2, c3, c4 = st.columns([2.2, 1.6, 1.6, 0.8])
        c1.write(f"**{r.nome}**")
        c2.caption(r.tipo)
        c3.markdown(f"<span class='dinheiro'>{ui.brl(r.saldo_inicial)}</span>", unsafe_allow_html=True)
        with c4.popover("✎", width="stretch"):
            with st.form(f"edconta{r.id}"):
                n_nome = st.text_input("Nome", value=r.nome)
                n_tipo = st.selectbox(
                    "Tipo", TIPOS_CONTA,
                    index=TIPOS_CONTA.index(r.tipo) if r.tipo in TIPOS_CONTA else 0,
                )
                n_saldo = st.number_input(
                    "Saldo inicial (R$)", step=100.0, format="%.2f", value=float(r.saldo_inicial)
                )
                e1, e2 = st.columns(2)
                salvar_c = e1.form_submit_button("Salvar", type="primary", width="stretch")
                remover_c = e2.form_submit_button("Remover", width="stretch")
            if salvar_c:
                try:
                    repo.salvar_conta(n_nome, n_tipo, float(n_saldo), id_=r.id)
                    st.rerun()
                except ValueError as erro:
                    st.error(str(erro))
            if remover_c:
                repo.arquivar_conta(r.id)
                st.rerun()

    with st.form("nova_conta", clear_on_submit=True):
        st.markdown("**Nova conta**")
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Nome", placeholder="Nubank, Inter, Carteira…")
        tipo = c2.selectbox("Tipo", TIPOS_CONTA)
        saldo = c3.number_input("Saldo inicial (R$)", step=100.0, format="%.2f")
        if st.form_submit_button("Salvar conta", type="primary"):
            try:
                repo.salvar_conta(nome, tipo, float(saldo))
                st.success("Conta salva.")
                st.rerun()
            except ValueError as erro:
                st.error(str(erro))

    st.caption(
        "O saldo inicial é quanto havia na conta quando você começou a usar o app. "
        "A partir daí o saldo se atualiza sozinho com os lançamentos pagos. "
        "Remover uma conta só a esconde: os lançamentos dela continuam contando."
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
            with c4.popover("✎", width="stretch"):
                with st.form(f"edcard{r.id}"):
                    n_nome = st.text_input("Apelido", value=r.nome)
                    n_banco = st.text_input("Banco", value=r.banco or "")
                    n_limite = st.number_input(
                        "Limite (R$)", min_value=0.0, step=500.0, format="%.2f", value=float(r.limite)
                    )
                    f1, f2 = st.columns(2)
                    n_fech = f1.number_input("Fechamento", 1, 31, int(r.dia_fechamento))
                    n_venc = f2.number_input("Vencimento", 1, 31, int(r.dia_vencimento))
                    st.caption("Mudar o fechamento recalcula em que fatura cada compra cai.")
                    e1, e2 = st.columns(2)
                    salvar_k = e1.form_submit_button("Salvar", type="primary", width="stretch")
                    remover_k = e2.form_submit_button("Remover", width="stretch")
                if salvar_k:
                    try:
                        repo.salvar_cartao(
                            n_nome, n_banco, float(n_limite), int(n_fech), int(n_venc), id_=r.id
                        )
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))
                if remover_k:
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
            try:
                repo.salvar_cartao(nome, banco, float(limite), int(fechamento), int(vencimento))
                st.success("Cartão salvo.")
                st.rerun()
            except ValueError as erro:
                st.error(str(erro))

# --------------------------------------------------------------------------- #
with aba_cats:
    c_desp, c_rec = st.columns(2)
    for coluna, tipo, titulo in ((c_desp, "despesa", "Despesas"), (c_rec, "receita", "Receitas")):
        with coluna:
            st.markdown(f"**{titulo}**")
            cats = repo.listar_categorias(tipo)
            for r in cats.itertuples():
                a, b = st.columns([4, 1.4])
                a.markdown(
                    f"<span class='tag' style='background:{r.cor}'>{r.nome}</span>",
                    unsafe_allow_html=True,
                )
                with b.popover("✎", width="stretch"):
                    with st.form(f"edcat{r.id}"):
                        novo_nome = st.text_input("Nome", value=r.nome)
                        nova_cor = st.color_picker("Cor", value=r.cor)
                        e1, e2 = st.columns(2)
                        salvar_cat = e1.form_submit_button("Salvar", type="primary", width="stretch")
                        remover_cat = e2.form_submit_button("Remover", width="stretch")
                    if salvar_cat:
                        try:
                            repo.salvar_categoria(novo_nome, tipo, nova_cor, id_=r.id)
                            st.rerun()
                        except (repo.NomeRepetido, ValueError) as erro:
                            st.error(str(erro))
                    if remover_cat:
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
            if not nome.strip():
                st.error("Dê um nome à categoria.")
            else:
                try:
                    repo.salvar_categoria(nome, tipo, cor)
                    st.success("Categoria criada.")
                    st.rerun()
                except repo.NomeRepetido as erro:
                    st.error(str(erro))

    st.caption("Renomear uma categoria muda o nome em todos os lançamentos dela. Remover só a esconde: os lançamentos antigos continuam intactos.")

# --------------------------------------------------------------------------- #
with aba_carteiras:
    usuario = st.session_state.get("_usuario") or {}
    usuario_id = usuario.get("id")
    ws_atual = escopo.atual_ou_none()
    carteiras = auth.workspaces_de(usuario_id) if usuario_id else []
    eu_sou_dono = any(
        c["id"] == ws_atual and c["papel"] == "dono" for c in carteiras
    )

    st.subheader("Suas carteiras")
    st.caption(
        "Cada carteira tem contas, lançamentos e metas próprios. Use uma para você, "
        "outra para a sua esposa e uma terceira compartilhada para as contas da casa."
    )
    for c in carteiras:
        marca = " · **aberta agora**" if c["id"] == ws_atual else ""
        w1, w2 = st.columns([5, 0.8])
        w1.write(f"**{c['nome']}** — {c['papel']}{marca}")
        if c["papel"] == "dono":
            with w2.popover("✎", width="stretch"):
                with st.form(f"edws{c['id']}"):
                    n_ws = st.text_input("Nome da carteira", value=c["nome"])
                    if st.form_submit_button("Salvar", type="primary", width="stretch"):
                        try:
                            auth.renomear_workspace(c["id"], n_ws, usuario_id)
                            st.session_state.pop("_carteiras", None)
                            st.rerun()
                        except auth.ErroDeAuth as erro:
                            st.error(str(erro))

    with st.form("nova_carteira", clear_on_submit=True):
        nome_nova = st.text_input("Nome da nova carteira", placeholder="Contas da casa")
        if st.form_submit_button("Criar carteira", type="primary"):
            try:
                auth.criar_workspace(nome_nova, usuario_id)
                st.success("Carteira criada. Troque por ela na barra lateral.")
                st.rerun()
            except auth.ErroDeAuth as erro:
                st.error(str(erro))

    st.divider()
    st.subheader("Quem tem acesso a esta carteira")
    for m in auth.membros_de(ws_atual) if ws_atual else []:
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"**{m['nome']}**")
        c2.caption(f"{m['email']} · {m['papel']}")
        if eu_sou_dono and m["usuario_id"] != usuario_id:
            if c3.button("Remover", key=f"delmembro{m['usuario_id']}"):
                try:
                    auth.remover_membro(ws_atual, m["usuario_id"], usuario_id)
                    st.rerun()
                except auth.ErroDeAuth as erro:
                    st.error(str(erro))

    if eu_sou_dono:
        with st.form("convidar", clear_on_submit=True):
            st.markdown("**Dar acesso a alguém**")
            email_convite = st.text_input("E-mail de quem já tem conta no app")
            if st.form_submit_button("Liberar acesso"):
                try:
                    auth.adicionar_membro(ws_atual, email_convite, usuario_id)
                    st.success("Acesso liberado.")
                    st.rerun()
                except auth.ErroDeAuth as erro:
                    st.error(str(erro))
        st.caption(
            "A pessoa precisa criar a conta dela primeiro, na tela de login. "
            "Depois é só liberar o e-mail aqui."
        )
    else:
        st.caption("Só o dono da carteira pode convidar ou remover alguém.")

    st.divider()
    st.subheader("Sua senha")
    with st.form("trocar_senha", clear_on_submit=True):
        atual_txt = st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha", type="password")
        repetir = st.text_input("Repita a nova senha", type="password")
        if st.form_submit_button("Trocar senha"):
            if nova != repetir:
                st.error("As duas senhas não são iguais.")
            else:
                try:
                    auth.trocar_senha(usuario_id, atual_txt, nova)
                    st.success(
                        "Senha trocada. Os outros navegadores conectados foram desconectados."
                    )
                except auth.ErroDeAuth as erro:
                    st.error(str(erro))

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
        file_name="wstack-finance-backup.csv",
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
