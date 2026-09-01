"""Prepares a client logo for compositing onto the box art.

A logo arriving by WhatsApp is a photo (JPEG, no transparency), so pasting it as-is drops the
logo inside a white/photo rectangle on the box. This removes the background so the logo sits
cleanly on the artwork, and always writes a PNG (alpha preserved) that the engine's logo mask
can use.

Background removal uses `rembg` (optional dependency, local ONNX model). It is best-effort:
if rembg isn't installed, removal is disabled, or anything fails, the original image is kept so
the pipeline never breaks. Install with `pip install pizza-box-agent[logo]`.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from app.config import settings

logger = logging.getLogger(__name__)

_session = None  # cached rembg session (model is loaded once, lazily)


def prepare_logo(image_bytes: bytes, dest_path: Path) -> Path:
    """Write `image_bytes` to `dest_path` (forced to .png), background removed when possible.

    Returns the path actually written. Never raises on bad input: if the bytes aren't a
    decodable image, they're written verbatim so the downstream engine reports the usual
    "formato invalido" warning instead of crashing.
    """
    dest_path = dest_path.with_suffix(".png")
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    image = None
    if settings.logo_remove_background:
        image = _remove_background(image_bytes)
    if image is None:
        image = _open_rgba(image_bytes)

    if image is None:
        # Not a decodable image — keep raw bytes so the file exists; engine warns later.
        dest_path.write_bytes(image_bytes)
        return dest_path

    image.save(dest_path, "PNG")
    return dest_path


def _open_rgba(image_bytes: bytes) -> Image.Image | None:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        return img.convert("RGBA")
    except Exception:
        return None


def _remove_background(image_bytes: bytes) -> Image.Image | None:
    img = _open_rgba(image_bytes)
    if img is None:
        return None

    try:
        from rembg import remove, new_session
    except Exception:
        logger.warning(
            "rembg nao instalado -- logo usada sem remocao de fundo. "
            "Instale com: pip install pizza-box-agent[logo]"
        )
        return None

    try:
        global _session
        if _session is None:
            _session = new_session()  # downloads the model on first use
        return remove(img, session=_session).convert("RGBA")
    except Exception:
        logger.exception("Falha ao remover fundo da logo -- usando imagem original")
        return img
