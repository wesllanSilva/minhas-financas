"""Peças de interface reaproveitadas em todas as páginas."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from . import auth, cookies, escopo, repo, tema
from .versao import __version__

# Nomes que as telas já usam. Os valores vêm da identidade Wstack (core/tema.py).
VERDE = tema.OK
VERMELHO = tema.ERRO
AMBAR = tema.AVISO
TINTA = tema.TINTA
CINZA = tema.CINZA
VIOLETA = tema.VIOLETA
VIOLETA_BRILHO = tema.VIOLETA_BRILHO
CIANO = tema.CIANO
SERIE = tema.SERIE
LINHA = tema.LINHA
GRADE = tema.GRADE
SUPERFICIE = tema.SURFACE
PLOTLY = tema.PLOTLY_LAYOUT


def brl(valor: float) -> str:
    negativo = valor < 0
    txt = f"{abs(valor):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{'-' if negativo else ''}R$ {txt}"


def configurar_pagina(titulo: str) -> None:
    st.set_page_config(
        page_title=f"{titulo} · {tema.NOME}",
        page_icon=tema.logo_pil() or "💰",
        layout="wide",
    )
    st.markdown(tema.CSS_BASE, unsafe_allow_html=True)
    logo = tema.logo_pil()
    if logo is not None:
        # Fica acima do menu de navegação, que o st.navigation desenha antes de
        # qualquer conteúdo nosso na barra lateral.
        st.logo(logo, size="large")


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


def _tela_de_login() -> None:
    st.markdown(tema.css_login(), unsafe_allow_html=True)
    st.markdown(
        tema.marca_html("login").replace(
            "</div></div>", f"</div><div class='versao'>v{__version__}</div></div>"
        ),
        unsafe_allow_html=True,
    )

    if not auth.existe_algum_usuario():
        st.caption("Primeiro acesso: crie a sua conta.")
        _form_cadastro(primeiro=True)
        return

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

        st.markdown(
            f"<div class='usuario'><i></i><b>{usuario['nome']}</b></div>",
            unsafe_allow_html=True,
        )
        if st.button("Sair", key="_sair", width="stretch", type="secondary"):
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
        f"<div class='ficha resumo' style='--acento:{cor}'><div class='rotulo'>{rotulo}</div>"
        f"<div class='cifra' style='color:{cor}'>{valor}</div>"
        f"<div class='nota'>{nota}</div></div>"
        for rotulo, valor, cor, nota in fichas
    )
    st.markdown(f"<div class='painel'>{blocos}</div>", unsafe_allow_html=True)


def painel_interativo(
    fichas: list[tuple[str, str, str, str, str]], chave: str = "detalhe"
) -> str | None:
    """Cards de resumo clicáveis: (id, rótulo, valor, cor, nota).

    Clicar abre o card; clicar de novo fecha. Devolve o id do card aberto.
    Quem chama desenha o detalhe logo abaixo — o painel só cuida do clique.
    """
    aberto = st.session_state.get(chave)
    colunas = st.columns(len(fichas))
    for coluna, (id_, rotulo, valor, cor, nota) in zip(colunas, fichas):
        with coluna, st.container(key=f"ficha_{id_}"):
            ativa = " ativa" if aberto == id_ else ""
            st.markdown(
                f"<div class='painel'><div class='ficha resumo{ativa}' style='--acento:{cor}'>"
                f"<span class='abrir'>{'fechar' if ativa else 'detalhes'}</span>"
                f"<div class='rotulo'>{rotulo}</div>"
                f"<div class='cifra' style='color:{cor}'>{valor}</div>"
                f"<div class='nota'>{nota}</div></div></div>",
                unsafe_allow_html=True,
            )
            if st.button(rotulo, key=f"btn_ficha_{id_}", width="stretch"):
                st.session_state[chave] = None if aberto == id_ else id_
                st.rerun()
    return aberto


def detalhe(titulo: str, linhas_html: str, cor: str, rodape: str = "") -> None:
    """Painel que abre abaixo dos cards."""
    fim = f"<div class='rodape'>{rodape}</div>" if rodape else ""
    st.markdown(
        f"<div class='detalhe' style='--acento:{cor}'><div class='titulo'>{titulo}</div>"
        f"{linhas_html}{fim}</div>",
        unsafe_allow_html=True,
    )


def linha_detalhe(nome: str, valor: str, cor_valor: str, sub: str = "", ponto: str = "") -> str:
    p = f"<span class='ponto' style='background:{ponto}'></span>" if ponto else ""
    s = f"<div class='sub'>{sub}</div>" if sub else ""
    return (
        f"<div class='linha'>{p}<div class='nome'>{nome}{s}</div>"
        f"<span class='dinheiro' style='color:{cor_valor}'>{valor}</span></div>"
    )


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
        f"{f'<div style=\"margin-top:6px;font-size:.82rem;color:{CINZA}\">{acao}</div>' if acao else ''}"
        f"</div>",
        unsafe_allow_html=True,
    )
