"""Build a print-sized artwork PDF from an approved master image and die spec."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, RectangleObject

from app.print_specs.pdf_boxes import pt_to_mm
from app.print_specs.preflight import load_die_spec


def _box_points_from_mm(width_mm: float, height_mm: float) -> tuple[float, float]:
    return width_mm * 72.0 / 25.4, height_mm * 72.0 / 25.4


def _expected_canvas(spec: dict[str, Any]) -> tuple[int, int]:
    canvas = spec["canvas_px"]
    return int(canvas["width"]), int(canvas["height"])


def _validate_master_size(master: Image.Image, spec: dict[str, Any]) -> None:
    expected = _expected_canvas(spec)
    if master.size != expected:
        raise ValueError(
            f"Master tem {master.size[0]}x{master.size[1]} px, mas o spec exige "
            f"{expected[0]}x{expected[1]} px."
        )


def _page_geometry(spec: dict[str, Any]) -> dict[str, Any]:
    bleed_w_pt, bleed_h_pt = _box_points_from_mm(
        spec["bleed_size_mm"]["width"],
        spec["bleed_size_mm"]["height"],
    )
    left_bleed_pt = spec["bleed_mm"]["left"] * 72.0 / 25.4
    right_bleed_pt = spec["bleed_mm"]["right"] * 72.0 / 25.4
    bottom_bleed_pt = spec["bleed_mm"]["bottom"] * 72.0 / 25.4
    top_bleed_pt = spec["bleed_mm"]["top"] * 72.0 / 25.4
    return {
        "bleed": RectangleObject([0, 0, bleed_w_pt, bleed_h_pt]),
        "trim": RectangleObject([
            left_bleed_pt,
            bottom_bleed_pt,
            bleed_w_pt - right_bleed_pt,
            bleed_h_pt - top_bleed_pt,
        ]),
        "width_pt": bleed_w_pt,
        "height_pt": bleed_h_pt,
    }


def _apply_page_boxes(page, geometry: dict[str, Any]) -> None:
    page.mediabox = geometry["bleed"]
    page.cropbox = geometry["bleed"]
    page.bleedbox = geometry["bleed"]
    page.trimbox = geometry["trim"]
    page.artbox = page.trimbox


def image_xobject_color_spaces(pdf_path: Path) -> list[str]:
    """Return image XObject color spaces found in a PDF, useful for CMYK verification."""
    reader = PdfReader(str(pdf_path))
    colors: list[str] = []
    for page in reader.pages:
        resources = page.get("/Resources", {})
        xobjects = resources.get("/XObject", {})
        for obj in xobjects.values():
            resolved = obj.get_object()
            if resolved.get("/Subtype") != NameObject("/Image"):
                continue
            color_space = resolved.get("/ColorSpace")
            colors.append(str(color_space))
    return colors


def build_artwork_pdf(
    *,
    master_path: Path,
    spec_path: Path,
    output_path: Path,
    quality: int = 95,
) -> dict[str, Any]:
    spec = load_die_spec(spec_path)
    master = Image.open(master_path).convert("RGB")
    _validate_master_size(master, spec)

    dpi = int(spec["dpi"])
    geometry = _page_geometry(spec)

    with tempfile.TemporaryDirectory(prefix="pizzabox_pdf_") as tmp:
        raw_pdf = Path(tmp) / "raw.pdf"
        master.save(raw_pdf, "PDF", resolution=dpi, quality=quality)

        reader = PdfReader(str(raw_pdf))
        writer = PdfWriter()
        page = reader.pages[0]

        _apply_page_boxes(page, geometry)
        writer.add_page(page)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as stream:
            writer.write(stream)

    return {
        "pdf": str(output_path),
        "master": str(master_path),
        "spec": str(spec_path),
        "dpi": dpi,
        "page_size_mm": {
            "width": round(pt_to_mm(geometry["width_pt"]), 2),
            "height": round(pt_to_mm(geometry["height_pt"]), 2),
        },
        "trim_size_mm": spec["trim_size_mm"],
        "bleed_mm": spec["bleed_mm"],
        "canvas_px": spec["canvas_px"],
        "color_mode": "RGB",
        "production_note": "PDF geometrico para validacao; conversao CMYK/PDF-X vem na etapa seguinte.",
    }


def build_cmyk_artwork_pdf(
    *,
    cmyk_path: Path,
    spec_path: Path,
    output_path: Path,
    quality: int = 95,
) -> dict[str, Any]:
    spec = load_die_spec(spec_path)
    cmyk = Image.open(cmyk_path)
    if cmyk.mode != "CMYK":
        raise ValueError(f"Imagem precisa estar em CMYK; recebido {cmyk.mode}.")
    _validate_master_size(cmyk, spec)

    dpi = int(spec["dpi"])
    geometry = _page_geometry(spec)
    with tempfile.TemporaryDirectory(prefix="pizzabox_pdf_cmyk_") as tmp:
        raw_pdf = Path(tmp) / "raw.pdf"
        cmyk.save(raw_pdf, "PDF", resolution=dpi, quality=quality)

        reader = PdfReader(str(raw_pdf))
        writer = PdfWriter()
        page = reader.pages[0]
        _apply_page_boxes(page, geometry)
        writer.add_page(page)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as stream:
            writer.write(stream)

    return {
        "pdf": str(output_path),
        "cmyk_master": str(cmyk_path),
        "spec": str(spec_path),
        "dpi": dpi,
        "page_size_mm": {
            "width": round(pt_to_mm(geometry["width_pt"]), 2),
            "height": round(pt_to_mm(geometry["height_pt"]), 2),
        },
        "trim_size_mm": spec["trim_size_mm"],
        "bleed_mm": spec["bleed_mm"],
        "canvas_px": spec["canvas_px"],
        "color_mode": "CMYK",
        "image_color_spaces": image_xobject_color_spaces(output_path),
        "production_note": "PDF CMYK raster com boxes tecnicos; PDF/X e OutputIntent ficam para validacao final.",
    }


def write_pdf_metadata(result: dict[str, Any], output_path: Path) -> Path:
    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metadata_path
