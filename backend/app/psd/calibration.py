"""Maps editable fields to PSD layers and reads their geometry for the calibration UI.

A field can map to several layers, one per box face: the convention is a base layer name
plus an optional numeric suffix (`TEXTO_TELEFONE`, `TEXTO_TELEFONE_2`, ...). The engine fills
every matching layer with the same content, and each is positioned independently via
calibration, so a DUPLA (mirrored two-face) box shows the phone/logo on both faces.

Calibration coordinates are stored in PSD canvas pixels as a top-left box plus, for text,
a font size, keyed by the exact layer name:

    {
      "TEXTO_TELEFONE":   {"x": 700, "y": 1800, "width": 600, "height": 120, "font_size": 96},
      "TEXTO_TELEFONE_2": {"x": 2700, "y": 1800, "width": 600, "height": 120, "font_size": 96},
      "LOGO_CLIENTE":     {"x": 1600, "y": 300, "width": 800, "height": 800}
    }

The convention deliberately matches how the renderer draws each layer, so a saved box maps
1:1 to what shows up on the preview:
- text is drawn at y = transform_ty - font_size, so the box top `y` == transform_ty - font_size;
- image layers are pasted at (center_x, center_y) treated as top-left, so `x`/`y` == those.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import photoshopapi as psapi

# Editable field base layer names and their human labels.
TEXT_BASES = ("TEXTO_TELEFONE", "TEXTO_INSTAGRAM", "TEXTO_FRASE_OPCIONAL")
LOGO_BASE = "LOGO_CLIENTE"
ALL_BASES = (*TEXT_BASES, LOGO_BASE)

FIELD_LABELS = {
    "TEXTO_TELEFONE": "Telefone",
    "TEXTO_INSTAGRAM": "Instagram",
    "TEXTO_FRASE_OPCIONAL": "Frase",
    "LOGO_CLIENTE": "Logo",
}

# `BASE` or `BASE_<n>`; the numeric suffix is the box face (1 when absent).
_SUFFIX = re.compile(r"^(?P<base>.+?)(?:_(?P<n>\d+))?$")


def split_layer_name(name: str | None) -> tuple[str, int]:
    """Return (base_name, face_number) for a layer, e.g. 'TEXTO_TELEFONE_2' -> ('TEXTO_TELEFONE', 2)."""
    normalized = name or ""
    m = _SUFFIX.match(normalized)
    if not m:
        return normalized, 1
    base = m.group("base")
    n = m.group("n")
    return base, (int(n) if n else 1)


def layers_for_base(layer_names, base: str) -> list[str]:
    """All layer names belonging to a field base, ordered by face number."""
    matches = [n for n in layer_names if split_layer_name(n)[0] == base]
    return sorted(matches, key=lambda n: split_layer_name(n)[1])


def field_label(name: str) -> str:
    """Display label for a (possibly mirrored) layer, e.g. 'Telefone' or 'Telefone (2)'."""
    base, face = split_layer_name(name)
    label = FIELD_LABELS.get(base, name)
    return label if face == 1 else f"{label} ({face})"


@dataclass
class LayerBox:
    name: str
    kind: str  # "text" | "logo"
    x: float
    y: float
    width: float
    height: float
    font_size: float | None = None


@dataclass
class TemplateGeometry:
    width: int
    height: int
    boxes: list[LayerBox]


def read_template_geometry(template_path: Path) -> TemplateGeometry:
    """Read canvas size and the default geometry of every editable layer (all faces)."""
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            file = psapi.LayeredFile.read(str(template_path))
            break
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(0.2 * attempt)
    else:
        raise last_exc  # type: ignore[misc]

    boxes: list[LayerBox] = []
    for layer in file.flat_layers:
        base, _face = split_layer_name(layer.name)
        if base in TEXT_BASES and "TextLayer" in type(layer).__name__:
            boxes.append(_text_box(layer))
        elif base == LOGO_BASE and "ImageLayer" in type(layer).__name__:
            boxes.append(LayerBox(
                name=layer.name, kind="logo",
                x=float(layer.center_x), y=float(layer.center_y),
                width=float(layer.width), height=float(layer.height),
            ))

    return TemplateGeometry(width=file.width, height=file.height, boxes=boxes)


def _text_box(layer) -> LayerBox:
    try:
        font_size = float(layer.style_run_font_size(0))
    except Exception:
        font_size = 24.0

    width = height = 0.0
    try:
        if layer.is_box_text:
            width = float(layer.box_width())
            height = float(layer.box_height())
    except Exception:
        pass
    if width <= 0:
        width = max(font_size * 8, 200.0)
    if height <= 0:
        height = max(font_size * 1.4, 40.0)

    # Box top aligns with where the renderer draws the baseline-anchored text.
    return LayerBox(
        name=layer.name, kind="text",
        x=float(layer.transform_tx),
        y=float(layer.transform_ty) - font_size,
        width=width, height=height, font_size=font_size,
    )


def merge_geometry(geometry: TemplateGeometry, calibration: dict) -> list[dict]:
    """Overlay saved calibration onto the PSD defaults, for rendering the UI."""
    merged: list[dict] = []
    for box in geometry.boxes:
        data = asdict(box)
        saved = calibration.get(box.name)
        if isinstance(saved, dict):
            for key in ("x", "y", "width", "height", "font_size"):
                if saved.get(key) is not None:
                    data[key] = saved[key]
        data["label"] = field_label(box.name)
        merged.append(data)
    return merged
