"""Versão do sistema.

Fonte única: a tela de login lê daqui, e o CHANGELOG.md conta o que mudou em
cada número. Versionamento semântico — MAIOR.MENOR.CORREÇÃO:

- CORREÇÃO (0.2.1): conserto de bug, sem mudança no que o app faz.
- MENOR (0.3.0): funcionalidade nova, sem quebrar o que já existia.
- MAIOR (1.0.0): mudança que exige alguma ação de quem já usa.

Toda correção ou funcionalidade nova sobe o número aqui e ganha uma linha no
CHANGELOG.md, no mesmo commit.
"""
from __future__ import annotations

__version__ = "0.5.0"
