"""Login, cadastro e sessões que sobrevivem ao refresh.

O `st.session_state` do Streamlit é recriado a cada F5, então ele sozinho não
sustenta um login. Aqui cada login abre uma `Sessao`: um token aleatório vai
para um cookie do navegador e só o seu hash SHA-256 fica no banco. No refresh o
cookie volta na requisição, o hash confere e a sessão é restaurada.

Guardar o hash (e não o token) significa que quem ler o banco não consegue se
passar por ninguém — é o mesmo motivo de guardar a senha em bcrypt.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets

import bcrypt
from sqlalchemy import delete, func, select

from .db import get_session, semear_workspace
from .models import Membro, Sessao, Usuario, Workspace

#: Quanto tempo um login continua valendo sem novo uso.
DIAS_DE_SESSAO = 30

#: bcrypt ignora tudo além de 72 bytes. Em vez de truncar em silêncio — o que
#: faria "senha longa A" e "senha longa B" virarem a mesma senha — recusamos.
MAX_SENHA_BYTES = 72
MIN_SENHA = 8


class ErroDeAuth(Exception):
    """Falha esperada de cadastro ou login, com mensagem pronta para a tela."""


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #


def validar_senha(senha: str) -> None:
    if len(senha) < MIN_SENHA:
        raise ErroDeAuth(f"A senha precisa de pelo menos {MIN_SENHA} caracteres.")
    if len(senha.encode("utf-8")) > MAX_SENHA_BYTES:
        raise ErroDeAuth(
            f"A senha é longa demais (limite de {MAX_SENHA_BYTES} bytes). "
            "Use uma frase mais curta."
        )


def gerar_hash(senha: str) -> str:
    validar_senha(senha)
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def conferir_senha(senha: str, senha_hash: str) -> bool:
    if len(senha.encode("utf-8")) > MAX_SENHA_BYTES:
        return False
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except ValueError:
        return False


def normalizar_email(email: str) -> str:
    return email.strip().lower()


# --------------------------------------------------------------------------- #
# Usuários e workspaces
# --------------------------------------------------------------------------- #


def existe_algum_usuario() -> bool:
    """False só no primeiro acesso, quando o app oferece criar o dono."""
    with get_session() as s:
        return s.scalar(select(func.count()).select_from(Usuario)) > 0


def criar_usuario(
    email: str,
    nome: str,
    senha: str,
    nome_workspace: str | None = None,
    semear: bool = True,
) -> int:
    """Cria o usuário junto com a carteira pessoal dele. Devolve o id do usuário.

    `semear=False` serve à migração de um banco 0.1.x: lá a carteira vai adotar
    as categorias e contas que já existiam, e semear por cima criaria um par
    duplicado de cada uma.
    """
    email = normalizar_email(email)
    if not email or "@" not in email:
        raise ErroDeAuth("Informe um e-mail válido.")
    if not nome.strip():
        raise ErroDeAuth("Informe um nome.")
    senha_hash = gerar_hash(senha)

    with get_session() as s:
        if s.scalar(select(Usuario).where(Usuario.email == email)):
            raise ErroDeAuth("Já existe uma conta com esse e-mail.")

        usuario = Usuario(email=email, nome=nome.strip(), senha_hash=senha_hash)
        s.add(usuario)
        s.flush()

        ws = Workspace(nome=nome_workspace or f"Finanças de {usuario.nome}")
        s.add(ws)
        s.flush()
        s.add(Membro(usuario_id=usuario.id, workspace_id=ws.id, papel="dono"))
        if semear:
            semear_workspace(s, ws.id)
        s.commit()
        return usuario.id


def autenticar(email: str, senha: str) -> Usuario | None:
    """Devolve o usuário se a senha bater. None em qualquer outro caso.

    A mesma resposta para "e-mail não existe" e "senha errada" é proposital:
    distinguir os dois revelaria quais e-mails têm conta.
    """
    with get_session() as s:
        usuario = s.scalar(select(Usuario).where(Usuario.email == normalizar_email(email)))
        if usuario is None or not usuario.ativo:
            return None
        if not conferir_senha(senha, usuario.senha_hash):
            return None
        return usuario


def trocar_senha(usuario_id: int, senha_atual: str, senha_nova: str) -> None:
    novo_hash = gerar_hash(senha_nova)
    with get_session() as s:
        usuario = s.get(Usuario, usuario_id)
        if usuario is None or not conferir_senha(senha_atual, usuario.senha_hash):
            raise ErroDeAuth("Senha atual incorreta.")
        usuario.senha_hash = novo_hash
        # Trocar a senha derruba as outras sessões: é o que torna a troca útil
        # quando o motivo dela é suspeita de acesso indevido.
        s.execute(delete(Sessao).where(Sessao.usuario_id == usuario_id))
        s.commit()


def workspaces_de(usuario_id: int) -> list[dict]:
    with get_session() as s:
        membros = s.scalars(
            select(Membro).where(Membro.usuario_id == usuario_id).order_by(Membro.id)
        ).all()
        return [
            {"id": m.workspace_id, "nome": m.workspace.nome, "papel": m.papel} for m in membros
        ]


def pode_acessar(usuario_id: int, workspace_id: int) -> bool:
    """Checagem de autorização. Toda troca de workspace passa por aqui."""
    with get_session() as s:
        return (
            s.scalar(
                select(Membro).where(
                    Membro.usuario_id == usuario_id, Membro.workspace_id == workspace_id
                )
            )
            is not None
        )


def criar_workspace(nome: str, usuario_id: int) -> int:
    if not nome.strip():
        raise ErroDeAuth("Dê um nome para a carteira.")
    with get_session() as s:
        ws = Workspace(nome=nome.strip())
        s.add(ws)
        s.flush()
        s.add(Membro(usuario_id=usuario_id, workspace_id=ws.id, papel="dono"))
        semear_workspace(s, ws.id)
        s.commit()
        return ws.id


def renomear_workspace(workspace_id: int, nome: str, solicitante_id: int) -> None:
    """Só o dono renomeia. Membro convidado enxerga, mas a carteira não é dele."""
    if not nome.strip():
        raise ErroDeAuth("Dê um nome para a carteira.")
    with get_session() as s:
        dono = s.scalar(
            select(Membro).where(
                Membro.usuario_id == solicitante_id,
                Membro.workspace_id == workspace_id,
                Membro.papel == "dono",
            )
        )
        if dono is None:
            raise ErroDeAuth("Só o dono da carteira pode renomeá-la.")
        s.get(Workspace, workspace_id).nome = nome.strip()
        s.commit()


def adicionar_membro(workspace_id: int, email: str, solicitante_id: int) -> None:
    """Dá a outro usuário acesso a uma carteira. Só o dono pode."""
    with get_session() as s:
        dono = s.scalar(
            select(Membro).where(
                Membro.usuario_id == solicitante_id,
                Membro.workspace_id == workspace_id,
                Membro.papel == "dono",
            )
        )
        if dono is None:
            raise ErroDeAuth("Só o dono da carteira pode convidar alguém.")

        convidado = s.scalar(select(Usuario).where(Usuario.email == normalizar_email(email)))
        if convidado is None:
            raise ErroDeAuth("Não existe conta com esse e-mail. Crie a conta primeiro.")
        ja_membro = s.scalar(
            select(Membro).where(
                Membro.usuario_id == convidado.id, Membro.workspace_id == workspace_id
            )
        )
        if ja_membro:
            raise ErroDeAuth(f"{convidado.nome} já participa dessa carteira.")

        s.add(Membro(usuario_id=convidado.id, workspace_id=workspace_id, papel="membro"))
        s.commit()


def remover_membro(workspace_id: int, usuario_id: int, solicitante_id: int) -> None:
    with get_session() as s:
        dono = s.scalar(
            select(Membro).where(
                Membro.usuario_id == solicitante_id,
                Membro.workspace_id == workspace_id,
                Membro.papel == "dono",
            )
        )
        if dono is None:
            raise ErroDeAuth("Só o dono da carteira pode remover alguém.")
        if usuario_id == solicitante_id:
            raise ErroDeAuth("O dono não pode sair da própria carteira.")
        s.execute(
            delete(Membro).where(
                Membro.usuario_id == usuario_id, Membro.workspace_id == workspace_id
            )
        )
        s.commit()


def membros_de(workspace_id: int) -> list[dict]:
    with get_session() as s:
        membros = s.scalars(
            select(Membro).where(Membro.workspace_id == workspace_id).order_by(Membro.id)
        ).all()
        return [
            {
                "usuario_id": m.usuario_id,
                "nome": m.usuario.nome,
                "email": m.usuario.email,
                "papel": m.papel,
            }
            for m in membros
        ]


# --------------------------------------------------------------------------- #
# Sessões persistentes
# --------------------------------------------------------------------------- #


def _hash_token(token: str) -> str:
    """SHA-256 basta aqui (e bcrypt não serviria).

    O token já é 256 bits de aleatoriedade vinda do `secrets` — não há o que
    adivinhar por força bruta, que é o risco de que o bcrypt protege nas senhas
    escolhidas por gente. Em compensação, este hash roda a cada requisição, e
    aí a lentidão deliberada do bcrypt seria um problema.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def abrir_sessao(usuario_id: int) -> str:
    """Cria uma sessão e devolve o token que vai para o cookie."""
    token = secrets.token_urlsafe(32)
    expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=DIAS_DE_SESSAO)
    with get_session() as s:
        s.add(Sessao(token_hash=_hash_token(token), usuario_id=usuario_id, expira_em=expira))
        s.commit()
    return token


def usuario_da_sessao(token: str | None) -> Usuario | None:
    """Valida o token do cookie. Sessão vencida é apagada na hora."""
    if not token:
        return None
    with get_session() as s:
        sessao = s.scalar(select(Sessao).where(Sessao.token_hash == _hash_token(token)))
        if sessao is None:
            return None
        if _vencida(sessao.expira_em):
            s.delete(sessao)
            s.commit()
            return None
        usuario = sessao.usuario
        if usuario is None or not usuario.ativo:
            return None
        return usuario


def fechar_sessao(token: str | None) -> None:
    if not token:
        return
    with get_session() as s:
        s.execute(delete(Sessao).where(Sessao.token_hash == _hash_token(token)))
        s.commit()


def limpar_sessoes_vencidas() -> int:
    agora = dt.datetime.now(dt.timezone.utc)
    with get_session() as s:
        alvo = [x for x in s.scalars(select(Sessao)).all() if _vencida(x.expira_em, agora)]
        for sessao in alvo:
            s.delete(sessao)
        s.commit()
        return len(alvo)


def _vencida(expira_em: dt.datetime, agora: dt.datetime | None = None) -> bool:
    """Compara datas tolerando o SQLite, que devolve datetime sem timezone."""
    agora = agora or dt.datetime.now(dt.timezone.utc)
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=dt.timezone.utc)
    return expira_em < agora
