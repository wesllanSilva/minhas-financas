"""Identidade visual do Wstack Finance.

Herda a família Wstack (mesma do Wstack Ops): violeta sobre fundo profundo,
Sora para títulos, Inter para texto, JetBrains Mono para dado. O que é próprio
do Finance está em dois lugares — o fundo do login, um extrato virado em
paisagem, e o dinheiro, que aparece sempre em mono tabular com cor semântica:
verde entra, vermelho sai.

As imagens ficam em `static/img` e entram na página como data URI: não
dependem de o servidor estático do Streamlit estar ligado, que na nuvem é uma
opção a mais para dar errado.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
IMG = RAIZ / "static" / "img"

# --------------------------------------------------------------------------- #
# Tokens — os mesmos nomes do CSS do Wstack Ops
# --------------------------------------------------------------------------- #

BG_0 = "#131320"
BG_1 = "#1b1b2e"
SURFACE = "#21213a"
SURFACE_2 = "#282845"
VIOLETA = "#7b68ee"
VIOLETA_BRILHO = "#9d8cff"
VIOLETA_FUNDO = "#5a48c7"
TINTA = "#ecebf7"
CINZA = "#9b97b8"
OK = "#34d399"
AVISO = "#fbbf24"
ERRO = "#f87171"
CIANO = "#38bdf8"
BORDA = "rgba(123, 104, 238, 0.28)"
LINHA = "rgba(123, 104, 238, 0.16)"  # divisórias finas dentro das listas
GRADE = "rgba(155, 151, 184, 0.14)"  # linhas de grade dos gráficos

#: Paleta categórica para séries e categorias: vizinhas do violeta no círculo
#: cromático, todas com luminância parecida para ler igual no fundo escuro.
SERIE = [
    "#9d8cff",  # violeta
    "#34d399",  # menta
    "#38bdf8",  # ciano
    "#fbbf24",  # âmbar
    "#fb7185",  # coral
    "#f472b6",  # rosa
    "#60a5fa",  # azul
    "#a3e635",  # lima
    "#c084fc",  # lilás
    "#fb923c",  # laranja
    "#2dd4bf",  # turquesa
    "#e879f9",  # fúcsia
]

NOME = "Wstack Finance"


# --------------------------------------------------------------------------- #
# Imagens
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=None)
def data_uri(nome: str) -> str:
    """Conteúdo de `static/img/<nome>` como data URI. Vazio se o arquivo faltar."""
    caminho = IMG / nome
    if not caminho.exists():
        return ""
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}[caminho.suffix[1:].lower()]
    return f"data:{mime};base64,{base64.b64encode(caminho.read_bytes()).decode('ascii')}"


def logo_pil():
    """A logo como imagem PIL, para o ícone da aba. None se faltar."""
    caminho = IMG / "logo_w.png"
    if not caminho.exists():
        return None
    from PIL import Image

    return Image.open(caminho)


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #

CSS_BASE = f"""
<style>
@import url("https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600&display=swap");

:root {{
  --bg-0: {BG_0};
  --bg-1: {BG_1};
  --surface: {SURFACE};
  --surface-2: {SURFACE_2};
  --violet: {VIOLETA};
  --violet-bright: {VIOLETA_BRILHO};
  --violet-deep: {VIOLETA_FUNDO};
  --ink: {TINTA};
  --muted: {CINZA};
  --ok: {OK};
  --warn: {AVISO};
  --err: {ERRO};
  --border: {BORDA};
  --line: {LINHA};
  --font-display: "Sora", "Segoe UI", sans-serif;
  --font-body: "Inter", "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", Consolas, monospace;
}}

/* ---------- base ---------- */
html, body, .stApp, button, input, textarea, select {{
  font-family: var(--font-body);
}}
/* Os ícones do Streamlit são ligatures da Material Symbols: trocar a fonte
   deles faz o nome do ícone vazar como texto. */
[data-testid="stIconMaterial"] {{
  font-family: "Material Symbols Rounded" !important;
}}

.stApp {{
  background:
    radial-gradient(1200px 600px at 85% -10%, rgba(123, 104, 238, 0.14), transparent 60%),
    linear-gradient(to bottom right, var(--bg-0), var(--bg-1));
  color: var(--ink);
}}
[data-testid="stHeader"] {{
  background: transparent;
}}
.stApp::after {{
  content: "© 2026 Wstack · By Wstack Solution";
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 6px 0 8px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  color: var(--muted);
  background: linear-gradient(to top, rgba(19, 19, 32, 0.92), transparent);
  pointer-events: none;
  z-index: 999;
}}

h1, h2, h3, h4 {{
  font-family: var(--font-display);
  color: var(--ink);
  letter-spacing: -0.01em;
}}
h1 {{ font-size: 1.9rem; font-weight: 700; }}
h2 {{ font-size: 1.25rem; font-weight: 600; }}
h3 {{ font-size: 1.02rem; font-weight: 600; }}
h1::after {{
  content: ""; display: block;
  width: 56px; height: 3px; margin-top: 10px; border-radius: 2px;
  background: linear-gradient(90deg, var(--violet), var(--ok));
}}

p, li, label, .stMarkdown {{ color: var(--ink); }}
/* Caption é frase, não dado: fica na fonte de texto. Mono só onde é número,
   rótulo curto ou versão. */
[data-testid="stCaptionContainer"], .stCaption, small {{
  color: var(--muted) !important;
  font-size: 0.8rem;
}}
[data-testid="stWidgetLabel"] p {{ color: var(--muted); font-size: 0.85rem; }}
hr {{ border-color: var(--line) !important; }}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #17172a 0%, #14141f 100%) !important;
  border-right: 1px solid var(--border) !important;
}}
/* Topo da barra lateral: a logo vem do st.logo (é o único jeito de ficar
   acima do menu); o wordmark entra por CSS ao lado dela. */
[data-testid="stSidebarHeader"] {{
  display: flex; align-items: center;
  padding: 1rem 1rem 0.9rem 1.25rem;
  background: linear-gradient(135deg, rgba(123, 104, 238, 0.16), rgba(40, 40, 69, 0.6));
  border-bottom: 1px solid var(--border);
}}
/* O wrapper da logo vira a marca inteira: imagem + wordmark (via ::after). */
/* Dependendo da página o Streamlit usa <div> ou <button> aqui — daí o
   seletor não citar o tag, e o reset de botão logo abaixo. */
[data-testid="stSidebarHeader"] > :first-child {{
  display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0;
  padding: 0 2.9rem 0 0;  /* espaço do botão de recolher, que é absoluto */
  margin: 0; background: none; border: none; box-shadow: none;
  color: inherit; font: inherit; cursor: default; text-align: left;
}}
[data-testid="stSidebarLogo"] {{
  width: 46px !important; height: 46px !important; max-height: none !important;
  border-radius: 12px; padding: 4px;
  object-fit: contain;
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 4px 16px rgba(123, 104, 238, 0.45);
}}
[data-testid="stSidebarHeader"] > :first-child::after {{
  content: "Wstack Finance";
  font-family: var(--font-display); font-size: 0.98rem; font-weight: 700;
  color: var(--ink); letter-spacing: 0.01em; line-height: 1.15;
  white-space: nowrap;
}}

[data-testid="stSidebarNav"] a {{
  border-radius: 8px;
  border-left: 3px solid transparent;
  transition: background 0.15s ease, border-color 0.15s ease;
}}
[data-testid="stSidebarNav"] a:hover {{ background: rgba(123, 104, 238, 0.12); }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: rgba(123, 104, 238, 0.18);
  border-left-color: var(--violet);
}}
[data-testid="stSidebarNav"] a span {{ color: var(--ink); }}
[data-testid="stSidebarNavSectionHeader"] {{
  font-family: var(--font-mono); font-size: 0.66rem;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted);
}}

.usuario {{
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono); font-size: 0.78rem; color: var(--muted);
  background: rgba(123, 104, 238, 0.1);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 12px; margin-bottom: 0.5rem;
}}
.usuario i {{
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: var(--ok); box-shadow: 0 0 6px var(--ok);
}}
.usuario b {{ color: var(--ink); font-weight: 600; }}

/* ---------- controles ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button {{
  font-family: var(--font-display); font-weight: 600;
  background: linear-gradient(135deg, var(--violet), var(--violet-deep));
  color: #fff;
  border: 1px solid rgba(157, 140, 255, 0.35); border-radius: 8px;
  box-shadow: 0 4px 14px rgba(123, 104, 238, 0.3);
  transition: all 0.18s ease-in-out;
}}
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {{
  background: linear-gradient(135deg, var(--violet-bright), var(--violet));
  box-shadow: 0 6px 20px rgba(123, 104, 238, 0.5);
  transform: translateY(-1px);
  color: #fff; border-color: rgba(157, 140, 255, 0.6);
}}
.stButton > button:active {{ transform: translateY(0); }}
.stButton > button:focus-visible {{ outline: 2px solid var(--violet-bright); outline-offset: 2px; }}
.stButton > button[kind="secondary"] {{
  background: rgba(33, 33, 58, 0.8);
  box-shadow: none;
}}

[data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] {{
  background-color: rgba(33, 33, 58, 0.92) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--ink) !important;
}}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] * {{
  color: var(--ink) !important;
  background: transparent !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {{
  border-color: var(--violet-bright) !important;
  box-shadow: 0 0 0 2px rgba(123, 104, 238, 0.25) !important;
}}
[data-baseweb="popover"] li, [data-baseweb="menu"] {{
  background: var(--surface) !important; color: var(--ink) !important;
}}

[data-testid="stExpander"] details {{
  background: rgba(33, 33, 58, 0.8);
  border: 1px solid var(--border); border-radius: 8px;
}}
[data-testid="stExpander"] summary {{ font-family: var(--font-display); color: var(--ink); }}

.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--line); }}
.stTabs [data-baseweb="tab"] {{ font-family: var(--font-display); color: var(--muted); }}
.stTabs [aria-selected="true"] {{ color: var(--ink); }}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--violet); }}

.stAlert {{ border-radius: 8px; }}
[data-testid="stAlertContentSuccess"] {{ color: var(--ok); }}
[data-testid="stAlertContentError"] {{ color: var(--err); }}
[data-testid="stAlertContentInfo"] {{ color: var(--violet-bright); }}
[data-testid="stAlertContentWarning"] {{ color: var(--warn); }}

.stDataFrame, [data-testid="stDataFrame"] {{
  font-variant-numeric: tabular-nums;
  border: 1px solid var(--border); border-radius: 8px;
}}
div[data-testid="stMetricValue"] {{
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
}}

/* ---------- peças do Finance ---------- */
.painel {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px; margin: 4px 0 22px 0;
}}
.ficha {{
  background: rgba(33, 33, 58, 0.72);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px 15px 16px;
  box-shadow: 0 6px 22px rgba(0, 0, 0, 0.35);
}}
.ficha .rotulo {{
  font-family: var(--font-mono); font-size: 0.68rem;
  letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted);
  margin-bottom: 6px;
}}
.ficha .cifra {{
  font-family: var(--font-mono); font-size: 1.45rem; font-weight: 600;
  letter-spacing: -0.01em; font-variant-numeric: tabular-nums;
}}
.ficha .nota {{ font-size: 0.74rem; color: var(--muted); margin-top: 4px; }}
.ficha.destaque {{ border-left: 3px solid var(--violet); }}
/* Card de resumo: a cor do valor vira o acento da borda e um brilho discreto
   no canto — o card inteiro diz o que o número diz. */
.ficha.resumo {{
  position: relative; overflow: hidden;
  border-top: 2px solid var(--acento, var(--violet));
}}
.ficha.resumo::before {{
  content: ""; position: absolute; inset: -40% auto auto -20%;
  width: 60%; height: 120%;
  background: radial-gradient(closest-side, var(--acento, var(--violet)), transparent);
  opacity: 0.09; pointer-events: none;
}}
.dinheiro {{
  font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-weight: 500;
}}

.trilho {{ height: 6px; background: rgba(123, 104, 238, 0.15); border-radius: 3px; overflow: hidden; }}
.trilho > div {{ height: 100%; border-radius: 3px; box-shadow: 0 0 8px rgba(123, 104, 238, 0.45); }}

.tag {{
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 0.74rem; font-weight: 500; color: #fff;
}}

/* O componente que grava o cookie não desenha nada, mas ocupa a altura de um
   bloco. Sem isto sobra um buraco no topo da página. */
iframe[title="streamlit.components.v1.html"][height="0"] {{ display: none; }}

footer, #MainMenu, .stAppDeployButton {{ visibility: hidden; }}

@media (prefers-reduced-motion: reduce) {{
  * {{ transition: none !important; animation: none !important; }}
}}
</style>
"""


def css_login() -> str:
    """CSS só da tela de login: fundo em imagem e o card central."""
    fundo = data_uri("bg_login.jpg")
    camada_fundo = (
        f'url("{fundo}") center / cover no-repeat, ' if fundo else ""
    )
    return f"""
<style>
.stApp {{
  background: {camada_fundo}linear-gradient(to bottom right, var(--bg-0), var(--bg-1));
}}
[data-testid="stMainBlockContainer"] {{
  max-width: 460px;
  margin: 8vh auto 0;
  padding: 2.5rem 2.5rem 2rem;
  background: rgba(23, 23, 40, 0.86);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.7), 0 0 40px rgba(123, 104, 238, 0.12);
}}
.login-marca {{ text-align: center; margin-bottom: 1.4rem; }}
.login-marca img {{
  width: 76px; height: 76px; border-radius: 16px; padding: 8px;
  object-fit: contain; background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 6px 20px rgba(123, 104, 238, 0.5);
  margin-bottom: 0.6rem;
}}
.login-marca .nome {{
  font-family: var(--font-display); font-size: 1.9rem; font-weight: 700;
  color: var(--ink); letter-spacing: 0.02em; line-height: 1.1;
}}
.login-marca .nome b {{ font-weight: 400; color: var(--violet-bright); }}
.login-marca .produto {{
  font-family: var(--font-mono); font-size: 0.78rem; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--muted); margin-top: 0.4rem;
}}
.login-marca .versao {{
  font-family: var(--font-mono); font-size: 0.66rem; letter-spacing: 0.14em;
  color: var(--muted); opacity: 0.8; margin-top: 0.15rem;
}}
[data-testid="stMainBlockContainer"] h1 {{ display: none; }}
[data-testid="stFormSubmitButton"] > button {{ width: 100%; margin-top: 0.5rem; }}
[data-testid="stForm"] {{ border: none; padding: 0; }}
@media (max-width: 520px) {{
  [data-testid="stMainBlockContainer"] {{ margin-top: 3vh; padding: 1.75rem 1.25rem 1.5rem; }}
}}
</style>
"""


def marca_html(tamanho: str = "sidebar") -> str:
    """Logo + wordmark. `tamanho` escolhe a classe: 'sidebar' ou 'login'."""
    logo = data_uri("logo_w.png")
    img = f'<img src="{logo}" alt="Wstack">' if logo else ""
    classe = "marca" if tamanho == "sidebar" else "login-marca"
    return (
        f'<div class="{classe}">{img}'
        f'<div class="nome">W<b>stack</b></div>'
        f'<div class="produto">Finance</div></div>'
    )


# --------------------------------------------------------------------------- #
# Plotly
# --------------------------------------------------------------------------- #

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", color=TINTA, size=12),
    xaxis=dict(gridcolor=GRADE, zerolinecolor=GRADE, linecolor=GRADE, tickfont=dict(color=CINZA)),
    yaxis=dict(gridcolor=GRADE, zerolinecolor=GRADE, linecolor=GRADE, tickfont=dict(color=CINZA)),
    legend=dict(font=dict(color=CINZA)),
    hoverlabel=dict(bgcolor=SURFACE_2, bordercolor=VIOLETA, font=dict(color=TINTA, family="JetBrains Mono")),
)
