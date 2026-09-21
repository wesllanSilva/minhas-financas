# Histórico de versões

Versionamento semântico. A versão em vigor fica em `core/versao.py` e aparece
na tela de login.

## 0.6.0

- **Marcar pendentes como pagas em lote**, em Transações. O botão age sobre o
  que os filtros deixaram na tela — Forma = Nubank, Situação = Pendentes — e
  pede confirmação mostrando quantos lançamentos e quanto. Caso típico: pagou a
  fatura, tudo do cartão naquele mês vira pago de uma vez.
- Filtro **Situação** (Todas / Pendentes / Pagas) na lista de transações, e o
  resumo passa a mostrar quantos estão pendentes e quanto somam.

## 0.5.1

- Fixa o piso do Streamlit em 1.63 no `requirements.txt`. O app usa
  `st.container(key=...)`, `st.dialog`, `st.logo` e `width="stretch"`; com o
  piso anterior (1.49) a nuvem podia instalar uma versão sem esses recursos, e
  a falha só aparecia na tela que os usa. `testes/test_ambiente.py` passa a
  checar isso localmente.

## 0.5.0

- Os quatro cards do Painel abrem ao clique. **Saldo em conta** mostra cada
  conta (negativo inclusive) e como o número foi montado; **Receitas** e
  **Despesas** abrem por categoria, com o que ainda está em aberto; **Balanço**
  compara com os três meses anteriores. Clicar de novo fecha.

## 0.4.0

Editar em vez de excluir e refazer.

- **Lançamento**: "Editar" no menu ⋯ de cada linha abre um diálogo já
  preenchido. Se o lançamento tem parcelas ou repetições, pergunta se a
  mudança vale só para ele ou para todos — no "todos", descrição, valor,
  categoria, conta, cartão e observação mudam em cada um; data e pago/pendente
  continuam como estão. Trocar o cartão recalcula a fatura de cada parcela.
- **Categoria**: ✎ ao lado de cada uma em Configurações renomeia e troca a cor.
  Reflete em todos os lançamentos que já a usavam.
- **Conta**: nome, tipo e saldo inicial editáveis; remover só esconde, os
  lançamentos continuam contando.
- **Cartão**: apelido, banco, limite, fechamento e vencimento editáveis. Mudar
  o dia de fechamento move cada compra para a fatura certa.
- **Carteira**: o dono renomeia pelo ✎ em Carteiras e acesso.
- Nome repetido (ignorando maiúsculas) em categoria, conta ou cartão é
  recusado com aviso, em vez de estourar erro do banco.

## 0.3.1

- `ferramentas/recolorir_categorias.py`: troca as cores das categorias criadas
  antes da 0.3.0 (terrosas, feitas para o fundo claro) pela paleta escura.
  Categoria padrão recebe a cor padrão; as demais, cores da paleta sem repetir
  dentro da carteira.

## 0.3.0

Vira **Wstack Finance**, com a identidade visual da família Wstack.

- Tema escuro violeta (mesma base do Wstack Ops): Sora nos títulos, Inter no
  texto, JetBrains Mono em tudo que é dinheiro — sempre tabular, verde para o
  que entra e vermelho para o que sai.
- Tela de login com logo, nome, versão e um fundo próprio, gerado por código
  (`ferramentas/gerar_bg_login.py`): um extrato virado em paisagem, com a
  receita em verde e a despesa em violeta atravessando o escuro.
- Logo e nome no topo da barra lateral; ícone da aba é a logo Wstack.
- Cards de resumo com a cor do valor como acento; gráficos com paleta
  categórica própria em vez de tudo violeta.
- Categorias padrão ganham cores que funcionam no fundo escuro (só para
  carteiras novas — as existentes mantêm as cores que já tinham, editáveis em
  Configurações → Categorias).
- Backup passa a se chamar `wstack-finance-backup.csv`.

## 0.2.1

- Ferramenta de migração para quem já tinha banco na 0.1.x
  (`ferramentas/migrar_0_2_0.py`). Preserva os lançamentos: acrescenta
  `workspace_id` nas tabelas antigas, cria o dono e põe tudo que já existia
  dentro da carteira dele. Troca também os índices únicos de nome, que eram
  globais — enquanto eles existissem, duas pessoas não poderiam ter cada uma
  o seu "Nubank".
- Corrige o tipo do cookie de sessão lido na fronteira: em certos ambientes
  `st.context.cookies` devolve um objeto que não é string, e a quebra só
  aparecia bem depois, dentro do hash do token.

## 0.2.0

Multiusuário. O app deixa de ser de uma pessoa só.

- Login com e-mail e senha (hash bcrypt); a senha nunca é guardada em texto.
- Sessão que sobrevive ao refresh: o F5 não derruba mais ninguém para a tela de
  login. Token em cookie, com validade de 30 dias.
- Carteiras (workspaces): cada pessoa tem a sua, e dá para criar uma
  compartilhada. Todo dado financeiro passa a pertencer a uma carteira, e uma
  não enxerga a outra.
- Nova aba **Configurações → Carteiras e acesso**: criar carteira, liberar
  acesso por e-mail, remover membro e trocar a própria senha.
- Seletor de carteira e botão "Sair" na barra lateral.
- Suíte de testes automatizados (99 testes, `pytest`), no lugar do antigo script
  `testes.py`.

Mudança de banco: as tabelas financeiras ganharam `workspace_id`, e os nomes de
conta, cartão e investimento passaram a ser únicos por carteira em vez de
únicos globalmente — sem isso duas pessoas não poderiam ter, cada uma, um
"Nubank".

## 0.1.1

- Corrige o nome dos ícones vazando como texto por cima dos rótulos do menu. Um
  seletor CSS amplo demais (`[class*="st-"]`) trocava a fonte dos ícones do
  Streamlit, que são ligatures da Material Symbols.

## 0.1.0

- Primeira versão: painel, transações, planejamento, cartões, investimentos,
  objetivos, configurações, importação de CSV e backup.
