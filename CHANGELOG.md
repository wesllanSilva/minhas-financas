# Histórico de versões

Versionamento semântico. A versão em vigor fica em `core/versao.py` e aparece
na tela de login.

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
