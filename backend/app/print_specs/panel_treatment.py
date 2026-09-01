"""Deterministic panel-level artwork treatments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from app.print_specs.layout_template import NormalizedBox, template_panel


@dataclass(frozen=True)
class PixelBox:
    left: int
    top: int
    right: int
    bottom: int

    def as_dict(self) -> dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }


def normalized_box_to_pixels(box: NormalizedBox, size: tuple[int, int]) -> PixelBox:
    width, height = size
    left = max(0, min(width, round(box.x_min * width)))
    top = max(0, min(height, round(box.y_min * height)))
    right = max(left, min(width, round(box.x_max * width)))
    bottom = max(top, min(height, round(box.y_max * height)))
    return PixelBox(left=left, top=top, right=right, bottom=bottom)


def blank_design_panel(
    *,
    image_path: Path,
    output_path: Path,
    panel_name: str = "bottom_panel",
    fill: tuple[int, int, int] = (255, 255, 255),
) -> dict[str, Any]:
    """Blank a named design-template panel without changing the die geometry."""
    image = Image.open(image_path).convert("RGB")
    panel_box = template_panel(panel_name, inset_safe_margin=False)
    pixel_box = normalized_box_to_pixels(panel_box, image.size)

    treated = image.copy()
    draw = ImageDraw.Draw(treated)
    draw.rectangle(
        (pixel_box.left, pixel_box.top, pixel_box.right, pixel_box.bottom),
        fill=fill,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    treated.save(output_path)
    return {
        "applied": True,
        "panel": panel_name,
        "box": pixel_box.as_dict(),
        "fill_rgb": list(fill),
    }
