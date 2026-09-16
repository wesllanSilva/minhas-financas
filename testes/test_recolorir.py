"""Recoloração das categorias antigas para a paleta escura."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from core import escopo, repo, tema

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))


def _planejar():
    mod = importlib.import_module("recolorir_categorias")
    return importlib.reload(mod).planejar()


def test_categoria_padrao_com_cor_antiga_volta_para_a_cor_padrao(carteira):
    aluguel = int(repo.listar_categorias().query("nome == 'Aluguel'").iloc[0]["id"])
    repo.salvar_categoria("Aluguel", "despesa", "#8C4A3F", id_=aluguel)  # cor da 0.1.x

    mudancas = [(c.nome, nova) for c, _, nova in _planejar() if c.workspace_id == carteira]
    assert ("Aluguel", "#fb7185") in mudancas


def test_categoria_propria_recebe_cor_da_paleta_sem_repetir(carteira):
    repo.salvar_categoria("Pet", "despesa", "#8C4A3F")
    repo.salvar_categoria("Academia", "despesa", "#8C4A3F")

    novas = {c.nome: nova for c, _, nova in _planejar() if c.workspace_id == carteira}
    assert novas["Pet"] in tema.SERIE and novas["Academia"] in tema.SERIE
    assert novas["Pet"] != novas["Academia"]


def test_carteira_ja_na_paleta_nao_muda(carteira):
    assert not [c for c, _, _ in _planejar() if c.workspace_id == carteira]


def test_nao_toca_em_outra_carteira(usuario, emails):
    from core import auth

    outro = auth.criar_usuario(emails(), "Outra", "senha-de-teste-123")
    ws_outro = auth.workspaces_de(outro)[0]["id"]
    with escopo.usando(ws_outro):
        cat = int(repo.listar_categorias().iloc[0]["id"])
        repo.salvar_categoria("Aluguel", "despesa", "#000000", id_=cat)

    afetadas = {c.workspace_id for c, _, _ in _planejar()}
    assert ws_outro in afetadas
    assert usuario[1] not in afetadas


def test_categoria_propria_depois_de_todas_as_padrao_ainda_ganha_cor(carteira):
    """As 21 padrão já ocupam a paleta inteira; uma "Zoológico" (que ordena
    depois de todas) não pode ficar sem cor."""
    repo.salvar_categoria("Zoológico", "despesa", "#8C4A3F")
    novas = {c.nome: nova for c, _, nova in _planejar() if c.workspace_id == carteira}
    assert novas["Zoológico"] in tema.SERIE
