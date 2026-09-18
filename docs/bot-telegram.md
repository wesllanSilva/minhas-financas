# Bot do Telegram

> `mercado 187,40 nubank` → lançado. Três segundos, do celular.

O bot faz duas coisas, nesta ordem de importância:

1. **Lançar** por mensagem curta — parser determinístico, sem modelo de IA.
   É o que faz o dado existir.
2. **Responder perguntas** — repassa para o agente de `docs/agente.md`.

Telegram porque a Bot API é gratuita, sem aprovação, e o bot existe em dois
minutos. WhatsApp (Meta Cloud API) exige conta business verificada, número
dedicado e webhook aprovado — semanas de burocracia para um app de família.

## 1. Criar o bot (2 minutos)

1. No Telegram, abra **@BotFather** → `/newbot`.
2. Nome de exibição: `Wstack Finance`. Username: algo terminado em `bot`,
   ex.: `wstack_finance_bot`.
3. Ele devolve o **token** (`123456:ABC-...`). Guarde como `TELEGRAM_TOKEN`.
   É segredo — quem tem o token controla o bot.
4. Opcional, `/setcommands` no BotFather:
   ```
   vincular - Ligar este chat à sua conta
   mes - Resumo do mês
   ajuda - Como lançar
   ```

## 2. Quem está falando

O Telegram identifica cada conversa por `chat_id`. O bot precisa saber qual
`usuario` e qual `workspace` esse chat representa — sem isso, nada pode ser
lido nem gravado.

Tabela nova em `core/models.py`:

```python
class VinculoTelegram(Base):
    __tablename__ = "vinculo_telegram"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"))
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_agora)
```

Fluxo de vínculo, para não precisar digitar senha no Telegram:

1. No app, Configurações → Carteiras e acesso → botão **Ligar ao Telegram**
   gera um código de 6 dígitos, válido por 10 minutos, guardado com o
   `usuario_id` e o `workspace_id` ativo.
2. A pessoa manda `/vincular 482913` para o bot.
3. O bot confere o código, grava o vínculo, apaga o código.

Sem vínculo, qualquer mensagem recebe "Não sei quem você é. Gere um código em
Configurações e mande /vincular CÓDIGO." e para ali. **Essa checagem é a
autenticação do bot inteira** — trate como tal.

Se a pessoa tem mais de uma carteira, o vínculo aponta para a que estava ativa
quando gerou o código. Trocar: gerar outro código com a outra carteira aberta.

## 3. Lançar por mensagem — o parser

Formato: `descrição valor [conta ou cartão] [categoria]`. Exemplos que devem
funcionar:

```
mercado 187,40
mercado 187,40 nubank
uber 23,90 nubank transporte
salario 9800 itau            → receita, porque a categoria "Salário" é receita
aluguel 2450 pago            → marca como pago (padrão: pago)
farmacia 163,50 pendente
```

Regras, em ordem:

1. **Valor** = primeiro token que `repo.parse_valor` entende. O resto antes
   dele é a descrição; o resto depois são modificadores.
2. **Conta/cartão** = token que casa (sem acento, sem caixa) com o nome de uma
   conta ou cartão da carteira. `nubank` casa com o cartão "Nubank" se houver
   cartão; senão com a conta. Se os dois existem, prefira o **cartão** para
   despesa e a **conta** para receita.
3. **Categoria** = token que casa com o nome de uma categoria. Se não vier,
   use a **última categoria usada para essa descrição** (busque em
   `repo.transacoes()` por descrição igual). "mercado" já foi Mercearia 12
   vezes; não pergunte de novo.
4. **Tipo** = "receita" se a categoria resolvida é de receita; senão despesa.
5. `pago` / `pendente` alterna o flag. Padrão: pago.
6. Sem categoria resolvida → responda com botões inline (as 5 mais usadas +
   "outra"), e só grave depois da escolha. Nunca grave em "Outros" por padrão:
   é o jeito mais rápido de encher o app de lixo.

Confirmação sempre, com botão de desfazer:

```
✓ Mercado · R$ 187,40 · Mercearia · Nubank · hoje
[desfazer]
```

O parser é Python puro e testável no `pytest` sem Telegram nenhum. Escreva os
testes primeiro com os 6 exemplos acima — é a parte que vai dar trabalho, e a
única que importa acertar.

## 4. Estrutura do código

```
bot/
  __init__.py
  parser.py       # texto → dict(descricao, valor, conta_id, cartao_id, categoria_id, tipo, pago)
  vinculo.py      # gerar código, resolver chat_id → (usuario_id, workspace_id)
  app.py          # handlers do Telegram + servidor web do webhook
```

`bot/app.py` importa `core` diretamente — é o mesmo pacote, o mesmo Neon:

```python
from core import escopo, repo
from bot import parser, vinculo

async def mensagem(update, context):
    chat_id = update.effective_chat.id
    v = vinculo.resolver(chat_id)
    if v is None:
        await update.message.reply_text("Não sei quem você é. Gere um código em Configurações e mande /vincular CÓDIGO.")
        return
    with escopo.usando(v.workspace_id):        # <- toda leitura/escrita fica presa à carteira
        texto = update.message.text.strip()
        if texto.endswith("?"):
            from agente import perguntar
            await update.message.reply_text(perguntar(v.workspace_id, texto))
            return
        lanc = parser.interpretar(texto)
        ...
```

`escopo.usando()` fora do Streamlit usa o `ContextVar` — é exatamente o caso
para o qual ele existe. Cada mensagem define a carteira e a devolve no fim.

Biblioteca: `python-telegram-bot` (v21+). Exemplos oficiais de webhook:
[customwebhookbot](https://docs.python-telegram-bot.org/en/stable/examples.customwebhookbot.html).

## 5. Webhook, não polling

**Polling** = o bot fica perguntando ao Telegram "tem mensagem?" a cada
segundo. Precisa de processo sempre vivo — não roda no Render grátis (que
dorme) e não roda dentro do Streamlit Cloud.

**Webhook** = o Telegram chama a sua URL quando chega mensagem. É um servidor
web comum; dorme quando não há nada, acorda na primeira mensagem. Cabe no
Render grátis.

Registrar o webhook, uma vez, depois do deploy:

```
https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://SEU-APP.onrender.com/telegram/<SEGREDO>
```

O `<SEGREDO>` no caminho é uma string aleatória longa: sem ele, qualquer um que
descubra a URL pode mandar mensagens falsas para o bot. Guarde como
`TELEGRAM_WEBHOOK_SECRET` e confira no handler.

## 6. Segredos

| Variável | Onde |
|---|---|
| `DATABASE_URL` | mesma do Streamlit Cloud (o Neon) |
| `TELEGRAM_TOKEN` | do BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `GEMINI_API_KEY` | só se o agente estiver ligado |

Nunca no Git. No Render vão em *Environment*; no Oracle, num arquivo `.env`
lido pelo `systemd`.

## 7. Ordem de construção

1. `bot/parser.py` + testes. Sem Telegram, sem rede.
2. `VinculoTelegram` + geração de código no app + `/vincular`.
3. `bot/app.py` com `/start`, `/vincular`, mensagem de lançamento, `/mes`.
   Teste local com polling (`application.run_polling()`) — é só para
   desenvolvimento.
4. Deploy (`docs/deploy-render.md`) e troca para webhook.
5. Perguntas (`?` no fim) → `agente.perguntar`.
