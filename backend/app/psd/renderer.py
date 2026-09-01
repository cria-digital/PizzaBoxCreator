"""Preview renderer: composites PSD layers into a flat JPG using PhotoshopAPI + Pillow."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import photoshopapi as psapi
from PIL import Image, ImageDraw

from app.config import settings
from app.psd.engine import psd_read, rgb_channels, text_fill_rgb
from app.psd.text_metrics import get_font, wrap_text


def generate_preview(psd_path: Path, preview_path: Path) -> Path:
    """Render a PSD to a JPG preview by manually compositing visible layers."""
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    file = psd_read(str(psd_path))
    canvas = Image.new("RGB", (file.width, file.height), (255, 255, 255))

    cid = psapi.enum.ChannelID
    _composite_layers(file.layers, canvas, file, cid)

    max_w = settings.preview_max_width
    if canvas.width > max_w:
        ratio = max_w / canvas.width
        new_size = (max_w, int(canvas.height * ratio))
        canvas = canvas.resize(new_size, Image.LANCZOS)

    canvas.save(str(preview_path), "JPEG", quality=settings.preview_quality)
    return preview_path


def _composite_layers(layers, canvas: Image.Image, file, cid):
    for layer in layers:
        if not layer.is_visible:
            continue

        tname = type(layer).__name__

        if "GroupLayer" in tname:
            if hasattr(layer, "layers"):
                _composite_layers(layer.layers, canvas, file, cid)

        elif "ImageLayer" in tname:
            _paste_image_layer(layer, canvas, cid)

        elif "TextLayer" in tname:
            _render_text_layer(layer, canvas)


def _paste_image_layer(layer, canvas: Image.Image, cid):
    try:
        data = layer.get_image_data()
    except Exception:
        return

    if isinstance(data, dict):
        rgb = rgb_channels(data)
        if rgb is None:
            return
        r, g, b = rgb
        img = Image.fromarray(np.stack([r, g, b], axis=-1), "RGB")
    elif isinstance(data, np.ndarray):
        if data.ndim == 3 and data.shape[2] >= 3:
            img = Image.fromarray(data[:, :, :3], "RGB")
        else:
            return
    else:
        return

    x = int(layer.center_x)
    y = int(layer.center_y)

    opacity = getattr(layer, "opacity", 1.0)
    alpha = _layer_mask_alpha(layer, img.width, img.height)

    if alpha is not None:
        img.putalpha(Image.fromarray(alpha, "L"))
        if opacity < 1.0:
            scaled = img.getchannel("A").point(lambda v: int(v * opacity))
            img.putalpha(scaled)
        canvas.paste(img, (x, y), img)
    elif opacity < 1.0:
        img.putalpha(int(opacity * 255))
        canvas.paste(img, (x, y), img)
    else:
        canvas.paste(img, (x, y))


def _layer_mask_alpha(layer, width: int, height: int) -> np.ndarray | None:
    """Read the layer's pixel mask (set by logo replacement) as a preview alpha channel.

    If the mask dimensions don't match the layer (e.g. a mask sized for a previous
    logo position), it's resized to fit rather than silently discarded, so the logo
    keeps its transparency.
    """
    try:
        if not layer.has_mask():
            return None
        mask = np.array(layer.mask, dtype=np.uint8)
    except Exception:
        return None

    if mask.shape != (height, width):
        from PIL import Image as _Image
        resized = _Image.fromarray(mask, "L").resize((width, height), _Image.LANCZOS)
        mask = np.array(resized, dtype=np.uint8)
    return mask


def _render_text_layer(layer, canvas: Image.Image):
    text = layer.text
    if not text:
        return

    try:
        font_size = int(layer.style_run_font_size(0))
    except Exception:
        font_size = 24
    font_name = getattr(layer, "primary_font_name", None)
    font = get_font(max(font_size, 10), font_name)

    draw = ImageDraw.Draw(canvas)
    color = text_fill_rgb(layer)

    x = int(layer.transform_tx)
    y = int(layer.transform_ty) - font_size

    max_width = _safe_box_width(layer)
    lines = wrap_text(draw, text, font, max_width) if max_width else [text]

    line_height = font_size * 1.2
    for i, line in enumerate(lines):
        draw.text((x, y + i * line_height), line, font=font, fill=color)


def _safe_box_width(layer) -> float | None:
    """Width of the layer's text box, if it's box (paragraph) text with a real size."""
    try:
        if not layer.is_box_text:
            return None
        width = layer.box_width()
        return width if width > 0 else None
    except Exception:
        return None
