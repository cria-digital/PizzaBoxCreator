"""Web views: HTML pages served by Jinja2 templates."""

from __future__ import annotations

import html
import re
import json
import logging
import shutil
import uuid
from pathlib import Path

import hmac
from urllib.parse import quote

from fastapi import APIRouter, Request, Form, UploadFile, File, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile as FormUploadFile

from app.ai.vision import analyze_box_photo, VisionUnavailable
from app.config import settings
from app.db.session import get_db
from app.db.models import Order, Client, Template, OrderRevision
from app.db import repositories as repo
from app.psd.calibration import read_template_geometry, merge_geometry
from app.psd.fields import build_editable_fields
from app.psd.gabarito_builder import build_editable_gabarito, is_editable_gabarito
from app.psd.renderer import generate_preview
from app.services.admin_account import get_effective_username, save_account, verify_login
from app.services.logo_service import prepare_logo
from app.ai.providers import AIUnavailable
from app.services.order_service import (
    approve_order,
    generate_ai_preview,
    generate_order_preview,
    render_sample_preview,
)
from app.print_specs.ai_art_pipeline import run_ai_art_pipeline
from app.print_specs.pilot_config import pilot_die_pdf_path, pilot_spec_path
from app.services.ai_job_control import AIJobCancelled, cancel_job, finish_job, register_job
from app.services.whatsapp_service import send_preview_to_whatsapp
from app.services.whatsapp_config import apply_whatsapp_config, mask_secret, merge_blank_with_existing
from app.web.auth import (
    require_login, create_session, clear_session, get_current_user,
    is_locked_out, record_failed_login, clear_failed_logins,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth routes (no login required)
# ---------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {
        "request": request, "error": None, "next_url": next,
    })


@router.post("/login")
def login_submit(request: Request, username: str = Form(...),
                 password: str = Form(...), next: str = Form("/"),
                 db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"

    if is_locked_out(client_ip):
        return templates.TemplateResponse(request, "login.html", {
            "request": request,
            "error": "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
            "next_url": next,
        }, status_code=429)

    valid = verify_login(db, username, password)

    if valid:
        clear_failed_logins(client_ip)
        response = RedirectResponse(next, status_code=303)
        create_session(response, username)
        return response

    record_failed_login(client_ip)
    return templates.TemplateResponse(request, "login.html", {
        "request": request, "error": "Usuario ou senha incorretos", "next_url": next,
    }, status_code=401)


@router.get("/logout")
def logout(request: Request):
    response = RedirectResponse("/login", status_code=303)
    clear_session(response)
    return response

STATUS_LABELS = {
    "draft": "Rascunho",
    "preview_sent": "Preview Enviado",
    "revision": "Em Revisao",
    "approved": "Aprovado",
    "production": "Producao",
    "delivered": "Entregue",
}

STATUS_COLORS = {
    "draft": "secondary",
    "preview_sent": "info",
    "revision": "warning",
    "approved": "primary",
    "production": "primary",
    "delivered": "success",
}

ALL_STATUSES = ["draft", "preview_sent", "revision", "production", "delivered"]


def _auth(request: Request) -> RedirectResponse | None:
    """Check auth. Returns redirect to login if not authenticated."""
    return require_login(request)


def _base_ctx(request: Request, active_page: str = "") -> dict:
    return {
        "request": request,
        "active_page": active_page,
        "user": get_current_user(request),
        "status_labels": STATUS_LABELS,
        "status_colors": STATUS_COLORS,
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    orders_by_status = {}
    for status, cnt in db.execute(
        select(Order.status, func.count()).group_by(Order.status)
    ).all():
        orders_by_status[status.value] = cnt

    total_orders = db.scalar(select(func.count()).select_from(Order))
    total_clients = db.scalar(select(func.count()).select_from(Client))
    total_templates = db.scalar(
        select(func.count()).select_from(Template).where(Template.active == True)  # noqa: E712
    )

    recent_orders = []
    for row in db.execute(
        select(
            Order.id, Order.status, Order.created_at, Order.updated_at,
            Client.name.label("client_name"),
            Template.display_name.label("template_name"),
        )
        .join(Client, Order.client_id == Client.id)
        .join(Template, Order.template_id == Template.id)
        .order_by(Order.updated_at.desc())
        .limit(10)
    ).all():
        recent_orders.append({
            "id": row.id,
            "status": row.status.value if row.status else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "client_name": row.client_name,
            "template_name": row.template_name,
        })

    disk = shutil.disk_usage(str(settings.output_dir.resolve()))

    def dir_size_mb(p: Path) -> float:
        if not p.exists():
            return 0.0
        return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / (1024 * 1024), 1)

    stats = {
        "orders_by_status": orders_by_status,
        "total_orders": total_orders,
        "total_clients": total_clients,
        "total_templates": total_templates,
        "recent_orders": recent_orders,
        "disk_usage": {
            "total_gb": round(disk.total / (1024 ** 3), 1),
            "used_gb": round(disk.used / (1024 ** 3), 1),
            "free_gb": round(disk.free / (1024 ** 3), 1),
            "percent_used": round(disk.used / disk.total * 100, 1),
            "storage_breakdown": {
                "output_psd_mb": dir_size_mb(settings.output_dir),
                "preview_jpg_mb": dir_size_mb(settings.preview_dir),
                "templates_mb": dir_size_mb(settings.templates_dir),
                "thumbnails_mb": dir_size_mb(settings.thumbnails_dir),
                "temp_mb": dir_size_mb(settings.temp_dir),
            },
        },
    }

    ctx = _base_ctx(request, "dashboard")
    ctx["stats"] = stats
    return templates.TemplateResponse(request, "dashboard.html", ctx)


# ---------------------------------------------------------------------------
# Funnel (Kanban)
# ---------------------------------------------------------------------------

@router.get("/funil", response_class=HTMLResponse)
def funnel(request: Request, client_id: int | None = None, db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    stmt = (
        select(Order, Client.name.label("client_name"), Template.display_name.label("template_name"))
        .join(Client, Order.client_id == Client.id)
        .join(Template, Order.template_id == Template.id)
    )
    if client_id:
        stmt = stmt.where(Order.client_id == client_id)
    stmt = stmt.order_by(Order.updated_at.desc())

    rows = db.execute(stmt).all()

    orders_by_status: dict[str, list] = {s: [] for s in ALL_STATUSES}
    for order, client_name, template_name in rows:
        d = {
            "id": order.id,
            "client_id": order.client_id,
            "template_id": order.template_id,
            "status": order.status.value if order.status else None,
            "quantidade": order.quantidade,
            "edit_data": order.edit_data or {},
            "output_psd": order.output_psd,
            "preview_jpg": order.preview_jpg,
            "cmyk_psd": order.cmyk_psd,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "client_name": client_name,
            "template_name": template_name,
        }
        status = d["status"]
        if status == "approved":
            status = "production"
        if status in orders_by_status:
            orders_by_status[status].append(d)

    ctx = _base_ctx(request, "funnel")
    ctx["orders_by_status"] = orders_by_status
    return templates.TemplateResponse(request, "funnel.html", ctx)


# ---------------------------------------------------------------------------
# Create order (must be before /pedidos/{order_id} to avoid route conflict)
# ---------------------------------------------------------------------------

@router.get("/pedidos/novo", response_class=HTMLResponse)
def order_create_page(request: Request, client_phone: str | None = None,
                      template_id: int | None = None, db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    tpl_list = repo.template_list_active(db)

    client_found = None
    if client_phone:
        client_found = repo.client_get_by_phone(db, client_phone)

    fields = []
    if template_id:
        t = repo.template_get(db, template_id)
        if t:
            fields = t.get("editable_fields", [])

    ctx = _base_ctx(request)
    ctx["templates"] = tpl_list
    ctx["client_found"] = client_found
    ctx["prefill_phone"] = client_phone or ""
    ctx["prefill_name"] = ""
    ctx["selected_template"] = template_id
    ctx["fields"] = fields
    return templates.TemplateResponse(request, "order_create.html", ctx)


@router.post("/pedidos/novo")
async def order_create_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    client_id = form.get("client_id")
    if not client_id:
        phone = form.get("client_phone", "").strip()
        name = form.get("client_name", "").strip()
        instagram = form.get("client_instagram", "").strip() or None
        if not phone:
            return RedirectResponse("/pedidos/novo", status_code=303)

        client = repo.client_get_by_phone(db, phone)
        if client:
            client_id = client["id"]
        elif name:
            client = repo.client_create(db, name, phone, instagram)
            client_id = client["id"]
        else:
            return RedirectResponse("/pedidos/novo", status_code=303)

    template_id = int(form.get("template_id", 0))
    if not template_id:
        return RedirectResponse("/pedidos/novo", status_code=303)

    template = repo.template_get(db, template_id)
    edit_data = {}
    for field in template.get("editable_fields", []):
        key = f"field_{field['name']}"
        val = form.get(key)
        if field["type"] == "toggle":
            edit_data[field["name"]] = val == "true"
        elif field["type"] == "image":
            if isinstance(val, FormUploadFile) and val.filename:
                content = await val.read()
                dest = settings.logos_dir / f"client_{client_id}_{uuid.uuid4().hex[:8]}.png"
                edit_data[field["name"]] = str(prepare_logo(content, dest))
        elif val:
            edit_data[field["name"]] = val

    quantidade_raw = form.get("quantidade", "").strip()
    quantidade = int(quantidade_raw) if quantidade_raw.isdigit() else None

    order = repo.order_create(db, int(client_id), template_id, edit_data, quantidade)

    has_data = any(v for v in edit_data.values() if v and v is not False)
    if has_data:
        try:
            generate_order_preview(order["id"], db)
        except Exception:
            pass

    return RedirectResponse(f"/pedidos/{order['id']}", status_code=303)


_VISION_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_AI_TEST_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
_AI_JOB_ID_PATTERN = re.compile(r"^ai_test_[a-f0-9]{10}$")


def _new_ai_test_job_id() -> str:
    return f"ai_test_{uuid.uuid4().hex[:10]}"


def _normalize_ai_test_job_id(job_id: str | None) -> str:
    if job_id and _AI_JOB_ID_PATTERN.match(job_id):
        return job_id
    return _new_ai_test_job_id()


def _pilot_spec_path() -> Path:
    return pilot_spec_path()


def _pilot_die_pdf_path() -> Path:
    return pilot_die_pdf_path()


def _artifact_url(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if p.parent == settings.art_masters_dir:
        return f"/teste/ia-caixa/arquivo/art/{p.name}"
    if p.parent == Path("output/pdf"):
        return f"/teste/ia-caixa/arquivo/pdf/{p.name}"
    if p.parent == Path("tmp/preflight"):
        return f"/teste/ia-caixa/arquivo/preflight/{p.name}"
    return None


def _ai_test_view_model(result: dict | None) -> dict | None:
    if not result:
        return None
    return {
        "job_id": result.get("job_id"),
        "model": result.get("model"),
        "die_aspect_ratio": result.get("die_aspect_ratio"),
        "aspect_ratio_requested": result.get("aspect_ratio_requested"),
        "generated_url": _artifact_url(result.get("generated")),
        "generated_preview_url": _artifact_url(result.get("generated_preview")),
        "preview_url": _artifact_url(result.get("master", {}).get("approval_preview")),
        "preflight_url": _artifact_url(result.get("preflight")),
        "safety_url": _artifact_url(result.get("safety")),
        "pdf_url": _artifact_url(result.get("pdf", {}).get("pdf")),
        "metadata_url": _artifact_url(result.get("metadata")),
        "technical_reference": result.get("technical_reference"),
        "technical_reference_error": result.get("technical_reference_error"),
        "references": result.get("references", []),
        "generation_references": result.get("generation_references", []),
        "source_px": result.get("master", {}).get("source_px"),
        "canvas_px": result.get("master", {}).get("canvas_px"),
        "margin_trim": result.get("master", {}).get("margin_trim"),
        "edge_leak_repair": result.get("master", {}).get("edge_leak_repair"),
        "tac_after": result.get("cmyk", {}).get("tac_after"),
        "pdf": result.get("pdf", {}),
    }


@router.get("/teste/ia-caixa", response_class=HTMLResponse)
def ai_box_test_page(request: Request):
    if redirect := _auth(request): return redirect

    spec_path = _pilot_spec_path()
    die_pdf_path = _pilot_die_pdf_path()
    ctx = _base_ctx(request, "ai_test")
    ctx.update({
        "spec_path": spec_path,
        "die_pdf_path": die_pdf_path,
        "spec_ok": spec_path.exists(),
        "die_pdf_ok": die_pdf_path.exists(),
        "gemini_ok": bool(settings.gemini_api_key),
        "result": None,
        "error": None,
        "job_id": _new_ai_test_job_id(),
    })
    return templates.TemplateResponse(request, "ai_box_test.html", ctx)


@router.post("/teste/ia-caixa", response_class=HTMLResponse)
async def ai_box_test_generate(
    request: Request,
    brand: str = Form(...),
    phone: str = Form(""),
    instagram: str = Form(""),
    frase: str = Form("Sua pizza chegou!"),
    tema: str = Form("premium"),
    product_type: str = Form("pizza"),
    job_id: str = Form(""),
    reference: UploadFile | None = File(None),
):
    if redirect := _auth(request): return redirect

    spec_path = _pilot_spec_path()
    die_pdf_path = _pilot_die_pdf_path()
    job_id = _normalize_ai_test_job_id(job_id)
    ctx = _base_ctx(request, "ai_test")
    ctx.update({
        "spec_path": spec_path,
        "die_pdf_path": die_pdf_path,
        "spec_ok": spec_path.exists(),
        "die_pdf_ok": die_pdf_path.exists(),
        "gemini_ok": bool(settings.gemini_api_key),
        "result": None,
        "error": None,
        "job_id": _new_ai_test_job_id(),
        "form_values": {
            "brand": brand,
            "phone": phone,
            "instagram": instagram,
            "frase": frase,
            "tema": tema,
            "product_type": product_type,
        },
    })

    if not settings.gemini_api_key:
        ctx["error"] = "GEMINI_API_KEY nao esta configurada."
        return templates.TemplateResponse(request, "ai_box_test.html", ctx, status_code=400)
    if not spec_path.exists():
        ctx["error"] = f"Spec da faca nao encontrado: {spec_path}"
        return templates.TemplateResponse(request, "ai_box_test.html", ctx, status_code=400)
    if not die_pdf_path.exists():
        ctx["error"] = f"PDF da faca nao encontrado: {die_pdf_path}"
        return templates.TemplateResponse(request, "ai_box_test.html", ctx, status_code=400)

    references: list[Path] = []
    if reference and reference.filename:
        if reference.content_type not in _AI_TEST_MEDIA_TYPES:
            ctx["error"] = "Imagem de referencia precisa ser PNG, JPG ou WEBP."
            return templates.TemplateResponse(request, "ai_box_test.html", ctx, status_code=400)
        suffix = Path(reference.filename).suffix.lower()
        dest = settings.temp_dir / "ai_pilot_refs" / f"{job_id}{suffix or '.png'}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await reference.read())
        references.append(dest)

    cancel_event = register_job(job_id)
    try:
        pipeline_result = await run_in_threadpool(
            run_ai_art_pipeline,
            job_id=job_id,
            spec_path=spec_path,
            die_pdf_path=die_pdf_path,
            client={"name": brand.strip(), "phone": phone.strip(), "instagram": instagram.strip()},
            template={"product_type": product_type.strip() or "pizza"},
            edit_data={
                "telefone": phone.strip(),
                "instagram": instagram.strip(),
                "frase": frase.strip(),
                "tema_fundo": tema,
            },
            reference_paths=references,
            fit_mode="cover",
            tac_max=300,
            cancel_event=cancel_event,
        )
    except AIUnavailable as e:
        ctx["error"] = str(e)
        return templates.TemplateResponse(request, "ai_box_test.html", ctx, status_code=503)
    except AIJobCancelled:
        ctx["error"] = "Geracao cancelada."
        return templates.TemplateResponse(request, "ai_box_test.html", ctx)
    except Exception:
        logger.exception("Falha no teste de geracao IA")
        ctx["error"] = "Falha ao gerar a arte. Veja o log do servidor para o detalhe tecnico."
        return templates.TemplateResponse(request, "ai_box_test.html", ctx, status_code=500)
    finally:
        finish_job(job_id)

    ctx["result"] = _ai_test_view_model(pipeline_result)
    return templates.TemplateResponse(request, "ai_box_test.html", ctx)


@router.post("/teste/ia-caixa/cancelar")
async def ai_box_test_cancel(request: Request, job_id: str = Form(...)):
    if redirect := _auth(request): return redirect
    cancelled = cancel_job(job_id)
    return JSONResponse({"cancelled": cancelled, "job_id": job_id})


@router.get("/teste/ia-caixa/arquivo/{kind}/{filename:path}")
def ai_box_test_artifact(request: Request, kind: str, filename: str):
    if redirect := _auth(request): return redirect
    safe_name = Path(filename).name
    roots = {
        "art": settings.art_masters_dir,
        "pdf": Path("output/pdf"),
        "preflight": Path("tmp/preflight"),
    }
    root = roots.get(kind)
    if root is None:
        return Response("Tipo de arquivo invalido", status_code=404)
    path = root / safe_name
    if not path.exists() or not path.is_file():
        return Response("Arquivo nao encontrado", status_code=404)
    return FileResponse(path)


@router.post("/pedidos/analisar-foto")
async def order_analyze_photo(request: Request, foto: UploadFile = File(...),
                              db: Session = Depends(get_db)):
    """AI vision: from a customer's box photo, suggest the closest catalog model and read any
    contact data already printed on it, to pre-fill the new-order form."""
    if redirect := _auth(request): return redirect

    content = await foto.read()
    media_type = foto.content_type if foto.content_type in _VISION_MEDIA_TYPES else "image/jpeg"
    tpl_list = repo.template_list_active(db)
    try:
        result = analyze_box_photo(content, tpl_list, media_type=media_type)
    except VisionUnavailable as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception:
        logger.exception("Falha ao analisar foto da caixa")
        return JSONResponse({"error": "Falha ao analisar a foto"}, status_code=500)

    if result.get("template_id"):
        match = next((t for t in tpl_list if t["id"] == result["template_id"]), None)
        result["template_name"] = match["display_name"] if match else None
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Order detail
# ---------------------------------------------------------------------------

@router.get("/pedidos/{order_id}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: int, wa_error: str | None = None,
                 ai_error: str | None = None, db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    order = repo.order_get(db, order_id)
    if not order:
        return RedirectResponse("/funil")

    client = repo.client_get(db, order["client_id"])
    template = repo.template_get(db, order["template_id"])
    revisions = repo.revision_list(db, order_id)

    ctx = _base_ctx(request)
    ctx["order"] = order
    ctx["client"] = client
    ctx["template"] = template
    ctx["revisions"] = revisions
    ctx["editable_fields"] = template.get("editable_fields", [])
    ctx["whatsapp_enabled"] = settings.whatsapp_enabled
    ctx["wa_error"] = wa_error
    ctx["ai_error"] = ai_error
    return templates.TemplateResponse(request, "order_detail.html", ctx)


@router.post("/pedidos/{order_id}/whatsapp/enviar")
def order_send_whatsapp(order_id: int, db: Session = Depends(get_db)):
    try:
        send_preview_to_whatsapp(db, order_id)
    except ValueError as e:
        return RedirectResponse(
            f"/pedidos/{order_id}?wa_error={quote(str(e))}", status_code=303
        )
    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


@router.post("/pedidos/{order_id}/preview")
def order_generate_preview(order_id: int, db: Session = Depends(get_db)):
    generate_order_preview(order_id, db)
    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


@router.post("/pedidos/{order_id}/ai-preview")
def order_generate_ai_preview(order_id: int, db: Session = Depends(get_db)):
    try:
        generate_ai_preview(order_id, db)
    except AIUnavailable as e:
        return RedirectResponse(
            f"/pedidos/{order_id}?ai_error={quote(str(e))}", status_code=303
        )
    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


@router.post("/pedidos/{order_id}/approve")
def order_approve(order_id: int, db: Session = Depends(get_db)):
    approve_order(order_id, db)
    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


@router.post("/pedidos/{order_id}/reject")
def order_reject(order_id: int, feedback: str = Form(...), db: Session = Depends(get_db)):
    latest = repo.revision_get_latest(db, order_id)
    if latest:
        stmt = (
            select(OrderRevision)
            .where(OrderRevision.id == latest["id"])
        )
        rev = db.scalar(stmt)
        if rev:
            rev.feedback = feedback
            db.commit()
    repo.order_update_status(db, order_id, "revision")
    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


@router.post("/pedidos/{order_id}/deliver")
def order_deliver(order_id: int, db: Session = Depends(get_db)):
    repo.order_update_status(db, order_id, "delivered")
    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


@router.post("/pedidos/{order_id}/update")
async def order_update_form(request: Request, order_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    order = repo.order_get(db, order_id)
    template = repo.template_get(db, order["template_id"])

    edit_data = {}
    for field in template.get("editable_fields", []):
        key = field["name"]
        val = form.get(key)
        if field["type"] == "toggle":
            edit_data[key] = val == "true"
        elif field["type"] == "image":
            if isinstance(val, FormUploadFile) and val.filename:
                content = await val.read()
                dest = settings.logos_dir / f"client_{order['client_id']}_{uuid.uuid4().hex[:8]}.png"
                edit_data[key] = str(prepare_logo(content, dest))
            # no new file chosen -> key omitted, order_update_edit_data keeps the old value
        elif val:
            edit_data[key] = val

    repo.order_update_edit_data(db, order_id, edit_data)

    quantidade_raw = form.get("quantidade", "").strip()
    if quantidade_raw.isdigit():
        repo.order_update_quantidade(db, order_id, int(quantidade_raw))

    return RedirectResponse(f"/pedidos/{order_id}", status_code=303)


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------

@router.get("/web/buscar-cliente", response_class=HTMLResponse)
def buscar_cliente_partial(request: Request, client_phone: str = "",
                           db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    client = repo.client_get_by_phone(db, client_phone) if client_phone.strip() else None
    if not client:
        return HTMLResponse(
            '<div class="small text-muted mt-2">'
            '<i class="bi bi-x-circle"></i> Nenhum cliente encontrado com esse telefone.</div>'
        )

    name = html.escape(client["name"])
    phone = html.escape(client["phone"])
    insta = f' | {html.escape(client["instagram"])}' if client.get("instagram") else ""
    return HTMLResponse(
        f'<div class="alert alert-brand py-2 small mt-2">'
        f'<strong>{name}</strong><br>{phone}{insta}'
        f'<input type="hidden" name="client_id" value="{client["id"]}"></div>'
    )


@router.get("/web/campos-template/{template_id}", response_class=HTMLResponse)
def get_template_fields(request: Request, template_id: int, db: Session = Depends(get_db)):
    t = repo.template_get(db, template_id)
    if not t:
        return HTMLResponse("<p class='text-muted small'>Template nao encontrado</p>")

    fields = t.get("editable_fields", [])
    html_str = ""
    for f in fields:
        html_str += f'<div class="mb-2"><label class="form-label small mb-0">{f["label"]}</label>'
        if f["type"] == "choice":
            html_str += f'<select name="field_{f["name"]}" class="form-select form-select-sm">'
            html_str += '<option value="">-- Nenhum --</option>'
            for opt in f.get("options", []):
                html_str += f'<option value="{opt}">{opt}</option>'
            html_str += '</select>'
        elif f["type"] == "toggle":
            html_str += f'<div class="form-check form-switch">'
            html_str += f'<input type="checkbox" name="field_{f["name"]}" value="true" class="form-check-input">'
            html_str += f'<label class="form-check-label small">Ativar</label></div>'
        else:
            html_str += f'<input type="text" name="field_{f["name"]}" class="form-control form-control-sm" placeholder="{f["label"]}">'
        html_str += '</div>'

    return HTMLResponse(html_str)


@router.get("/web/cleanup-preview", response_class=HTMLResponse)
def cleanup_preview_partial(request: Request):
    if redirect := _auth(request): return redirect
    from app.api.stats import cleanup_preview
    data = cleanup_preview()

    if data["total_files"] == 0:
        return HTMLResponse("""
            <div class="text-center text-muted small py-2">
                <i class="bi bi-check-circle" style="color: var(--brand-orange)"></i> Nada para limpar
            </div>
        """)

    return HTMLResponse(f"""
        <div class="small mb-2">
            <div class="d-flex justify-content-between">
                <span>Pedidos entregues</span><strong>{data['delivered_orders']}</strong>
            </div>
            <div class="d-flex justify-content-between">
                <span>Arquivos para deletar</span><strong>{data['total_files']}</strong>
            </div>
            <div class="d-flex justify-content-between">
                <span>Espaco a recuperar</span>
                <strong style="color: var(--brand-orange)">{data['total_mb']} MB</strong>
            </div>
        </div>
        <button class="btn btn-brand btn-sm w-100"
                hx-post="/web/cleanup-execute"
                hx-target="#cleanupArea"
                hx-swap="innerHTML"
                hx-confirm="Tem certeza? Isto vai apagar os arquivos de pedidos entregues.">
            <i class="bi bi-trash3"></i> Limpar {data['total_mb']} MB
        </button>
    """)


@router.post("/web/cleanup-execute", response_class=HTMLResponse)
def cleanup_execute_partial(request: Request):
    if redirect := _auth(request): return redirect
    from app.api.stats import cleanup_execute
    data = cleanup_execute()

    return HTMLResponse(f"""
        <div class="text-center py-2">
            <i class="bi bi-check-circle-fill" style="color: var(--brand-orange); font-size: 1.5rem"></i>
            <div class="fw-semibold small mt-1">{data['deleted_files']} arquivos removidos</div>
            <div class="small" style="color: var(--brand-orange)">{data['freed_mb']} MB recuperados</div>
        </div>
    """)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@router.get("/clientes", response_class=HTMLResponse)
def clients_page(request: Request, search: str | None = None,
                 db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    clients_raw = repo.client_list(db, search)
    clients = []
    for c in clients_raw:
        order_count = db.scalar(
            select(func.count()).select_from(Order).where(Order.client_id == c["id"])
        )
        c["order_count"] = order_count
        clients.append(c)

    ctx = _base_ctx(request, "clients")
    ctx["clients"] = clients
    ctx["search"] = search
    return templates.TemplateResponse(request, "clients.html", ctx)


@router.post("/clientes/novo")
def client_create(name: str = Form(...), phone: str = Form(...),
                  instagram: str = Form(None), db: Session = Depends(get_db)):
    repo.client_upsert(db, name, phone, instagram)
    return RedirectResponse("/clientes", status_code=303)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@router.get("/catalogo", response_class=HTMLResponse)
def catalog_page(request: Request, msg: str | None = None,
                 db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    tpl_list = repo.template_list_all(db)
    for t in tpl_list:
        t["order_count"] = repo.template_order_count(db, t["id"])
    ctx = _base_ctx(request, "catalog")
    ctx["templates"] = tpl_list
    ctx["msg"] = msg
    return templates.TemplateResponse(request, "catalog.html", ctx)


@router.post("/catalogo/upload")
async def catalog_upload(request: Request, display_name: str = Form(...),
                         product_type: str = Form("pizza"),
                         size_cm: int = Form(None),
                         psd_file: UploadFile = File(...),
                         db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    safe_name = Path(psd_file.filename).name
    if not safe_name.lower().endswith(".psd"):
        return Response("Arquivo deve ser .psd", status_code=400)

    dest = settings.templates_dir / safe_name
    with open(str(dest), "wb") as f:
        content = await psd_file.read()
        f.write(content)

    # A flattened factory PSD (CMYK, no named layers) can't be edited directly. Bridge it
    # into an editable gabarito automatically and start a calibration over its reserved area.
    calibration = None
    if not is_editable_gabarito(dest):
        editable = settings.templates_dir / f"{dest.stem}_editavel.psd"
        try:
            calibration = build_editable_gabarito(dest, editable)
            dest = editable  # the template points at the editable version
        except Exception:
            logger.exception("Falha ao preparar gabarito achatado %s", safe_name)

    thumb_name = f"{dest.stem}.jpg"
    thumb_path = settings.thumbnails_dir / thumb_name
    try:
        generate_preview(dest, thumb_path)
    except Exception:
        thumb_name = None

    try:
        fields = build_editable_fields(dest)
    except Exception:
        fields = []

    template = repo.template_create(
        db,
        filename=dest.name,
        display_name=display_name,
        description=f"Modelo {product_type} {size_cm or '?'}cm",
        size_cm=size_cm,
        product_type=product_type,
        editable_fields=fields,
        thumbnail=thumb_name,
    )
    if calibration and template:
        repo.template_set_calibration(db, template["id"], calibration)

    return RedirectResponse("/catalogo", status_code=303)


# ---------------------------------------------------------------------------
# Calibration: position editable fields over the artwork
# ---------------------------------------------------------------------------

@router.get("/catalogo/{template_id}/calibrar", response_class=HTMLResponse)
def calibrate_page(request: Request, template_id: int, db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    t = repo.template_get(db, template_id)
    if not t:
        return RedirectResponse("/catalogo", status_code=303)

    psd_path = settings.templates_dir / t["filename"]
    if not psd_path.exists():
        return RedirectResponse("/catalogo", status_code=303)

    # The background is the rendered artwork; make sure it exists on disk.
    if not t.get("thumbnail") or not (settings.thumbnails_dir / t["thumbnail"]).exists():
        thumb_name = f"{psd_path.stem}.jpg"
        try:
            generate_preview(psd_path, settings.thumbnails_dir / thumb_name)
            tmpl = db.get(Template, template_id)
            if tmpl:
                tmpl.thumbnail = thumb_name
                db.commit()
        except Exception:
            pass

    geometry = read_template_geometry(psd_path)
    boxes = merge_geometry(geometry, t.get("calibration") or {})

    ctx = _base_ctx(request, "catalog")
    ctx["template"] = t
    ctx["canvas_w"] = geometry.width
    ctx["canvas_h"] = geometry.height
    ctx["boxes"] = boxes
    ctx["bg_url"] = f"/api/catalog/{template_id}/thumbnail"
    return templates.TemplateResponse(request, "calibrate.html", ctx)


def _clean_calibration(payload) -> dict[str, dict]:
    """Coerce a calibration payload from the editor into floats, dropping junk entries."""
    clean: dict[str, dict] = {}
    if not isinstance(payload, dict):
        return clean
    for name, box in payload.items():
        if not isinstance(box, dict):
            continue
        entry = {}
        for key in ("x", "y", "width", "height", "font_size"):
            val = box.get(key)
            if val is not None:
                try:
                    entry[key] = float(val)
                except (TypeError, ValueError):
                    pass
        if entry:
            clean[name] = entry
    return clean


@router.post("/catalogo/{template_id}/calibrar")
async def calibrate_save(request: Request, template_id: int,
                         db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    clean = _clean_calibration(await request.json())
    repo.template_set_calibration(db, template_id, clean)
    return JSONResponse({"status": "ok", "saved": len(clean)})


@router.post("/catalogo/{template_id}/test-preview")
async def calibrate_test_preview(request: Request, template_id: int,
                                 db: Session = Depends(get_db)):
    """Render a preview with sample data using the (possibly unsaved) calibration in the body."""
    if redirect := _auth(request): return redirect

    t = repo.template_get(db, template_id)
    if not t:
        return JSONResponse({"error": "template nao encontrado"}, status_code=404)

    psd_path = settings.templates_dir / t["filename"]
    if not psd_path.exists():
        return JSONResponse({"error": "arquivo PSD nao encontrado"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        body = {}
    calibration = _clean_calibration(body) or (t.get("calibration") or {})

    dest = settings.preview_dir / f"sample_template_{template_id}.jpg"
    render_sample_preview(psd_path, calibration, dest, template=t)
    return Response(content=dest.read_bytes(), media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Template management
# ---------------------------------------------------------------------------

@router.post("/catalogo/{template_id}/editar")
def template_edit(request: Request, template_id: int, display_name: str = Form(...),
                  product_type: str = Form("pizza"), size_cm: str = Form(""),
                  db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    repo.template_update(
        db, template_id,
        display_name=display_name.strip(),
        product_type=product_type.strip() or "pizza",
        size_cm=int(size_cm) if size_cm.strip().isdigit() else None,
    )
    return RedirectResponse("/catalogo", status_code=303)


@router.post("/catalogo/{template_id}/ativar")
def template_activate(request: Request, template_id: int, active: str = Form("1"),
                      db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    repo.template_set_active(db, template_id, active == "1")
    return RedirectResponse("/catalogo", status_code=303)


@router.post("/catalogo/{template_id}/thumbnail")
def template_regen_thumbnail(request: Request, template_id: int,
                             db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    t = repo.template_get(db, template_id)
    if t:
        psd_path = settings.templates_dir / t["filename"]
        if psd_path.exists():
            thumb_name = f"{psd_path.stem}.jpg"
            try:
                generate_preview(psd_path, settings.thumbnails_dir / thumb_name)
                repo.template_update(db, template_id, thumbnail=thumb_name)
            except Exception:
                pass
    return RedirectResponse("/catalogo", status_code=303)


@router.post("/catalogo/{template_id}/excluir")
def template_delete(request: Request, template_id: int, db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    count = repo.template_order_count(db, template_id)
    if count > 0:
        # Pedidos referenciam o template (FK); desativa em vez de apagar.
        repo.template_set_active(db, template_id, False)
        msg = quote(f"Template tem {count} pedido(s) — foi desativado em vez de excluido.")
        return RedirectResponse(f"/catalogo?msg={msg}", status_code=303)

    t = repo.template_get(db, template_id)
    repo.template_delete(db, template_id)
    if t:
        for p in (settings.templates_dir / t["filename"],
                  settings.thumbnails_dir / (t.get("thumbnail") or "")):
            try:
                if p.name and p.exists():
                    p.unlink()
            except OSError:
                pass
    return RedirectResponse("/catalogo?msg=" + quote("Template excluido."), status_code=303)


# ---------------------------------------------------------------------------
# Settings: WhatsApp (Meta Cloud API) integration
# ---------------------------------------------------------------------------

@router.get("/configuracoes/whatsapp", response_class=HTMLResponse)
def whatsapp_settings_page(request: Request, msg: str | None = None, error: str | None = None,
                           db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    cfg = repo.whatsapp_config_get(db) or {}
    ctx = _base_ctx(request, "configuracoes")
    ctx["cfg"] = cfg
    ctx["token_masked"] = mask_secret(cfg.get("token"))
    ctx["app_secret_masked"] = mask_secret(cfg.get("app_secret"))
    ctx["api_version"] = cfg.get("api_version") or settings.meta_api_version
    ctx["webhook_url"] = f"{request.url.scheme}://{request.url.netloc}/api/webhooks/whatsapp"
    ctx["whatsapp_enabled"] = settings.whatsapp_enabled
    ctx["msg"] = msg
    ctx["error"] = error
    return templates.TemplateResponse(request, "whatsapp_settings.html", ctx)


@router.post("/configuracoes/whatsapp")
def whatsapp_settings_save(request: Request, token: str = Form(""), phone_number_id: str = Form(""),
                           verify_token: str = Form(""), app_secret: str = Form(""),
                           api_version: str = Form("v21.0"),
                           db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    merged = merge_blank_with_existing(
        db, token.strip(), phone_number_id.strip(), verify_token.strip(),
        app_secret.strip(), api_version.strip() or "v21.0",
    )
    repo.whatsapp_config_set(db, **merged)
    apply_whatsapp_config(db)
    msg = quote("Configuracao salva. A integracao ja esta ativa com os novos dados.")
    return RedirectResponse(f"/configuracoes/whatsapp?msg={msg}", status_code=303)


@router.post("/configuracoes/whatsapp/testar")
def whatsapp_settings_test(request: Request, telefone_teste: str = Form(...)):
    if redirect := _auth(request): return redirect
    if not settings.whatsapp_enabled:
        error = quote("Preencha e salve o token e o phone_number_id antes de testar.")
        return RedirectResponse(f"/configuracoes/whatsapp?error={error}", status_code=303)

    from app.integrations.whatsapp_client import WhatsAppClient, WhatsAppOutsideWindowError
    from app.utils.phone import normalize_phone

    wa = WhatsAppClient()
    try:
        wa.send_text(normalize_phone(telefone_teste),
                     "Teste de integracao Pizza Box Agent - tudo funcionando!")
        msg = quote(f"Mensagem de teste enviada para {telefone_teste} com sucesso!")
        return RedirectResponse(f"/configuracoes/whatsapp?msg={msg}", status_code=303)
    except WhatsAppOutsideWindowError:
        error = quote(
            "Credenciais validas, mas esse numero esta fora da janela de 24h "
            "(o cliente precisa ter mandado mensagem recentemente, ou use um template aprovado)."
        )
        return RedirectResponse(f"/configuracoes/whatsapp?error={error}", status_code=303)
    except Exception as e:
        error = quote(f"Falha ao enviar: {e}")
        return RedirectResponse(f"/configuracoes/whatsapp?error={error}", status_code=303)
    finally:
        wa.close()


# ---------------------------------------------------------------------------
# Settings: admin account (username + password)
# ---------------------------------------------------------------------------

@router.get("/configuracoes/conta", response_class=HTMLResponse)
def account_settings_page(request: Request, msg: str | None = None, error: str | None = None,
                          db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    ctx = _base_ctx(request, "configuracoes")
    ctx["current_username"] = get_current_user(request) or get_effective_username(db)
    ctx["msg"] = msg
    ctx["error"] = error
    return templates.TemplateResponse(request, "account_settings.html", ctx)


@router.post("/configuracoes/conta")
def account_settings_save(request: Request, current_password: str = Form(...),
                          username: str = Form(...), new_password: str = Form(""),
                          confirm_password: str = Form(""),
                          db: Session = Depends(get_db)):
    if redirect := _auth(request): return redirect

    current_user = get_current_user(request)
    if not verify_login(db, current_user, current_password):
        error = quote("Senha atual incorreta.")
        return RedirectResponse(f"/configuracoes/conta?error={error}", status_code=303)

    username = username.strip()
    if not username:
        error = quote("Usuario nao pode ficar em branco.")
        return RedirectResponse(f"/configuracoes/conta?error={error}", status_code=303)

    if new_password and new_password != confirm_password:
        error = quote("Confirmacao de senha nao bate.")
        return RedirectResponse(f"/configuracoes/conta?error={error}", status_code=303)

    if new_password and len(new_password) < 8:
        error = quote("Nova senha precisa ter pelo menos 8 caracteres.")
        return RedirectResponse(f"/configuracoes/conta?error={error}", status_code=303)

    save_account(db, username, new_password or None, current_username=current_user)

    response = RedirectResponse(
        "/configuracoes/conta?msg=" + quote("Dados salvos. Use o novo login na proxima vez."),
        status_code=303,
    )
    create_session(response, username)  # refresh the session cookie with the new username
    return response
