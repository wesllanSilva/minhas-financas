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
    ("Aluguel", "despesa", "#8C4A3F"),
    ("Moradia", "despesa", "#A65D50"),
    ("Mercearia", "despesa", "#3E7D5A"),
    ("Açougue", "despesa", "#5C8F6E"),
    ("Cerveja/Refrigerante", "despesa", "#7FA88C"),
    ("Combustível", "despesa", "#B07A2E"),
    ("Uber", "despesa", "#C99B45"),
    ("Telefone/Internet", "despesa", "#3F6E88"),
    ("Streaming", "despesa", "#5A88A3"),
    ("Saúde/Higiene", "despesa", "#7B5EA7"),
    ("Presente/Compras", "despesa", "#A37BB8"),
    ("Lazer", "despesa", "#C46A8D"),
    ("Seguro", "despesa", "#4C6B75"),
    ("Educação", "despesa", "#2F6F6B"),
    ("Investimento", "despesa", "#1F5D4A"),
    ("Outros", "despesa", "#8A8F94"),
    ("Salário", "receita", "#1F5D4A"),
    ("VR/VA", "receita", "#3E7D5A"),
    ("Bonificação", "receita", "#5C8F6E"),
    ("Rendimentos", "receita", "#7FA88C"),
    ("Outras receitas", "receita", "#8A8F94"),
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
