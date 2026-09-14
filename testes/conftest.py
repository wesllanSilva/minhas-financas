"""Infraestrutura comum dos testes.

Cada execução usa um SQLite descartável numa pasta temporária, então o banco de
verdade (e o Postgres de produção) nunca é tocado.
"""
from __future__ import annotations

import itertools
import os
import uuid

import pytest


@pytest.fixture(scope="session", autouse=True)
def banco_temporario(tmp_path_factory):
    """Aponta o app para um banco vazio antes de qualquer import de `core`."""
    destino = tmp_path_factory.mktemp("banco") / "testes.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{destino.as_posix()}"

    from core import db

    db.reiniciar_engine()
    db.get_engine()  # cria o schema
    yield destino
    db.reiniciar_engine()


@pytest.fixture(autouse=True)
def escopo_limpo():
    """Nenhum teste começa com workspace ativo.

    Sem isso, um teste que esquecesse de definir o escopo passaria por herdar o
    workspace do teste anterior — e é justamente esse esquecimento que os
    testes de isolamento precisam conseguir detectar.
    """
    from core import escopo

    escopo.limpar()
    yield
    escopo.limpar()


@pytest.fixture
def emails():
    """Gera e-mails únicos.

    O banco vive a sessão de testes inteira, então e-mail fixo faria o segundo
    teste a usar a mesma fixture esbarrar no cadastro deixado pelo primeiro.
    """
    contador = itertools.count()

    def novo(prefixo: str = "pessoa") -> str:
        return f"{prefixo}-{next(contador)}-{uuid.uuid4().hex[:8]}@exemplo.test"

    return novo


@pytest.fixture
def usuario(emails):
    """Um usuário novo com a carteira pessoal dele já semeada.

    Devolve (usuario_id, workspace_id).
    """
    from core import auth

    uid = auth.criar_usuario(emails(), "Pessoa de Teste", "senha-de-teste-123")
    ws = auth.workspaces_de(uid)[0]["id"]
    return uid, ws


@pytest.fixture
def carteira(usuario):
    """Workspace ativo, pronto para chamar o `repo` direto. Devolve o id."""
    from core import escopo

    _, ws = usuario
    escopo.definir(ws)
    return ws


@pytest.fixture
def base(carteira):
    """Carteira com cartão criado. Devolve os ids mais usados nos testes."""
    from core import repo

    repo.salvar_cartao("Nubank Teste", "Nubank", 5000, 25, 5)
    cats = repo.listar_categorias()
    return {
        "workspace": carteira,
        "conta": int(repo.listar_contas().iloc[0]["id"]),
        "cat_despesa": int(cats[cats.tipo == "despesa"].iloc[0]["id"]),
        "cat_despesa2": int(cats[cats.tipo == "despesa"].iloc[3]["id"]),
        "cat_receita": int(cats[cats.tipo == "receita"].iloc[0]["id"]),
        "cartao": int(repo.listar_cartoes().iloc[0]["id"]),
    }
