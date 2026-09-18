"""Wstack Finance — painel do mês."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from core import repo, ui
from core.forms import formulario_lancamento

competencia = ui.seletor_mes()
resumo = repo.resumo_mes(competencia)
saldo = repo.saldo_total()

st.title("Painel")
st.caption(repo.rotulo_mes(competencia))

cor_saldo = ui.VIOLETA_BRILHO if saldo >= 0 else ui.VERMELHO
cor_balanco = ui.CIANO if resumo["balanco"] >= 0 else ui.AMBAR
aberto = ui.painel_interativo(
    [
        ("saldo", "Saldo em conta", ui.brl(saldo), cor_saldo, "Somando todas as contas"),
        ("receitas", "Receitas do mês", ui.brl(resumo["receitas"]), ui.VERDE, "Tudo que entrou"),
        ("despesas", "Despesas do mês", ui.brl(resumo["despesas"]), ui.VERMELHO,
         f"{ui.brl(resumo['a_pagar'])} ainda em aberto"),
        ("balanco", "Balanço", ui.brl(resumo["balanco"]), cor_balanco, "Receitas menos despesas"),
    ]
)

# --------------------------------------------------------------------------- #
# Detalhe do card aberto
# --------------------------------------------------------------------------- #
if aberto == "saldo":
    contas = repo.saldo_por_conta()
    linhas = "".join(
        ui.linha_detalhe(
            r.nome, ui.brl(r.saldo), ui.VERDE if r.saldo >= 0 else ui.VERMELHO,
            sub=f"{r.tipo} · inicial {ui.brl(r.saldo_inicial)} + {ui.brl(r.entradas)} − {ui.brl(r.saidas)}",
        )
        for r in contas.itertuples()
    ) or "<div class='linha'><div class='nome'>Nenhuma conta ativa.</div></div>"
    ui.detalhe(
        "Por conta", linhas, cor_saldo,
        "Só o que já foi pago ou recebido. Compras no cartão entram na fatura, não aqui.",
    )

elif aberto in ("receitas", "despesas"):
    tipo = "receita" if aberto == "receitas" else "despesa"
    cor = ui.VERDE if tipo == "receita" else ui.VERMELHO
    cats = repo.por_categoria(competencia, tipo)
    if cats.empty:
        linhas = f"<div class='linha'><div class='nome'>Nenhuma {tipo} neste mês.</div></div>"
    else:
        total = float(cats["total"].sum()) or 1.0
        linhas = "".join(
            ui.linha_detalhe(
                r.categoria, ui.brl(r.total), cor, ponto=r.cor,
                sub=(
                    f"{r.total / total * 100:.0f}% · {r.itens} lançamento(s)"
                    + (f" · {ui.brl(r.pendente)} em aberto" if r.pendente > 0.005 else "")
                ),
            )
            for r in cats.itertuples()
        )
    ui.detalhe(f"{aberto.capitalize()} por categoria", linhas, cor)

elif aberto == "balanco":
    serie = repo.serie_mensal(4, ate=competencia)
    linhas = "".join(
        ui.linha_detalhe(
            r.mes.capitalize(), ui.brl(r.saldo), ui.VERDE if r.saldo >= 0 else ui.VERMELHO,
            sub=f"{ui.brl(r.receitas)} entrou · {ui.brl(r.despesas)} saiu",
        )
        for r in serie.sort_values("competencia", ascending=False).itertuples()
    )
    media = float(serie["saldo"].mean()) if not serie.empty else 0.0
    ui.detalhe(
        "Este mês e os três anteriores", linhas, cor_balanco,
        f"Média dos quatro: {ui.brl(media)} por mês.",
    )

with st.expander("Lançar receita ou despesa", expanded=False):
    if formulario_lancamento("dash", data_padrao=competencia):
        st.success("Lançamento salvo.")
        st.rerun()

esquerda, direita = st.columns([1, 1])

# --------------------------------------------------------------------------- #
# Despesas por categoria
# --------------------------------------------------------------------------- #
with esquerda:
    st.subheader("Para onde o dinheiro foi")
    df = repo.transacoes(competencia, tipo="despesa")
    if df.empty:
        ui.vazio("Nenhuma despesa neste mês.", "Use o formulário acima para lançar a primeira.")
    else:
        por_cat = (
            df.groupby(["categoria", "cor"], as_index=False)["valor"]
            .sum()
            .sort_values("valor", ascending=False)
        )
        fig = go.Figure(
            go.Pie(
                labels=por_cat["categoria"],
                values=por_cat["valor"],
                hole=0.62,
                marker=dict(colors=por_cat["cor"].tolist(), line=dict(color=ui.SUPERFICIE, width=2)),
                textinfo="none",
                hovertemplate="%{label}<br>R$ %{value:,.2f} · %{percent}<extra></extra>",
            )
        )
        fig.update_layout(ui.PLOTLY)
        fig.update_layout(
            height=300,
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False,
            annotations=[
                dict(
                    text=f"<b>{ui.brl(por_cat['valor'].sum())}</b>",
                    x=0.5, y=0.52, font_size=18, showarrow=False,
                    font=dict(family="JetBrains Mono, monospace", color=ui.TINTA),
                ),
                dict(text="no mês", x=0.5, y=0.42, font_size=11, font_color=ui.CINZA, showarrow=False),
            ],
        )
        st.plotly_chart(fig, width="stretch")

        total = por_cat["valor"].sum()
        linhas = "".join(
            f"<div style='display:flex;align-items:center;gap:9px;padding:5px 0;"
            f"border-bottom:1px solid {ui.LINHA}'>"
            f"<span style='width:9px;height:9px;border-radius:50%;background:{r.cor}'></span>"
            f"<span style='flex:1'>{r.categoria}</span>"
            f"<span style='color:{ui.CINZA};font-size:.8rem'>{r.valor / total * 100:.0f}%</span>"
            f"<span class='dinheiro'>{ui.brl(r.valor)}</span>"
            f"</div>"
            for r in por_cat.head(8).itertuples()
        )
        st.markdown(f"<div class='ficha'>{linhas}</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Orçamento e cartões
# --------------------------------------------------------------------------- #
with direita:
    st.subheader("Orçamento do mês")
    orc = repo.orcamento_mes(competencia)
    if orc.empty or orc["planejado"].sum() == 0:
        ui.vazio(
            "Você ainda não definiu metas para este mês.",
            "Abra Planejamento e copie as metas do mês passado em um clique.",
        )
    else:
        com_meta = orc[orc["planejado"] > 0].sort_values("uso", ascending=False)
        blocos = []
        for r in com_meta.head(7).itertuples():
            cor = ui.cor_do_uso(r.uso)
            blocos.append(
                f"<div style='padding:8px 0'>"
                f"<div style='display:flex;justify-content:space-between;font-size:.86rem'>"
                f"<span>{r.categoria}</span>"
                f"<span class='dinheiro' style='color:{cor}'>"
                f"{ui.brl(r.gasto)} <span style='color:{ui.CINZA}'>/ {ui.brl(r.planejado)}</span></span>"
                f"</div>{ui.barra(r.uso, cor)}</div>"
            )
        st.markdown(f"<div class='ficha'>{''.join(blocos)}</div>", unsafe_allow_html=True)

    st.subheader("Faturas")
    fat = repo.faturas(competencia)
    if fat.empty:
        ui.vazio("Nenhum cartão cadastrado.", "Cadastre em Configurações para acompanhar as faturas.")
    else:
        blocos = []
        for r in fat.itertuples():
            cor = ui.cor_do_uso(r.uso) if r.limite else ui.VERDE
            extra = f"limite {ui.brl(r.limite)}" if r.limite else "sem limite definido"
            blocos.append(
                f"<div style='padding:8px 0'>"
                f"<div style='display:flex;justify-content:space-between;font-size:.86rem'>"
                f"<span>{r.cartao}</span>"
                f"<span class='dinheiro'>{ui.brl(r.total)}</span>"
                f"</div>{ui.barra(r.uso, cor) if r.limite else ''}"
                f"<div style='font-size:.72rem;color:{ui.CINZA};margin-top:3px'>{extra}</div></div>"
            )
        st.markdown(f"<div class='ficha'>{''.join(blocos)}</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Histórico
# --------------------------------------------------------------------------- #
st.subheader("Últimos 12 meses")
serie = repo.serie_mensal(12, ate=competencia)
fig = go.Figure()
fig.add_bar(x=serie["mes"], y=serie["receitas"], name="Receitas", marker_color=ui.VERDE)
fig.add_bar(x=serie["mes"], y=serie["despesas"], name="Despesas", marker_color=ui.VERMELHO)
fig.add_scatter(
    x=serie["mes"], y=serie["saldo"], name="Sobra", mode="lines+markers",
    line=dict(color=ui.VIOLETA_BRILHO, width=2.5),
    marker=dict(size=7, color=ui.VIOLETA_BRILHO, line=dict(color=ui.SUPERFICIE, width=1.5)),
)
fig.update_traces(marker_line_width=0, selector=dict(type="bar"))
fig.update_layout(ui.PLOTLY)
fig.update_layout(
    barmode="group",
    bargap=0.28,
    height=320,
    margin=dict(t=10, b=10, l=10, r=10),
    legend=dict(orientation="h", y=1.12, x=0),
    yaxis=dict(tickprefix="R$ "),
    xaxis=dict(showgrid=False),
)
st.plotly_chart(fig, width="stretch")

with st.sidebar:
    st.caption("Wstack Finance · dados só seus")
    if repo.transacoes().empty:
        st.info("Comece importando sua planilha em **Configurações → Importar**.")
