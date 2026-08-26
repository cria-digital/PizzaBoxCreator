"""Create the approved artwork master from a generated/source image and a die spec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

from app.print_specs.preflight import fit_image_to_canvas, load_die_spec


def save_approval_preview(
    master: Image.Image,
    output_path: Path,
    *,
    max_width: int = 2400,
    watermark: str = "",
    quality: int = 90,
) -> Path:
    preview_w = min(max_width, master.width)
    preview_h = round(preview_w * master.height / master.width)
    preview = master.resize((preview_w, preview_h), Image.Resampling.LANCZOS).convert("RGBA")

    if watermark:
        draw = ImageDraw.Draw(preview)
        font_size = max(32, preview_w // 18)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), watermark, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (preview_w - text_w) // 2
        y = (preview_h - text_h) // 2
        pad = max(16, font_size // 3)
        draw.rounded_rectangle(
            (x - pad, y - pad, x + text_w + pad, y + text_h + pad),
            radius=max(8, pad // 2),
            fill=(255, 255, 255, 150),
        )
        draw.text((x, y), watermark, font=font, fill=(20, 20, 20, 190))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        preview.convert("RGB").save(output_path, "JPEG", quality=quality)
    else:
        preview.save(output_path)
    return output_path


def trim_generated_mockup_margin(
    image: Image.Image,
    *,
    threshold: int = 28,
    min_margin_fraction: float = 0.025,
    padding_fraction: float = 0.0,
) -> tuple[Image.Image, dict[str, Any]]:
    """Crop provider-created mockup/prancha margins before fitting to the die canvas."""
    source = image.convert("RGB")
    analysis_w = min(900, source.width)
    analysis_h = round(analysis_w * source.height / source.width)
    analysis = source.resize((analysis_w, analysis_h), Image.Resampling.BOX)

    sample = max(8, min(analysis.size) // 30)
    corner_boxes = (
        (0, 0, sample, sample),
        (analysis.width - sample, 0, analysis.width, sample),
        (0, analysis.height - sample, sample, analysis.height),
        (analysis.width - sample, analysis.height - sample, analysis.width, analysis.height),
    )
    medians = [ImageStat.Stat(analysis.crop(box)).median for box in corner_boxes]
    background = tuple(round(sum(color[channel] for color in medians) / len(medians)) for channel in range(3))

    diff = ImageChops.difference(analysis, Image.new("RGB", analysis.size, background)).convert("L")
    mask = diff.point(lambda px: 255 if px > threshold else 0).filter(ImageFilter.MaxFilter(5))
    bbox = mask.getbbox()
    info: dict[str, Any] = {
        "trimmed": False,
        "background_rgb": background,
        "threshold": threshold,
    }
    if not bbox:
        info["reason"] = "sem conteudo destacado da margem"
        return source, info

    sx = source.width / analysis.width
    sy = source.height / analysis.height
    left = round(bbox[0] * sx)
    top = round(bbox[1] * sy)
    right = round(bbox[2] * sx)
    bottom = round(bbox[3] * sy)

    pad = round(min(source.width, source.height) * padding_fraction)
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(source.width, right + pad)
    bottom = min(source.height, bottom + pad)

    crop_w = right - left
    crop_h = bottom - top
    margins = {
        "left": left / source.width,
        "right": (source.width - right) / source.width,
        "top": top / source.height,
        "bottom": (source.height - bottom) / source.height,
    }
    info.update({
        "crop_box": {"left": left, "top": top, "right": right, "bottom": bottom},
        "margins": margins,
    })

    max_margin = max(margins.values())
    crop_area_fraction = (crop_w * crop_h) / (source.width * source.height)
    if max_margin < min_margin_fraction:
        info["reason"] = "margem pequena demais para crop automatico"
        return source, info
    if crop_area_fraction < 0.35:
        info["reason"] = "crop descartado por remover conteudo demais"
        return source, info
    if crop_w <= 0 or crop_h <= 0:
        info["reason"] = "crop invalido"
        return source, info

    info["trimmed"] = True
    info["crop_area_fraction"] = round(crop_area_fraction, 4)
    return source.crop((left, top, right, bottom)), info


def build_art_master(
    *,
    source_path: Path,
    spec_path: Path,
    output_path: Path,
    fit_mode: str = "cover",
    auto_trim_mockup_margin: bool = False,
    preview_path: Path | None = None,
    preview_max_width: int = 2400,
    watermark: str = "",
) -> dict[str, Any]:
    spec = load_die_spec(spec_path)
    original = Image.open(source_path).convert("RGB")
    source = original
    margin_trim: dict[str, Any] | None = None
    if auto_trim_mockup_margin:
        source, margin_trim = trim_generated_mockup_margin(original)
    master = fit_image_to_canvas(source, spec["canvas_px"], mode=fit_mode)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.save(output_path, "PNG", compress_level=1)

    result: dict[str, Any] = {
        "source": str(source_path),
        "spec": str(spec_path),
        "master": str(output_path),
        "fit_mode": fit_mode,
        "source_px": {"width": original.width, "height": original.height},
        "fitted_source_px": {"width": source.width, "height": source.height},
        "canvas_px": {"width": master.width, "height": master.height},
        "dpi": spec["dpi"],
        "bleed_size_mm": spec["bleed_size_mm"],
        "trim_size_mm": spec["trim_size_mm"],
        "aspect_ratio": spec["aspect_ratio"],
    }
    if margin_trim:
        result["margin_trim"] = margin_trim

    if preview_path:
        save_approval_preview(
            master,
            preview_path,
            max_width=preview_max_width,
            watermark=watermark,
        )
        result["approval_preview"] = str(preview_path)

    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["metadata"] = str(metadata_path)
    return result
