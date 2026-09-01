"""Bridges a flattened factory PSD (CMYK or RGB, no named layers) into an editable gabarito.

Factory print files usually arrive flattened and in CMYK (channels stored inverted). The
engine/renderer are RGB and need named editable layers. This module composites the flat art
into sRGB, then builds a new RGB PSD with the art as `fundo_kraft_tradicional` plus named
`LOGO_CLIENTE`/`TEXTO_*` layers, and returns a starter calibration placed over the artwork's
reserved (blank) area.

Shared by the CLI (`scripts/build_gabarito_from_flat.py`) and the catalog upload flow.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import photoshopapi as psapi
from PIL import Image, ImageCms

from app.psd.calibration import TEXT_BASES, LOGO_BASE, split_layer_name
from app.psd.engine import rgb_channels, psd_read, psd_write

ICC_PROFILE = Path(__file__).parent / "profiles" / "uswebcoatedswop.icc"


def is_editable_gabarito(psd_path: Path) -> bool:
    """True if the PSD already has the named editable layers (no bridging needed)."""
    try:
        f = psd_read(str(psd_path))
    except Exception:
        return False
    bases = {split_layer_name(l.name)[0] for l in f.flat_layers}
    return bool(bases & set(TEXT_BASES)) or LOGO_BASE in bases


def flat_art_to_rgb(psd_path: Path) -> Image.Image:
    """Composite the visible image layers of a flattened PSD into an sRGB image.

    Handles CMYK (>=4 channels, stored inverted -> ICC) and RGB (3 channels) source layers.
    """
    f = psd_read(str(psd_path))
    cmyk_transform = None
    if ICC_PROFILE.exists():
        cmyk_transform = ImageCms.buildTransform(
            ImageCms.getOpenProfile(str(ICC_PROFILE)), ImageCms.createProfile("sRGB"),
            "CMYK", "RGB")

    canvas = Image.new("RGB", (f.width, f.height), (255, 255, 255))
    for layer in f.flat_layers:
        if "ImageLayer" not in type(layer).__name__ or not layer.is_visible:
            continue
        data = layer.get_image_data()
        colour = [k for k in data if not (hasattr(k, "value") and k.value < 0) and int(k) >= 0]

        if len(colour) >= 4 and cmyk_transform is not None:
            # Sort by channel id to guarantee C/M/Y/K order regardless of dict iteration
            colour_sorted = sorted(colour, key=lambda k: int(k))
            cmyk = 255 - np.stack(
                [data[k] for k in colour_sorted[:4]], axis=-1
            ).astype(np.uint8)
            rgb = ImageCms.applyTransform(Image.fromarray(cmyk, "CMYK"), cmyk_transform)
        else:
            channels = rgb_channels(data)
            if channels is None:
                continue
            r, g, b = channels
            rgb = Image.fromarray(np.stack([r, g, b], axis=-1), "RGB")

        # In a real PSD center_x/center_y is the layer's true center; paste at its top-left.
        top_left = (int(round(layer.center_x - layer.width / 2)),
                    int(round(layer.center_y - layer.height / 2)))
        canvas.paste(rgb, top_left)
    return canvas


def detect_reserved_boxes(arr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Find solid near-white rectangles reserved for contact/logo near the bottom.

    Excludes the outer bleed margins and requires columns filled top-to-bottom, so scattered
    white text/badges don't inflate the box. Separate rectangles become separate box faces.
    """
    H, W, _ = arr.shape
    white = (arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235)
    region = np.zeros_like(white)
    x1, x2, y1, y2 = int(W * 0.12), int(W * 0.88), int(H * 0.60), int(H * 0.97)
    region[y1:y2, x1:x2] = white[y1:y2, x1:x2]

    rowd = region.sum(axis=1)
    if rowd.max() == 0:
        return []
    rows = np.where(rowd > 0.4 * rowd.max())[0]
    top, bottom = int(rows.min()), int(rows.max())
    bh = bottom - top
    cols = np.where(region[top:bottom, :].sum(axis=0) > 0.7 * bh)[0]  # solid columns only
    if len(cols) == 0 or bh < H * 0.02:
        return []

    breaks = np.where(np.diff(cols) > 1)[0] + 1
    groups = np.split(cols, breaks)
    min_width = W * 0.03
    boxes = []
    for group in groups:
        left, right = int(group[0]), int(group[-1])
        if right - left >= min_width:
            boxes.append((left, top, right - left, bh))
    return boxes


def detect_reserved_box(arr: np.ndarray) -> tuple[int, int, int, int] | None:
    """Return the first reserved rectangle for backward compatibility."""
    boxes = detect_reserved_boxes(arr)
    return boxes[0] if boxes else None


def build_editable_gabarito(src: Path, out: Path) -> dict:
    """Build an editable RGB gabarito from a flat PSD. Returns the starter calibration dict."""
    art = flat_art_to_rgb(src)
    W, H = art.size
    arr = np.array(art, dtype=np.uint8)
    cid = psapi.enum.ChannelID

    f = psapi.LayeredFile_8bit(psapi.enum.ColorMode.rgb, W, H)

    grp_bg = psapi.GroupLayer_8bit("FONDOS_TEMATICOS")
    f.add_layer(grp_bg)
    grp_bg.add_layer(f, psapi.ImageLayer_8bit(
        {cid.red: np.ascontiguousarray(arr[:, :, 0]),
         cid.green: np.ascontiguousarray(arr[:, :, 1]),
         cid.blue: np.ascontiguousarray(arr[:, :, 2])},
        "fundo_kraft_tradicional", width=W, height=H, pos_x=0, pos_y=0, is_visible=True))

    boxes = detect_reserved_boxes(arr)
    if not boxes:
        boxes = [(int(W * 0.36), int(H * 0.91), int(W * 0.28), int(H * 0.055))]

    grp_graf = psapi.GroupLayer_8bit("ELEMENTOS_GRAFICOS")
    f.add_layer(grp_graf)
    grp_txt = psapi.GroupLayer_8bit("TEXTOS_EDITAVEIS")
    f.add_layer(grp_txt)
    calibration = {}
    for face, (bx, by, bw, bh) in enumerate(boxes, start=1):
        suffix = "" if face == 1 else f"_{face}"
        pad = max(1, int(bh * 0.14))
        logo_sz = max(1, bh - 2 * pad)
        logo_x, logo_y = bx + pad, by + pad
        text_x = logo_x + logo_sz + pad * 2
        text_w = max(1, bx + bw - text_x - pad)
        tel_size, ig_size = max(8, int(bh * 0.14)), max(8, int(bh * 0.11))
        tel_y = by + int(bh * 0.22)
        ig_y = tel_y + int(tel_size * 1.55)
        logo_name = f"LOGO_CLIENTE{suffix}"

        grp_graf.add_layer(f, psapi.ImageLayer_8bit(
            {cid.red: np.full((logo_sz, logo_sz), 210, np.uint8),
             cid.green: np.full((logo_sz, logo_sz), 210, np.uint8),
             cid.blue: np.full((logo_sz, logo_sz), 210, np.uint8)},
            logo_name, width=logo_sz, height=logo_sz, pos_x=logo_x, pos_y=logo_y))
        calibration[logo_name] = {
            "x": logo_x, "y": logo_y, "width": logo_sz, "height": logo_sz,
        }

        fields = [
            (f"TEXTO_TELEFONE{suffix}", "(11) 0000-0000", tel_size, text_x, tel_y),
            (f"TEXTO_INSTAGRAM{suffix}", "@pizzaria", ig_size, text_x, ig_y),
        ]
        for name, sample, size, x, y in fields:
            grp_txt.add_layer(f, psapi.TextLayer_8bit(
                name, sample, font="ArialMT", font_size=float(size),
                fill_color=[1.0, 0.0, 0.0, 0.0], position_x=float(x), position_y=float(y + size)))
            calibration[name] = {
                "x": x, "y": y, "width": text_w, "height": int(size * 1.3),
                "font_size": size,
            }

    out.parent.mkdir(parents=True, exist_ok=True)
    psd_write(f, str(out))
    return calibration
