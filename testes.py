"""Testes do app — rode com `python testes.py`.

Cria um banco SQLite descartável em `data/testes.db`, exercita as regras
(parcelas, contas fixas, fatura, orçamento, importação) e depois abre cada
tela para conferir que nenhuma quebra. O seu banco de verdade não é tocado.
"""
import datetime as dt
import os
import shutil

os.environ["DATABASE_URL"] = "sqlite:///data/testes.db"
os.environ.pop("APP_PASSWORD", None)
shutil.rmtree("data", ignore_errors=True)
os.makedirs("data", exist_ok=True)

import pandas as pd

from core import repo  # noqa: E402

falhas: list[str] = []


def check(nome, condicao, extra=""):
    print(("  ok     " if condicao else "  FALHA  ") + nome + (f"  [{extra}]" if extra else ""))
    if not condicao:
        falhas.append(nome)


print("\n--- valores em formatos diferentes ---")
for entrada, esperado in [
    ("R$ 1.592,00", 1592.0), ("45,90", 45.9), ("1592.00", 1592.0),
    ("1.592", 1592.0), ("1.234.567,89", 1234567.89), ("(85,00)", -85.0),
    ("R$ 3.000", 3000.0), ("", 0.0), (2500, 2500.0),
]:
    check(f"parse_valor({entrada!r})", abs(repo.parse_valor(entrada) - esperado) < 0.001)

print("\n== cadastros base ==")
cats = repo.listar_categorias()
check("categorias semeadas", len(cats) >= 20, f"{len(cats)}")
contas = repo.listar_contas()
check("conta padrao criada", len(contas) == 1, f"{len(contas)}")

conta_id = int(contas.iloc[0]["id"])
cat_desp = int(cats[cats.tipo == "despesa"].iloc[0]["id"])
cat_rec = int(cats[cats.tipo == "receita"].iloc[0]["id"])

repo.salvar_cartao("Nubank Teste", "Nubank", 5000, 25, 5)
cartoes = repo.listar_cartoes()
check("cartao salvo", len(cartoes) == 1)
cartao_id = int(cartoes.iloc[0]["id"])

print("\n== competencia da fatura (fechamento dia 25) ==")
from core.models import Cartao  # noqa: E402
from core.db import get_session  # noqa: E402

with get_session() as s:
    c = s.get(Cartao, cartao_id)
    antes = repo.competencia_de(dt.date(2026, 3, 20), c)
    depois = repo.competencia_de(dt.date(2026, 3, 26), c)
check("compra dia 20 cai em marco", antes == dt.date(2026, 3, 1), str(antes))
check("compra dia 26 cai em abril", depois == dt.date(2026, 4, 1), str(depois))

print("\n== lancamentos ==")
repo.salvar_transacao(
    data=dt.date(2026, 3, 5), descricao="Salario", valor=6000, tipo="receita",
    categoria_id=cat_rec, conta_id=conta_id,
)
repo.salvar_transacao(
    data=dt.date(2026, 3, 10), descricao="Mercado", valor=850.55, tipo="despesa",
    categoria_id=cat_desp, conta_id=conta_id,
)
repo.salvar_transacao(
    data=dt.date(2026, 3, 12), descricao="Cadeira", valor=600, tipo="despesa",
    categoria_id=cat_desp, cartao_id=cartao_id, parcelas=3,
)
repo.salvar_transacao(
    data=dt.date(2026, 3, 1), descricao="Aluguel", valor=2000, tipo="despesa",
    categoria_id=cat_desp, conta_id=conta_id, repetir_meses=12, pago=False,
)

mar = repo.comp(2026, 3)
tx = repo.transacoes(mar)
check("transacoes de marco", len(tx) == 4, f"{len(tx)}")

parc = tx[tx.descricao == "Cadeira"]
check("parcela 1/3 = 200,00", not parc.empty and abs(float(parc.iloc[0]["valor"]) - 200) < 0.01)

abr = repo.comp(2026, 4)
tx_abr = repo.transacoes(abr)
check("abril tem parcela 2 + aluguel", len(tx_abr) == 2, f"{len(tx_abr)}")

fev27 = repo.comp(2027, 2)
check("aluguel repetido ate fev/2027", len(repo.transacoes(fev27)) == 1)
check("nao vaza para mar/2027", len(repo.transacoes(repo.comp(2027, 3))) == 0)

print("\n== resumo e series ==")
r = repo.resumo_mes(mar)
check("receitas do mes", abs(r["receitas"] - 6000) < 0.01, str(r["receitas"]))
check("despesas do mes", abs(r["despesas"] - (850.55 + 200 + 2000)) < 0.01, str(r["despesas"]))
check("balanco do mes", abs(r["balanco"] - (6000 - 3050.55)) < 0.01, str(r["balanco"]))

serie = repo.serie_mensal(12, ate=mar)
check("serie mensal com 12 linhas", len(serie) == 12, f"{len(serie)}")
check("saldo_total roda", isinstance(repo.saldo_total(), float))

print("\n== fatura do cartao ==")
f = repo.faturas(mar)
check("fatura de marco = 200", not f.empty and abs(float(f.iloc[0]["total"]) - 200) < 0.01)

print("\n== orcamento ==")
repo.definir_orcamento(mar, cat_desp, 1500)
orc = repo.orcamento_mes(mar)
linha = orc[orc.categoria_id == cat_desp]
check("meta gravada", not linha.empty and abs(float(linha.iloc[0]["planejado"]) - 1500) < 0.01)
check("gasto batendo com a meta", abs(float(linha.iloc[0]["gasto"]) - 3050.55) < 0.01,
      str(float(linha.iloc[0]["gasto"])))
check("copiar_orcamento", repo.copiar_orcamento(mar, abr) >= 1)

print("\n== virada de mes ==")
mai = repo.comp(2026, 5)
antes_mai = len(repo.transacoes(mai))
n = repo.copiar_lancamentos(abr, mai)
check("copiar_lancamentos", len(repo.transacoes(mai)) == antes_mai + n, f"+{n}")

print("\n== pago / exclusao ==")
alvo = int(tx[tx.descricao == "Mercado"].iloc[0]["id"])
repo.alternar_pago(alvo)
repo.excluir_transacao(alvo)
check("lancamento excluido", len(repo.transacoes(mar)) == 3)

print("\n== investimentos ==")
repo.salvar_investimento("Tesouro Selic 2029", "Renda fixa", "Nubank")
inv = repo.listar_investimentos()
inv_id = int(inv.iloc[0]["id"])
repo.salvar_movimento_investimento(
    investimento_id=inv_id, data=dt.date(2026, 3, 15), tipo="aporte", valor=1000
)
repo.salvar_movimento_investimento(
    investimento_id=inv_id, data=dt.date(2026, 4, 15), tipo="rendimento", valor=12.5
)
inv = repo.listar_investimentos()
check("saldo do investimento", abs(float(inv.iloc[0]["saldo"]) - 1012.5) < 0.01,
      str(float(inv.iloc[0]["saldo"])))
check("movimentos listados", len(repo.movimentos_investimento(inv_id)) == 2)
check("evolucao patrimonio", len(repo.evolucao_patrimonio(12)) == 12)

print("\n== objetivos ==")
repo.salvar_objetivo(nome="Viagem", valor_alvo=10000, valor_atual=2500,
                     data_alvo=dt.date(2026, 12, 31))
obj = repo.listar_objetivos()
check("objetivo criado", len(obj) == 1)
check("percentual calculado", abs(float(obj.iloc[0]["progresso"]) - 25) < 0.5,
      str(float(obj.iloc[0]["progresso"])))

print("\n== importacao / exportacao ==")

df = pd.DataFrame({
    "data": ["01/06/2026", "02/06/2026"],
    "descricao": ["Padaria", "Farmacia"],
    "valor": ["R$ 1.592,00", "45,90"],
    "categoria": ["Mercearia", "Categoria Nova XPTO"],
    "conta": ["Conta corrente", "Conta Nova XPTO"],
    "cartao": ["", ""],
    "tipo": ["despesa", "despesa"],
})
n, erros = repo.importar_transacoes(df)
check("2 linhas importadas", n == 2, f"n={n} erros={erros}")
jun = repo.transacoes(repo.comp(2026, 6))
padaria = jun[jun.descricao == "Padaria"]
check("R$ 1.592,00 virou 1592.0", not padaria.empty and abs(float(padaria.iloc[0]["valor"]) - 1592) < 0.01)
check("categoria nova criada", "Categoria Nova XPTO" in set(repo.listar_categorias()["nome"]))
check("conta nova criada", "Conta Nova XPTO" in set(repo.listar_contas()["nome"]))
check("exportar_tudo", len(repo.exportar_tudo()) > 0)


print("\n--- telas ---")
# --- popula com dados realistas, incluindo o mês atual ---
hoje = dt.date.today()
cats = repo.listar_categorias()
cat_d = int(cats[cats.tipo == "despesa"].iloc[0]["id"])
cat_d2 = int(cats[cats.tipo == "despesa"].iloc[3]["id"])
cat_r = int(cats[cats.tipo == "receita"].iloc[0]["id"])
conta = int(repo.listar_contas().iloc[0]["id"])
cartao = cartao_id  # reaproveita o cartão criado acima

repo.salvar_transacao(data=hoje.replace(day=5), descricao="Salário", valor=7200,
                      tipo="receita", categoria_id=cat_r, conta_id=conta)
repo.salvar_transacao(data=hoje.replace(day=2), descricao="Aluguel", valor=1592,
                      tipo="despesa", categoria_id=cat_d, conta_id=conta, repetir_meses=6)
repo.salvar_transacao(data=hoje.replace(day=8), descricao="Mercado", valor=430.20,
                      tipo="despesa", categoria_id=cat_d2, cartao_id=cartao)
repo.salvar_transacao(data=hoje.replace(day=9), descricao="Cadeira", valor=900,
                      tipo="despesa", categoria_id=cat_d2, cartao_id=cartao, parcelas=3)
repo.definir_orcamento(repo.comp(hoje.year, hoje.month), cat_d2, 1200)
inv = int(repo.listar_investimentos().iloc[0]["id"])
repo.salvar_movimento_investimento(investimento_id=inv, data=hoje.replace(day=3),
                                   tipo="aporte", valor=1500)
repo.salvar_movimento_investimento(investimento_id=inv, data=hoje.replace(day=4),
                                   tipo="rendimento", valor=18.4)
repo.salvar_objetivo(nome="Reserva de emergência", valor_alvo=30000,
                     valor_atual=9000, data_alvo=dt.date(hoje.year + 1, 12, 31))

from streamlit.testing.v1 import AppTest  # noqa: E402

telas = ["views/painel.py", "views/transacoes.py", "views/planejamento.py",
         "views/cartoes.py", "views/investimentos.py", "views/objetivos.py",
         "views/configuracoes.py"]

for tela in telas:
    at = AppTest.from_file(tela, default_timeout=60)
    at.run()
    if at.exception:
        falhas.append("tela " + tela)
        print(f"  FALHA  {tela}")
        for e in at.exception:
            print(f"         {e.value}")
    else:
        widgets = (len(at.button) + len(at.selectbox) + len(at.text_input)
                   + len(at.number_input) + len(at.dataframe) + len(at.metric))
        print(f"  ok     {tela:<28} {widgets} widgets, {len(at.warning)} avisos")

print()
if falhas:
    print(f"{len(falhas)} FALHA(S): " + ", ".join(falhas))
else:
    print("Tudo passou.")
raise SystemExit(1 if falhas else 0)
