"""Troca as cores das categorias existentes pela paleta do tema escuro.

As categorias criadas antes da 0.3.0 vieram com cores terrosas, feitas para o
fundo claro — no escuro somem. Este script, para cada carteira:

- categoria com o mesmo nome de uma categoria padrão recebe a cor padrão;
- as demais recebem, em ordem, cores da paleta `tema.SERIE`, pulando as que a
  carteira já usa, para não repetir cor entre categorias vizinhas.

Rode sem argumento para ver o que mudaria; `--aplicar` grava.

    python ferramentas/recolorir_categorias.py
    python ferramentas/recolorir_categorias.py --aplicar

O banco é o mesmo que o app usa (DATABASE_URL, ou o SQLite local).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from core import tema  # noqa: E402
from core.db import CATEGORIAS_PADRAO, database_url, get_session  # noqa: E402
from core.models import Categoria, Workspace  # noqa: E402

PADRAO = {(nome.lower(), tipo): cor for nome, tipo, cor in CATEGORIAS_PADRAO}


def planejar() -> list[tuple[Categoria, str, str]]:
    """Devolve (categoria, cor_atual, cor_nova) para cada categoria que mudaria."""
    mudancas = []
    with get_session() as s:
        for ws in s.scalars(select(Workspace).order_by(Workspace.id)).all():
            cats = s.scalars(
                select(Categoria)
                .where(Categoria.workspace_id == ws.id)
                .order_by(Categoria.tipo, Categoria.nome)
            ).all()
            usadas: set[str] = set()
            fila = iter(tema.SERIE * 4)  # sobra para carteiras com muitas categorias
            for c in cats:
                nova = PADRAO.get((c.nome.lower(), c.tipo))
                if nova is None:
                    nova = next(x for x in fila if x not in usadas)
                usadas.add(nova)
                if nova.lower() != (c.cor or "").lower():
                    mudancas.append((c, c.cor, nova))
    return mudancas


def main() -> int:
    p = argparse.ArgumentParser(description="Recolore categorias com a paleta escura")
    p.add_argument("--aplicar", action="store_true", help="grava (sem isso, só relata)")
    args = p.parse_args()

    print(f"\nBanco: {database_url().split('@')[-1]}\n")
    mudancas = planejar()
    if not mudancas:
        print("Nada a fazer: todas as categorias já estão na paleta.")
        return 0

    for c, antiga, nova in mudancas:
        print(f"  carteira {c.workspace_id:>3}  {c.tipo:8} {c.nome:28} {antiga or '—':9} -> {nova}")
    print(f"\n{len(mudancas)} categoria(s) mudariam de cor.")

    if not args.aplicar:
        print("Nada foi alterado. Rode de novo com --aplicar para gravar.")
        return 0

    with get_session() as s:
        for c, _, nova in mudancas:
            s.get(Categoria, c.id).cor = nova
        s.commit()
    print("Gravado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
