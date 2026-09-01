"""End-to-end AI artwork pilot: generate image, master, CMYK and PDF."""

from __future__ import annotations

import json
import logging
import threading
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from app.ai.box_designer import build_box_prompt
from app.ai.providers import image_generation
from app.config import settings
from app.print_specs.art_master import build_art_master, save_approval_preview
from app.print_specs.color import convert_master_to_cmyk
from app.print_specs.layout_template import design_canvas_px, rotate_design_to_print, rotate_print_to_design
from app.print_specs.panel_treatment import blank_design_panel
from app.print_specs.preflight import (
    build_die_generation_guide,
    build_preflight_overlay,
    build_safety_overlay,
    load_die_spec,
)
from app.print_specs.production_pdf import build_cmyk_artwork_pdf, write_pdf_metadata
from app.print_specs.safe_composer import compose_safe_critical_content
from app.services.ai_job_control import AIJobCancelled
from app.services.logo_service import prepare_logo

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_ASPECT_RATIOS = (
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
    "1:8",
    "8:1",
    "1:4",
    "4:1",
)


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def load_references(paths: list[Path]) -> list[tuple[bytes, str]]:
    return [_reference_bytes_for_generation(path) for path in paths]


def _reference_bytes_for_generation(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    media_type = _media_type(path)
    try:
        image = Image.open(BytesIO(data))
    except Exception:
        return data, media_type

    if image.mode in {"RGBA", "LA"} or ("transparency" in image.info):
        rgba = _trim_transparent_reference_margins(image.convert("RGBA"))
        out = BytesIO()
        rgba.save(out, "PNG")
        return out.getvalue(), "image/png"

    trimmed = _trim_light_reference_margins(image)
    if trimmed.size != image.size:
        out = BytesIO()
        trimmed.save(out, "PNG")
        return out.getvalue(), "image/png"

    return data, media_type


def _trim_transparent_reference_margins(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return image
    left, top, right, bottom = bbox
    crop_w = right - left
    crop_h = bottom - top
    if crop_w >= image.width * 0.96 and crop_h >= image.height * 0.96:
        return image
    pad = max(4, round(max(crop_w, crop_h) * 0.06))
    return image.crop((
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad),
        min(image.height, bottom + pad),
    ))


def _trim_light_reference_margins(image: Image.Image) -> Image.Image:
    """Crop white logo margins so the image model sees the symbol, not the empty canvas."""
    rgb = image.convert("RGB")
    if rgb.width < 32 or rgb.height < 32:
        return rgb

    # Logo files commonly arrive as a small mark centered on a white canvas.
    # Photos/background references usually fill the whole image, so their bbox stays unchanged.
    mask = rgb.convert("L").point(lambda px: 255 if px < 245 else 0)
    bbox = mask.getbbox()
    if not bbox:
        return rgb

    left, top, right, bottom = bbox
    crop_w = right - left
    crop_h = bottom - top
    if crop_w >= rgb.width * 0.92 and crop_h >= rgb.height * 0.92:
        return rgb
    if crop_w * crop_h < rgb.width * rgb.height * 0.015:
        return rgb

    pad = max(8, round(max(crop_w, crop_h) * 0.08))
    return rgb.crop((
        max(0, left - pad),
        max(0, top - pad),
        min(rgb.width, right + pad),
        min(rgb.height, bottom + pad),
    ))


def die_aspect_ratio(spec: dict[str, Any]) -> str:
    canvas = design_canvas_px(spec)
    return f"{int(canvas['width'])}:{int(canvas['height'])}"


def _ratio_value(ratio: str) -> float:
    left, right = ratio.split(":", 1)
    return float(left) / float(right)


def provider_aspect_ratio_for_die(spec: dict[str, Any]) -> str:
    canvas = design_canvas_px(spec)
    exact = int(canvas["width"]) / int(canvas["height"])
    return min(SUPPORTED_IMAGE_ASPECT_RATIOS, key=lambda ratio: abs(_ratio_value(ratio) - exact))


def _save_print_master_from_design(*, design_master_path: Path, spec: dict[str, Any], output_path: Path) -> Path:
    image = Image.open(design_master_path).convert("RGB")
    rotated = rotate_design_to_print(image, spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rotated.save(output_path, "PNG", compress_level=1)
    return output_path


def _save_design_preview_from_print(*, print_preview_path: Path, spec: dict[str, Any], output_path: Path) -> Path:
    image = Image.open(print_preview_path).convert("RGB")
    rotated = rotate_print_to_design(image, spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        rotated.save(output_path, "JPEG", quality=92)
    else:
        rotated.save(output_path)
    return output_path


def _prepared_logo_overlay_path(source_path: Path, output_root: Path, job_id: str) -> Path:
    dest = output_root / f"{job_id}_logo_overlay.png"
    try:
        return prepare_logo(source_path.read_bytes(), dest)
    except Exception:
        logger.exception("Falha ao preparar logo para overlay; usando asset original")
        return source_path


def prepare_generation_references(
    *,
    job_id: str,
    die_pdf_path: Path,
    spec_path: Path,
    client_reference_paths: list[Path],
    include_die_guide: bool = False,
    temp_root: Path | None = None,
) -> tuple[list[Path], Path | None, str | None]:
    if not include_die_guide:
        return client_reference_paths, None, None

    temp_root = temp_root or settings.temp_dir
    guide_path = temp_root / "ai_pilot_guides" / f"{job_id}_die_guide.png"
    try:
        guide_path.parent.mkdir(parents=True, exist_ok=True)
        build_die_generation_guide(
            die_pdf_path=die_pdf_path,
            spec_path=spec_path,
            output_path=guide_path,
        )
    except Exception as e:
        logger.warning("Nao foi possivel gerar guia tecnico da faca para IA: %s", e)
        return client_reference_paths, None, str(e)

    return [guide_path, *client_reference_paths], guide_path, None


def save_generated_image(image_bytes: bytes, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Normalize provider output so downstream tooling always consumes PNG/RGB.
    Image.open(__import__("io").BytesIO(image_bytes)).convert("RGB").save(output_path, "PNG")
    return output_path


def run_ai_art_pipeline(
    *,
    job_id: str,
    spec_path: Path,
    die_pdf_path: Path,
    client: dict[str, Any],
    template: dict[str, Any],
    edit_data: dict[str, Any],
    reference_paths: list[Path] | None = None,
    output_root: Path | None = None,
    pdf_output_dir: Path | None = None,
    fit_mode: str = "cover",
    tac_max: int = 300,
    include_die_guide_reference: bool = False,
    empty_back_panel: bool = False,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    def check_cancelled() -> None:
        if cancel_event and cancel_event.is_set():
            raise AIJobCancelled("Geracao cancelada pelo usuario.")

    spec = load_die_spec(spec_path)
    output_root = output_root or settings.art_masters_dir
    pdf_output_dir = pdf_output_dir or Path("output/pdf")
    client_reference_paths = reference_paths or []

    generation_references, die_guide_path, die_guide_error = prepare_generation_references(
        job_id=job_id,
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        client_reference_paths=client_reference_paths,
        include_die_guide=include_die_guide_reference,
    )
    die_ratio = die_aspect_ratio(spec)
    generation_aspect_ratio = provider_aspect_ratio_for_die(spec)
    prompt = build_box_prompt(
        client,
        template,
        {**edit_data, "empty_back_panel": empty_back_panel},
        die_spec=spec,
        has_die_guide=die_guide_path is not None,
        has_client_references=bool(client_reference_paths),
        critical_content_by_code=True,
    )
    generated_path = output_root / f"{job_id}_ai_generated.png"
    generated_preview_path = output_root / f"{job_id}_ai_preview.jpg"
    raw_master_path = output_root / f"{job_id}_master_raw.png"
    master_path = output_root / f"{job_id}_master.png"
    print_master_path = output_root / f"{job_id}_master_print.png"
    preview_path = output_root / f"{job_id}_preview.jpg"
    preflight_path = Path("tmp/preflight") / f"{job_id}_overlay.jpg"
    preflight_print_path = Path("tmp/preflight") / f"{job_id}_overlay_print.jpg"
    safety_path = Path("tmp/preflight") / f"{job_id}_safety.jpg"
    safety_print_path = Path("tmp/preflight") / f"{job_id}_safety_print.jpg"
    preflight_path.parent.mkdir(parents=True, exist_ok=True)
    cmyk_path = output_root / f"{job_id}_master_cmyk.tif"
    proof_path = output_root / f"{job_id}_cmyk_proof.jpg"
    pdf_path = pdf_output_dir / f"{job_id}_arte_cmyk.pdf"

    image_bytes = image_generation(
        prompt,
        references=load_references(generation_references),
        aspect_ratio=generation_aspect_ratio,
        image_size=settings.gemini_image_size,
        mime_type=settings.gemini_image_mime_type,
    )
    check_cancelled()
    save_generated_image(image_bytes, generated_path)
    save_approval_preview(Image.open(generated_path), generated_preview_path, max_width=2400)

    master_result = build_art_master(
        source_path=generated_path,
        spec_path=spec_path,
        output_path=raw_master_path,
        fit_mode=fit_mode,
        auto_trim_mockup_margin=True,
        cover_edge_leaks=True,
        canvas_px=design_canvas_px(spec),
    )
    check_cancelled()
    back_panel_result = None
    if empty_back_panel:
        back_panel_result = blank_design_panel(
            image_path=raw_master_path,
            output_path=raw_master_path,
            panel_name="bottom_panel",
        )
        check_cancelled()

    composition_edit_data = dict(edit_data)
    if client_reference_paths and not composition_edit_data.get("logo_path"):
        composition_edit_data["logo_path"] = str(
            _prepared_logo_overlay_path(client_reference_paths[0], output_root, job_id)
        )

    composition_result = compose_safe_critical_content(
        art_path=raw_master_path,
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        output_path=master_path,
        client=client,
        edit_data=composition_edit_data,
    )
    check_cancelled()
    save_approval_preview(Image.open(master_path), preview_path, max_width=2400)
    _save_print_master_from_design(
        design_master_path=master_path,
        spec=spec,
        output_path=print_master_path,
    )
    master_result.update({
        "raw_master": str(raw_master_path),
        "master": str(master_path),
        "print_master": str(print_master_path),
        "approval_preview": str(preview_path),
        "safe_composition": composition_result,
        "empty_back_panel": empty_back_panel,
        "back_panel_treatment": back_panel_result,
    })
    build_preflight_overlay(
        art_path=print_master_path,
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        output_path=preflight_print_path,
        max_width=2400,
        fit_mode="stretch",
    )
    _save_design_preview_from_print(
        print_preview_path=preflight_print_path,
        spec=spec,
        output_path=preflight_path,
    )
    check_cancelled()
    build_safety_overlay(
        art_path=print_master_path,
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        output_path=safety_print_path,
        max_width=2400,
        fit_mode="stretch",
    )
    _save_design_preview_from_print(
        print_preview_path=safety_print_path,
        spec=spec,
        output_path=safety_path,
    )
    check_cancelled()
    cmyk_result = convert_master_to_cmyk(
        master_path=print_master_path,
        output_path=cmyk_path,
        dpi=spec["dpi"],
        tac_max=tac_max,
        proof_path=proof_path,
    )
    check_cancelled()
    pdf_result = build_cmyk_artwork_pdf(
        cmyk_path=cmyk_path,
        spec_path=spec_path,
        output_path=pdf_path,
    )
    write_pdf_metadata(pdf_result, pdf_path)

    result = {
        "job_id": job_id,
        "model": settings.gemini_image_model,
        "image_size": settings.gemini_image_size,
        "die_aspect_ratio": die_ratio,
        "aspect_ratio_requested": generation_aspect_ratio,
        "prompt": prompt,
        "technical_reference": str(die_guide_path) if die_guide_path else None,
        "technical_reference_error": die_guide_error,
        "references": [str(path) for path in client_reference_paths],
        "generation_references": [str(path) for path in generation_references],
        "generated": str(generated_path),
        "generated_preview": str(generated_preview_path),
        "master": master_result,
        "preflight": str(preflight_path),
        "preflight_print": str(preflight_print_path),
        "safety": str(safety_path),
        "safety_print": str(safety_print_path),
        "cmyk": cmyk_result,
        "pdf": pdf_result,
        "empty_back_panel": empty_back_panel,
    }
    metadata = output_root / f"{job_id}_pipeline.json"
    metadata.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["metadata"] = str(metadata)
    return result
