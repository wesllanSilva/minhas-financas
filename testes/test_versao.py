"""A versão é mostrada a quem entra, então precisa estar sempre coerente."""
from __future__ import annotations

import re
from pathlib import Path

from core.versao import __version__

RAIZ = Path(__file__).resolve().parent.parent


def test_versao_segue_o_padrao_semantico():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__), __version__


def test_versao_atual_esta_no_changelog():
    """Impede subir o número e esquecer de contar o que mudou."""
    changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {__version__}" in changelog


def test_tela_de_login_mostra_a_versao(usuario):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=90).run()
    texto = " ".join(m.value for m in at.markdown)
    assert __version__ in texto
