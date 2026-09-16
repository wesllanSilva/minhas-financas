"""Conexão com o banco.

Sem configuração nenhuma o app roda em SQLite local (arquivo `data/financas.db`).
Definindo `DATABASE_URL` (nos secrets do Streamlit ou como variável de ambiente)
ele usa Postgres — é assim que os dados sobrevivem aos reinícios na nuvem.
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Categoria, Conta

CATEGORIAS_PADRAO = [
    ("Aluguel", "despesa", "#fb7185"),
    ("Moradia", "despesa", "#f472b6"),
    ("Mercearia", "despesa", "#34d399"),
    ("Açougue", "despesa", "#2dd4bf"),
    ("Cerveja/Refrigerante", "despesa", "#a3e635"),
    ("Combustível", "despesa", "#fb923c"),
    ("Uber", "despesa", "#fbbf24"),
    ("Telefone/Internet", "despesa", "#38bdf8"),
    ("Streaming", "despesa", "#60a5fa"),
    ("Saúde/Higiene", "despesa", "#9d8cff"),
    ("Presente/Compras", "despesa", "#c084fc"),
    ("Lazer", "despesa", "#e879f9"),
    ("Seguro", "despesa", "#7dd3fc"),
    ("Educação", "despesa", "#5eead4"),
    ("Investimento", "despesa", "#86efac"),
    ("Outros", "despesa", "#9b97b8"),
    ("Salário", "receita", "#34d399"),
    ("VR/VA", "receita", "#5eead4"),
    ("Bonificação", "receita", "#a3e635"),
    ("Rendimentos", "receita", "#38bdf8"),
    ("Outras receitas", "receita", "#9b97b8"),
]


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:  # st.secrets só existe quando o Streamlit está rodando
            import streamlit as st

            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    if not url:
        Path("data").mkdir(exist_ok=True)
        return "sqlite:///data/financas.db"

    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = database_url()
        kwargs: dict = {"pool_pre_ping": True, "future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)()


def reiniciar_engine() -> None:
    """Esquece a conexão atual. Usado pelos testes ao trocar de banco."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def semear_workspace(s: Session, workspace_id: int) -> None:
    """Dá a uma carteira nova as categorias padrão e uma conta para começar.

    Recebe a sessão aberta em vez de abrir a sua: quem chama está criando o
    workspace na mesma transação, e semear fora dela deixaria uma carteira pela
    metade caso o commit falhasse.
    """
    s.add_all(
        Categoria(workspace_id=workspace_id, nome=n, tipo=t, cor=c)
        for n, t, c in CATEGORIAS_PADRAO
    )
    s.add(
        Conta(
            workspace_id=workspace_id,
            nome="Conta corrente",
            tipo="Conta corrente",
            saldo_inicial=0,
        )
    )


def usando_sqlite() -> bool:
    return database_url().startswith("sqlite")
