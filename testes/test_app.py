"""O app inteiro, da porta de entrada para dentro.

Os testes de tela carregam cada página já logada. Aqui o alvo é o que vem
antes: cadastro, login, e a garantia de que sem login nenhuma página aparece.
É o trecho que `test_telas` não cobre porque pula justamente o `app.py`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import auth

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=90)


def _textos(at: AppTest) -> str:
    return " ".join(
        [t.value for t in at.title]
        + [c.value for c in at.caption]
        + [m.value for m in at.markdown]
    )


@pytest.fixture
def sem_usuarios(monkeypatch):
    """Finge um banco recém-criado, sem nenhuma conta ainda."""
    monkeypatch.setattr(auth, "existe_algum_usuario", lambda: False)


def test_primeiro_acesso_pede_para_criar_a_conta(sem_usuarios):
    at = _app().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "Primeiro acesso" in _textos(at)
    assert [b.label for b in at.button] == ["Criar minha conta"]


def test_com_conta_existente_a_porta_e_o_login(usuario):
    at = _app().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    rotulos = [i.label for i in at.text_input]
    assert "E-mail" in rotulos and "Senha" in rotulos


def test_sem_login_nenhuma_pagina_carrega(usuario):
    """O `st.stop` tem que valer: nada de painel para quem não entrou."""
    at = _app().run()
    texto = _textos(at)
    assert "Painel" not in texto
    assert "Saldo em conta" not in texto


def test_senha_errada_nao_entra(usuario, emails):
    at = _app().run()
    at.text_input[0].set_value("qualquer@exemplo.test")
    at.text_input[1].set_value("senha-errada")
    at.button[0].click().run()

    assert any("incorretos" in e.value for e in at.error)


def test_login_correto_abre_o_app(usuario, emails):
    """Caminho feliz: entra e o painel aparece."""
    uid, _ = usuario
    from core.db import get_session
    from core.models import Usuario

    with get_session() as s:
        email = s.get(Usuario, uid).email

    at = _app().run()
    at.text_input[0].set_value(email)
    at.text_input[1].set_value("senha-de-teste-123")
    at.button[0].click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["_usuario"]["id"] == uid


def test_sessao_salva_permite_entrar_sem_digitar_nada(usuario, monkeypatch):
    """É o F5: o `session_state` some, o cookie fica, e o login se refaz sozinho."""
    from core import cookies

    uid, _ = usuario
    token = auth.abrir_sessao(uid)
    monkeypatch.setattr(cookies, "ler", lambda nome=cookies.NOME_COOKIE: token)

    at = _app().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.session_state["_usuario"]["id"] == uid


def test_cookie_invalido_cai_na_tela_de_login(usuario, monkeypatch):
    from core import cookies

    monkeypatch.setattr(cookies, "ler", lambda nome=cookies.NOME_COOKIE: "token-forjado")

    at = _app().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert "_usuario" not in at.session_state
    assert "E-mail" in [i.label for i in at.text_input]
