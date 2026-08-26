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
from app.print_specs.preflight import (
    build_die_generation_guide,
    build_preflight_overlay,
    build_safety_overlay,
    load_die_spec,
)
from app.print_specs.production_pdf import build_cmyk_artwork_pdf, write_pdf_metadata
from app.print_specs.safe_composer import compose_safe_critical_content
from app.services.ai_job_control import AIJobCancelled

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
        rgba = image.convert("RGBA")
        flattened = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        flattened.alpha_composite(rgba)
        out = BytesIO()
        flattened.convert("RGB").save(out, "PNG")
        return out.getvalue(), "image/png"

    return data, media_type


def die_aspect_ratio(spec: dict[str, Any]) -> str:
    canvas = spec["canvas_px"]
    return f"{int(canvas['width'])}:{int(canvas['height'])}"


def _ratio_value(ratio: str) -> float:
    left, right = ratio.split(":", 1)
    return float(left) / float(right)


def provider_aspect_ratio_for_die(spec: dict[str, Any]) -> str:
    exact = int(spec["canvas_px"]["width"]) / int(spec["canvas_px"]["height"])
    return min(SUPPORTED_IMAGE_ASPECT_RATIOS, key=lambda ratio: abs(_ratio_value(ratio) - exact))


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
        edit_data,
        die_spec=spec,
        has_die_guide=die_guide_path is not None,
        has_client_references=bool(client_reference_paths),
        critical_content_by_code=True,
    )
    generated_path = output_root / f"{job_id}_ai_generated.png"
    generated_preview_path = output_root / f"{job_id}_ai_preview.jpg"
    raw_master_path = output_root / f"{job_id}_master_raw.png"
    master_path = output_root / f"{job_id}_master.png"
    preview_path = output_root / f"{job_id}_preview.jpg"
    preflight_path = Path("tmp/preflight") / f"{job_id}_overlay.jpg"
    safety_path = Path("tmp/preflight") / f"{job_id}_safety.jpg"
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
    )
    check_cancelled()
    composition_edit_data = dict(edit_data)
    if client_reference_paths and not composition_edit_data.get("logo_path"):
        composition_edit_data["logo_path"] = str(client_reference_paths[0])

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
    master_result.update({
        "raw_master": str(raw_master_path),
        "master": str(master_path),
        "approval_preview": str(preview_path),
        "safe_composition": composition_result,
    })
    build_preflight_overlay(
        art_path=master_path,
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        output_path=preflight_path,
        max_width=2400,
        fit_mode="stretch",
    )
    check_cancelled()
    build_safety_overlay(
        art_path=master_path,
        die_pdf_path=die_pdf_path,
        spec_path=spec_path,
        output_path=safety_path,
        max_width=2400,
        fit_mode="stretch",
    )
    check_cancelled()
    cmyk_result = convert_master_to_cmyk(
        master_path=master_path,
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
        "safety": str(safety_path),
        "cmyk": cmyk_result,
        "pdf": pdf_result,
    }
    metadata = output_root / f"{job_id}_pipeline.json"
    metadata.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["metadata"] = str(metadata)
    return result
