"""Business logic for the order lifecycle."""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from PIL import Image

from app.ai.box_designer import build_box_prompt
from app.ai.providers import image_generation
from app.config import settings
from app.db import repositories as repo
from app.models.commands import (
    CatalogItem,
    ClientResponse,
    EditableFieldInfo,
    EditCommand,
    OrderResponse,
    OrderStatus,
    RevisionResponse,
    TemaFundo,
)
from app.psd.engine import PsdEngine, _retry_native
from app.psd.flat_engine import FlatEngine, find_flat_image
from app.psd.renderer import generate_preview


SAMPLE_EDIT_DATA = {
    "telefone": "(11) 99999-9999",
    "instagram": "@suapizzaria",
    "frase": "Sua Pizza Chegou!",
    "adicionar_selo_entrega": True,
}


def render_sample_preview(template_path: Path, calibration: dict | None,
                          dest_path: Path, template: dict | None = None) -> Path:
    """Render a preview of a template with fixed sample data, without touching any order.

    Used by the calibration UI so the designer sees how real content lands on the artwork
    with the geometry being edited. `calibration` may be the in-progress (unsaved) layout.

    When a flat image is available for the template, it is used instead of the PSD.
    """
    cmd = build_edit_command({**SAMPLE_EDIT_DATA, "logo_path": str(_sample_logo())})

    # Try flat engine first
    if template:
        tema = cmd.tema_fundo
        flat_path = find_flat_image(template, tema)
        if flat_path is not None:
            from app.psd.flat_engine import FlatEngine
            engine = FlatEngine(flat_path)
            engine.apply(cmd, calibration=calibration or {})
            engine.render(dest_path)
            return dest_path

    # Fallback to PSD engine
    out_psd = settings.temp_dir / f"{dest_path.stem}.psd"

    def _render():
        engine = PsdEngine(template_path)
        engine.apply(cmd, calibration=calibration or {})
        engine.save(out_psd)
        generate_preview(out_psd, dest_path)

    _retry_native(_render, what="gerar preview de exemplo")
    return dest_path


def _sample_logo() -> Path:
    """A placeholder logo (in an allowed upload dir) used only for sample previews."""
    from PIL import Image, ImageDraw

    path = settings.temp_dir / "sample_logo.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([20, 20, 380, 380], fill=(214, 40, 40, 255))
        draw.text((150, 185), "SUA LOGO", fill=(255, 255, 255, 255))
        img.save(path)
    return path


def build_edit_command(edit_data: dict) -> EditCommand:
    """Convert a JSON dict from the database into a typed EditCommand."""
    tema = edit_data.get("tema_fundo")
    if tema and not isinstance(tema, TemaFundo):
        tema = TemaFundo(tema)

    return EditCommand(
        telefone=edit_data.get("telefone"),
        instagram=edit_data.get("instagram"),
        frase=edit_data.get("frase"),
        tema_fundo=tema,
        adicionar_selo_entrega=edit_data.get("adicionar_selo_entrega", False),
        adicionar_forno_lenha=edit_data.get("adicionar_forno_lenha", False),
        logo_path=edit_data.get("logo_path"),
    )


def generate_order_preview(order_id: int, db: Session) -> tuple[dict, list[str]]:
    """Generate or regenerate the preview for an order.

    Uses the flat engine (image + calibration) when available, falling back to the
    PSD engine for legacy templates. Returns (updated order dict, list of changes applied).
    """
    order = repo.order_get(db, order_id)
    template = repo.template_get(db, order["template_id"])

    # Remember the current intermediate PSD so we can remove it after the new one is ready.
    # The preview JPG is kept — it's still referenced by the order's revision history.
    prev_output_psd = order.get("output_psd")

    job_id = uuid.uuid4().hex[:12]
    output_psd = settings.output_dir / f"order_{order_id}_{job_id}.psd"
    preview_jpg = settings.preview_dir / f"order_{order_id}_{job_id}.jpg"

    cmd = build_edit_command(order["edit_data"])
    calibration = template.get("calibration")

    # --- Flat engine path (fast, no PSD overhead) ---
    tema = cmd.tema_fundo
    flat_path = find_flat_image(template, tema)
    if flat_path is not None:
        changes = _render_flat(flat_path, cmd, calibration, preview_jpg)
        preview_source = "flat"
        # Flat engine produces only a JPG — no intermediate PSD.
        repo.order_set_paths(db, order_id, preview_jpg=str(preview_jpg))
        # Clear output_psd since we're not producing one in flat mode.
        if prev_output_psd:
            try:
                Path(prev_output_psd).unlink(missing_ok=True)
            except OSError:
                pass
            repo.order_set_paths(db, order_id, output_psd=None)
    else:
        # --- Legacy PSD engine path ---
        changes = _render_psd(template, cmd, calibration, output_psd, preview_jpg, order_id)
        preview_source = "psd"
        repo.order_set_paths(db, order_id,
                             output_psd=str(output_psd),
                             preview_jpg=str(preview_jpg))

    repo.order_update_status(db, order_id, OrderStatus.preview_sent.value)

    rev_num = repo.revision_count(db, order_id) + 1
    repo.revision_create(db, order_id, rev_num, order["edit_data"], str(preview_jpg),
                         preview_source=preview_source)

    # Remove the now-superseded intermediate PSD (can be large: 10-50 MB per revision).
    # Done after the DB commit so a failure here never corrupts order state.
    if prev_output_psd:
        try:
            Path(prev_output_psd).unlink(missing_ok=True)
        except OSError:
            pass

    return repo.order_get(db, order_id), changes


def _render_flat(flat_path: Path, cmd: EditCommand, calibration: dict | None,
                  preview_jpg: Path) -> list[str]:
    """Render preview using the flat image engine."""
    from app.psd.flat_engine import FlatEngine

    engine = FlatEngine(flat_path)
    engine.apply(cmd, calibration=calibration or {})
    engine.render(preview_jpg)
    return [f"Preview gerado via imagem plana ({flat_path.name})"]


def _render_psd(template: dict, cmd: EditCommand, calibration: dict | None,
                 output_psd: Path, preview_jpg: Path, order_id: int) -> list[str]:
    """Render preview using the legacy PSD engine."""
    template_path = settings.templates_dir / template["filename"]

    def _render() -> list[str]:
        engine = PsdEngine(template_path)
        applied = engine.apply(cmd, calibration=calibration)
        applied += engine.unsupported_layers()
        applied += engine.font_warnings()
        engine.save(output_psd)
        generate_preview(output_psd, preview_jpg)
        return applied

    return _retry_native(_render, what=f"gerar preview do pedido {order_id}")


def _load_ai_reference() -> tuple[bytes, str] | None:
    """Optional layout-guide image for AI previews (settings.ai_preview_reference)."""
    ref = settings.ai_preview_reference
    if not ref:
        return None
    path = Path(ref)
    if not path.exists():
        return None
    media = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return path.read_bytes(), media


def generate_ai_preview(order_id: int, db: Session) -> tuple[dict, list[str]]:
    """Generate the client-approval preview with the Gemini image model (Nano Banana).

    This is the mockup the client approves over WhatsApp — a polished RGB image, NOT a print
    file. The CMYK/die-cut production file is still produced from a gabarito after approval.
    Returns (updated order dict, notes).

    Cost controls applied:
    - If the same order+edit_data was already generated within the cache TTL, the cached
      preview is returned without calling the API.
    - A hard rate limit caps the number of revisions per order within a rolling window.
    """
    from app.services.ai_cost_guard import (
        AIRateLimitExceeded,
        check_rate_limit,
        find_cached_preview,
    )

    order = repo.order_get(db, order_id)
    client = repo.client_get(db, order["client_id"])
    template = repo.template_get(db, order["template_id"])

    # 1. Check rate limit before doing any work.
    check_rate_limit(db, order_id)

    # 2. Check cache — return existing preview if inputs haven't changed.
    cached = find_cached_preview(
        db, order_id, order["edit_data"],
        order["template_id"], order["client_id"],
    )
    if cached:
        repo.order_set_paths(db, order_id, preview_jpg=cached)
        repo.order_update_status(db, order_id, OrderStatus.preview_sent.value)
        notes = ["Preview obtido do cache (mesmos parametros)"]
        return repo.order_get(db, order_id), notes

    # 3. Cache miss — call the AI image generation API (paid).
    prompt = build_box_prompt(client, template, order["edit_data"])
    img_bytes = image_generation(prompt, reference=_load_ai_reference())

    job_id = uuid.uuid4().hex[:12]
    preview_jpg = settings.preview_dir / f"order_{order_id}_ai_{job_id}.jpg"
    preview_jpg.parent.mkdir(parents=True, exist_ok=True)
    Image.open(BytesIO(img_bytes)).convert("RGB").save(
        str(preview_jpg), "JPEG", quality=settings.preview_quality)

    prev_preview = order.get("preview_jpg")
    repo.order_set_paths(db, order_id, preview_jpg=str(preview_jpg))
    repo.order_update_status(db, order_id, OrderStatus.preview_sent.value)

    rev_num = repo.revision_count(db, order_id) + 1
    repo.revision_create(db, order_id, rev_num, order["edit_data"], str(preview_jpg),
                         preview_source="ai")

    # The AI preview replaces the previous one; the JPG isn't a production artifact so it's
    # safe to drop once superseded (revision history keeps the path record).
    if prev_preview and prev_preview != str(preview_jpg):
        try:
            Path(prev_preview).unlink(missing_ok=True)
        except OSError:
            pass

    return repo.order_get(db, order_id), [f"Preview gerado por IA ({settings.gemini_image_model})"]


def approve_order(order_id: int, db: Session) -> tuple[dict, list[str]]:
    """Approve an order and generate the CMYK production file + designer package.

    Returns (updated order dict, warnings) where warnings lists any layers dropped from the
    production file (unsupported types).
    """
    order = repo.order_get(db, order_id)
    template = repo.template_get(db, order["template_id"])
    from app.services.crm_service import record_order_status_change
    record_order_status_change(
        db,
        order_id=order_id,
        client_id=order["client_id"],
        from_status=order["status"],
        to_status=OrderStatus.approved.value,
        source="system",
    )

    # Generate the production package (designer deliverable).
    from app.services.production_package import build_production_package
    package_path = build_production_package(order, template, order.get("preview_jpg"))

    # Generate CMYK file only if we have an output PSD (PSD engine path).
    dropped: list[str] = []
    if order.get("output_psd"):
        rgb_path = Path(order["output_psd"])
        cmyk_path = settings.output_dir / f"order_{order_id}_cmyk.psd"

        def _to_cmyk() -> list[str]:
            return PsdEngine(rgb_path).save_as_cmyk(cmyk_path, source_psd=rgb_path)

        dropped = _retry_native(_to_cmyk, what=f"gerar CMYK do pedido {order_id}")
        repo.order_set_paths(db, order_id, cmyk_psd=str(cmyk_path))

    repo.order_update_status(db, order_id, OrderStatus.production.value)

    if package_path:
        dropped.append(f"Pacote de producao gerado: {package_path.name}")

    return repo.order_get(db, order_id), dropped


def _has_package(order_id: int) -> bool:
    """Check if a production package zip exists for the given order."""
    from app.services.production_package import get_package_path
    return get_package_path(order_id) is not None


def build_order_response(order: dict, db: Session,
                         changes: list[str] | None = None) -> OrderResponse:
    """Convert a raw order dict + related data into an OrderResponse."""
    client_row = repo.client_get(db, order["client_id"])
    template_row = repo.template_get(db, order["template_id"])
    revisions = repo.revision_list(db, order["id"])

    client = ClientResponse(**client_row)
    template = CatalogItem(
        id=template_row["id"],
        display_name=template_row["display_name"],
        description=template_row.get("description"),
        size_cm=template_row.get("size_cm"),
        product_type=template_row["product_type"],
        thumbnail_url=f"/api/catalog/{template_row['id']}/thumbnail",
        editable_fields=[EditableFieldInfo(**f) for f in template_row["editable_fields"]],
    )

    rev_responses = [
        RevisionResponse(
            id=r["id"],
            revision_number=r["revision_number"],
            edit_data=r["edit_data"],
            preview_url=f"/api/orders/{order['id']}/revisions/{r['revision_number']}/preview"
            if r.get("preview_jpg") else None,
            feedback=r.get("feedback"),
            created_at=r["created_at"],
        )
        for r in revisions
    ]

    return OrderResponse(
        id=order["id"],
        client=client,
        template=template,
        status=OrderStatus(order["status"]),
        quantidade=order.get("quantidade"),
        edit_data=order["edit_data"],
        preview_url=f"/api/orders/{order['id']}/preview" if order.get("preview_jpg") else None,
        cmyk_url=f"/api/orders/{order['id']}/production" if order.get("cmyk_psd") else None,
        package_url=f"/api/orders/{order['id']}/package" if _has_package(order["id"]) else None,
        created_at=order["created_at"],
        updated_at=order["updated_at"],
        revisions=rev_responses,
        changes_applied=changes or [],
    )
