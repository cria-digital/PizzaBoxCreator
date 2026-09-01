"""Monta um gabarito EG03 PREMIUM (esqueleto 'nivel JPEG'): DUPLA, com logo central grande,
slogan, bloco de contato e a faca em camada SEPARADA (FACAS_E_CORTES).

O fundo tematico e desenhado em codigo (placeholder profissional). O designer depois so
substitui a camada `fundo_*` pela arte final da marca — as zonas reservadas e a convencao de
camadas ja ficam prontas, e a calibracao acompanha (scripts nao mexem em mais nada).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import photoshopapi as psapi
from PIL import Image, ImageDraw

from app.psd.text_metrics import get_font

OUTPUT = Path("gabaritos/cod_eg03_premium.psd")
W, H = 6000, 3000          # DUPLA: duas faces lado a lado
FW = 3000                  # largura de uma face
FACES = [0, FW]            # offset x de cada face

# Zona reservada (por face, coords relativas ao offset da face)
LOGO_CX, LOGO_CY, LOGO_SZ = 1500, 1120, 1080     # logo central grande
SLOGAN_Y = 1830
TEL_Y, IG_Y = 2360, 2560


def _gradient(top, bottom):
    """Gradiente vertical (RGB) do topo ao rodape."""
    band = np.linspace(0, 1, H)[:, None]
    col = (np.array(top)[None, :] * (1 - band) + np.array(bottom)[None, :] * band)
    return np.repeat(col[:, None, :], W, axis=1).astype(np.uint8)


def _draw_theme(base_rgb, accent, glow, panel):
    """Desenha decoracoes de uma face (borda, glow do logo, painel de contato) nas duas faces."""
    img = Image.fromarray(base_rgb, "RGB")
    d = ImageDraw.Draw(img, "RGBA")
    f_top = get_font(70, "Arial Bold")
    for ox in FACES:
        # moldura interna
        d.rounded_rectangle([ox + 70, 70, ox + FW - 70, H - 70], radius=60,
                            outline=accent + (255,), width=10)
        # faixa superior (marca/tema)
        d.rounded_rectangle([ox + 120, 150, ox + FW - 120, 430], radius=40, fill=accent + (255,))
        d.text((ox + FW / 2, 290), "MINI SALGADOS ASSADOS", font=f_top,
               fill=(255, 255, 255, 255), anchor="mm")
        # glow atras do logo
        for i, r in enumerate(range(LOGO_SZ, 0, -40)):
            a = int(90 * (1 - i / (LOGO_SZ / 40)))
            d.ellipse([ox + LOGO_CX - r, LOGO_CY - r, ox + LOGO_CX + r, LOGO_CY + r],
                      fill=glow + (max(a, 0),))
        # painel de contato (rodape)
        d.rounded_rectangle([ox + 260, 2280, ox + FW - 260, 2760], radius=50,
                            fill=panel + (235,))
        # marca de validade (canto)
        d.rounded_rectangle([ox + 120, H - 360, ox + 640, H - 160], radius=20,
                            fill=(255, 255, 255, 255))
        d.text((ox + 380, H - 400), "VALIDADE", font=get_font(34), fill=(255, 255, 255, 220),
               anchor="mm")
    return np.array(img.convert("RGB"), dtype=np.uint8)


def _facas_layer(cid):
    """Camada separada de faca/corte: linhas amarelas sobre transparente (via mascara)."""
    mask_img = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask_img)
    for ox in FACES:
        md.rounded_rectangle([ox + 40, 40, ox + FW - 40, H - 40], radius=80, outline=255, width=8)
        # abas de dobra (ticks)
        for y in (40, H - 40):
            md.line([ox + FW / 2, y - 30, ox + FW / 2, y + 30], fill=255, width=6)
    mask = np.array(mask_img, dtype=np.uint8)
    yellow = {
        cid.red: np.full((H, W), 240, np.uint8),
        cid.green: np.full((H, W), 210, np.uint8),
        cid.blue: np.full((H, W), 30, np.uint8),
    }
    # pos_x/pos_y=0: o renderer trata center_x/y como canto superior esquerdo (convencao do projeto),
    # entao arte de canvas inteiro fica ancorada em (0,0).
    layer = psapi.ImageLayer_8bit(yellow, "FACAS_E_CORTES", width=W, height=H,
                                  pos_x=0, pos_y=0, is_locked=True)
    layer.mask = mask
    return layer


def build_calibration():
    calib = {}
    for face, ox in enumerate(FACES, start=1):
        sfx = "" if face == 1 else f"_{face}"
        calib[f"LOGO_CLIENTE{sfx}"] = {
            "x": ox + LOGO_CX - LOGO_SZ // 2, "y": LOGO_CY - LOGO_SZ // 2,
            "width": LOGO_SZ, "height": LOGO_SZ,
        }
        calib[f"TEXTO_FRASE_OPCIONAL{sfx}"] = {
            "x": ox + 500, "y": SLOGAN_Y, "width": 2000, "height": 130, "font_size": 92,
        }
        calib[f"TEXTO_TELEFONE{sfx}"] = {
            "x": ox + 620, "y": TEL_Y, "width": 1760, "height": 150, "font_size": 108,
        }
        calib[f"TEXTO_INSTAGRAM{sfx}"] = {
            "x": ox + 620, "y": IG_Y, "width": 1760, "height": 110, "font_size": 76,
        }
    return calib


def main():
    cid = psapi.enum.ChannelID
    f = psapi.LayeredFile_8bit(psapi.enum.ColorMode.rgb, W, H)

    # --- Fundos tematicos (toggle) ---
    grp_bg = psapi.GroupLayer_8bit("FONDOS_TEMATICOS")
    f.add_layer(grp_bg)
    # kraft (tradicional) — visivel por padrao
    kraft = _draw_theme(_gradient((214, 180, 120), (176, 138, 82)),
                        accent=(120, 72, 30), glow=(255, 240, 210), panel=(90, 55, 25))
    grp_bg.add_layer(f, psapi.ImageLayer_8bit(
        {cid.red: np.ascontiguousarray(kraft[:, :, 0]),
         cid.green: np.ascontiguousarray(kraft[:, :, 1]),
         cid.blue: np.ascontiguousarray(kraft[:, :, 2])},
        "fundo_kraft_tradicional", width=W, height=H, pos_x=0, pos_y=0, is_visible=True))
    # premium (preto/rosa) — oculto
    premium = _draw_theme(_gradient((28, 20, 40), (12, 10, 22)),
                          accent=(233, 30, 99), glow=(120, 40, 90), panel=(20, 14, 30))
    grp_bg.add_layer(f, psapi.ImageLayer_8bit(
        {cid.red: np.ascontiguousarray(premium[:, :, 0]),
         cid.green: np.ascontiguousarray(premium[:, :, 1]),
         cid.blue: np.ascontiguousarray(premium[:, :, 2])},
        "fundo_preto_premium", width=W, height=H, pos_x=0, pos_y=0, is_visible=False))

    # --- Logo central grande (uma por face) ---
    grp_graf = psapi.GroupLayer_8bit("ELEMENTOS_GRAFICOS")
    f.add_layer(grp_graf)
    for face, ox in enumerate(FACES, start=1):
        sfx = "" if face == 1 else f"_{face}"
        grp_graf.add_layer(f, psapi.ImageLayer_8bit(
            {cid.red: np.full((LOGO_SZ, LOGO_SZ), 220, np.uint8),
             cid.green: np.full((LOGO_SZ, LOGO_SZ), 220, np.uint8),
             cid.blue: np.full((LOGO_SZ, LOGO_SZ), 220, np.uint8)},
            f"LOGO_CLIENTE{sfx}", width=LOGO_SZ, height=LOGO_SZ,
            pos_x=ox + LOGO_CX, pos_y=LOGO_CY))

    # --- Textos editaveis (uma tripla por face) ---
    grp_txt = psapi.GroupLayer_8bit("TEXTOS_EDITAVEIS")
    f.add_layer(grp_txt)
    for face, ox in enumerate(FACES, start=1):
        sfx = "" if face == 1 else f"_{face}"
        for name, sample, size, y in [
            (f"TEXTO_FRASE_OPCIONAL{sfx}", "Feito com amor", 92.0, SLOGAN_Y),
            (f"TEXTO_TELEFONE{sfx}", "(00) 00000-0000", 108.0, TEL_Y),
            (f"TEXTO_INSTAGRAM{sfx}", "@suapizzaria", 76.0, IG_Y),
        ]:
            grp_txt.add_layer(f, psapi.TextLayer_8bit(
                name, sample, font="ArialMT", font_size=size,
                fill_color=[1.0, 1.0, 1.0, 1.0],
                position_x=float(ox + 620), position_y=float(y + size)))

    # --- Faca em camada SEPARADA (spot de corte) ---
    f.add_layer(_facas_layer(cid))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(OUTPUT))
    print(f"Gabarito premium criado: {OUTPUT} ({W}x{H})")


if __name__ == "__main__":
    main()
