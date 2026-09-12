"""Génère les icônes PWA (manifest + apple-touch-icon) à partir du dégradé de la marque.

Usage : python scripts/generate_pwa_icons.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE_DIR, 'static', 'icons')

COLOR_START = (232, 121, 249)   # primary #e879f9
COLOR_END = (192, 38, 211)      # primary-dark #c026d3


def make_icon(size, corner_ratio=0.22):
    img = Image.new('RGB', (size, size), COLOR_END)
    draw = ImageDraw.Draw(img)

    # Dégradé diagonal simple (haut-gauche -> bas-droite)
    for y in range(size):
        for_ratio = y / size
        r = int(COLOR_START[0] + (COLOR_END[0] - COLOR_START[0]) * for_ratio)
        g = int(COLOR_START[1] + (COLOR_END[1] - COLOR_START[1]) * for_ratio)
        b = int(COLOR_START[2] + (COLOR_END[2] - COLOR_START[2]) * for_ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    # Masque coins arrondis
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = int(size * corner_ratio)
    mask_draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=radius, fill=255)

    rounded = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    rounded.paste(img, (0, 0), mask)

    # Symbole "Ψ" (psi) centré, en blanc
    draw = ImageDraw.Draw(rounded)
    font_size = int(size * 0.58)
    font = None
    for candidate in ('arialbd.ttf', 'DejaVuSans-Bold.ttf', 'arial.ttf'):
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    text = "Ψ"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pos = ((size - text_w) / 2 - bbox[0], (size - text_h) / 2 - bbox[1])
    draw.text(pos, text, font=font, fill=(255, 255, 255, 255))

    return rounded


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    sizes = {
        'icon-192.png': 192,
        'icon-512.png': 512,
        'apple-touch-icon.png': 180,
        'favicon-32.png': 32,
    }

    for filename, size in sizes.items():
        icon = make_icon(size)
        path = os.path.join(OUT_DIR, filename)
        # apple-touch-icon ne doit pas avoir de transparence (fond blanc sinon coins noirs sur iOS)
        if filename == 'apple-touch-icon.png':
            flat = Image.new('RGB', icon.size, COLOR_END)
            flat.paste(icon, (0, 0), icon)
            flat.save(path, 'PNG')
        else:
            icon.save(path, 'PNG')
        print(f"Écrit {path}")


if __name__ == '__main__':
    main()
