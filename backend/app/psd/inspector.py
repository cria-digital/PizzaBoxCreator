"""PSD layer inspector: reads template structure for API responses."""

from __future__ import annotations

from pathlib import Path

import photoshopapi as psapi

from app.models.commands import LayerInfo, TemplateInfo
from app.psd.engine import psd_read


def inspect_template(template_path: Path) -> TemplateInfo:
    """Read a PSD and return its layer structure."""
    file = psd_read(str(template_path))

    layers: list[LayerInfo] = []
    for layer in file.flat_layers:
        tname = type(layer).__name__
        is_text = "TextLayer" in tname
        is_image = "ImageLayer" in tname
        is_smart = "SmartObject" in tname

        current_text = None
        if is_text:
            current_text = layer.text

        layers.append(LayerInfo(
            name=layer.name,
            layer_type="text" if is_text else "image" if is_image else "smart_object" if is_smart else "group",
            visible=layer.is_visible,
            editable=is_text or is_image or is_smart,
            current_text=current_text,
        ))

    return TemplateInfo(
        filename=template_path.name,
        width=file.width,
        height=file.height,
        layers=layers,
    )
