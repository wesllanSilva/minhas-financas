"""Aportes, resgates e rendimentos."""
from __future__ import annotations

import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from core import repo, ui

st.title("Investimentos")

invs = repo.listar_investimentos()
patrimonio = float(invs["saldo"].sum()) if not invs.empty else 0.0
aportado = float(invs["aportado"].sum()) if not invs.empty else 0.0
rendimento = float(invs["rendimento"].sum()) if not invs.empty else 0.0

ui.painel(
    [
        ("Patrimônio", ui.brl(patrimonio), ui.VERDE, "Aportes + rendimentos - resgates"),
        ("Total aportado", ui.brl(aportado), ui.TINTA, "Dinheiro que você colocou"),
        ("Rendimento", ui.brl(rendimento),
         ui.VERDE if rendimento >= 0 else ui.VERMELHO,
         f"{(rendimento / aportado * 100) if aportado else 0:.1f}% sobre o aportado"),
    ]
)

aba_mov, aba_carteira = st.tabs(["Lançar movimento", "Carteira"])

with aba_carteira:
    with st.form("novo_investimento", clear_on_submit=True):
        st.markdown("**Novo investimento**")
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Nome", placeholder="Tesouro Selic 2029, CDB Inter…")
        tipo = c2.selectbox(
            "Tipo",
            ["Renda fixa", "Ações", "FIIs", "Fundo", "Cripto", "Previdência", "Reserva de emergência"],
        )
        instituicao = c3.text_input("Instituição", placeholder="Nubank, Inter, XP…")
        if st.form_submit_button("Cadastrar", type="primary"):
            if nome.strip():
                repo.salvar_investimento(nome, tipo, instituicao)
                st.success("Investimento cadastrado.")
                st.rerun()
            else:
                st.error("Dê um nome ao investimento.")

    if invs.empty:
        ui.vazio("Sua carteira está vazia.", "Cadastre o primeiro investimento acima.")
    else:
        tabela = invs[["nome", "tipo", "instituicao", "aportado", "rendimento", "saldo"]].copy()
        for col in ("aportado", "rendimento", "saldo"):
            tabela[col] = tabela[col].map(ui.brl)
        tabela.columns = ["Nome", "Tipo", "Instituição", "Aportado", "Rendimento", "Saldo"]
        st.dataframe(tabela, hide_index=True, width="stretch")

with aba_mov:
    if invs.empty:
        st.info("Cadastre um investimento na aba Carteira antes de lançar movimentos.")
    else:
        with st.form("novo_movimento", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([2, 1.2, 1.2, 1.2])
            alvo = c1.selectbox("Investimento", invs["nome"].tolist())
            tipo_mov = c2.selectbox(
                "Movimento", ["aporte", "resgate", "rendimento"],
                format_func=lambda t: t.capitalize(),
            )
            valor = c3.number_input("Valor (R$)", min_value=0.0, step=50.0, format="%.2f")
            data = c4.date_input("Data", value=dt.date.today(), format="DD/MM/YYYY")
            obs = st.text_input("Observação (opcional)", "")
            if st.form_submit_button("Salvar movimento", type="primary"):
                if valor <= 0:
                    st.error("O valor precisa ser maior que zero.")
                else:
                    repo.salvar_movimento_investimento(
                        int(invs.loc[invs.nome == alvo, "id"].iloc[0]),
                        data, tipo_mov, float(valor), obs,
                    )
                    st.success("Movimento registrado.")
                    st.rerun()

        movs = repo.movimentos_investimento()
        if movs.empty:
            ui.vazio("Nenhum movimento registrado ainda.")
        else:
            st.markdown("**Histórico**")
            for r in movs.head(40).itertuples():
                c1, c2, c3, c4 = st.columns([1.2, 2.6, 1.6, 0.6])
                c1.write(r.data.strftime("%d/%m/%Y"))
                c2.write(f"{r.investimento}" + (f" · {r.observacao}" if r.observacao else ""))
                cor = ui.VERMELHO if r.tipo == "resgate" else ui.VERDE
                c3.markdown(
                    f"<div style='text-align:right;color:{cor};font-variant-numeric:tabular-nums'>"
                    f"{'-' if r.tipo == 'resgate' else '+'} {ui.brl(r.valor)}"
                    f"<div style='font-size:.7rem;color:{ui.CINZA}'>{r.tipo}</div></div>",
                    unsafe_allow_html=True,
                )
                if c4.button("✕", key=f"delmov{r.id}"):
                    repo.excluir_movimento_investimento(r.id)
                    st.rerun()

if not invs.empty and patrimonio:
    st.divider()
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Composição")
        por_tipo = invs.groupby("tipo", as_index=False)["saldo"].sum()
        por_tipo = por_tipo[por_tipo["saldo"] > 0]
        fig = go.Figure(
            go.Pie(
                labels=por_tipo["tipo"], values=por_tipo["saldo"], hole=0.6,
                textinfo="label+percent",
                marker=dict(colors=ui.SERIE, line=dict(color=ui.SUPERFICIE, width=2)),
                hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>",
            )
        )
        fig.update_layout(ui.PLOTLY)
        fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10), showlegend=False)
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Evolução")
        evo = repo.evolucao_patrimonio(12)
        fig = go.Figure(
            go.Scatter(
                x=evo["mes"], y=evo["patrimonio"], mode="lines+markers",
                line=dict(color=ui.VERDE, width=2.5), fill="tozeroy",
                fillcolor="rgba(52,211,153,0.12)",
                marker=dict(size=7, line=dict(color=ui.SUPERFICIE, width=1.5)),
            )
        )
        fig.update_layout(ui.PLOTLY)
        fig.update_layout(
            height=300, margin=dict(t=10, b=10, l=10, r=10),
            yaxis=dict(tickprefix="R$ "), xaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, width="stretch")
