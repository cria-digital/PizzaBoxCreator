"""Creates a DUPLA (two-face) placeholder PSD at the REAL factory canvas size
(12346x6242 -- matching assets/originais/COD. P35 001 ... .psd), so the full workflow
(catalog, calibration, order preview/CMYK) can be exercised at production resolution
while the real gabarito is still being prepared with named layers in Photoshop.

This is a stand-in, not the client's actual artwork -- swap it out once the real PSD
has TEXTO_TELEFONE/LOGO_CLIENTE/etc. layers built on top of the real design (see
docs/PREPARACAO_GABARITO.md).

Run: python scripts/create_placeholder_producao.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import photoshopapi as psapi
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT = Path("gabaritos/caixa_producao_placeholder.psd")

# Real factory canvas (assets/originais/COD. P35 001 - CX. PIZZA 35 PADRAO ... .psd)
WIDTH, HEIGHT = 12346, 6242
FACE_W = WIDTH // 2
FACE_X = [0, FACE_W]

# Reserved-area geometry, scaled up from the 1800x1800-per-face demo template so the
# same relative layout (logo center, title ribbon top, contact strip bottom) holds here.
SCALE = HEIGHT / 1800


def s(v: float) -> int:
    return round(v * SCALE)


LOGO_BOX = (s(640), s(250), s(520), s(360))
FRASE_BOX = (s(380), s(70), s(1040), s(120))
PHONE_BOX = (s(470), s(1430), s(760), s(80))
INSTA_BOX = (s(470), s(1530), s(760), s(64))


def _draw_face(draw: ImageDraw.ImageDraw, fx: int, dark: bool):
    """Draw one decorative box face onto the canvas at x-offset `fx`."""
    ink = (235, 225, 205) if dark else (90, 60, 30)
    accent = (214, 40, 40)

    rx, ry, rw, rh = FRASE_BOX
    draw.rounded_rectangle([fx + rx, ry, fx + rx + rw, ry + rh], radius=s(60),
                           outline=accent, width=s(6))

    cx, cy, r = fx + FACE_W // 2, s(760), s(300)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(225, 170, 90))
    draw.ellipse([cx - r + s(28), cy - r + s(28), cx + r - s(28), cy + r - s(28)], fill=accent)
    rng = np.random.default_rng(7)
    for _ in range(14):
        a = rng.uniform(0, 6.28); dist = rng.uniform(0, r - s(80))
        px, py = cx + dist * np.cos(a), cy + dist * np.sin(a)
        draw.ellipse([px - s(26), py - s(26), px + s(26), py + s(26)], fill=(180, 30, 30))

    lx, ly, lw, lh = LOGO_BOX
    draw.rounded_rectangle([fx + lx, ly, fx + lx + lw, ly + lh], radius=s(20),
                           outline=ink, width=s(4))
    draw.text((fx + lx + lw // 2 - s(60), ly + lh // 2 - s(10)), "AREA LOGO", fill=ink)

    draw.line([fx + s(460), s(1420), fx + s(1240), s(1420)], fill=ink, width=s(3))

    for mx, my in [(s(40), s(40)), (FACE_W - s(40), s(40)),
                   (s(40), HEIGHT - s(40)), (FACE_W - s(40), HEIGHT - s(40))]:
        draw.line([fx + mx - s(30), my, fx + mx + s(30), my], fill=(0, 0, 0), width=s(2))
        draw.line([fx + mx, my - s(30), fx + mx, my + s(30)], fill=(0, 0, 0), width=s(2))


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
    selo_w, selo_h = s(320), s(90)
    grp_deco.add_layer(file, psapi.ImageLayer_8bit(
        {cid.red: np.full((selo_h, selo_w), 220, np.uint8),
         cid.green: np.full((selo_h, selo_w), 50, np.uint8),
         cid.blue: np.full((selo_h, selo_w), 50, np.uint8)},
        "selo_entrega_rapida", width=selo_w, height=selo_h,
        pos_x=s(120), pos_y=s(120), is_visible=False))
    forno_w, forno_h = s(120), s(120)
    grp_deco.add_layer(file, psapi.ImageLayer_8bit(
        {cid.red: np.full((forno_h, forno_w), 180, np.uint8),
         cid.green: np.full((forno_h, forno_w), 80, np.uint8),
         cid.blue: np.full((forno_h, forno_w), 30, np.uint8)},
        "ilustracao_forno_lenha", width=forno_w, height=forno_h,
        pos_x=s(120), pos_y=s(1600), is_visible=False))

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
        ("TEXTO_FRASE_OPCIONAL", "Sua Pizza Chegou!", s(64.0), FRASE_BOX),
        ("TEXTO_TELEFONE", "(11) 0000-0000", s(48.0), PHONE_BOX),
        ("TEXTO_INSTAGRAM", "@pizzaria", s(38.0), INSTA_BOX),
    ]
    calibration: dict[str, dict] = {}
    for base, sample, size, (bx, by, bw, bh) in text_defs:
        for suffix, fx in [("", FACE_X[0]), ("_2", FACE_X[1])]:
            name = base + suffix
            grp_textos.add_layer(file, psapi.TextLayer_8bit(
                name, sample, font="ArialMT", font_size=float(size),
                fill_color=[1.0, 0.1, 0.1, 0.1], position_x=float(fx + bx), position_y=float(by + size)))
            calibration[name] = {"x": fx + bx, "y": by, "width": bw, "height": bh, "font_size": size}

    for base, (lx, ly, lw, lh) in [("LOGO_CLIENTE", LOGO_BOX)]:
        for suffix, fx in [("", FACE_X[0]), ("_2", FACE_X[1])]:
            calibration[base + suffix] = {"x": fx + lx, "y": ly, "width": lw, "height": lh}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    file.write(str(OUTPUT))
    (OUTPUT.with_suffix(".calibration.json")).write_text(
        json.dumps(calibration, indent=2), encoding="utf-8")
    print(f"Placeholder criado: {OUTPUT}  ({WIDTH}x{HEIGHT}, DUPLA, escala real de producao)")
    print(f"Calibracao de referencia salva: {OUTPUT.with_suffix('.calibration.json')}")


if __name__ == "__main__":
    main()
