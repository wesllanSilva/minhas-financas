# Deploy do bot no Oracle Cloud (Always Free)

Uma VM que fica ligada o tempo todo, de graça, sem dormir. É o upgrade do
Render quando o minuto de espera incomoda. Mais setup, zero delay.

## O que mudou em 2026 — leia antes

Verificado em setembro de 2026:

- **A cota Always Free de ARM foi cortada pela metade** em junho de 2026, sem
  anúncio: de 4 OCPU / 24 GB para **2 OCPU / 12 GB** (fonte:
  [InfoQ](https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)).
  Para o bot, ainda sobra muito.
- **"Out of capacity"** ao criar a VM ARM é comum — a região fica sem máquina
  grátis disponível. Não é erro seu. Soluções: tentar em horários diferentes,
  tentar outra *availability domain* na mesma região, ou usar a VM **AMD**
  (`VM.Standard.E2.1.Micro`, 1 OCPU / 1 GB) que raramente falta e é
  suficiente para o bot.
- **Precisa de cartão** para criar a conta, mesmo no free. Não cobra enquanto
  você ficar nos recursos *Always Free*. A conta começa em *trial* (30 dias
  com crédito) e depois vira *Always Free* automaticamente.
- Escolha a **home region** com cuidado: não muda depois. Para o Brasil,
  `sa-saopaulo-1` (São Paulo) ou `us-ashburn-1`. O Neon está em Ohio; Ashburn
  fica mais perto dele.

Fontes: [Always Free Resources (Oracle)](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
· [guia da comunidade](https://gist.github.com/rssnyder/51e3cfedd730e7dd5f4a816143b25dbd)

## Passo a passo

### 1. Conta e VM

1. [cloud.oracle.com](https://cloud.oracle.com) → *Sign up*. Cartão, telefone,
   home region.
2. Menu → **Compute → Instances → Create instance**.
   - **Image**: Ubuntu 24.04 (minimal serve).
   - **Shape**: *Ampere* → `VM.Standard.A1.Flex`, 1 OCPU, 6 GB (deixa margem
     na cota de 2/12). Se der *Out of capacity*: `VM.Standard.E2.1.Micro`.
   - **Networking**: crie uma VCN nova com subnet pública; marque *Assign a
     public IPv4 address*.
   - **SSH keys**: gere um par (ou cole a sua pública). **Baixe a privada** —
     não tem como recuperar depois.
3. Anote o **IP público**.

### 2. Abrir a porta (duas vezes — é a pegadinha do Oracle)

O firewall existe em dois lugares e os dois bloqueiam por padrão:

**a) Security list da VCN** (painel): Networking → VCN → Security Lists →
Default → *Add Ingress Rule*: Source `0.0.0.0/0`, protocol TCP, destination
port `443`. (E `80`, se for usar o Certbot em modo HTTP.)

**b) iptables dentro da VM** (o Ubuntu do Oracle vem com regras restritivas):

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
```

Sem o (b), a regra do painel não adianta e você perde uma hora achando que é
DNS.

### 3. Domínio e HTTPS

O Telegram **só chama webhook em HTTPS com certificado válido.** Precisa de um
nome de domínio apontando para o IP. Opções grátis: um subdomínio no
[DuckDNS](https://www.duckdns.org) (`wstackbot.duckdns.org`), ou um domínio
que você já tenha.

Na VM:

```bash
sudo apt update && sudo apt install -y caddy python3.12-venv git
```

Caddy faz o HTTPS sozinho (Let's Encrypt) e repassa para o bot. `/etc/caddy/Caddyfile`:

```
wstackbot.duckdns.org {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
sudo systemctl reload caddy
```

### 4. O bot

```bash
cd /opt && sudo git clone https://github.com/wesllanSilva/minhas-financas.git wstack
sudo chown -R ubuntu:ubuntu wstack && cd wstack
python3 -m venv .venv && .venv/bin/pip install -r requirements-bot.txt
```

Segredos em `/opt/wstack/.env` (permissão `600`):

```
DATABASE_URL=postgresql://...
TELEGRAM_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
GEMINI_API_KEY=...
```

Serviço `systemd` em `/etc/systemd/system/wstack-bot.service`:

```ini
[Unit]
Description=Wstack Finance - bot do Telegram
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/opt/wstack
EnvironmentFile=/opt/wstack/.env
ExecStart=/opt/wstack/.venv/bin/uvicorn bot.app:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now wstack-bot
sudo systemctl status wstack-bot     # tem que estar "active (running)"
journalctl -u wstack-bot -f          # logs ao vivo
```

### 5. Webhook

```
https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook?url=https://wstackbot.duckdns.org/telegram/<TELEGRAM_WEBHOOK_SECRET>
```

### 6. Atualizar

Não tem auto-deploy. Um script `/opt/wstack/atualizar.sh`:

```bash
#!/bin/bash
set -e
cd /opt/wstack
git pull --ff-only
.venv/bin/pip install -r requirements-bot.txt -q
sudo systemctl restart wstack-bot
```

Roda por SSH depois de cada push que mexa no bot. Se quiser automático, um
`cron` de hora em hora chamando esse script é o suficiente para um app de
família.

## Render vs Oracle, resumido

| | Render free | Oracle Always Free |
|---|---|---|
| Delay na primeira mensagem | ~1 min | nenhum |
| Setup | 10 min, tudo no painel | 1–2 h, SSH, firewall, domínio |
| Deploy | `git push` | script por SSH |
| Cartão | não | sim (não cobra) |
| Risco | serviço suspenso se estourar cota | *out of capacity* na criação; regras mudam sem aviso |

Comece no Render. Migre para o Oracle quando o delay virar irritação — o
código do bot é o mesmo, muda só onde roda.
