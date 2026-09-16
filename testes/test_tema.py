"""Identidade visual: as imagens entram na página e o CSS não quebra o app."""
from __future__ import annotations

from core import tema


def test_logo_e_fundo_estao_no_repositorio():
    """As duas imagens são parte do produto: sem elas a tela de login fica pela metade."""
    assert tema.data_uri("logo_w.png").startswith("data:image/png;base64,")
    assert tema.data_uri("bg_login.jpg").startswith("data:image/jpeg;base64,")


def test_imagem_que_falta_nao_derruba_a_pagina():
    assert tema.data_uri("nao-existe.png") == ""
    assert "url(" not in tema.css_login().replace('url("data:', "")


def test_css_do_login_embute_o_fundo():
    assert "bg_login" not in tema.css_login()  # nunca por caminho: sempre embutido
    assert 'url("data:image/jpeg;base64,' in tema.css_login()


def test_marca_tem_logo_e_nome():
    html = tema.marca_html("login")
    assert "<img" in html and "Finance" in html


def test_paleta_de_series_nao_repete_cor():
    assert len(set(tema.SERIE)) == len(tema.SERIE) >= 8
