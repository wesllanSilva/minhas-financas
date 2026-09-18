"""O app usa recursos recentes do Streamlit.

Com uma versão antiga instalada, o app sobe e só quebra na tela que usa o
recurso — em produção, longe de quem fez a mudança. Estes testes falham aqui,
com o nome do recurso que falta.
"""
from __future__ import annotations

import inspect

import streamlit as st


def test_container_aceita_key():
    """Os cards clicáveis do Painel dependem da classe st-key-<key> no DOM."""
    assert "key" in inspect.signature(st.container).parameters


def test_recursos_usados_existem():
    for nome in ("dialog", "logo", "navigation", "Page", "popover", "toast"):
        assert hasattr(st, nome), f"st.{nome} não existe nesta versão do Streamlit"


def test_piso_do_requirements_bate_com_o_instalado():
    """Impede o requirements pedir menos do que o app realmente precisa."""
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parent.parent
    texto = (raiz / "requirements.txt").read_text(encoding="utf-8")
    piso = re.search(r"^streamlit>=([\d.]+)", texto, re.M)
    assert piso, "requirements.txt não fixa um piso para o streamlit"

    def partes(v):
        return tuple(int(x) for x in v.split(".")[:3])

    assert partes(st.__version__) >= partes(piso.group(1)), (
        f"streamlit instalado ({st.__version__}) é anterior ao piso do "
        f"requirements ({piso.group(1)})"
    )
