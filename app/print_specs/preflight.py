"""Preflight helpers for checking artwork against a die-cut PDF."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter


def load_die_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fit_image_to_canvas(image: Image.Image, canvas_px: dict[str, int], mode: str = "cover") -> Image.Image:
    target_w = int(canvas_px["width"])
    target_h = int(canvas_px["height"])
    if target_w <= 0 or target_h <= 0:
        raise ValueError("Canvas precisa ter largura e altura positivas.")

    image = image.convert("RGB")
    src_w, src_h = image.size
    if src_w <= 0 or src_h <= 0:
        raise ValueError("Imagem de entrada invalida.")

    if mode == "stretch":
        return image.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if mode not in {"cover", "contain"}:
        raise ValueError("mode deve ser 'cover', 'contain' ou 'stretch'.")

    scale = max(target_w / src_w, target_h / src_h) if mode == "cover" else min(target_w / src_w, target_h / src_h)
    resized = image.resize((round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS)

    if mode == "cover":
        left = max(0, (resized.width - target_w) // 2)
        top = max(0, (resized.height - target_h) // 2)
        return resized.crop((left, top, left + target_w, top + target_h))

    canvas = Image.new("RGB", (target_w, target_h), "white")
    left = (target_w - resized.width) // 2
    top = (target_h - resized.height) // 2
    canvas.paste(resized, (left, top))
    return canvas


def bleed_crop_box_for_rendered_media(spec: dict[str, Any], rendered_media_size: tuple[int, int]) -> tuple[int, int, int, int]:
    media = spec["boxes"]["MediaBox"]["points"]
    bleed = spec["boxes"]["BleedBox"]["points"]
    rendered_w, rendered_h = rendered_media_size
    scale_x = rendered_w / media["width"]
    scale_y = rendered_h / media["height"]

    left = round((bleed["left"] - media["left"]) * scale_x)
    right = round((bleed["right"] - media["left"]) * scale_x)
    top = round((media["top"] - bleed["top"]) * scale_y)
    bottom = round((media["top"] - bleed["bottom"]) * scale_y)
    return left, top, right, bottom


def _render_pdf_page(pdf_path: Path, page: int, dpi: float, output_dir: Path) -> Path:
    prefix = output_dir / "die"
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-f",
            str(page),
            "-l",
            str(page),
            "-singlefile",
            "-r",
            f"{dpi:.6f}",
            str(pdf_path),
            str(prefix),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    rendered = prefix.with_suffix(".png")
    if not rendered.exists():
        raise RuntimeError("pdftoppm nao gerou o PNG esperado.")
    return rendered


def render_die_to_bleed_box(pdf_path: Path, spec: dict[str, Any], target_size: tuple[int, int]) -> Image.Image:
    bleed_width_pt = spec["boxes"]["BleedBox"]["points"]["width"]
    target_w, target_h = target_size
    scale = target_w / bleed_width_pt
    dpi = scale * 72.0

    with tempfile.TemporaryDirectory(prefix="pizzabox_preflight_") as tmp:
        rendered_path = _render_pdf_page(pdf_path, spec.get("page", 1), dpi, Path(tmp))
        rendered = Image.open(rendered_path).convert("RGB")
        crop_box = bleed_crop_box_for_rendered_media(spec, rendered.size)
        cropped = rendered.crop(crop_box)
        if cropped.size != target_size:
            cropped = cropped.resize(target_size, Image.Resampling.LANCZOS)
        return cropped


def line_art_overlay(die_image: Image.Image, color: tuple[int, int, int] = (0, 180, 255),
                     alpha: int = 220, thicken: int = 3) -> Image.Image:
    rgb = die_image.convert("RGB")
    white = Image.new("RGB", rgb.size, "white")
    diff = ImageChops.difference(rgb, white).convert("L")
    mask = diff.point(lambda px: 255 if px > 12 else 0)
    if thicken > 1:
        if thicken % 2 == 0:
            thicken += 1
        mask = mask.filter(ImageFilter.MaxFilter(thicken))

    overlay = Image.new("RGBA", rgb.size, (*color, 0))
    overlay.putalpha(mask.point(lambda px: alpha if px else 0))
    return overlay


def unsafe_area_overlay(
    die_image: Image.Image,
    *,
    color: tuple[int, int, int] = (255, 40, 40),
    alpha: int = 120,
    thicken: int = 41,
) -> Image.Image:
    """Expanded no-place zone around die/cut/fold lines for visual preflight."""
    return line_art_overlay(die_image, color=color, alpha=alpha, thicken=thicken)


def build_die_generation_guide(
    *,
    die_pdf_path: Path,
    spec_path: Path,
    output_path: Path,
    max_width: int = 1800,
) -> Path:
    """Render the die as a lightweight geometry reference for image generation.

    This guide is passed to the image model so it can avoid placing logos/text over
    cut/fold lines. It is not part of the final artwork.
    """
    spec = load_die_spec(spec_path)
    canvas = spec["canvas_px"]
    guide_w = min(max_width, int(canvas["width"]))
    guide_h = round(guide_w * int(canvas["height"]) / int(canvas["width"]))
    guide_size = (guide_w, guide_h)

    die = render_die_to_bleed_box(die_pdf_path, spec, guide_size)
    guide = Image.new("RGBA", guide_size, (246, 246, 242, 255))
    guide.alpha_composite(unsafe_area_overlay(die, alpha=135, thicken=37))
    guide.alpha_composite(line_art_overlay(die, color=(0, 90, 220), alpha=255, thicken=5))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    guide.convert("RGB").save(output_path, "PNG", optimize=True)
    return output_path


def build_safety_overlay(
    *,
    art_path: Path,
    die_pdf_path: Path,
    spec_path: Path,
    output_path: Path,
    max_width: int = 2400,
    fit_mode: str = "cover",
    unsafe_thicken: int = 51,
) -> Path:
    spec = load_die_spec(spec_path)
    canvas = fit_image_to_canvas(Image.open(art_path), spec["canvas_px"], mode=fit_mode)

    preview_w = min(max_width, canvas.width)
    preview_h = round(preview_w * canvas.height / canvas.width)
    preview = canvas.resize((preview_w, preview_h), Image.Resampling.LANCZOS).convert("RGBA")

    die = render_die_to_bleed_box(die_pdf_path, spec, preview.size)
    preview.alpha_composite(unsafe_area_overlay(die, alpha=125, thicken=unsafe_thicken))
    preview.alpha_composite(line_art_overlay(die, color=(0, 180, 255), alpha=230, thicken=5))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        preview.convert("RGB").save(output_path, "JPEG", quality=92)
    else:
        preview.save(output_path)
    return output_path


def build_preflight_overlay(
    *,
    art_path: Path,
    die_pdf_path: Path,
    spec_path: Path,
    output_path: Path,
    max_width: int = 2400,
    fit_mode: str = "cover",
) -> Path:
    spec = load_die_spec(spec_path)
    canvas = fit_image_to_canvas(Image.open(art_path), spec["canvas_px"], mode=fit_mode)

    preview_w = min(max_width, canvas.width)
    preview_h = round(preview_w * canvas.height / canvas.width)
    preview = canvas.resize((preview_w, preview_h), Image.Resampling.LANCZOS).convert("RGBA")

    die = render_die_to_bleed_box(die_pdf_path, spec, preview.size)
    preview.alpha_composite(line_art_overlay(die))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        preview.convert("RGB").save(output_path, "JPEG", quality=92)
    else:
        preview.save(output_path)
    return output_path
