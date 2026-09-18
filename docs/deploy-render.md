# Deploy do bot no Render (grátis)

O Streamlit continua no Streamlit Cloud. O que vai para o Render é só o
**bot** (`bot/app.py`), como um *Web Service* que recebe o webhook do Telegram.
Os dois falam com o mesmo Neon.

## O que o tier grátis dá — e o que cobra em troca

Verificado em [render.com/docs/free](https://render.com/docs/free), setembro
de 2026:

- **Dorme após 15 minutos** sem requisição. Acorda na próxima, em **~1 minuto**.
  Na prática: a primeira mensagem do dia para o bot demora até um minuto para
  ser respondida; as seguintes são imediatas. O Telegram guarda a mensagem e
  reentrega, então nada se perde — só atrasa.
- **750 horas de instância por mês.** Um serviço que dorme usa muito menos.
- **Sem cartão** para começar. Se estourar banda ou minutos de build sem
  cartão cadastrado, o serviço é suspenso até o mês virar.
- **Background worker não é grátis** — por isso o bot é um Web Service com
  webhook, não um worker com polling.

Se o minuto de espera incomodar, o caminho é o Oracle (`docs/deploy-oracle.md`).

## Passo a passo

### 1. O serviço precisa responder HTTP

`bot/app.py` tem que subir um servidor web na porta que o Render passa em
`$PORT`. Com `python-telegram-bot` + `starlette` + `uvicorn` (é o exemplo
oficial da biblioteca):

```python
# bot/app.py — esqueleto
import os
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

SEGREDO = os.environ["TELEGRAM_WEBHOOK_SECRET"]
application = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).updater(None).build()
# application.add_handler(CommandHandler("start", start)) ...

async def telegram(request: Request):
    if request.path_params["segredo"] != SEGREDO:
        return PlainTextResponse("", status_code=403)
    await application.update_queue.put(Update.de_json(await request.json(), application.bot))
    return PlainTextResponse("ok")

async def saude(request: Request):
    return PlainTextResponse("ok")

app = Starlette(routes=[
    Route("/telegram/{segredo}", telegram, methods=["POST"]),
    Route("/", saude),
])
```

A rota `/` respondendo `ok` serve para o *health check* do Render.

### 2. Arquivos na raiz do repositório

`requirements-bot.txt` (separado do do Streamlit, para o Render não instalar
Streamlit e Plotly à toa):

```
SQLAlchemy>=2.0
psycopg[binary]>=3.2
pandas>=2.2
bcrypt>=4.2
python-telegram-bot>=21
starlette
uvicorn
google-genai
```

Comando de start (vai no painel do Render):

```
uvicorn bot.app:app --host 0.0.0.0 --port $PORT
```

### 3. Criar o serviço

1. [dashboard.render.com](https://dashboard.render.com) → **New → Web Service**.
2. Conecte o GitHub e escolha `wesllanSilva/minhas-financas`.
3. Preencha:
   - **Name**: `wstack-finance-bot`
   - **Region**: Ohio (mesma do Neon → menos latência)
   - **Branch**: `main`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements-bot.txt`
   - **Start Command**: `uvicorn bot.app:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
4. **Environment** → adicione as variáveis de `docs/bot-telegram.md` § 6
   (`DATABASE_URL`, `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`,
   `GEMINI_API_KEY`). Também `PYTHON_VERSION` = `3.12` (o Render usa uma
   versão antiga por padrão).
5. **Create Web Service**. O primeiro build leva uns 3 minutos. A URL fica
   `https://wstack-finance-bot.onrender.com`.

### 4. Registrar o webhook

Uma vez só, no navegador (substitua token, URL e segredo):

```
https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://wstack-finance-bot.onrender.com/telegram/<TELEGRAM_WEBHOOK_SECRET>
```

Deve responder `{"ok":true,"result":true,"description":"Webhook was set"}`.
Conferir depois: `.../getWebhookInfo`.

### 5. Testar

Mande `/start` para o bot. Se a resposta demorar ~1 minuto, é o serviço
acordando — normal. Se não responder nunca: **Logs** no painel do Render, e
`getWebhookInfo` mostra o último erro que o Telegram recebeu ao chamar a URL.

## Atualizações

Todo `git push` na `main` redeploya o Render também (auto-deploy vem ligado).
Se quiser que só o Streamlit redeploye num push, desligue *Auto-Deploy* no
Render e dispare manualmente.

## Um cuidado com o Neon

O Render acorda, abre conexão, o Neon (que também dorme) acorda. Dois
cold-starts em série. `pool_pre_ping=True` em `core/db.py` já cobre a conexão
morta; o que pode aparecer é timeout na primeira query após horas parado.
Se acontecer, `connect_args={"connect_timeout": 15}` no `create_engine` resolve.
