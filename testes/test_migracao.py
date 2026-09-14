"""Migração de um banco 0.1.x para o modelo multiusuário.

Quem já usava o app tem lançamentos lá dentro. Uma migração que os perca é pior
do que não migrar, então o teste confere que tudo continua legível depois.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "ferramentas"))

ESQUEMA_0_1 = """
CREATE TABLE conta (id INTEGER PRIMARY KEY, nome VARCHAR(80) UNIQUE, tipo VARCHAR(30),
                    saldo_inicial NUMERIC(12,2), ativa BOOLEAN);
CREATE TABLE cartao (id INTEGER PRIMARY KEY, nome VARCHAR(80) UNIQUE, banco VARCHAR(80),
                     limite NUMERIC(12,2), dia_fechamento INTEGER, dia_vencimento INTEGER,
                     ativo BOOLEAN);
CREATE TABLE categoria (id INTEGER PRIMARY KEY, nome VARCHAR(60), tipo VARCHAR(10),
                        cor VARCHAR(9), ativa BOOLEAN);
CREATE TABLE transacao (id INTEGER PRIMARY KEY, data DATE, competencia DATE,
                        descricao VARCHAR(160), valor NUMERIC(12,2), tipo VARCHAR(10),
                        pago BOOLEAN, observacao VARCHAR(300), categoria_id INTEGER,
                        conta_id INTEGER, cartao_id INTEGER, parcela_num INTEGER,
                        parcela_total INTEGER, grupo VARCHAR(40));
CREATE TABLE orcamento (id INTEGER PRIMARY KEY, competencia DATE, categoria_id INTEGER,
                        valor NUMERIC(12,2));
CREATE TABLE investimento (id INTEGER PRIMARY KEY, nome VARCHAR(80) UNIQUE, tipo VARCHAR(40),
                           instituicao VARCHAR(80), ativo BOOLEAN);
CREATE TABLE movimento_investimento (id INTEGER PRIMARY KEY, investimento_id INTEGER,
                                     data DATE, tipo VARCHAR(20), valor NUMERIC(12,2),
                                     observacao VARCHAR(200));
CREATE TABLE objetivo (id INTEGER PRIMARY KEY, nome VARCHAR(80), valor_alvo NUMERIC(12,2),
                       valor_atual NUMERIC(12,2), data_alvo DATE, concluido BOOLEAN);
INSERT INTO conta VALUES (1,'Conta corrente','Conta corrente',1000,1);
INSERT INTO categoria VALUES (1,'Aluguel','despesa','#8C4A3F',1),
                             (2,'Salario','receita','#1F5D4A',1);
INSERT INTO transacao VALUES (1,'2026-03-01','2026-03-01','Aluguel de marco',1592,
                              'despesa',1,'',1,1,NULL,1,1,NULL);
INSERT INTO transacao VALUES (2,'2026-03-05','2026-03-01','Salario',7200,
                              'receita',1,'',2,1,NULL,1,1,NULL);
INSERT INTO objetivo VALUES (1,'Viagem',10000,2500,'2026-12-31',0);
"""


@pytest.fixture
def banco_antigo(tmp_path, monkeypatch):
    """Um banco no formato 0.1.x, com dados, ligado ao `core` por DATABASE_URL.

    Troca o banco da sessão inteira, então devolve o anterior no fim — senão os
    testes seguintes rodariam contra um arquivo que já foi embora.
    """
    from core import db

    destino = tmp_path / "antigo.db"
    engine = create_engine(f"sqlite:///{destino.as_posix()}")
    with engine.begin() as con:
        for comando in filter(str.strip, ESQUEMA_0_1.split(";")):
            con.execute(text(comando))
    engine.dispose()

    anterior = __import__("os").environ["DATABASE_URL"]
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{destino.as_posix()}")
    db.reiniciar_engine()
    yield destino
    db.reiniciar_engine()
    monkeypatch.setenv("DATABASE_URL", anterior)
    db.reiniciar_engine()


def _migrar(email="dono@exemplo.test"):
    migrar = importlib.import_module("migrar_0_2_0")
    importlib.reload(migrar)
    from core.db import get_engine

    engine = get_engine()
    migrar.aplicar(engine, email, "Dono", "senha-de-teste-123", "Minhas contas")
    return email


def test_diagnostico_aponta_as_tabelas_sem_workspace_id(banco_antigo):
    migrar = importlib.import_module("migrar_0_2_0")
    importlib.reload(migrar)
    from core.db import get_engine

    estado = migrar.diagnosticar(get_engine())
    assert "transacao" in estado["faltando_coluna"]
    assert estado["linhas"]["transacao"] == 2
    assert not estado["ja_migradas"]


def test_migracao_preserva_os_lancamentos(banco_antigo):
    from core import auth, escopo, repo

    email = _migrar()
    usuario = auth.autenticar(email, "senha-de-teste-123")
    assert usuario is not None

    carteira = auth.workspaces_de(usuario.id)[0]
    escopo.definir(carteira["id"])

    tx = repo.transacoes(repo.comp(2026, 3))
    assert len(tx) == 2
    assert set(tx["descricao"]) == {"Aluguel de marco", "Salario"}

    resumo = repo.resumo_mes(repo.comp(2026, 3))
    assert resumo["receitas"] == pytest.approx(7200)
    assert resumo["despesas"] == pytest.approx(1592)
    assert repo.saldo_total() == pytest.approx(6608)
    assert list(repo.listar_objetivos()["nome"]) == ["Viagem"]


def test_migracao_nao_duplica_o_que_ja_existia(banco_antigo):
    """A carteira adota as categorias antigas em vez de semear por cima."""
    from core import auth, escopo, repo

    email = _migrar()
    usuario = auth.autenticar(email, "senha-de-teste-123")
    escopo.definir(auth.workspaces_de(usuario.id)[0]["id"])

    assert len(repo.listar_categorias()) == 2
    assert list(repo.listar_contas()["nome"]) == ["Conta corrente"]


def test_depois_da_migracao_outra_carteira_repete_nomes(banco_antigo):
    """O único de nome era global na 0.1.x. Se continuasse, a segunda pessoa
    não conseguiria ter uma conta com o mesmo nome da primeira — e o próprio
    cadastro dela quebraria, porque o seed cria uma "Conta corrente"."""
    from core import auth, escopo, repo

    email = _migrar()
    dono = auth.autenticar(email, "senha-de-teste-123")
    with escopo.usando(auth.workspaces_de(dono.id)[0]["id"]):
        assert "Conta corrente" in set(repo.listar_contas()["nome"])

    outro = auth.criar_usuario("outra@exemplo.test", "Outra", "senha-de-teste-123")
    with escopo.usando(auth.workspaces_de(outro)[0]["id"]):
        assert "Conta corrente" in set(repo.listar_contas()["nome"])
        repo.salvar_cartao("Nubank", "Nubank", 5000, 25, 5)
        assert list(repo.listar_cartoes()["nome"]) == ["Nubank"]


def test_migrar_duas_vezes_nao_estraga_nada(banco_antigo):
    """Rodar de novo por engano não pode duplicar nem perder lançamento."""
    from core import auth, escopo, repo

    email = _migrar()
    _migrar(email)  # segunda passada, mesmo usuário

    usuario = auth.autenticar(email, "senha-de-teste-123")
    escopo.definir(auth.workspaces_de(usuario.id)[0]["id"])
    assert len(repo.transacoes(repo.comp(2026, 3))) == 2
