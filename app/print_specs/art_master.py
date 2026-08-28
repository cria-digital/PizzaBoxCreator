"""Create the approved artwork master from a generated/source image and a die spec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
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


def cover_light_edge_leaks(
    image: Image.Image,
    *,
    threshold: int = 176,
    saturation_delta: int = 64,
    max_edge_fraction: float = 0.18,
) -> tuple[Image.Image, dict[str, Any]]:
    """Fill bright neutral areas connected to canvas edges with nearby artwork."""
    source = image.convert("RGB")
    analysis_size = _analysis_size(source.size, max_width=900)
    analysis = source.resize(analysis_size, Image.Resampling.BOX)
    mask = _light_neutral_mask(analysis, threshold=threshold, saturation_delta=saturation_delta)
    edge_mask_small = _edge_connected_mask(
        mask,
        max_edge_px=round(min(analysis.size) * max_edge_fraction),
    )
    bbox = edge_mask_small.getbbox()
    info: dict[str, Any] = {
        "applied": False,
        "threshold": threshold,
        "saturation_delta": saturation_delta,
        "analysis_px": {"width": analysis.width, "height": analysis.height},
    }
    if not bbox:
        info["reason"] = "sem vazamento claro conectado a borda"
        return source, info

    total = analysis.width * analysis.height
    covered_px = sum(edge_mask_small.histogram()[1:])
    covered_fraction = covered_px / max(1, total)
    info["covered_fraction"] = round(covered_fraction, 5)
    sx = source.width / analysis.width
    sy = source.height / analysis.height
    info["bbox"] = {
        "left": round(bbox[0] * sx),
        "top": round(bbox[1] * sy),
        "right": round(bbox[2] * sx),
        "bottom": round(bbox[3] * sy),
    }
    if covered_fraction > 0.32:
        info["reason"] = "area clara grande demais para reparo automatico"
        return source, info

    filled = source.copy()
    color = _dominant_non_light_color(source)
    repair_size = _analysis_size(source.size, max_width=1400)
    blurred_small = source.resize(repair_size, Image.Resampling.BOX).filter(
        ImageFilter.GaussianBlur(radius=max(10, min(repair_size) // 70))
    )
    blurred = blurred_small.resize(source.size, Image.Resampling.BICUBIC)
    base = Image.new("RGB", source.size, color)
    repaired = Image.blend(base, blurred, 0.08)
    edge_mask = edge_mask_small.resize(source.size, Image.Resampling.NEAREST)
    softened_mask = edge_mask.filter(ImageFilter.GaussianBlur(radius=max(6, min(source.size) // 420)))
    filled.paste(repaired, (0, 0), softened_mask)
    info["applied"] = True
    info["fill_rgb"] = color
    return filled, info


def _light_neutral_mask(image: Image.Image, *, threshold: int, saturation_delta: int) -> Image.Image:
    arr = np.asarray(image.convert("RGB"), dtype=np.uint8)
    channel_min = arr.min(axis=2)
    channel_delta = arr.max(axis=2) - channel_min
    mask = (channel_min >= threshold) & (channel_delta <= saturation_delta)
    return Image.fromarray(mask.astype(np.uint8) * 255)


def _edge_connected_mask(mask: Image.Image, *, max_edge_px: int) -> Image.Image:
    max_edge_px = max(4, max_edge_px)
    edge = Image.new("L", mask.size, 0)
    draw = ImageDraw.Draw(edge)
    draw.rectangle((0, 0, mask.width, max_edge_px), fill=255)
    draw.rectangle((0, mask.height - max_edge_px, mask.width, mask.height), fill=255)
    draw.rectangle((0, 0, max_edge_px, mask.height), fill=255)
    draw.rectangle((mask.width - max_edge_px, 0, mask.width, mask.height), fill=255)
    seed = ImageChops.multiply(mask, edge)
    connected = seed
    while True:
        expanded = connected.filter(ImageFilter.MaxFilter(5))
        expanded = ImageChops.multiply(expanded, mask)
        if ImageChops.difference(expanded, connected).getbbox() is None:
            return connected.filter(ImageFilter.MaxFilter(7))
        connected = expanded


def _dominant_non_light_color(image: Image.Image) -> tuple[int, int, int]:
    sample_w = min(500, image.width)
    sample_h = round(sample_w * image.height / image.width)
    small = image.resize((sample_w, sample_h), Image.Resampling.BOX)
    arr = np.asarray(small.convert("RGB"), dtype=np.uint8)
    channel_min = arr.min(axis=2)
    channel_delta = arr.max(axis=2) - channel_min
    keep = ~((channel_min >= 204) & (channel_delta <= 42))
    pixels = arr[keep]
    if pixels.size == 0:
        return (25, 28, 34)
    brightness = pixels.astype(np.uint16).sum(axis=1)
    chosen = pixels[np.argsort(brightness)[len(pixels) // 3]]
    return tuple(int(value) for value in chosen)


def _analysis_size(size: tuple[int, int], *, max_width: int) -> tuple[int, int]:
    width, height = size
    if width <= max_width:
        return size
    return max_width, round(max_width * height / width)


def build_art_master(
    *,
    source_path: Path,
    spec_path: Path,
    output_path: Path,
    fit_mode: str = "cover",
    auto_trim_mockup_margin: bool = False,
    cover_edge_leaks: bool = False,
    preview_path: Path | None = None,
    preview_max_width: int = 2400,
    watermark: str = "",
    canvas_px: dict[str, int] | None = None,
) -> dict[str, Any]:
    spec = load_die_spec(spec_path)
    original = Image.open(source_path).convert("RGB")
    source = original
    margin_trim: dict[str, Any] | None = None
    if auto_trim_mockup_margin:
        source, margin_trim = trim_generated_mockup_margin(original)
    target_canvas = canvas_px or spec["canvas_px"]
    master = fit_image_to_canvas(source, target_canvas, mode=fit_mode)
    edge_leak_repair: dict[str, Any] | None = None
    if cover_edge_leaks:
        master, edge_leak_repair = cover_light_edge_leaks(master)

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
        "aspect_ratio": round(master.width / master.height, 4),
    }
    if margin_trim:
        result["margin_trim"] = margin_trim
    if edge_leak_repair:
        result["edge_leak_repair"] = edge_leak_repair

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
