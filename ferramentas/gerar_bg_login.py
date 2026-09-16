"""Gera `static/img/bg_login.jpg`, o fundo da tela de login.

A imagem é um extrato virado em paisagem: um grid fino de caderno de contas e
duas curvas luminosas atravessando o escuro — receita em verde, despesa em
violeta — com o rastro de meses no eixo. Não tem texto nenhum: texto em imagem
envelhece mal e não escala.

É determinística (semente fixa), então rodar de novo produz o mesmo arquivo.
Rode quando quiser trocar o visual:

    python ferramentas/gerar_bg_login.py
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "static" / "img" / "bg_login.jpg"

# Mesma paleta do CSS (core/tema.py). Tudo em RGB inteiro.
BG_0 = (19, 19, 32)
BG_1 = (27, 27, 46)
VIOLETA = (123, 104, 238)
VIOLETA_BRILHO = (157, 140, 255)
VERDE = (52, 211, 153)
GRID = (123, 104, 238)

LARGURA, ALTURA = 1920, 1080
ESCALA = 2  # desenha em 2x e reduz: antisserrilhado de graça


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def grid(img: Image.Image, w: int, h: int) -> None:
    """Caderno de contas: linhas horizontais mais presentes, verticais discretas."""
    camada = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    passo = int(h / 14)
    for y in range(passo, h, passo):
        d.line((0, y, w, y), fill=(*GRID, 26), width=ESCALA)
    passo_x = int(w / 24)
    for x in range(passo_x, w, passo_x):
        d.line((x, 0, x, h), fill=(*GRID, 14), width=ESCALA)
    # A linha de base, onde receita e despesa se encontram: um pouco mais forte.
    base = int(h * 0.62)
    d.line((0, base, w, base), fill=(*GRID, 60), width=ESCALA)
    img.paste(camada, (0, 0), camada)


def curva(w: int, rng: random.Random, base_y: float, amp: float, fase: float, tendencia: float):
    """Uma série mensal suavizada: seno lento + ruído de mês a mês + tendência."""
    pontos = []
    n = 14
    valores = []
    for i in range(n):
        t = i / (n - 1)
        v = math.sin(t * math.pi * 1.6 + fase) * 0.55 + rng.uniform(-0.35, 0.35) + tendencia * t
        valores.append(v)
    # Suaviza para não parecer serrilhado.
    suave = []
    for i in range(n):
        vizinhos = valores[max(0, i - 1) : i + 2]
        suave.append(sum(vizinhos) / len(vizinhos))
    for i, v in enumerate(suave):
        x = i / (n - 1) * w
        y = base_y - v * amp
        pontos.append((x, y))
    return _catmull_rom(pontos, passos=40)


def _catmull_rom(p, passos=24):
    """Interpola os pontos numa curva suave que passa por todos eles."""
    out = []
    pts = [p[0]] + p + [p[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(passos):
            t = s / passos
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(p[-1])
    return out


def traco_luminoso(img: Image.Image, w: int, h: int, pontos, cor, base_y: float, forca: float) -> None:
    """Área preenchida bem sutil + linha com halo gaussiano por baixo + linha nítida por cima."""
    # Área sob a curva
    area = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(area)
    poligono = pontos + [(w, base_y), (0, base_y)]
    d.polygon(poligono, fill=(*cor, int(28 * forca)))
    area = area.filter(ImageFilter.GaussianBlur(6 * ESCALA))
    img.paste(area, (0, 0), area)

    # Halo em duas camadas: um largo e difuso, um estreito e mais vivo.
    for largura, desfoque, alfa in ((22, 26, 90), (8, 8, 170)):
        halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(halo)
        d.line(pontos, fill=(*cor, int(alfa * forca)), width=int(largura * ESCALA), joint="curve")
        halo = halo.filter(ImageFilter.GaussianBlur(desfoque * ESCALA))
        img.paste(halo, (0, 0), halo)

    # Linha nítida
    nitida = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(nitida)
    d.line(pontos, fill=(*cor, int(235 * forca)), width=int(2.2 * ESCALA), joint="curve")
    img.paste(nitida, (0, 0), nitida)


def marcadores(img: Image.Image, w: int, h: int, pontos, cor, rng: random.Random) -> None:
    """Alguns pontos de dado na curva — os meses em que alguém olhou de perto."""
    camada = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    passo = len(pontos) // 13
    for i in range(passo, len(pontos) - 1, passo):
        if rng.random() < 0.55:
            continue
        x, y = pontos[i]
        r = 4 * ESCALA
        d.ellipse((x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2), fill=(*cor, 40))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(*cor, 230))
        d.ellipse((x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45), fill=(19, 19, 32, 255))
    img.paste(camada, (0, 0), camada)


def vinheta(img: Image.Image, w: int, h: int) -> Image.Image:
    """Escurece as bordas para o card de login ler bem em qualquer canto."""
    mascara = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mascara)
    d.ellipse((-w * 0.15, -h * 0.25, w * 1.15, h * 1.25), fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(w * 0.18))
    escuro = Image.new("RGB", (w, h), (11, 11, 20))
    return Image.composite(img, escuro, mascara)


def gerar() -> Path:
    rng = random.Random(2026)
    w, h = LARGURA * ESCALA, ALTURA * ESCALA

    # Degradê diagonal: pinta pixel a pixel numa miniatura e amplia com
    # interpolação — sai perfeitamente suave sem iterar 8 milhões de pixels.
    mini = Image.new("RGB", (96, 54))
    px = mini.load()
    for y in range(54):
        for x in range(96):
            px[x, y] = _lerp(BG_0, BG_1, x / 95 * 0.55 + y / 53 * 0.45)
    img = mini.resize((w, h), Image.BICUBIC)
    # Halo violeta no canto superior direito, como no CSS do app.
    halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    cx, cy, r = int(w * 0.86), int(-h * 0.08), int(w * 0.42)
    hd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*VIOLETA, 46))
    halo = halo.filter(ImageFilter.GaussianBlur(w * 0.10))
    img.paste(halo, (0, 0), halo)

    grid(img, w, h)

    base_y = h * 0.62
    despesa = curva(w, rng, base_y, amp=h * 0.16, fase=0.9, tendencia=0.25)
    receita = curva(w, rng, base_y, amp=h * 0.22, fase=-0.4, tendencia=0.75)

    # Despesa primeiro (atrás), receita por cima: é a que se quer ver crescer.
    traco_luminoso(img, w, h, despesa, VIOLETA, base_y, forca=0.75)
    traco_luminoso(img, w, h, receita, VERDE, base_y, forca=1.0)
    marcadores(img, w, h, despesa, VIOLETA_BRILHO, rng)
    marcadores(img, w, h, receita, VERDE, rng)

    img = vinheta(img, w, h)
    img = img.resize((LARGURA, ALTURA), Image.LANCZOS)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    img.save(DESTINO, "JPEG", quality=86, optimize=True, progressive=True)
    return DESTINO


if __name__ == "__main__":
    caminho = gerar()
    print(f"{caminho} ({caminho.stat().st_size // 1024} KB)")
