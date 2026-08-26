"""Inspect PDF page boxes used to derive print geometry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader


PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
BOX_ATTRS = {
    "MediaBox": ("mediabox", "/MediaBox"),
    "CropBox": ("cropbox", "/CropBox"),
    "BleedBox": ("bleedbox", "/BleedBox"),
    "TrimBox": ("trimbox", "/TrimBox"),
    "ArtBox": ("artbox", "/ArtBox"),
}


def pt_to_mm(value: float) -> float:
    return value * MM_PER_INCH / PT_PER_INCH


def pt_to_px(value: float, dpi: int) -> float:
    return value * dpi / PT_PER_INCH


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _box_to_dict(box: Any, dpi: int, explicit: bool) -> dict[str, Any]:
    left = float(box.left)
    bottom = float(box.bottom)
    right = float(box.right)
    top = float(box.top)
    width = right - left
    height = top - bottom
    return {
        "explicit": explicit,
        "points": {
            "left": _round(left),
            "bottom": _round(bottom),
            "right": _round(right),
            "top": _round(top),
            "width": _round(width),
            "height": _round(height),
        },
        "mm": {
            "left": _round(pt_to_mm(left)),
            "bottom": _round(pt_to_mm(bottom)),
            "right": _round(pt_to_mm(right)),
            "top": _round(pt_to_mm(top)),
            "width": _round(pt_to_mm(width)),
            "height": _round(pt_to_mm(height)),
        },
        "pixels": {
            "width": int(round(pt_to_px(width, dpi))),
            "height": int(round(pt_to_px(height, dpi))),
        },
        "aspect_ratio": _round(width / height, 4) if height else None,
    }


def _bleed_from_boxes(trim: dict[str, Any], bleed: dict[str, Any]) -> dict[str, Any]:
    trim_pt = trim["points"]
    bleed_pt = bleed["points"]
    sides_pt = {
        "left": trim_pt["left"] - bleed_pt["left"],
        "right": bleed_pt["right"] - trim_pt["right"],
        "bottom": trim_pt["bottom"] - bleed_pt["bottom"],
        "top": bleed_pt["top"] - trim_pt["top"],
    }
    return {
        "points": {side: _round(value) for side, value in sides_pt.items()},
        "mm": {side: _round(pt_to_mm(value)) for side, value in sides_pt.items()},
    }


def inspect_pdf(path: Path, page_number: int = 1, dpi: int = 300) -> dict[str, Any]:
    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError(f"PDF sem paginas: {path}")
    if page_number < 1 or page_number > len(reader.pages):
        raise ValueError(f"Pagina {page_number} fora do intervalo 1..{len(reader.pages)}")

    page = reader.pages[page_number - 1]
    boxes: dict[str, Any] = {}
    for label, (attr, pdf_key) in BOX_ATTRS.items():
        explicit = pdf_key in page
        box = getattr(page, attr)
        boxes[label] = _box_to_dict(box, dpi=dpi, explicit=explicit)

    recommended_box = "BleedBox" if boxes["BleedBox"]["explicit"] else "MediaBox"
    result: dict[str, Any] = {
        "file": str(path),
        "page_count": len(reader.pages),
        "page": page_number,
        "dpi": dpi,
        "boxes": boxes,
        "recommended_canvas_box": recommended_box,
        "recommended_canvas": boxes[recommended_box],
    }

    if boxes["TrimBox"]["explicit"] and boxes["BleedBox"]["explicit"]:
        result["bleed"] = _bleed_from_boxes(boxes["TrimBox"], boxes["BleedBox"])
    else:
        result["bleed"] = None

    return result


def _format_dimension(box: dict[str, Any]) -> str:
    mm = box["mm"]
    px = box["pixels"]
    pt = box["points"]
    explicit = "explicito" if box["explicit"] else "padrao/inferido"
    return (
        f"{pt['width']:.2f} x {pt['height']:.2f} pt | "
        f"{mm['width']:.2f} x {mm['height']:.2f} mm | "
        f"{px['width']} x {px['height']} px | "
        f"ratio {box['aspect_ratio']} | {explicit}"
    )


def format_human(result: dict[str, Any]) -> str:
    lines = [
        f"Arquivo: {result['file']}",
        f"Pagina: {result['page']} de {result['page_count']}",
        f"DPI de referencia: {result['dpi']}",
        "",
        "Boxes:",
    ]
    for label in BOX_ATTRS:
        lines.append(f"  {label}: {_format_dimension(result['boxes'][label])}")

    lines.append("")
    if result["bleed"]:
        bleed_mm = result["bleed"]["mm"]
        lines.append(
            "Sangria TrimBox -> BleedBox: "
            f"left {bleed_mm['left']:.2f} mm, "
            f"right {bleed_mm['right']:.2f} mm, "
            f"bottom {bleed_mm['bottom']:.2f} mm, "
            f"top {bleed_mm['top']:.2f} mm"
        )
    else:
        lines.append("Sangria TrimBox -> BleedBox: indisponivel (TrimBox ou BleedBox nao explicito)")

    canvas_label = result["recommended_canvas_box"]
    canvas = result["recommended_canvas"]
    lines.append("")
    lines.append(f"Canvas recomendado: {canvas_label}")
    lines.append(f"  {_format_dimension(canvas)}")
    return "\n".join(lines)
