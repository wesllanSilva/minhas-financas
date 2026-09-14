"""Peças de interface reaproveitadas em todas as páginas."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from . import auth, cookies, escopo, repo
from .versao import __version__

VERDE = "#0F5D4A"
VERMELHO = "#A8352A"
AMBAR = "#B5852B"
TINTA = "#16241F"
CINZA = "#6B7A75"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

html, body, .stApp, button, input, textarea, select {
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
}

/* Os ícones do Streamlit são ligatures da fonte Material Symbols: o span
   contém o nome do ícone em texto puro. Se a fonte for trocada, a ligature
   não acontece e o nome ("dashboard", "settings") vaza por cima do rótulo. */
[data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded' !important;
}

.stApp { background: #F1F3F2; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #DFE5E2; }
[data-testid="stHeader"] { background: transparent; }

h1 { font-size: 1.9rem; font-weight: 600; letter-spacing: -0.02em; color: #16241F; }
h2 { font-size: 1.25rem; font-weight: 600; color: #16241F; }
h3 { font-size: 1.02rem; font-weight: 600; color: #16241F; }

.painel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 12px;
    margin: 4px 0 22px 0;
}
.ficha {
    background: #FFFFFF;
    border: 1px solid #E2E8E5;
    border-radius: 10px;
    padding: 14px 16px 15px 16px;
}
.ficha .rotulo { font-size: .78rem; color: #6B7A75; margin-bottom: 4px; }
.ficha .cifra {
    font-size: 1.5rem; font-weight: 600; letter-spacing: -0.02em;
    font-variant-numeric: tabular-nums;
}
.ficha .nota { font-size: .74rem; color: #8A9691; margin-top: 3px; }
.ficha.destaque { border-left: 3px solid #0F5D4A; }

.trilho { height: 6px; background: #E6EBE9; border-radius: 3px; overflow: hidden; }
.trilho > div { height: 100%; border-radius: 3px; }

.tag {
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: .74rem; font-weight: 500; color: #fff;
}

div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
.stDataFrame { font-variant-numeric: tabular-nums; }
footer, #MainMenu { visibility: hidden; }

/* O componente que grava o cookie não desenha nada, mas ainda ocupa a altura
   de um bloco. Sem isto sobra um buraco no topo da página. */
iframe[title="streamlit.components.v1.html"][height="0"] { display: none; }
</style>
"""


def brl(valor: float) -> str:
    negativo = valor < 0
    txt = f"{abs(valor):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{'-' if negativo else ''}R$ {txt}"


def configurar_pagina(titulo: str, icone: str = "💰") -> None:
    st.set_page_config(page_title=f"{titulo} · Minhas Finanças", page_icon=icone, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


def usuario_logado() -> dict | None:
    """Quem está usando o app agora, ou None.

    Tenta a memória da sessão primeiro; se ela estiver vazia (foi um F5), cai
    no cookie e restaura a partir dele.
    """
    if st.session_state.get("_usuario"):
        return st.session_state["_usuario"]

    usuario = auth.usuario_da_sessao(cookies.ler())
    if usuario is None:
        return None

    dados = {"id": usuario.id, "nome": usuario.nome, "email": usuario.email}
    st.session_state["_usuario"] = dados
    return dados


def _entrar(usuario, lembrar: bool = True) -> None:
    st.session_state["_usuario"] = {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
    }
    if lembrar:
        token = auth.abrir_sessao(usuario.id)
        st.session_state["_token"] = token
        cookies.gravar(token, auth.DIAS_DE_SESSAO)


def sair() -> None:
    auth.fechar_sessao(st.session_state.get("_token") or cookies.ler())
    cookies.apagar()
    for chave in ("_usuario", "_token", escopo.CHAVE, "competencia"):
        st.session_state.pop(chave, None)


def exigir_login() -> bool:
    """Garante alguém logado e um workspace ativo. False = a tela de login está aberta."""
    usuario = usuario_logado()
    if usuario is None:
        _tela_de_login()
        return False
    return _definir_workspace(usuario)


def _rodape_versao() -> None:
    st.markdown(
        f"<div style='margin-top:26px;font-size:.76rem;color:#8A9691'>"
        f"Minhas Finanças · versão {__version__}</div>",
        unsafe_allow_html=True,
    )


def _tela_de_login() -> None:
    st.title("Minhas Finanças")

    if not auth.existe_algum_usuario():
        st.caption("Primeiro acesso: crie a sua conta.")
        _form_cadastro(primeiro=True)
        _rodape_versao()
        return

    st.caption("Entre para ver seus lançamentos.")
    entrar, criar = st.tabs(["Entrar", "Criar conta"])

    with entrar:
        with st.form("login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            lembrar = st.checkbox("Continuar conectado neste navegador", value=True)
            if st.form_submit_button("Entrar", width="stretch"):
                usuario = auth.autenticar(email, senha)
                if usuario is None:
                    st.error("E-mail ou senha incorretos.")
                else:
                    _entrar(usuario, lembrar)
                    st.rerun()

    with criar:
        _form_cadastro()

    _rodape_versao()


def _form_cadastro(primeiro: bool = False) -> None:
    with st.form("cadastro"):
        nome = st.text_input("Seu nome")
        email = st.text_input("E-mail", key="cad_email")
        senha = st.text_input("Senha", type="password", key="cad_senha")
        repetir = st.text_input("Repita a senha", type="password")
        rotulo = "Criar minha conta" if primeiro else "Criar conta"
        if st.form_submit_button(rotulo, width="stretch"):
            if senha != repetir:
                st.error("As duas senhas não são iguais.")
                return
            try:
                auth.criar_usuario(email, nome, senha)
            except auth.ErroDeAuth as erro:
                st.error(str(erro))
                return
            usuario = auth.autenticar(email, senha)
            if usuario:
                _entrar(usuario)
                st.rerun()


def _definir_workspace(usuario: dict) -> bool:
    """Escolhe a carteira ativa e a publica no escopo. Roda a cada rerun."""
    carteiras = auth.workspaces_de(usuario["id"])
    if not carteiras:  # só acontece se alguém apagar o vínculo no banco
        st.error("Sua conta não está ligada a nenhuma carteira. Fale com o dono.")
        if st.button("Sair"):
            sair()
            st.rerun()
        return False

    ids = [c["id"] for c in carteiras]
    atual = escopo.atual_ou_none()
    # Confere a cada rerun: o vínculo pode ter sido removido desde o login.
    if atual not in ids or not auth.pode_acessar(usuario["id"], atual):
        atual = ids[0]
    escopo.definir(atual)
    st.session_state["_carteiras"] = carteiras
    return True


def barra_lateral_conta() -> None:
    """Seletor de carteira e botão de sair. Chamado no topo de cada página."""
    usuario = st.session_state.get("_usuario")
    if not usuario:
        return
    carteiras = st.session_state.get("_carteiras") or []

    with st.sidebar:
        if len(carteiras) > 1:
            ids = [c["id"] for c in carteiras]
            nomes = {c["id"]: c["nome"] for c in carteiras}
            atual = escopo.atual_ou_none()
            escolhida = st.selectbox(
                "Carteira",
                ids,
                index=ids.index(atual) if atual in ids else 0,
                format_func=lambda i: nomes[i],
                key="_seletor_carteira",
            )
            if escolhida != atual and auth.pode_acessar(usuario["id"], escolhida):
                escopo.definir(escolhida)
                st.rerun()
        elif carteiras:
            st.caption(carteiras[0]["nome"])

        esq, dir_ = st.columns([3, 2])
        esq.caption(usuario["nome"])
        if dir_.button("Sair", key="_sair", width="stretch"):
            sair()
            st.rerun()
        st.divider()


def seletor_mes() -> dt.date:
    """Navegação de mês na barra lateral, compartilhada entre as páginas."""
    hoje = dt.date.today()
    if "competencia" not in st.session_state:
        st.session_state["competencia"] = repo.comp(hoje.year, hoje.month)

    atual: dt.date = st.session_state["competencia"]
    with st.sidebar:
        st.markdown("#### Mês")
        esq, meio, dir_ = st.columns([1, 3, 1])
        if esq.button("‹", width="stretch", key="mes_ant"):
            st.session_state["competencia"] = repo.somar_meses(atual, -1)
            st.rerun()
        meio.markdown(
            f"<div style='text-align:center;padding-top:6px;font-weight:600'>"
            f"{repo.rotulo_mes(atual)}</div>",
            unsafe_allow_html=True,
        )
        if dir_.button("›", width="stretch", key="mes_prox"):
            st.session_state["competencia"] = repo.somar_meses(atual, 1)
            st.rerun()
        if atual != repo.comp(hoje.year, hoje.month):
            if st.button("Voltar para o mês atual", width="stretch"):
                st.session_state["competencia"] = repo.comp(hoje.year, hoje.month)
                st.rerun()
        st.divider()
    return st.session_state["competencia"]


def painel(fichas: list[tuple[str, str, str, str]]) -> None:
    """Linha de cartões: (rótulo, valor, cor do valor, nota)."""
    blocos = "".join(
        f"<div class='ficha'><div class='rotulo'>{rotulo}</div>"
        f"<div class='cifra' style='color:{cor}'>{valor}</div>"
        f"<div class='nota'>{nota}</div></div>"
        for rotulo, valor, cor, nota in fichas
    )
    st.markdown(f"<div class='painel'>{blocos}</div>", unsafe_allow_html=True)


def barra(pct: float, cor: str = VERDE) -> str:
    pct = max(0.0, min(pct, 100.0))
    return f"<div class='trilho'><div style='width:{pct:.1f}%;background:{cor}'></div></div>"


def cor_do_uso(uso: float) -> str:
    if uso >= 100:
        return VERMELHO
    if uso >= 80:
        return AMBAR
    return VERDE


def vazio(mensagem: str, acao: str = "") -> None:
    st.markdown(
        f"<div class='ficha' style='text-align:center;padding:34px 16px'>"
        f"<div style='color:{CINZA}'>{mensagem}</div>"
        f"{f'<div style=\"margin-top:6px;font-size:.82rem;color:#8A9691\">{acao}</div>' if acao else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )
