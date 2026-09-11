"""Modelo de dados do app de finanças."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Conta(Base):
    """Conta bancária, carteira ou qualquer lugar onde o dinheiro fica."""

    __tablename__ = "conta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    tipo: Mapped[str] = mapped_column(String(30), default="Conta corrente")
    saldo_inicial: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Cartao(Base):
    """Cartão de crédito. A fatura é calculada a partir do dia de fechamento."""

    __tablename__ = "cartao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    banco: Mapped[str] = mapped_column(String(80), default="")
    limite: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    dia_fechamento: Mapped[int] = mapped_column(Integer, default=1)
    dia_vencimento: Mapped[int] = mapped_column(Integer, default=10)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Categoria(Base):
    __tablename__ = "categoria"
    __table_args__ = (UniqueConstraint("nome", "tipo", name="uq_categoria_nome_tipo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
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
        UniqueConstraint("competencia", "categoria_id", name="uq_orcamento_mes_cat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competencia: Mapped[dt.date] = mapped_column(Date, index=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    valor: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    categoria: Mapped[Categoria] = relationship(lazy="joined")


class Investimento(Base):
    __tablename__ = "investimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    tipo: Mapped[str] = mapped_column(String(40), default="Renda fixa")
    instituicao: Mapped[str] = mapped_column(String(80), default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class MovimentoInvestimento(Base):
    """Aporte, resgate ou rendimento de um investimento."""

    __tablename__ = "movimento_investimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investimento_id: Mapped[int] = mapped_column(ForeignKey("investimento.id"))
    data: Mapped[dt.date] = mapped_column(Date, index=True)
    tipo: Mapped[str] = mapped_column(String(20))  # aporte | resgate | rendimento
    valor: Mapped[float] = mapped_column(Numeric(12, 2))
    observacao: Mapped[str] = mapped_column(String(200), default="")

    investimento: Mapped[Investimento] = relationship(lazy="joined")


class Objetivo(Base):
    __tablename__ = "objetivo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80))
    valor_alvo: Mapped[float] = mapped_column(Numeric(12, 2))
    valor_atual: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    data_alvo: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    concluido: Mapped[bool] = mapped_column(Boolean, default=False)
