"""Modelo de dados do app de finanças.

Tudo que é dado financeiro pertence a um *workspace* — uma carteira. Um usuário
pode participar de vários: a sua, a do cônjuge, a compartilhada do casal. O
isolamento entre workspaces é aplicado em `core/repo.py`, que filtra toda
consulta pelo workspace ativo (veja `core/escopo.py`).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _agora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------- #
# Contas de acesso
# --------------------------------------------------------------------------- #


class Usuario(Base):
    """Quem faz login. A senha nunca é guardada — só o hash bcrypt."""

    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(80))
    senha_hash: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_agora)


class Workspace(Base):
    """Uma carteira: o conjunto de contas, cartões, lançamentos e metas."""

    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_agora)


class Membro(Base):
    """Liga usuário e workspace. É o que decide quem enxerga o quê."""

    __tablename__ = "membro"
    __table_args__ = (
        UniqueConstraint("usuario_id", "workspace_id", name="uq_membro_usuario_workspace"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    papel: Mapped[str] = mapped_column(String(10), default="dono")  # dono | membro

    usuario: Mapped[Usuario] = relationship(lazy="joined")
    workspace: Mapped[Workspace] = relationship(lazy="joined")


class Sessao(Base):
    """Sessão persistente: é o que mantém o login de pé depois de um F5.

    O `st.session_state` do Streamlit morre a cada refresh. Guardamos aqui um
    token cujo hash fica no banco e cujo valor vai num cookie do navegador. Só
    o hash é persistido, então vazar o banco não dá login a ninguém.
    """

    __tablename__ = "sessao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    criada_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_agora)
    expira_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)

    usuario: Mapped[Usuario] = relationship(lazy="joined")


# --------------------------------------------------------------------------- #
# Dados financeiros — sempre presos a um workspace
# --------------------------------------------------------------------------- #


class Conta(Base):
    """Conta bancária, carteira ou qualquer lugar onde o dinheiro fica."""

    __tablename__ = "conta"
    __table_args__ = (UniqueConstraint("workspace_id", "nome", name="uq_conta_ws_nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(30), default="Conta corrente")
    saldo_inicial: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Cartao(Base):
    """Cartão de crédito. A fatura é calculada a partir do dia de fechamento."""

    __tablename__ = "cartao"
    __table_args__ = (UniqueConstraint("workspace_id", "nome", name="uq_cartao_ws_nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    banco: Mapped[str] = mapped_column(String(80), default="")
    limite: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    dia_fechamento: Mapped[int] = mapped_column(Integer, default=1)
    dia_vencimento: Mapped[int] = mapped_column(Integer, default=10)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (
        UniqueConstraint("workspace_id", "nome", "tipo", name="uq_categoria_ws_nome_tipo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    nome: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(10), default="despesa")  # despesa | receita
    cor: Mapped[str] = mapped_column(String(9), default="#5B7A86")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Transacao(Base):
    """Uma entrada ou saída de dinheiro.

    - `data` é a data do lançamento (data da compra, no caso de cartão).
    - `competencia` é o primeiro dia do mês em que a despesa entra no orçamento.
      Para compras no cartão, é o mês da fatura; para o resto, é o mês da `data`.
    - Parcelas e repetições compartilham o mesmo `grupo`, para poder apagar tudo de uma vez.
    """

    __tablename__ = "transacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    data: Mapped[dt.date] = mapped_column(Date, index=True)
    competencia: Mapped[dt.date] = mapped_column(Date, index=True)
    descricao: Mapped[str] = mapped_column(String(160))
    valor: Mapped[float] = mapped_column(Numeric(12, 2))
    tipo: Mapped[str] = mapped_column(String(10))  # despesa | receita
    pago: Mapped[bool] = mapped_column(Boolean, default=True)
    observacao: Mapped[str] = mapped_column(String(300), default="")

    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria.id"))
    conta_id: Mapped[int | None] = mapped_column(ForeignKey("conta.id"))
    cartao_id: Mapped[int | None] = mapped_column(ForeignKey("cartao.id"))

    parcela_num: Mapped[int] = mapped_column(Integer, default=1)
    parcela_total: Mapped[int] = mapped_column(Integer, default=1)
    grupo: Mapped[str | None] = mapped_column(String(40), index=True)

    categoria: Mapped[Categoria | None] = relationship(lazy="joined")
    conta: Mapped[Conta | None] = relationship(lazy="joined")
    cartao: Mapped[Cartao | None] = relationship(lazy="joined")


class Orcamento(Base):
    """Meta de gasto de uma categoria em um mês (a aba Planejamento)."""

    __tablename__ = "orcamento"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "competencia", "categoria_id", name="uq_orcamento_ws_mes_cat"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    competencia: Mapped[dt.date] = mapped_column(Date, index=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    valor: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    categoria: Mapped[Categoria] = relationship(lazy="joined")


class Investimento(Base):
    __tablename__ = "investimento"
    __table_args__ = (UniqueConstraint("workspace_id", "nome", name="uq_investimento_ws_nome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(40), default="Renda fixa")
    instituicao: Mapped[str] = mapped_column(String(80), default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class MovimentoInvestimento(Base):
    """Aporte, resgate ou rendimento de um investimento."""

    __tablename__ = "movimento_investimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    investimento_id: Mapped[int] = mapped_column(ForeignKey("investimento.id"))
    data: Mapped[dt.date] = mapped_column(Date, index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # aporte | resgate | rendimento
    valor: Mapped[float] = mapped_column(Numeric(12, 2))
    observacao: Mapped[str] = mapped_column(String(200), default="")

    investimento: Mapped[Investimento] = relationship(lazy="joined")


class Objetivo(Base):
    __tablename__ = "objetivo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), index=True)
    nome: Mapped[str] = mapped_column(String(80))
    valor_alvo: Mapped[float] = mapped_column(Numeric(12, 2))
    valor_atual: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    data_alvo: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    concluido: Mapped[bool] = mapped_column(Boolean, default=False)


#: Tabelas cujo conteúdo é privado a um workspace. `core/repo.py` filtra todas
#: por `workspace_id`; `testes/` verifica que nenhuma escapa dessa lista.
COM_ESCOPO = (
    Conta,
    Cartao,
    Categoria,
    Transacao,
    Orcamento,
    Investimento,
    MovimentoInvestimento,
    Objetivo,
)
