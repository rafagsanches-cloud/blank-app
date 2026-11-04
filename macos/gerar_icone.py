"""Desenha o ícone do app (1024 px) em macos/ChuvaSP/Icone/icone_1024.png."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
# fundo: quadrado arredondado no tamanho usado pelos ícones do macOS (824 px)
m = 100
fundo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    r = int(16 + (42 - 16) * t)
    g = int(66 + (120 - 66) * t)
    b = int(129 + (214 - 129) * t)
    gd.line([(0, y), (S, y)], fill=(r, g, b, 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([m, m, S - m, S - m], radius=185, fill=255)
fundo.paste(grad, (0, 0), mask)
sombra = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(sombra).rounded_rectangle([m, m + 14, S - m, S - m + 14], radius=185, fill=(0, 0, 0, 90))
sombra = sombra.filter(ImageFilter.GaussianBlur(18))
img = Image.alpha_composite(img, sombra)
img = Image.alpha_composite(img, fundo)
# barras de chuva anual (translúcidas) numa camada própria
camada = Image.new("RGBA", (S, S), (0, 0, 0, 0))
dc = ImageDraw.Draw(camada)
alturas = [0.50, 0.62, 0.44, 0.58, 0.40, 0.47, 0.33, 0.38, 0.27]
x0, base, larg, passo = 205, 805, 52, 70
for i, h in enumerate(alturas):
    x = x0 + i * passo
    dc.rounded_rectangle([x, base - h * 330, x + larg, base], radius=12, fill=(255, 255, 255, 80))
img = Image.alpha_composite(img, camada)
# gota
gota = Image.new("RGBA", (S, S), (0, 0, 0, 0))
dg = ImageDraw.Draw(gota)
cx, cy, r = 512, 400, 120
dg.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
dg.polygon([(cx - r * 0.97, cy - 30), (cx, cy - 245), (cx + r * 0.97, cy - 30)], fill=(255, 255, 255, 255))
img = Image.alpha_composite(img, gota)
# linha de tendência (queda) sobre as barras
linha = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(linha).line([(215, 600), (815, 735)], fill=(235, 104, 52, 255), width=24)
img = Image.alpha_composite(img, linha)
out = Path(__file__).resolve().parent / "ChuvaSP" / "Icone"
out.mkdir(parents=True, exist_ok=True)
img.save(out / "icone_1024.png")
print(out / "icone_1024.png")
