# Minhas Finanças

App pessoal de controle financeiro em Python + Streamlit, para substituir a planilha
mensal. Lançamentos, cartões, orçamento por categoria, investimentos e objetivos —
tudo num banco só, sem precisar duplicar nada quando vira o mês.

## O que tem dentro

| Página | Para quê |
| --- | --- |
| Painel | Saldo, receitas, despesas, gráfico por categoria e histórico de 12 meses |
| Transações | Lista do mês com filtros, busca, parcelas e marcação de pago/pendente |
| Planejamento | Metas por categoria + botões para copiar metas e repetir contas fixas do mês anterior |
| Cartões | Fatura de cada cartão, comparada com o mês passado |
| Investimentos | Aportes, resgates, rendimentos, composição da carteira e evolução |
| Objetivos | Quanto falta para cada meta e quanto guardar por mês |
| Configurações | Contas, cartões, categorias, importação de CSV e backup |

Detalhes que resolvem dores da planilha:

- **Parcelas**: lance "Cadeira, R$ 600, 3x" e o app cria as três parcelas nos meses certos.
- **Contas fixas**: "repetir por 12 meses" cria o aluguel do ano inteiro de uma vez.
- **Fatura certa**: uma compra depois do dia de fechamento do cartão cai no mês seguinte, como no banco.
- **Virada de mês**: em Planejamento você copia as metas e escolhe quais lançamentos repetir.

## Rodar no seu computador

```bash
git clone https://github.com/SEU-USUARIO/minhas-financas.git
cd minhas-financas
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`. Sem configuração nenhuma ele grava num arquivo
SQLite em `data/financas.db` — ótimo para testar.

## Publicar de graça (leva uns 15 minutos)

O caminho mais curto é **GitHub → Neon (banco) → Streamlit Community Cloud (app)**.
Nada de Docker, nada de cartão de crédito.

### 1. Subir o código no GitHub

```bash
git init
git add .
git commit -m "primeira versao"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/minhas-financas.git
git push -u origin main
```

O `.gitignore` já impede que o banco local e o arquivo de senhas subam junto.

### 2. Criar o banco no Neon

O disco do Streamlit Cloud é apagado a cada reinício, então o SQLite não serve lá.
Use um Postgres gratuito:

1. Entre em [neon.com](https://neon.com) e crie uma conta (login com GitHub serve).
2. Crie um projeto — a região `AWS us-east` funciona bem no Brasil.
3. Na tela do projeto, copie a **connection string**. Ela tem esta cara:
   `postgresql://usuario:senha@ep-algo-123.us-east-2.aws.neon.tech/neondb?sslmode=require`

O Neon foi a escolha aqui porque no plano grátis ele hiberna em minutos e acorda
sozinho na próxima consulta. O Supabase também funciona (mesma string de conexão),
mas pausa o projeto depois de uma semana parado e você tem que reativar na mão.

### 3. Publicar no Streamlit Community Cloud

1. Vá em [share.streamlit.io](https://share.streamlit.io) e entre com o GitHub.
2. **Create app → Deploy a public app from GitHub**.
3. Preencha: repositório `SEU-USUARIO/minhas-financas`, branch `main`, arquivo `app.py`.
4. Abra **Advanced settings → Secrets** e cole:

   ```toml
   DATABASE_URL = "postgresql://usuario:senha@ep-algo-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
   app_password = "uma-senha-sua"
   ```

5. **Deploy**. Em poucos minutos você tem uma URL `https://algo.streamlit.app`.

O app abre pedindo a senha, então dá para deixar o repositório público sem expor os
seus dados. Se preferir, o plano grátis também permite **um** app privado.

Depois disso, todo `git push` atualiza o app sozinho.

Duas coisas para saber do plano grátis: o app dorme depois de ~12 horas sem visita
(o primeiro acesso mostra uma tela de "acordando" por alguns segundos) e roda com
cerca de 1 GB de memória, o que é bastante para um app de finanças pessoais.

### Outras hospedagens

O mesmo código roda em Render, Railway ou Fly. O comando de start é:

```
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Defina as variáveis de ambiente `DATABASE_URL` e `APP_PASSWORD` no painel da
plataforma — o app lê as duas de lá quando não encontra os secrets do Streamlit.

## Trazer os dados da planilha

Em **Configurações → Importar e exportar**:

1. No Google Sheets, baixe cada bloco como CSV (Arquivo → Fazer download → CSV).
   Como a sua planilha tem despesas e receitas lado a lado, o mais fácil é copiar
   cada bloco para uma aba nova e limpa, com uma linha de cabeçalho só.
2. Envie o CSV, escolha qual coluna é data, valor, descrição, categoria, conta e cartão.
3. Diga se aquelas linhas são despesas ou receitas e clique em Importar.

Categorias, contas e cartões que ainda não existirem são criados automaticamente.
Não precisa limpar os valores antes: `R$ 1.592,00`, `1.592`, `1592.00` e `(85,00)`
(negativo, como alguns extratos escrevem) são todos entendidos.

Vale importar um mês primeiro para conferir se ficou do jeito certo. Tem um botão
para baixar o modelo de CSV na mesma tela, e outro para baixar um backup de tudo.

## Estrutura

```
app.py                    navegação e trava de senha
core/models.py            tabelas (SQLAlchemy)
core/db.py                conexão: SQLite local ou Postgres via DATABASE_URL
core/repo.py              todas as consultas e regras (parcelas, fatura, orçamento)
core/forms.py             formulário de lançamento
core/ui.py                tema, formatação em R$, seletor de mês
views/                    uma tela por arquivo
testes.py                 confere as regras e abre todas as telas
```

Depois de mexer no código, vale rodar:

```bash
python testes.py
```

Ele cria um banco descartável em `data/testes.db`, testa as regras (parcelas,
contas fixas, competência da fatura, orçamento, importação) e abre cada tela para
ver se nenhuma quebrou. Não encosta no seu banco de verdade.

Para mudar as cores, mexa em `core/ui.py` e `.streamlit/config.toml`.
Para adicionar um campo, comece por `core/models.py` — as tabelas são criadas
sozinhas na primeira execução.
