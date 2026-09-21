"""Consultas e regras de negócio. Tudo que mexe no banco passa por aqui.

Toda consulta é filtrada pelo workspace ativo (`core/escopo.py`). As telas não
passam `workspace_id` — não teriam como esquecer, e não têm como forjar. Buscas
por id usam `_buscar`, que confere o dono antes de devolver o registro: sem
isso, bastaria adivinhar um id para editar o lançamento de outra pessoa.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid
from decimal import Decimal

import pandas as pd
from sqlalchemy import delete, func, select

from . import escopo
from .db import get_session
from .models import (
    Cartao,
    Categoria,
    Conta,
    Investimento,
    MovimentoInvestimento,
    Objetivo,
    Orcamento,
    Transacao,
)

# --------------------------------------------------------------------------- #
# Escopo
# --------------------------------------------------------------------------- #


def _ws() -> int:
    """Workspace ativo. Levanta `SemWorkspace` se não houver — nunca devolve tudo."""
    return escopo.atual()


def _buscar(s, Model, id_: int | None):
    """Carrega um registro só se ele for do workspace ativo.

    Devolve None quando o id não existe *ou* é de outra carteira. As duas
    situações são a mesma coisa do ponto de vista de quem pediu: aquele
    registro não existe para essa pessoa.
    """
    if id_ is None:
        return None
    obj = s.get(Model, id_)
    if obj is None or obj.workspace_id != _ws():
        return None
    return obj


def _existe(s, Model, id_: int | None) -> int | None:
    """Valida uma chave estrangeira apontada pela tela. Devolve o id ou None."""
    return None if _buscar(s, Model, id_) is None else id_


# --------------------------------------------------------------------------- #
# Datas
# --------------------------------------------------------------------------- #


def comp(ano: int, mes: int) -> dt.date:
    """Competência = primeiro dia do mês."""
    return dt.date(ano, mes, 1)


def somar_meses(data: dt.date, n: int) -> dt.date:
    total = data.month - 1 + n
    ano = data.year + total // 12
    mes = total % 12 + 1
    dia = min(data.day, _ultimo_dia(ano, mes))
    return dt.date(ano, mes, dia)


def _ultimo_dia(ano: int, mes: int) -> int:
    prox = dt.date(ano + (mes == 12), (mes % 12) + 1, 1)
    return (prox - dt.timedelta(days=1)).day


def competencia_de(data: dt.date, cartao: Cartao | None) -> dt.date:
    """Mês em que o gasto entra no orçamento.

    No cartão, uma compra depois do fechamento cai na fatura do mês seguinte.
    """
    if cartao is None:
        return comp(data.year, data.month)
    base = comp(data.year, data.month)
    return base if data.day <= (cartao.dia_fechamento or 31) else somar_meses(base, 1)


MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def rotulo_mes(c: dt.date) -> str:
    return f"{MESES_PT[c.month - 1].capitalize()} {c.year}"


def _f(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def parse_valor(bruto) -> float:
    """Lê um valor monetário escrito de qualquer jeito e devolve float.

    Entende `R$ 1.592,00` (padrão brasileiro) e também `1592.00` (como muitos
    bancos e o Google Sheets exportam). A regra: quando só há pontos, eles são
    separador de milhar apenas se cada grupo depois deles tiver exatamente três
    dígitos — senão o ponto é decimal. Assim `1.592` vira 1592 e `1592.00`
    continua 1592,00 em vez de virar 159200.
    """
    if bruto is None:
        return 0.0
    if isinstance(bruto, (int, float, Decimal)):
        return float(bruto)

    t = str(bruto).strip()
    if not t:
        return 0.0

    negativo = t.startswith("-") or (t.startswith("(") and t.endswith(")"))
    t = re.sub(r"[^\d.,]", "", t)
    if not t:
        return 0.0

    if "," in t:  # vírgula sempre é o decimal
        t = t.replace(".", "").replace(",", ".")
    elif "." in t:
        grupos = t.split(".")
        if len(grupos) > 1 and all(len(g) == 3 for g in grupos[1:]):
            t = "".join(grupos)  # 1.592 / 1.592.300 → milhar

    try:
        valor = float(t)
    except ValueError:
        raise ValueError(f"não entendi o valor {bruto!r}") from None
    return -valor if negativo else valor


# --------------------------------------------------------------------------- #
# Cadastros
# --------------------------------------------------------------------------- #


def listar_categorias(tipo: str | None = None, apenas_ativas: bool = True) -> pd.DataFrame:
    with get_session() as s:
        q = select(Categoria).where(Categoria.workspace_id == _ws())
        if tipo:
            q = q.where(Categoria.tipo == tipo)
        if apenas_ativas:
            q = q.where(Categoria.ativa.is_(True))
        linhas = s.scalars(q.order_by(Categoria.tipo, Categoria.nome)).all()
    return pd.DataFrame(
        [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "cor": c.cor} for c in linhas],
        columns=["id", "nome", "tipo", "cor"],
    )


class NomeRepetido(ValueError):
    """Já existe um registro com esse nome nesta carteira."""


def _exigir_nome_livre(s, Model, nome: str, id_: int | None, rotulo: str, *extra) -> str:
    """Devolve o nome limpo ou levanta NomeRepetido/ValueError.

    A comparação ignora caixa: "nubank" e "Nubank" seriam a mesma conta para
    quem usa, e o índice único do banco não sabe disso.
    """
    nome = nome.strip()
    if not nome:
        raise ValueError(f"Dê um nome ao {rotulo}." if rotulo[-1] != "a" else f"Dê um nome à {rotulo}.")
    repetido = s.scalar(
        select(Model).where(
            Model.workspace_id == _ws(),
            func.lower(Model.nome) == nome.lower(),
            Model.id != (id_ or 0),
            *extra,
        )
    )
    if repetido is not None:
        raise NomeRepetido(f'Já existe {rotulo} "{repetido.nome}".')
    return nome


def salvar_categoria(nome: str, tipo: str, cor: str, id_: int | None = None) -> None:
    """Cria ou renomeia. Renomear reflete nos lançamentos: eles guardam o id."""
    with get_session() as s:
        nome = _exigir_nome_livre(s, Categoria, nome, id_, "categoria", Categoria.tipo == tipo)
        obj = _buscar(s, Categoria, id_) if id_ else Categoria(workspace_id=_ws())
        if obj is None:
            return
        obj.nome, obj.tipo, obj.cor = nome, tipo, cor
        s.add(obj)
        s.commit()


def arquivar_categoria(id_: int) -> None:
    with get_session() as s:
        obj = _buscar(s, Categoria, id_)
        if obj:
            obj.ativa = False
            s.commit()


def listar_contas(apenas_ativas: bool = True) -> pd.DataFrame:
    with get_session() as s:
        q = select(Conta).where(Conta.workspace_id == _ws())
        if apenas_ativas:
            q = q.where(Conta.ativa.is_(True))
        linhas = s.scalars(q.order_by(Conta.nome)).all()
    return pd.DataFrame(
        [
            {"id": c.id, "nome": c.nome, "tipo": c.tipo, "saldo_inicial": _f(c.saldo_inicial)}
            for c in linhas
        ],
        columns=["id", "nome", "tipo", "saldo_inicial"],
    )


def salvar_conta(nome: str, tipo: str, saldo_inicial: float, id_: int | None = None) -> None:
    with get_session() as s:
        nome = _exigir_nome_livre(s, Conta, nome, id_, "conta")
        obj = _buscar(s, Conta, id_) if id_ else Conta(workspace_id=_ws())
        if obj is None:
            return
        obj.nome, obj.tipo, obj.saldo_inicial = nome, tipo, saldo_inicial
        s.add(obj)
        s.commit()


def arquivar_conta(id_: int) -> None:
    """Esconde a conta. Os lançamentos dela continuam existindo e contando."""
    with get_session() as s:
        obj = _buscar(s, Conta, id_)
        if obj:
            obj.ativa = False
            s.commit()


def listar_cartoes(apenas_ativos: bool = True) -> pd.DataFrame:
    with get_session() as s:
        q = select(Cartao).where(Cartao.workspace_id == _ws())
        if apenas_ativos:
            q = q.where(Cartao.ativo.is_(True))
        linhas = s.scalars(q.order_by(Cartao.nome)).all()
    return pd.DataFrame(
        [
            {
                "id": c.id,
                "nome": c.nome,
                "banco": c.banco,
                "limite": _f(c.limite),
                "dia_fechamento": c.dia_fechamento,
                "dia_vencimento": c.dia_vencimento,
            }
            for c in linhas
        ],
        columns=["id", "nome", "banco", "limite", "dia_fechamento", "dia_vencimento"],
    )


def salvar_cartao(
    nome: str,
    banco: str,
    limite: float,
    dia_fechamento: int,
    dia_vencimento: int,
    id_: int | None = None,
) -> None:
    with get_session() as s:
        nome = _exigir_nome_livre(s, Cartao, nome, id_, "cartão")
        obj = _buscar(s, Cartao, id_) if id_ else Cartao(workspace_id=_ws())
        if obj is None:
            return
        fechamento_mudou = bool(id_) and obj.dia_fechamento != dia_fechamento
        obj.nome, obj.banco, obj.limite = nome, banco.strip(), limite
        obj.dia_fechamento, obj.dia_vencimento = dia_fechamento, dia_vencimento
        s.add(obj)
        if fechamento_mudou:
            # O dia de fechamento decide em que fatura cada compra cai. Mudou,
            # cada lançamento do cartão precisa reencontrar o seu mês.
            for t in s.scalars(
                select(Transacao).where(
                    Transacao.workspace_id == _ws(), Transacao.cartao_id == obj.id
                )
            ).all():
                t.competencia = competencia_de(t.data, obj)
        s.commit()


def excluir_cartao(id_: int) -> None:
    with get_session() as s:
        obj = _buscar(s, Cartao, id_)
        if obj:
            obj.ativo = False
            s.commit()


# --------------------------------------------------------------------------- #
# Transações
# --------------------------------------------------------------------------- #


def salvar_transacao(
    *,
    data: dt.date,
    descricao: str,
    valor: float,
    tipo: str,
    categoria_id: int | None,
    conta_id: int | None = None,
    cartao_id: int | None = None,
    pago: bool = True,
    observacao: str = "",
    parcelas: int = 1,
    repetir_meses: int = 1,
    id_: int | None = None,
) -> None:
    """Cria (ou edita) um lançamento.

    `parcelas` divide o valor em N meses; `repetir_meses` repete o valor cheio
    em N meses (contas fixas). Use um ou outro.
    """
    ws = _ws()
    with get_session() as s:
        # Categoria, conta e cartão vêm da tela como ids soltos. Se apontarem
        # para outra carteira viram None em vez de criar um vínculo cruzado.
        categoria_id = _existe(s, Categoria, categoria_id)
        conta_id = _existe(s, Conta, conta_id)
        cartao = _buscar(s, Cartao, cartao_id)
        cartao_id = cartao.id if cartao else None

        if id_:
            obj = _buscar(s, Transacao, id_)
            if obj is None:
                return
            obj.data, obj.descricao, obj.valor = data, descricao.strip(), valor
            obj.tipo, obj.categoria_id = tipo, categoria_id
            obj.conta_id, obj.cartao_id = conta_id, cartao_id
            obj.pago, obj.observacao = pago, observacao
            obj.competencia = competencia_de(data, cartao)
            s.commit()
            return

        n = max(int(parcelas), 1)
        repeticoes = max(int(repetir_meses), 1)
        if n > 1:
            repeticoes, valor_parcela = n, round(valor / n, 2)
        else:
            valor_parcela = valor

        grupo = uuid.uuid4().hex[:16] if repeticoes > 1 else None
        for i in range(repeticoes):
            data_i = somar_meses(data, i)
            s.add(
                Transacao(
                    workspace_id=ws,
                    data=data_i,
                    competencia=competencia_de(data_i, cartao),
                    descricao=descricao.strip(),
                    valor=valor_parcela,
                    tipo=tipo,
                    categoria_id=categoria_id,
                    conta_id=conta_id,
                    cartao_id=cartao_id,
                    pago=pago if i == 0 else False,
                    observacao=observacao,
                    parcela_num=i + 1 if n > 1 else 1,
                    parcela_total=n,
                    grupo=grupo,
                )
            )
        s.commit()


def excluir_transacao(id_: int, grupo_inteiro: bool = False) -> None:
    with get_session() as s:
        obj = _buscar(s, Transacao, id_)
        if obj is None:
            return
        if grupo_inteiro and obj.grupo:
            s.execute(
                delete(Transacao).where(
                    Transacao.grupo == obj.grupo, Transacao.workspace_id == _ws()
                )
            )
        else:
            s.delete(obj)
        s.commit()


def obter_transacao(id_: int) -> dict | None:
    """Um lançamento pronto para preencher o formulário de edição."""
    with get_session() as s:
        t = _buscar(s, Transacao, id_)
        if t is None:
            return None
        tamanho_grupo = (
            s.scalar(
                select(func.count()).select_from(Transacao).where(
                    Transacao.grupo == t.grupo, Transacao.workspace_id == _ws()
                )
            )
            if t.grupo
            else 1
        )
        return {
            "id": t.id,
            "data": t.data,
            "descricao": t.descricao,
            "valor": _f(t.valor),
            "tipo": t.tipo,
            "categoria_id": t.categoria_id,
            "conta_id": t.conta_id,
            "cartao_id": t.cartao_id,
            "pago": bool(t.pago),
            "observacao": t.observacao or "",
            "grupo": t.grupo,
            "parcela_num": t.parcela_num,
            "parcela_total": t.parcela_total,
            "tamanho_grupo": int(tamanho_grupo),
        }


def editar_grupo(
    id_: int,
    *,
    descricao: str,
    valor: float,
    tipo: str,
    categoria_id: int | None,
    conta_id: int | None,
    cartao_id: int | None,
    observacao: str = "",
) -> int:
    """Aplica a mesma mudança a todas as parcelas/repetições do lançamento.

    Data e situação de pago ficam como estão em cada linha — são o que
    distingue uma parcela da outra. Trocar o cartão recalcula a competência de
    cada uma, porque o dia de fechamento pode mudar o mês da fatura.
    Devolve quantos lançamentos foram alterados.
    """
    with get_session() as s:
        alvo = _buscar(s, Transacao, id_)
        if alvo is None:
            return 0
        categoria_id = _existe(s, Categoria, categoria_id)
        conta_id = _existe(s, Conta, conta_id)
        cartao = _buscar(s, Cartao, cartao_id)
        cartao_id = cartao.id if cartao else None

        if alvo.grupo:
            linhas = s.scalars(
                select(Transacao).where(
                    Transacao.grupo == alvo.grupo, Transacao.workspace_id == _ws()
                )
            ).all()
        else:
            linhas = [alvo]

        for t in linhas:
            t.descricao, t.valor, t.tipo = descricao.strip(), valor, tipo
            t.categoria_id, t.conta_id, t.cartao_id = categoria_id, conta_id, cartao_id
            t.observacao = observacao
            t.competencia = competencia_de(t.data, cartao)
        s.commit()
        return len(linhas)


def marcar_pagos(ids: list[int], pago: bool = True) -> int:
    """Marca vários lançamentos de uma vez. Devolve quantos mudaram.

    Caso típico: a fatura foi paga, então toda compra do cartão naquele mês
    vira paga. Só alcança lançamentos da carteira ativa — id de fora é ignorado.
    """
    ids = [int(i) for i in ids]
    if not ids:
        return 0
    with get_session() as s:
        linhas = s.scalars(
            select(Transacao).where(
                Transacao.workspace_id == _ws(),
                Transacao.id.in_(ids),
                Transacao.pago.is_(not pago),
            )
        ).all()
        for t in linhas:
            t.pago = pago
        s.commit()
        return len(linhas)


def alternar_pago(id_: int) -> None:
    with get_session() as s:
        obj = _buscar(s, Transacao, id_)
        if obj:
            obj.pago = not obj.pago
            s.commit()


def transacoes(
    competencia: dt.date | None = None,
    tipo: str | None = None,
    cartao_id: int | None = None,
) -> pd.DataFrame:
    colunas = [
        "id", "data", "competencia", "descricao", "valor", "tipo", "pago",
        "categoria", "categoria_id", "cor", "conta", "cartao", "cartao_id",
        "parcela", "grupo", "observacao",
    ]
    with get_session() as s:
        q = select(Transacao).where(Transacao.workspace_id == _ws())
        if competencia is not None:
            q = q.where(Transacao.competencia == competencia)
        if tipo:
            q = q.where(Transacao.tipo == tipo)
        if cartao_id:
            q = q.where(Transacao.cartao_id == cartao_id)
        linhas = s.scalars(q.order_by(Transacao.data.desc(), Transacao.id.desc())).all()

        registros = [
            {
                "id": t.id,
                "data": t.data,
                "competencia": t.competencia,
                "descricao": t.descricao,
                "valor": _f(t.valor),
                "tipo": t.tipo,
                "pago": bool(t.pago),
                "categoria": t.categoria.nome if t.categoria else "Sem categoria",
                "categoria_id": t.categoria_id,
                "cor": t.categoria.cor if t.categoria else "#8A8F94",
                "conta": t.conta.nome if t.conta else "",
                "cartao": t.cartao.nome if t.cartao else "",
                "cartao_id": t.cartao_id,
                "parcela": f"{t.parcela_num}/{t.parcela_total}" if t.parcela_total > 1 else "",
                "grupo": t.grupo,
                "observacao": t.observacao or "",
            }
            for t in linhas
        ]
    return pd.DataFrame(registros, columns=colunas)


def resumo_mes(competencia: dt.date) -> dict:
    df = transacoes(competencia)
    receitas = df.loc[df.tipo == "receita", "valor"].sum() if not df.empty else 0.0
    despesas = df.loc[df.tipo == "despesa", "valor"].sum() if not df.empty else 0.0
    pagas = (
        df.loc[(df.tipo == "despesa") & df.pago, "valor"].sum() if not df.empty else 0.0
    )
    return {
        "receitas": float(receitas),
        "despesas": float(despesas),
        "despesas_pagas": float(pagas),
        "a_pagar": float(despesas - pagas),
        "balanco": float(receitas - despesas),
    }


def saldo_total() -> float:
    """Saldo em conta: saldo inicial + receitas pagas - despesas pagas (fora cartão)."""
    ws = _ws()
    with get_session() as s:
        inicial = _f(
            s.scalar(
                select(func.sum(Conta.saldo_inicial)).where(
                    Conta.workspace_id == ws, Conta.ativa.is_(True)
                )
            )
        )
        entradas = _f(
            s.scalar(
                select(func.sum(Transacao.valor)).where(
                    Transacao.workspace_id == ws,
                    Transacao.tipo == "receita",
                    Transacao.pago.is_(True),
                )
            )
        )
        saidas = _f(
            s.scalar(
                select(func.sum(Transacao.valor)).where(
                    Transacao.workspace_id == ws,
                    Transacao.tipo == "despesa",
                    Transacao.pago.is_(True),
                    Transacao.cartao_id.is_(None),
                )
            )
        )
    return inicial + entradas - saidas


def saldo_por_conta() -> pd.DataFrame:
    """Quanto há em cada conta ativa, negativo inclusive.

    saldo = inicial + receitas pagas - despesas pagas fora do cartão. A mesma
    regra do saldo total, só que aberta por conta. Lançamento pago sem conta
    vira a linha "Sem conta", para a soma continuar batendo com o total.
    """
    ws = _ws()
    colunas = ["id", "nome", "tipo", "saldo_inicial", "entradas", "saidas", "saldo"]
    with get_session() as s:
        contas = s.scalars(
            select(Conta)
            .where(Conta.workspace_id == ws, Conta.ativa.is_(True))
            .order_by(Conta.nome)
        ).all()

        def por_conta(*cond):
            return {
                cid: _f(v)
                for cid, v in s.execute(
                    select(Transacao.conta_id, func.sum(Transacao.valor))
                    .where(Transacao.workspace_id == ws, Transacao.pago.is_(True), *cond)
                    .group_by(Transacao.conta_id)
                ).all()
            }

        entradas = por_conta(Transacao.tipo == "receita")
        saidas = por_conta(Transacao.tipo == "despesa", Transacao.cartao_id.is_(None))

    linhas = [
        {
            "id": c.id, "nome": c.nome, "tipo": c.tipo, "saldo_inicial": _f(c.saldo_inicial),
            "entradas": entradas.get(c.id, 0.0), "saidas": saidas.get(c.id, 0.0),
            "saldo": _f(c.saldo_inicial) + entradas.get(c.id, 0.0) - saidas.get(c.id, 0.0),
        }
        for c in contas
    ]
    soltas_e, soltas_s = entradas.get(None, 0.0), saidas.get(None, 0.0)
    if soltas_e or soltas_s:
        linhas.append({
            "id": None, "nome": "Sem conta", "tipo": "—", "saldo_inicial": 0.0,
            "entradas": soltas_e, "saidas": soltas_s, "saldo": soltas_e - soltas_s,
        })
    return pd.DataFrame(linhas, columns=colunas)


def por_categoria(competencia: dt.date, tipo: str) -> pd.DataFrame:
    """Total do mês por categoria, com quanto já está pago. Maior primeiro."""
    df = transacoes(competencia, tipo=tipo)
    colunas = ["categoria", "cor", "total", "pago", "pendente", "itens"]
    if df.empty:
        return pd.DataFrame(columns=colunas)
    df = df.assign(pago_v=df["valor"].where(df["pago"], 0.0))
    g = (
        df.groupby(["categoria", "cor"], as_index=False)
        .agg(total=("valor", "sum"), pago=("pago_v", "sum"), itens=("id", "count"))
    )
    g["pendente"] = g["total"] - g["pago"]
    return g.sort_values("total", ascending=False)[colunas].reset_index(drop=True)


def serie_mensal(meses: int = 12, ate: dt.date | None = None) -> pd.DataFrame:
    """Receitas x despesas dos últimos N meses."""
    fim = ate or dt.date.today().replace(day=1)
    inicio = somar_meses(fim, -(meses - 1))
    with get_session() as s:
        linhas = s.execute(
            select(
                Transacao.competencia,
                Transacao.tipo,
                func.sum(Transacao.valor),
            )
            .where(
                Transacao.workspace_id == _ws(),
                Transacao.competencia >= inicio,
                Transacao.competencia <= fim,
            )
            .group_by(Transacao.competencia, Transacao.tipo)
        ).all()

    base = pd.DataFrame(
        {"competencia": [somar_meses(inicio, i) for i in range(meses)]}
    )
    base["receitas"] = 0.0
    base["despesas"] = 0.0
    idx = {c: i for i, c in enumerate(base["competencia"])}
    for competencia, tipo, total in linhas:
        if isinstance(competencia, dt.datetime):
            competencia = competencia.date()
        if competencia in idx:
            base.loc[idx[competencia], "receitas" if tipo == "receita" else "despesas"] = _f(total)
    base["saldo"] = base["receitas"] - base["despesas"]
    base["mes"] = [f"{MESES_PT[c.month - 1][:3]}/{str(c.year)[2:]}" for c in base["competencia"]]
    return base


# --------------------------------------------------------------------------- #
# Orçamento
# --------------------------------------------------------------------------- #


def orcamento_mes(competencia: dt.date) -> pd.DataFrame:
    """Planejado x gasto por categoria de despesa."""
    ws = _ws()
    with get_session() as s:
        metas = {
            o.categoria_id: _f(o.valor)
            for o in s.scalars(
                select(Orcamento).where(
                    Orcamento.workspace_id == ws, Orcamento.competencia == competencia
                )
            ).all()
        }
        cats = s.scalars(
            select(Categoria)
            .where(
                Categoria.workspace_id == ws,
                Categoria.tipo == "despesa",
                Categoria.ativa.is_(True),
            )
            .order_by(Categoria.nome)
        ).all()
        gastos_rows = s.execute(
            select(Transacao.categoria_id, func.sum(Transacao.valor))
            .where(
                Transacao.workspace_id == ws,
                Transacao.competencia == competencia,
                Transacao.tipo == "despesa",
            )
            .group_by(Transacao.categoria_id)
        ).all()
        gastos = {cid: _f(v) for cid, v in gastos_rows}

    registros = []
    for c in cats:
        planejado = metas.get(c.id, 0.0)
        gasto = gastos.get(c.id, 0.0)
        if planejado == 0 and gasto == 0:
            continue
        registros.append(
            {
                "categoria_id": c.id,
                "categoria": c.nome,
                "cor": c.cor,
                "planejado": planejado,
                "gasto": gasto,
                "restante": planejado - gasto,
                "uso": (gasto / planejado * 100) if planejado else 0.0,
            }
        )
    return pd.DataFrame(
        registros,
        columns=["categoria_id", "categoria", "cor", "planejado", "gasto", "restante", "uso"],
    )


def definir_orcamento(competencia: dt.date, categoria_id: int, valor: float) -> None:
    ws = _ws()
    with get_session() as s:
        if _buscar(s, Categoria, categoria_id) is None:
            return
        obj = s.scalar(
            select(Orcamento).where(
                Orcamento.workspace_id == ws,
                Orcamento.competencia == competencia,
                Orcamento.categoria_id == categoria_id,
            )
        )
        if valor <= 0:
            if obj:
                s.delete(obj)
        elif obj:
            obj.valor = valor
        else:
            s.add(
                Orcamento(
                    workspace_id=ws,
                    competencia=competencia,
                    categoria_id=categoria_id,
                    valor=valor,
                )
            )
        s.commit()


def copiar_orcamento(de: dt.date, para: dt.date) -> int:
    """Copia as metas de um mês para outro. É o que substitui o 'copiar a planilha'."""
    ws = _ws()
    with get_session() as s:
        origem = s.scalars(
            select(Orcamento).where(Orcamento.workspace_id == ws, Orcamento.competencia == de)
        ).all()
        existentes = {
            o.categoria_id
            for o in s.scalars(
                select(Orcamento).where(
                    Orcamento.workspace_id == ws, Orcamento.competencia == para
                )
            ).all()
        }
        novos = 0
        for o in origem:
            if o.categoria_id in existentes:
                continue
            s.add(
                Orcamento(
                    workspace_id=ws,
                    competencia=para,
                    categoria_id=o.categoria_id,
                    valor=o.valor,
                )
            )
            novos += 1
        s.commit()
    return novos


def copiar_lancamentos(de: dt.date, para: dt.date, apenas_ids: list[int] | None = None) -> int:
    """Repete lançamentos de um mês no outro (contas fixas, salário)."""
    ws = _ws()
    with get_session() as s:
        q = select(Transacao).where(
            Transacao.workspace_id == ws, Transacao.competencia == de
        )
        if apenas_ids:
            q = q.where(Transacao.id.in_(apenas_ids))
        origem = s.scalars(q).all()
        delta = (para.year - de.year) * 12 + (para.month - de.month)
        for t in origem:
            nova_data = somar_meses(t.data, delta)
            s.add(
                Transacao(
                    workspace_id=ws,
                    data=nova_data,
                    competencia=para,
                    descricao=t.descricao,
                    valor=t.valor,
                    tipo=t.tipo,
                    categoria_id=t.categoria_id,
                    conta_id=t.conta_id,
                    cartao_id=t.cartao_id,
                    pago=False,
                    observacao=t.observacao,
                )
            )
        s.commit()
    return len(origem)


# --------------------------------------------------------------------------- #
# Cartões
# --------------------------------------------------------------------------- #


def faturas(competencia: dt.date) -> pd.DataFrame:
    cartoes = listar_cartoes()
    if cartoes.empty:
        return pd.DataFrame(columns=["cartao_id", "cartao", "banco", "total", "limite", "uso"])
    df = transacoes(competencia, tipo="despesa")
    registros = []
    for _, c in cartoes.iterrows():
        total = float(df.loc[df.cartao_id == c["id"], "valor"].sum()) if not df.empty else 0.0
        registros.append(
            {
                "cartao_id": c["id"],
                "cartao": c["nome"],
                "banco": c["banco"],
                "total": total,
                "limite": c["limite"],
                "uso": (total / c["limite"] * 100) if c["limite"] else 0.0,
            }
        )
    return pd.DataFrame(registros)


# --------------------------------------------------------------------------- #
# Investimentos
# --------------------------------------------------------------------------- #


def listar_investimentos() -> pd.DataFrame:
    ws = _ws()
    with get_session() as s:
        invs = s.scalars(
            select(Investimento)
            .where(Investimento.workspace_id == ws, Investimento.ativo.is_(True))
            .order_by(Investimento.nome)
        ).all()
        movs = s.scalars(
            select(MovimentoInvestimento).where(MovimentoInvestimento.workspace_id == ws)
        ).all()

    saldo: dict[int, float] = {}
    aportado: dict[int, float] = {}
    rendimento: dict[int, float] = {}
    for m in movs:
        v = _f(m.valor)
        if m.tipo == "aporte":
            saldo[m.investimento_id] = saldo.get(m.investimento_id, 0) + v
            aportado[m.investimento_id] = aportado.get(m.investimento_id, 0) + v
        elif m.tipo == "resgate":
            saldo[m.investimento_id] = saldo.get(m.investimento_id, 0) - v
            aportado[m.investimento_id] = aportado.get(m.investimento_id, 0) - v
        else:  # rendimento
            saldo[m.investimento_id] = saldo.get(m.investimento_id, 0) + v
            rendimento[m.investimento_id] = rendimento.get(m.investimento_id, 0) + v

    return pd.DataFrame(
        [
            {
                "id": i.id,
                "nome": i.nome,
                "tipo": i.tipo,
                "instituicao": i.instituicao,
                "aportado": aportado.get(i.id, 0.0),
                "rendimento": rendimento.get(i.id, 0.0),
                "saldo": saldo.get(i.id, 0.0),
            }
            for i in invs
        ],
        columns=["id", "nome", "tipo", "instituicao", "aportado", "rendimento", "saldo"],
    )


def salvar_investimento(nome: str, tipo: str, instituicao: str, id_: int | None = None) -> None:
    with get_session() as s:
        obj = _buscar(s, Investimento, id_) if id_ else Investimento(workspace_id=_ws())
        if obj is None:
            return
        obj.nome, obj.tipo, obj.instituicao = nome.strip(), tipo, instituicao.strip()
        s.add(obj)
        s.commit()


def salvar_movimento_investimento(
    investimento_id: int, data: dt.date, tipo: str, valor: float, observacao: str = ""
) -> None:
    ws = _ws()
    with get_session() as s:
        if _buscar(s, Investimento, investimento_id) is None:
            return
        s.add(
            MovimentoInvestimento(
                workspace_id=ws,
                investimento_id=investimento_id,
                data=data,
                tipo=tipo,
                valor=valor,
                observacao=observacao,
            )
        )
        s.commit()


def movimentos_investimento(investimento_id: int | None = None) -> pd.DataFrame:
    with get_session() as s:
        q = select(MovimentoInvestimento).where(MovimentoInvestimento.workspace_id == _ws())
        if investimento_id:
            q = q.where(MovimentoInvestimento.investimento_id == investimento_id)
        movs = s.scalars(q.order_by(MovimentoInvestimento.data.desc())).all()
        registros = [
            {
                "id": m.id,
                "data": m.data,
                "investimento": m.investimento.nome if m.investimento else "",
                "tipo": m.tipo,
                "valor": _f(m.valor),
                "observacao": m.observacao or "",
            }
            for m in movs
        ]
    return pd.DataFrame(
        registros, columns=["id", "data", "investimento", "tipo", "valor", "observacao"]
    )


def excluir_movimento_investimento(id_: int) -> None:
    with get_session() as s:
        obj = _buscar(s, MovimentoInvestimento, id_)
        if obj:
            s.delete(obj)
            s.commit()


def evolucao_patrimonio(meses: int = 12) -> pd.DataFrame:
    movs = movimentos_investimento()
    fim = dt.date.today().replace(day=1)
    linha = [somar_meses(fim, -(meses - 1 - i)) for i in range(meses)]
    valores = []
    acumulado = 0.0
    for c in linha:
        limite = somar_meses(c, 1)
        if not movs.empty:
            do_mes = movs[(movs.data >= c) & (movs.data < limite)]
            for _, m in do_mes.iterrows():
                acumulado += -m.valor if m.tipo == "resgate" else m.valor
        valores.append(acumulado)
    return pd.DataFrame(
        {
            "competencia": linha,
            "mes": [f"{MESES_PT[c.month - 1][:3]}/{str(c.year)[2:]}" for c in linha],
            "patrimonio": valores,
        }
    )


# --------------------------------------------------------------------------- #
# Objetivos
# --------------------------------------------------------------------------- #


def listar_objetivos() -> pd.DataFrame:
    with get_session() as s:
        objs = s.scalars(
            select(Objetivo)
            .where(Objetivo.workspace_id == _ws())
            .order_by(Objetivo.concluido, Objetivo.id)
        ).all()
        registros = [
            {
                "id": o.id,
                "nome": o.nome,
                "valor_alvo": _f(o.valor_alvo),
                "valor_atual": _f(o.valor_atual),
                "data_alvo": o.data_alvo,
                "concluido": bool(o.concluido),
                "progresso": (_f(o.valor_atual) / _f(o.valor_alvo) * 100)
                if _f(o.valor_alvo)
                else 0.0,
            }
            for o in objs
        ]
    return pd.DataFrame(
        registros,
        columns=["id", "nome", "valor_alvo", "valor_atual", "data_alvo", "concluido", "progresso"],
    )


def salvar_objetivo(
    nome: str,
    valor_alvo: float,
    valor_atual: float,
    data_alvo: dt.date | None,
    id_: int | None = None,
) -> None:
    with get_session() as s:
        obj = _buscar(s, Objetivo, id_) if id_ else Objetivo(workspace_id=_ws())
        if obj is None:
            return
        obj.nome, obj.valor_alvo, obj.valor_atual = nome.strip(), valor_alvo, valor_atual
        obj.data_alvo = data_alvo
        obj.concluido = valor_alvo > 0 and valor_atual >= valor_alvo
        s.add(obj)
        s.commit()


def excluir_objetivo(id_: int) -> None:
    with get_session() as s:
        obj = _buscar(s, Objetivo, id_)
        if obj:
            s.delete(obj)
            s.commit()


# --------------------------------------------------------------------------- #
# Importação / exportação
# --------------------------------------------------------------------------- #


def importar_transacoes(df: pd.DataFrame) -> tuple[int, list[str]]:
    """Importa um DataFrame com as colunas:
    data, descricao, valor, tipo, categoria, conta, cartao.
    Categorias e contas que não existirem são criadas.
    """
    ws = _ws()
    erros: list[str] = []
    inseridos = 0
    with get_session() as s:
        cats = {
            (c.nome.lower(), c.tipo): c
            for c in s.scalars(select(Categoria).where(Categoria.workspace_id == ws)).all()
        }
        contas = {
            c.nome.lower(): c
            for c in s.scalars(select(Conta).where(Conta.workspace_id == ws)).all()
        }
        cartoes = {
            c.nome.lower(): c
            for c in s.scalars(select(Cartao).where(Cartao.workspace_id == ws)).all()
        }

        for i, linha in df.iterrows():
            try:
                data = pd.to_datetime(linha["data"], dayfirst=True).date()
                valor = parse_valor(linha["valor"])
                if valor == 0:
                    continue
                tipo = str(linha.get("tipo", "despesa")).strip().lower()
                tipo = "receita" if tipo.startswith("r") else "despesa"

                nome_cat = str(linha.get("categoria") or "Outros").strip()
                chave = (nome_cat.lower(), tipo)
                if chave not in cats:
                    nova = Categoria(workspace_id=ws, nome=nome_cat, tipo=tipo)
                    s.add(nova)
                    s.flush()
                    cats[chave] = nova

                conta = None
                nome_conta = str(linha.get("conta") or "").strip()
                if nome_conta:
                    if nome_conta.lower() not in contas:
                        nova_conta = Conta(workspace_id=ws, nome=nome_conta)
                        s.add(nova_conta)
                        s.flush()
                        contas[nome_conta.lower()] = nova_conta
                    conta = contas[nome_conta.lower()]

                cartao = None
                nome_cartao = str(linha.get("cartao") or "").strip()
                if nome_cartao:
                    if nome_cartao.lower() not in cartoes:
                        novo_cartao = Cartao(
                            workspace_id=ws, nome=nome_cartao, banco=nome_cartao
                        )
                        s.add(novo_cartao)
                        s.flush()
                        cartoes[nome_cartao.lower()] = novo_cartao
                    cartao = cartoes[nome_cartao.lower()]

                s.add(
                    Transacao(
                        workspace_id=ws,
                        data=data,
                        competencia=competencia_de(data, cartao),
                        descricao=str(linha.get("descricao") or "(sem descrição)")[:160],
                        valor=abs(valor),
                        tipo=tipo,
                        categoria_id=cats[chave].id,
                        conta_id=conta.id if conta else None,
                        cartao_id=cartao.id if cartao else None,
                        pago=True,
                    )
                )
                inseridos += 1
            except Exception as exc:  # noqa: BLE001
                erros.append(f"linha {i + 2}: {exc}")
        s.commit()
    return inseridos, erros


def exportar_tudo() -> pd.DataFrame:
    df = transacoes()
    return df[
        ["data", "competencia", "descricao", "valor", "tipo", "categoria", "conta", "cartao", "pago", "parcela"]
    ]
