# Agente de perguntas sobre os seus dados

> "Quanto gastei com streaming mês passado?" → o agente chama as funções do
> app, lê a resposta e escreve em português.

Este guia cobre três coisas: qual modelo usar (e o que "grátis" custa de
verdade), como o agente se liga ao código que já existe, e um esqueleto em
Python com a API do Gemini. Verificado em setembro de 2026 — as APIs de modelo
mudam rápido; confira os links antes de copiar.

## 1. Escolha do modelo

### O que "plano Plus" não inclui

Assinatura do Gemini (Google One AI Pro / Gemini Advanced) é o produto de
consumidor: o app e o site do Gemini. **Não dá crédito nem cota na API.** A API
tem o próprio tier grátis, que existe para qualquer conta Google, com ou sem
assinatura. São dois balcões diferentes.

### As opções, honestas

| Opção | Custo | Tool calling | O problema |
|---|---|---|---|
| **Gemini API, tier grátis** (`gemini-3.8-flash`) | R$ 0 | Sim | **O conteúdo enviado é usado para melhorar produtos do Google.** Aqui o conteúdo é a finança da sua família. |
| **Gemini API, tier pago** | US$ 0,75 entrada / US$ 3,75 saída por 1M tokens. Uma pergunta ≈ 2k tokens → **~US$ 0,002**. 300 perguntas/mês ≈ US$ 0,60. | Sim | Precisa cadastrar cartão no AI Studio. Conteúdo **não** é usado para treino. |
| **Groq, tier grátis** (Llama e outros) | R$ 0 | Sim | 30 req/min, 6k tokens/min. Modelos abertos, tool calling menos confiável que Gemini/Claude. Confira a política de dados deles. |
| **OpenRouter, roteador grátis** | R$ 0 | Sim (filtra modelos com suporte) | 50 req/dia sem crédito; 1.000/dia depois de comprar US$ 10 uma vez. Modelo sorteado a cada chamada — qualidade varia. |
| **Claude API** (Haiku 4.5) | US$ 1 / US$ 5 por 1M → ~US$ 0,003 por pergunta | Sim, o mais confiável dos quatro | Não tem tier grátis. |
| **Ollama local** | R$ 0 | Depende do modelo | Precisa de máquina ligada. Não funciona com o bot no Render. |

### Recomendação

**Gemini no tier pago.** É o que você já escolheu, o custo é café, e resolve o
único problema sério do tier grátis: seus dados não viram treino. Cadastre o
cartão no AI Studio e coloque um **limite de gasto** de US$ 5/mês — se algo
entrar em loop, para ali.

Se "zero" for inegociável: Gemini grátis com a consciência do que está sendo
enviado. Dá para reduzir o dano mandando só agregados (totais por categoria)
em vez de lançamentos linha a linha — o agente responde "quanto gastei" sem
nunca ver "Farmácia São João, R$ 163,50, 14/09".

Fontes: [preços Gemini](https://ai.google.dev/gemini-api/docs/pricing) ·
[limites do tier grátis](https://ai.google.dev/gemini-api/docs/rate-limits) ·
[Groq free tier](https://theneuralbase.com/groq/qna/groq-free-tier-limits/) ·
[OpenRouter free router](https://openrouter.ai/docs/guides/routing/routers/free-router)

## 2. Como o agente se liga ao app

**Regra única: o modelo nunca escreve SQL.** Ele chama funções que já existem
em `core/repo.py`, e essas funções já filtram pela carteira ativa
(`core/escopo.py`). O isolamento entre usuários é o mesmo que os testes de
`testes/test_isolamento.py` garantem — o agente não tem como escapar dele,
porque nunca toca o banco direto.

```
mensagem → [quem é? qual carteira?] → escopo.definir(ws)
        → modelo escolhe uma função → repo.xxx(...) → resultado → modelo escreve
```

`core/repo.py` e `core/escopo.py` funcionam fora do Streamlit (é assim que o
`pytest` roda). O "preparar o app para agente" está feito pela arquitetura
atual. O que falta é só a cola.

### As funções que viram ferramentas

Comece com poucas. Cada uma vira uma declaração JSON para o modelo:

| Ferramenta | Chama | Responde |
|---|---|---|
| `resumo_do_mes(ano, mes)` | `repo.resumo_mes(comp(ano, mes))` | receitas, despesas, balanço, a pagar |
| `gastos_por_categoria(ano, mes)` | `repo.por_categoria(comp, "despesa")` | lista categoria → total |
| `lancamentos(ano, mes, categoria?, busca?)` | `repo.transacoes(comp)` + filtro | lista curta (limite 30) |
| `saldo_por_conta()` | `repo.saldo_por_conta()` | conta → saldo |
| `faturas(ano, mes)` | `repo.faturas(comp)` | cartão → total |
| `orcamento(ano, mes)` | `repo.orcamento_mes(comp)` | categoria → meta, gasto, uso % |

Regras de ouro:

- **Só leitura.** O agente de perguntas não lança, não edita, não apaga. Lançar
  é do bot de Telegram (`docs/bot-telegram.md`), com parser determinístico.
- **Limite o tamanho.** `lancamentos` devolve no máximo 30 linhas. Quem quer
  mais abre o app.
- **Data de hoje no prompt.** "Mês passado" só funciona se o modelo souber que
  dia é.
- **Números em texto formatado.** Devolva `"R$ 1.592,00"`, não `1592.0`. Evita
  o modelo inventar arredondamento.

### Ligando o usuário

Precisa de uma tabela nova, `vinculo_telegram(chat_id, usuario_id, workspace_id)`.
Fluxo: no app, em Configurações → Carteiras e acesso, um botão gera um código
de 6 dígitos válido por 10 minutos; a pessoa manda `/vincular 123456` para o
bot; o bot grava o `chat_id`. Sem código válido, o bot responde "não sei quem
você é" e nada mais.

## 3. Esqueleto com a API do Gemini

Instalação:

```bash
pip install google-genai
```

Chave: crie em [AI Studio](https://aistudio.google.com/apikey) e exporte como
`GEMINI_API_KEY`. O SDK lê sozinho.

A API atual usa `client.interactions.create` e um `previous_interaction_id`
para continuar a conversa — o servidor guarda o histórico, você só manda o que
é novo. Cópia fiel do que está em
[Function calling](https://ai.google.dev/gemini-api/docs/function-calling) hoje:

```python
"""agente.py — responde perguntas sobre a carteira ativa via Gemini."""
from __future__ import annotations

import datetime as dt
import json

from google import genai

from core import escopo, repo

MODELO = "gemini-3.8-flash"

FERRAMENTAS = [
    {
        "type": "function",
        "name": "resumo_do_mes",
        "description": "Receitas, despesas, balanço e valor em aberto de um mês.",
        "parameters": {
            "type": "object",
            "properties": {
                "ano": {"type": "integer"},
                "mes": {"type": "integer", "description": "1 a 12"},
            },
            "required": ["ano", "mes"],
        },
    },
    {
        "type": "function",
        "name": "gastos_por_categoria",
        "description": "Total gasto em cada categoria num mês, maior primeiro.",
        "parameters": {
            "type": "object",
            "properties": {"ano": {"type": "integer"}, "mes": {"type": "integer"}},
            "required": ["ano", "mes"],
        },
    },
    {
        "type": "function",
        "name": "saldo_por_conta",
        "description": "Quanto há em cada conta agora.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def _brl(v: float) -> str:
    s = f"{abs(v):,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"{'-' if v < 0 else ''}R$ {s}"


def executar(nome: str, args: dict) -> dict:
    """Ponte entre o nome da ferramenta e o repo. Só leitura."""
    if nome == "resumo_do_mes":
        r = repo.resumo_mes(repo.comp(args["ano"], args["mes"]))
        return {k: _brl(v) for k, v in r.items()}
    if nome == "gastos_por_categoria":
        df = repo.por_categoria(repo.comp(args["ano"], args["mes"]), "despesa")
        return {"categorias": [{"categoria": r.categoria, "total": _brl(r.total)} for r in df.itertuples()]}
    if nome == "saldo_por_conta":
        df = repo.saldo_por_conta()
        return {"contas": [{"conta": r.nome, "saldo": _brl(r.saldo)} for r in df.itertuples()]}
    return {"erro": f"ferramenta desconhecida: {nome}"}


def perguntar(workspace_id: int, pergunta: str) -> str:
    """Uma pergunta, uma resposta. Fixa a carteira antes de qualquer coisa."""
    escopo.definir(workspace_id)
    client = genai.Client()
    hoje = dt.date.today().isoformat()
    sistema = (
        f"Você responde perguntas sobre as finanças pessoais de quem pergunta. "
        f"Hoje é {hoje}. Use as ferramentas para buscar números; nunca invente. "
        f"Responda em português, curto, com valores em R$."
    )

    interacao = client.interactions.create(
        model=MODELO,
        input=f"{sistema}\n\nPergunta: {pergunta}",
        tools=FERRAMENTAS,
    )

    # Loop: enquanto o modelo pedir função, executa e devolve o resultado.
    for _ in range(6):  # teto: evita loop infinito
        chamadas = [s for s in interacao.steps if s.type == "function_call"]
        if not chamadas:
            break
        resultados = []
        for fc in chamadas:
            saida = executar(fc.name, fc.arguments or {})
            resultados.append({
                "type": "function_result",
                "name": fc.name,
                "call_id": fc.id,
                "result": [{"type": "text", "text": json.dumps(saida, ensure_ascii=False)}],
            })
        interacao = client.interactions.create(
            model=MODELO,
            input=resultados,
            tools=FERRAMENTAS,
            previous_interaction_id=interacao.id,
        )

    return interacao.output_text or "Não consegui responder."
```

Uso, num script ou no bot:

```python
print(perguntar(workspace_id=1, pergunta="quanto gastei com streaming mês passado?"))
```

O que conferir contra a doc antes de rodar (são os pontos que mudam entre
versões do SDK): o nome exato de `client.interactions.create`, o formato do
bloco `function_result`, e se `previous_interaction_id` continua sendo o jeito
de continuar.

### Colocando no Streamlit

Uma página `views/perguntar.py` com `st.chat_input` chamando `perguntar(escopo.atual(), texto)`.
O `escopo` já está definido pelo `app.py`, então dentro do Streamlit não
precisa passar o `workspace_id` — use `escopo.atual()`.

## 4. Testar sem gastar

`executar()` é Python puro e roda no `pytest` com a fixture `carteira`, sem
chamar modelo nenhum. Teste isso — é onde estão os bugs de verdade (mês errado,
categoria errada). O modelo só traduz português em chamada de função.

Para o modelo, um teste manual com 10 perguntas reais basta: "quanto gastei com
mercado esse mês", "qual meu saldo", "estourei alguma meta", "o que ainda falta
pagar". Anote as que erram e ajuste a descrição da ferramenta — é a alavanca
que mais muda o comportamento.
