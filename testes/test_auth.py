"""Cadastro, login, permissões e sessões persistentes."""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from core import auth, escopo, repo
from core.db import get_session
from core.models import Sessao, Usuario


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #


def test_senha_nunca_e_guardada_em_texto():
    hash_ = auth.gerar_hash("senha-de-teste-123")
    assert "senha-de-teste-123" not in hash_
    assert hash_.startswith("$2")
    assert auth.conferir_senha("senha-de-teste-123", hash_)
    assert not auth.conferir_senha("senha errada", hash_)


def test_hashes_da_mesma_senha_sao_diferentes():
    """Sal por hash: dois usuários com a mesma senha não têm o mesmo registro."""
    assert auth.gerar_hash("senha-de-teste-123") != auth.gerar_hash("senha-de-teste-123")


def test_senha_curta_e_recusada():
    with pytest.raises(auth.ErroDeAuth):
        auth.gerar_hash("1234")


def test_senha_acima_do_limite_do_bcrypt_e_recusada():
    """bcrypt corta em 72 bytes. Truncar em silêncio faria duas senhas
    diferentes passarem a valer uma pela outra."""
    with pytest.raises(auth.ErroDeAuth):
        auth.gerar_hash("a" * 73)


def test_conferir_senha_longa_nao_estoura():
    hash_ = auth.gerar_hash("senha-de-teste-123")
    assert auth.conferir_senha("a" * 200, hash_) is False


# --------------------------------------------------------------------------- #
# Cadastro e login
# --------------------------------------------------------------------------- #


def test_cadastro_cria_a_carteira_ja_semeada():
    uid = auth.criar_usuario("novo@exemplo.test", "Novo", "senha-de-teste-123")
    carteiras = auth.workspaces_de(uid)
    assert len(carteiras) == 1
    assert carteiras[0]["papel"] == "dono"

    with escopo.usando(carteiras[0]["id"]):
        assert len(repo.listar_categorias()) >= 20
        assert len(repo.listar_contas()) == 1


def test_email_duplicado_e_recusado():
    auth.criar_usuario("dup@exemplo.test", "Um", "senha-de-teste-123")
    with pytest.raises(auth.ErroDeAuth):
        auth.criar_usuario("dup@exemplo.test", "Outro", "senha-de-teste-123")


def test_email_e_tratado_sem_diferenca_de_caixa():
    auth.criar_usuario("Maiuscula@Exemplo.Test", "Pessoa", "senha-de-teste-123")
    assert auth.autenticar("maiuscula@exemplo.test", "senha-de-teste-123") is not None
    with pytest.raises(auth.ErroDeAuth):
        auth.criar_usuario("MAIUSCULA@EXEMPLO.TEST", "Outra", "senha-de-teste-123")


def test_email_sem_arroba_e_recusado():
    with pytest.raises(auth.ErroDeAuth):
        auth.criar_usuario("nao-e-email", "Pessoa", "senha-de-teste-123")


def test_login_com_senha_errada_falha():
    auth.criar_usuario("login@exemplo.test", "Pessoa", "senha-de-teste-123")
    assert auth.autenticar("login@exemplo.test", "senha-de-teste-123") is not None
    assert auth.autenticar("login@exemplo.test", "outra-senha") is None


def test_login_de_email_inexistente_falha_igual():
    assert auth.autenticar("ninguem@exemplo.test", "qualquer-coisa") is None


# --------------------------------------------------------------------------- #
# Sessões
# --------------------------------------------------------------------------- #


def test_sessao_sobrevive_ao_refresh(usuario):
    """O token do cookie é o que recupera o login quando o session_state some."""
    uid, _ = usuario
    token = auth.abrir_sessao(uid)
    recuperado = auth.usuario_da_sessao(token)
    assert recuperado is not None and recuperado.id == uid


def test_token_invalido_nao_abre_nada():
    assert auth.usuario_da_sessao("token-inventado") is None
    assert auth.usuario_da_sessao(None) is None
    assert auth.usuario_da_sessao("") is None


def test_o_token_em_si_nao_fica_no_banco(usuario):
    uid, _ = usuario
    token = auth.abrir_sessao(uid)
    with get_session() as s:
        guardados = [x.token_hash for x in s.scalars(select(Sessao)).all()]
    assert token not in guardados


def test_sair_invalida_o_token(usuario):
    uid, _ = usuario
    token = auth.abrir_sessao(uid)
    auth.fechar_sessao(token)
    assert auth.usuario_da_sessao(token) is None


def test_sessao_vencida_nao_vale(usuario):
    uid, _ = usuario
    token = auth.abrir_sessao(uid)
    with get_session() as s:
        sessao = s.scalar(select(Sessao).where(Sessao.token_hash == auth._hash_token(token)))
        sessao.expira_em = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        s.commit()
    assert auth.usuario_da_sessao(token) is None


def test_trocar_senha_derruba_as_outras_sessoes(usuario):
    """Se a troca foi motivada por suspeita de acesso indevido, o invasor sai."""
    uid, _ = usuario
    token = auth.abrir_sessao(uid)
    auth.trocar_senha(uid, "senha-de-teste-123", "nova-senha-456")

    assert auth.usuario_da_sessao(token) is None
    with get_session() as s:
        usuario_db = s.get(Usuario, uid)
    assert auth.conferir_senha("nova-senha-456", usuario_db.senha_hash)


def test_trocar_senha_exige_a_senha_atual(usuario):
    uid, _ = usuario
    with pytest.raises(auth.ErroDeAuth):
        auth.trocar_senha(uid, "senha-errada", "nova-senha-456")


# --------------------------------------------------------------------------- #
# Carteiras compartilhadas
# --------------------------------------------------------------------------- #


@pytest.fixture
def casal(emails):
    """Duas contas e uma carteira "Casa" que só o dono enxerga por enquanto."""
    email_dono, email_conjuge = emails("dono"), emails("conjuge")
    dono = auth.criar_usuario(email_dono, "Dono", "senha-de-teste-123")
    conjuge = auth.criar_usuario(email_conjuge, "Cônjuge", "senha-de-teste-123")
    return {
        "dono": dono,
        "conjuge": conjuge,
        "email_dono": email_dono,
        "email_conjuge": email_conjuge,
        "casa": auth.criar_workspace("Casa", dono),
    }


def test_convidado_passa_a_enxergar_a_carteira(casal):
    assert not auth.pode_acessar(casal["conjuge"], casal["casa"])
    auth.adicionar_membro(casal["casa"], casal["email_conjuge"], casal["dono"])
    assert auth.pode_acessar(casal["conjuge"], casal["casa"])

    ids = [w["id"] for w in auth.workspaces_de(casal["conjuge"])]
    assert casal["casa"] in ids


def test_quem_nao_e_dono_nao_convida(casal, emails):
    auth.adicionar_membro(casal["casa"], casal["email_conjuge"], casal["dono"])
    email_terceiro = emails("terceiro")
    terceiro = auth.criar_usuario(email_terceiro, "Terceiro", "senha-de-teste-123")
    with pytest.raises(auth.ErroDeAuth):
        auth.adicionar_membro(casal["casa"], email_terceiro, casal["conjuge"])
    assert not auth.pode_acessar(terceiro, casal["casa"])


def test_nao_da_para_convidar_quem_nao_tem_conta(casal):
    with pytest.raises(auth.ErroDeAuth):
        auth.adicionar_membro(casal["casa"], "fantasma@exemplo.test", casal["dono"])


def test_convite_repetido_e_recusado(casal):
    auth.adicionar_membro(casal["casa"], casal["email_conjuge"], casal["dono"])
    with pytest.raises(auth.ErroDeAuth):
        auth.adicionar_membro(casal["casa"], casal["email_conjuge"], casal["dono"])


def test_membros_compartilham_de_fato_os_lancamentos(casal):
    auth.adicionar_membro(casal["casa"], casal["email_conjuge"], casal["dono"])
    with escopo.usando(casal["casa"]):
        cat = int(repo.listar_categorias(tipo="despesa").iloc[0]["id"])
        repo.salvar_transacao(
            data=dt.date(2026, 3, 10), descricao="Mercado do mês", valor=700,
            tipo="despesa", categoria_id=cat,
        )
        assert len(repo.transacoes(repo.comp(2026, 3))) == 1


def test_remover_membro_tira_o_acesso(casal):
    auth.adicionar_membro(casal["casa"], casal["email_conjuge"], casal["dono"])
    auth.remover_membro(casal["casa"], casal["conjuge"], casal["dono"])
    assert not auth.pode_acessar(casal["conjuge"], casal["casa"])


def test_dono_nao_se_remove(casal):
    with pytest.raises(auth.ErroDeAuth):
        auth.remover_membro(casal["casa"], casal["dono"], casal["dono"])


def test_carteira_nova_nasce_semeada_e_separada(casal):
    with escopo.usando(casal["casa"]):
        assert len(repo.listar_categorias()) >= 20
        assert repo.transacoes().empty
