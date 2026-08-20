"""Creates a realistic DUPLA (two-face) production-like pizza box PSD for end-to-end demos.

Unlike create_test_template.py (flat colors, for unit tests), this draws a believable box
layout — pizza illustration, title ribbon, reserved logo/contact zones — at production
resolution, with one editable layer per field per face (BASE and BASE_2). It prints a ready
calibration so the seeding step can position the fields over the reserved areas.

Run: python scripts/create_simulado_producao.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import photoshopapi as psapi
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT = Path("gabaritos/caixa_35cm_simulado.psd")
WIDTH, HEIGHT = 3600, 1800
FACE_W = WIDTH // 2
FACE_X = [0, FACE_W]  # left/right face origins

# Reserved-area geometry per face (relative to face origin), reused for calibration.
LOGO_BOX = (640, 250, 520, 360)        # x, y, w, h
FRASE_BOX = (380, 70, 1040, 120)
PHONE_BOX = (470, 1430, 760, 80)
INSTA_BOX = (470, 1530, 760, 64)


def _draw_face(draw: ImageDraw.ImageDraw, fx: int, dark: bool):
    """Draw one decorative box face onto the canvas at x-offset `fx`."""
    ink = (235, 225, 205) if dark else (90, 60, 30)
    accent = (214, 40, 40)

    # Title ribbon (empty — the editable frase sits here)
    rx, ry, rw, rh = FRASE_BOX
    draw.rounded_rectangle([fx + rx, ry, fx + rx + rw, ry + rh], radius=60,
                           outline=accent, width=6)

    # Pizza illustration (center)
    cx, cy, r = fx + FACE_W // 2, 760, 300
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(225, 170, 90))           # crust
    draw.ellipse([cx - r + 28, cy - r + 28, cx + r - 28, cy + r - 28], fill=accent)  # sauce
    rng = np.random.default_rng(7)
    for _ in range(14):
        a = rng.uniform(0, 6.28); dist = rng.uniform(0, r - 80)
        px, py = cx + dist * np.cos(a), cy + dist * np.sin(a)
        draw.ellipse([px - 26, py - 26, px + 26, py + 26], fill=(180, 30, 30))   # pepperoni

    # Reserved logo zone (light placeholder)
    lx, ly, lw, lh = LOGO_BOX
    draw.rounded_rectangle([fx + lx, ly, fx + lx + lw, ly + lh], radius=20,
                           outline=ink, width=4)
    draw.text((fx + lx + lw // 2 - 60, ly + lh // 2 - 10), "AREA LOGO", fill=ink)

    # Contact strip (phone + instagram land here)
    draw.line([fx + 460, 1420, fx + 1240, 1420], fill=ink, width=3)

    # Crop marks
    for mx, my in [(40, 40), (FACE_W - 40, 40), (40, HEIGHT - 40), (FACE_W - 40, HEIGHT - 40)]:
        draw.line([fx + mx - 30, my, fx + mx + 30, my], fill=(0, 0, 0), width=2)
        draw.line([fx + mx, my - 30, fx + mx, my + 30], fill=(0, 0, 0), width=2)


def _background(base_rgb: tuple[int, int, int], dark: bool) -> dict:
    img = Image.new("RGB", (WIDTH, HEIGHT), base_rgb)
    draw = ImageDraw.Draw(img)
    for fx in FACE_X:
        _draw_face(draw, fx, dark)
    arr = np.array(img, dtype=np.uint8)
    cid = psapi.enum.ChannelID
    return {cid.red: np.ascontiguousarray(arr[:, :, 0]),
            cid.green: np.ascontiguousarray(arr[:, :, 1]),
            cid.blue: np.ascontiguousarray(arr[:, :, 2])}


def main():
    file = psapi.LayeredFile_8bit(psapi.enum.ColorMode.rgb, WIDTH, HEIGHT)
    cid = psapi.enum.ChannelID

    grp_fundos = psapi.GroupLayer_8bit("FONDOS_TEMATICOS")
    file.add_layer(grp_fundos)
    grp_fundos.add_layer(file, psapi.ImageLayer_8bit(
        _background((232, 205, 150), dark=False), "fundo_kraft_tradicional",
        width=WIDTH, height=HEIGHT, is_visible=True))
    grp_fundos.add_layer(file, psapi.ImageLayer_8bit(
        _background((28, 28, 30), dark=True), "fundo_preto_premium",
        width=WIDTH, height=HEIGHT, is_visible=False))

    grp_deco = psapi.GroupLayer_8bit("DECORACOES_OPCIONAIS")
    file.add_layer(grp_deco)
    grp_deco.add_layer(file, psapi.ImageLayer_8bit(
        {cid.red: np.full((90, 320), 220, np.uint8),
         cid.green: np.full((90, 320), 50, np.uint8),
         cid.blue: np.full((90, 320), 50, np.uint8)},
        "selo_entrega_rapida", width=320, height=90, pos_x=120, pos_y=120, is_visible=False))
    grp_deco.add_layer(file, psapi.ImageLayer_8bit(
        {cid.red: np.full((120, 120), 180, np.uint8),
         cid.green: np.full((120, 120), 80, np.uint8),
         cid.blue: np.full((120, 120), 30, np.uint8)},
        "ilustracao_forno_lenha", width=120, height=120, pos_x=120, pos_y=1600, is_visible=False))

    grp_graf = psapi.GroupLayer_8bit("ELEMENTOS_GRAFICOS")
    file.add_layer(grp_graf)
    for name, fx in [("LOGO_CLIENTE", FACE_X[0]), ("LOGO_CLIENTE_2", FACE_X[1])]:
        lx, ly, lw, lh = LOGO_BOX
        grp_graf.add_layer(file, psapi.ImageLayer_8bit(
            {cid.red: np.full((lh, lw), 200, np.uint8),
             cid.green: np.full((lh, lw), 200, np.uint8),
             cid.blue: np.full((lh, lw), 200, np.uint8)},
            name, width=lw, height=lh, pos_x=fx + lx, pos_y=ly))

    grp_textos = psapi.GroupLayer_8bit("TEXTOS_EDITAVEIS")
    file.add_layer(grp_textos)
    text_defs = [
        ("TEXTO_FRASE_OPCIONAL", "Sua Pizza Chegou!", 64.0, FRASE_BOX),
        ("TEXTO_TELEFONE", "(11) 0000-0000", 48.0, PHONE_BOX),
        ("TEXTO_INSTAGRAM", "@pizzaria", 38.0, INSTA_BOX),
    ]
    calibration: dict[str, dict] = {}
    for base, sample, size, (bx, by, bw, bh) in text_defs:
        for suffix, fx in [("", FACE_X[0]), ("_2", FACE_X[1])]:
            name = base + suffix
            grp_textos.add_layer(file, psapi.TextLayer_8bit(
                name, sample, font="ArialMT", font_size=size,
                fill_color=[1.0, 0.1, 0.1, 0.1], position_x=float(fx + bx), position_y=float(by + size)))
            calibration[name] = {"x": fx + bx, "y": by, "width": bw, "height": bh, "font_size": size}

    for base, (lx, ly, lw, lh) in [("LOGO_CLIENTE", LOGO_BOX)]:
        for suffix, fx in [("", FACE_X[0]), ("_2", FACE_X[1])]:
            calibration[base + suffix] = {"x": fx + lx, "y": ly, "width": lw, "height": lh}

    psapi.GroupLayer_8bit("FACAS_E_CORTES", is_locked=True)  # placeholder group name reserved

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    file.write(str(OUTPUT))
    (OUTPUT.with_suffix(".calibration.json")).write_text(
        json.dumps(calibration, indent=2), encoding="utf-8")
    print(f"Simulado criado: {OUTPUT}  ({WIDTH}x{HEIGHT}, DUPLA)")
    print(f"Calibracao salva: {OUTPUT.with_suffix('.calibration.json')}")


if __name__ == "__main__":
    main()
