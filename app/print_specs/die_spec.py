"""Build reusable die-cut specifications from PDF page boxes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.print_specs.pdf_boxes import inspect_pdf


SCHEMA_VERSION = 1


def build_die_spec(
    pdf_path: Path,
    *,
    name: str,
    product_type: str = "pizza_box",
    page_number: int = 1,
    dpi: int = 300,
) -> dict[str, Any]:
    inspection = inspect_pdf(pdf_path, page_number=page_number, dpi=dpi)
    boxes = inspection["boxes"]

    if not boxes["TrimBox"]["explicit"]:
        raise ValueError("TrimBox nao esta explicito no PDF; nao da para confiar na linha de corte.")
    if not boxes["BleedBox"]["explicit"]:
        raise ValueError("BleedBox nao esta explicito no PDF; nao da para derivar a sangria.")

    trim = boxes["TrimBox"]
    bleed = boxes["BleedBox"]
    media = boxes["MediaBox"]
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "product_type": product_type,
        "source_pdf": str(pdf_path),
        "page": page_number,
        "dpi": dpi,
        "cutline_source": "TrimBox",
        "canvas_source": "BleedBox",
        "trim_size_mm": {
            "width": trim["mm"]["width"],
            "height": trim["mm"]["height"],
        },
        "bleed_size_mm": {
            "width": bleed["mm"]["width"],
            "height": bleed["mm"]["height"],
        },
        "media_size_mm": {
            "width": media["mm"]["width"],
            "height": media["mm"]["height"],
        },
        "bleed_mm": inspection["bleed"]["mm"],
        "trim_px": trim["pixels"],
        "canvas_px": bleed["pixels"],
        "aspect_ratio": bleed["aspect_ratio"],
        "prompt_constraints": {
            "layout": "arte planificada horizontal de caixa",
            "aspect_ratio": bleed["aspect_ratio"],
            "target_canvas_px": bleed["pixels"],
            "must_not_draw": ["faca", "linha de corte", "vinco", "serrilha", "miras de registro"],
            "critical_note": "Preview e arte final devem derivar do mesmo master aprovado.",
        },
        "boxes": boxes,
    }


def write_die_spec(spec: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path

