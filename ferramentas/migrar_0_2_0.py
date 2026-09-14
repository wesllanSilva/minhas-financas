"""Migra um banco da versão 0.1.x para o modelo multiusuário da 0.2.0.

O `create_all` cria tabela que falta, mas nunca altera tabela que já existe.
Um banco criado na 0.1.x tem as tabelas financeiras sem `workspace_id`, e o app
0.2.0 não sobe em cima dele. Este script faz a ponte, preservando o que já foi
lançado: cria as tabelas novas, acrescenta a coluna nas antigas e põe tudo que
já existia dentro de uma carteira.

Rode primeiro sem argumento nenhum: ele apenas olha e conta o que encontrou.

    python ferramentas/migrar_0_2_0.py

Para aplicar de verdade, informando o dono dos dados que já estão lá:

    python ferramentas/migrar_0_2_0.py --aplicar --email voce@exemplo.com \\
        --nome "Seu Nome" --senha "sua-senha" --carteira "Minhas contas"

O banco é o mesmo que o app usa: a variável de ambiente DATABASE_URL, ou o
SQLite local se ela não estiver definida.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, select, text  # noqa: E402

from core import auth  # noqa: E402
from core.db import database_url, get_engine, get_session  # noqa: E402
from core.models import COM_ESCOPO, Base, Usuario, Workspace  # noqa: E402

TABELAS = [m.__tablename__ for m in COM_ESCOPO]


def _colunas(engine, tabela: str) -> set[str]:
    inspetor = inspect(engine)
    if tabela not in inspetor.get_table_names():
        return set()
    return {c["name"] for c in inspetor.get_columns(tabela)}


def diagnosticar(engine) -> dict:
    inspetor = inspect(engine)
    existentes = set(inspetor.get_table_names())
    estado = {"faltando_coluna": [], "ja_migradas": [], "inexistentes": [], "linhas": {}}

    for tabela in TABELAS:
        if tabela not in existentes:
            estado["inexistentes"].append(tabela)
            continue
        colunas = _colunas(engine, tabela)
        destino = "ja_migradas" if "workspace_id" in colunas else "faltando_coluna"
        estado[destino].append(tabela)
        with engine.connect() as con:
            estado["linhas"][tabela] = con.execute(
                text(f'SELECT COUNT(*) FROM "{tabela}"')
            ).scalar_one()

    estado["tem_usuario"] = "usuario" in existentes
    return estado


def relatar(estado: dict) -> None:
    print(f"\nBanco: {database_url().split('@')[-1]}\n")
    total = sum(estado["linhas"].values())
    print(f"Registros financeiros encontrados: {total}")
    for tabela, n in sorted(estado["linhas"].items()):
        if n:
            print(f"  {tabela:26} {n}")

    if estado["faltando_coluna"]:
        print(f"\nPrecisam de workspace_id: {', '.join(estado['faltando_coluna'])}")
    if estado["ja_migradas"]:
        print(f"Já migradas: {', '.join(estado['ja_migradas'])}")
    if estado["inexistentes"]:
        print(f"Ainda não existem: {', '.join(estado['inexistentes'])}")


#: Nome único global na 0.1.x -> único por carteira na 0.2.0. Enquanto o índice
#: antigo existir, duas pessoas não conseguem ter cada uma o seu "Nubank".
UNICOS_A_TROCAR = {
    "conta": ("uq_conta_ws_nome", ["nome"]),
    "cartao": ("uq_cartao_ws_nome", ["nome"]),
    "investimento": ("uq_investimento_ws_nome", ["nome"]),
    "categoria": ("uq_categoria_ws_nome_tipo", ["nome", "tipo"]),
    "orcamento": ("uq_orcamento_ws_mes_cat", ["competencia", "categoria_id"]),
}


def _recriar_tabela_sqlite(engine, tabela: str) -> None:
    """Reconstrói uma tabela do SQLite com o schema atual, preservando as linhas.

    O SQLite não remove uma constraint declarada dentro do CREATE TABLE — e o
    UNIQUE global de `nome` na 0.1.x é exatamente assim. O jeito é recriar: a
    tabela nova sai do metadata do SQLAlchemy, então já nasce com o único
    composto certo.
    """
    modelo = Base.metadata.tables[tabela]
    atuais = _colunas(engine, tabela)
    comuns = [c.name for c in modelo.columns if c.name in atuais]
    lista = ", ".join(f'"{c}"' for c in comuns)
    provisorio = f"{tabela}__antigo"

    with engine.begin() as con:
        con.execute(text("PRAGMA foreign_keys=OFF"))
        con.execute(text(f'ALTER TABLE "{tabela}" RENAME TO "{provisorio}"'))

    modelo.create(engine)

    with engine.begin() as con:
        con.execute(text(f'INSERT INTO "{tabela}" ({lista}) SELECT {lista} FROM "{provisorio}"'))
        con.execute(text(f'DROP TABLE "{provisorio}"'))
        con.execute(text("PRAGMA foreign_keys=ON"))
    print(f"  ~ {tabela} recriada com o único por carteira")


def trocar_unicos(engine) -> None:
    """Derruba os únicos globais e cria os equivalentes por carteira."""
    existentes = set(inspect(engine).get_table_names())
    e_sqlite = engine.dialect.name == "sqlite"

    for tabela, (novo_nome, colunas) in UNICOS_A_TROCAR.items():
        if tabela not in existentes:
            continue
        alvo = set(colunas)
        inspetor = inspect(engine)

        # Já no formato novo? O único composto inclui workspace_id.
        composto = {"workspace_id", *colunas}
        ja_composto = any(
            set(i["column_names"]) == composto
            for i in inspetor.get_indexes(tabela)
            if i.get("unique")
        ) or any(
            set(c["column_names"]) == composto
            for c in inspetor.get_unique_constraints(tabela)
        )

        nomeados = [
            c["name"]
            for c in inspetor.get_unique_constraints(tabela)
            if set(c["column_names"]) == alvo and c["name"]
        ] + [
            i["name"]
            for i in inspetor.get_indexes(tabela)
            if i.get("unique") and set(i["column_names"]) == alvo and i["name"]
        ]

        for nome_antigo in dict.fromkeys(nomeados):
            with engine.begin() as con:
                try:
                    con.execute(text(f'ALTER TABLE "{tabela}" DROP CONSTRAINT "{nome_antigo}"'))
                except Exception:
                    try:
                        con.execute(text(f'DROP INDEX "{nome_antigo}"'))
                    except Exception as erro:
                        print(f"  ! não consegui remover {nome_antigo}: {erro}")
                        continue
            print(f"  - único global {nome_antigo} removido de {tabela}")

        if ja_composto:
            continue

        # No SQLite o UNIQUE inline não tem nome e não aparece acima; a única
        # saída é reconstruir a tabela.
        if e_sqlite and _tem_unico_inline(engine, tabela, colunas):
            _recriar_tabela_sqlite(engine, tabela)
            continue

        cols = ", ".join(f'"{c}"' for c in ["workspace_id", *colunas])
        with engine.begin() as con:
            con.execute(text(f'CREATE UNIQUE INDEX "{novo_nome}" ON "{tabela}" ({cols})'))
        print(f"  + único por carteira em {tabela} ({', '.join(colunas)})")


def _tem_unico_inline(engine, tabela: str, colunas: list[str]) -> bool:
    """Procura um UNIQUE sem nome no DDL original da tabela (caso do SQLite)."""
    with engine.connect() as con:
        ddl = con.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name = :t"),
            {"t": tabela},
        ).scalar()
    if not ddl:
        return False
    if len(colunas) == 1:
        alvo = colunas[0].lower()
        for linha in ddl.replace("(", "(\n").split(","):
            trecho = linha.strip().lower()
            if trecho.startswith(f'"{alvo}"') or trecho.startswith(f"{alvo} "):
                return "unique" in trecho
        return False
    return "unique (" in ddl.lower()


def aplicar(engine, email: str, nome: str, senha: str, carteira: str) -> None:
    """Acrescenta a coluna, cria o dono e adota os registros órfãos."""
    Base.metadata.create_all(engine)  # tabelas novas: usuario, workspace, membro, sessao

    pendentes = [t for t in TABELAS if "workspace_id" not in _colunas(engine, t)]
    with engine.begin() as con:
        for tabela in pendentes:
            # Sem NOT NULL nesta hora: as linhas antigas ainda não têm dono.
            con.execute(text(f'ALTER TABLE "{tabela}" ADD COLUMN workspace_id INTEGER'))
            print(f"  + workspace_id em {tabela}")

    with get_session() as s:
        usuario = s.scalar(select(Usuario).where(Usuario.email == auth.normalizar_email(email)))
    if usuario is None:
        # Sem semear: a carteira vai adotar as categorias e contas que já
        # existiam no banco, e semear por cima duplicaria cada uma delas.
        uid = auth.criar_usuario(email, nome, senha, nome_workspace=carteira, semear=False)
        print(f"  usuário criado: {email}")
        ws = auth.workspaces_de(uid)[0]["id"]
    else:
        print(f"  usuário {email} já existe; usando a carteira dele")
        ws = auth.workspaces_de(usuario.id)[0]["id"]

    with engine.begin() as con:
        for tabela in TABELAS:
            if "workspace_id" not in _colunas(engine, tabela):
                continue
            n = con.execute(
                text(f'UPDATE "{tabela}" SET workspace_id = :ws WHERE workspace_id IS NULL'),
                {"ws": ws},
            ).rowcount
            if n:
                print(f"  {tabela}: {n} registro(s) adotado(s) pela carteira {ws}")

    # Só agora: no SQLite a troca recria a tabela com workspace_id NOT NULL, e
    # as linhas antigas precisavam já ter dono.
    trocar_unicos(engine)

    with get_session() as s:
        nome_ws = s.get(Workspace, ws).nome
    print(f"\nPronto. Tudo que já existia agora pertence à carteira '{nome_ws}'.")
    print(f"Entre no app com {email} e confira se os lançamentos estão lá.")


def main() -> int:
    p = argparse.ArgumentParser(description="Migra o banco para o modelo multiusuário 0.2.0")
    p.add_argument("--aplicar", action="store_true", help="executa a migração (sem isso, só relata)")
    p.add_argument("--email", help="e-mail do dono dos dados que já estão no banco")
    p.add_argument("--nome", default="", help="nome desse dono")
    p.add_argument("--senha", help="senha dele (mínimo 8 caracteres)")
    p.add_argument("--carteira", default="Minhas contas", help="nome da carteira a criar")
    args = p.parse_args()

    engine = get_engine()
    estado = diagnosticar(engine)
    relatar(estado)

    if not args.aplicar:
        if estado["faltando_coluna"]:
            print("\nNada foi alterado. Para migrar de verdade, rode de novo com:")
            print('  --aplicar --email voce@exemplo.com --nome "Seu Nome" --senha "sua-senha"')
        else:
            print("\nNada a fazer: o banco já está no formato 0.2.0.")
        return 0

    if not (args.email and args.senha):
        print("\n--aplicar exige --email e --senha.", file=sys.stderr)
        return 2

    print("\nAplicando...")
    aplicar(engine, args.email, args.nome or args.email, args.senha, args.carteira)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
