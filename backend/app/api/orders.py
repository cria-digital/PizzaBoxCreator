"""Orders API: full order lifecycle (create → preview → approve/reject → production)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db import repositories as repo
from app.db.models import OrderRevision
from app.models.commands import (
    OrderCreate,
    OrderResponse,
    OrderStatus,
    OrderUpdate,
)
from app.ai.providers import AIUnavailable
from app.api.auth import require_api_user
from app.services.ai_cost_guard import AIRateLimitExceeded
from app.services.order_service import (
    approve_order,
    build_order_response,
    generate_ai_preview,
    generate_order_preview,
)
from app.web.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["orders"], dependencies=[Depends(require_api_user)])


class RejectBody(BaseModel):
    feedback: str


class StatusUpdate(BaseModel):
    status: OrderStatus


class AuditLogResponse(BaseModel):
    id: int
    order_id: int | None = None
    username: str
    action: str
    details: dict | None = None
    created_at: str


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/orders", response_model=OrderResponse)
def create_order(data: OrderCreate, request: Request, db: Session = Depends(get_db)):
    client_id = data.client_id
    if not client_id and data.client_phone:
        client = repo.client_get_by_phone(db, data.client_phone)
        if not client:
            raise HTTPException(404, "Cliente nao encontrado com esse telefone")
        client_id = client["id"]
    if not client_id:
        raise HTTPException(400, "Informe client_id ou client_phone")

    template = repo.template_get(db, data.template_id)
    if not template:
        raise HTTPException(404, "Template nao encontrado")

    edit_data = dict(data.edit_data)
    if data.message:
        edit_data.update(_parse_message(data.message))

    user = get_current_user(request) or "system"
    order = repo.order_create(
        db,
        client_id,
        data.template_id,
        edit_data,
        data.quantidade,
        created_by=user,
        source="api",
    )
    repo.audit_log(db, user, "order_created", order_id=order["id"],
                   details={"template_id": data.template_id})

    has_data = any(v for v in edit_data.values() if v and v is not False)
    changes = []
    if has_data:
        try:
            order, changes = generate_order_preview(order["id"], db)
        except Exception:
            logger.exception("Falha ao gerar preview inicial do pedido %s", order["id"])

    return build_order_response(order, db, changes)


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db), status: str | None = None,
                client_id: int | None = None, limit: int = 50, offset: int = 0):
    orders = repo.order_list(db, status=status, client_id=client_id,
                             limit=limit, offset=offset)
    return [build_order_response(o, db) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")
    return build_order_response(order, db)


@router.patch("/orders/{order_id}", response_model=OrderResponse)
def update_order(order_id: int, data: OrderUpdate, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] in (OrderStatus.approved.value, OrderStatus.production.value,
                            OrderStatus.delivered.value):
        raise HTTPException(409, "Pedido ja aprovado, nao pode ser alterado")

    edit_data = {}
    if data.edit_data:
        edit_data.update(data.edit_data)
    if data.message:
        edit_data.update(_parse_message(data.message))

    if edit_data:
        order = repo.order_update_edit_data(db, order_id, edit_data)
    if data.quantidade is not None:
        order = repo.order_update_quantidade(db, order_id, data.quantidade)

    return build_order_response(order, db)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

@router.post("/orders/{order_id}/preview", response_model=OrderResponse)
def request_preview(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] in (OrderStatus.production.value, OrderStatus.delivered.value):
        raise HTTPException(409, "Pedido ja em producao")

    order, changes = generate_order_preview(order_id, db)
    return build_order_response(order, db, changes)


@router.post("/orders/{order_id}/ai-preview", response_model=OrderResponse)
def request_ai_preview(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] in (OrderStatus.production.value, OrderStatus.delivered.value):
        raise HTTPException(409, "Pedido ja em producao")

    try:
        order, notes = generate_ai_preview(order_id, db)
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
    except AIRateLimitExceeded as e:
        raise HTTPException(429, str(e))
    return build_order_response(order, db, notes)


@router.post("/orders/{order_id}/approve", response_model=OrderResponse)
def approve(order_id: int, request: Request, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] not in (OrderStatus.preview_sent.value, OrderStatus.revision.value):
        raise HTTPException(
            409, f"Pedido em status '{order['status']}' nao pode ser aprovado. "
                 f"Gere o preview primeiro.")

    user = get_current_user(request) or "system"
    order, warnings = approve_order(order_id, db)
    repo.audit_log(db, user, "order_approved", order_id=order_id)
    return build_order_response(order, db, warnings)


@router.post("/orders/{order_id}/reject", response_model=OrderResponse)
def reject(order_id: int, body: RejectBody, request: Request, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] != OrderStatus.preview_sent.value:
        raise HTTPException(409, "So e possivel rejeitar pedidos com preview enviado")

    latest = repo.revision_get_latest(db, order_id)
    if latest:
        stmt = (
            update(OrderRevision)
            .where(OrderRevision.id == latest["id"])
            .values(feedback=body.feedback)
        )
        db.execute(stmt)
        db.commit()

    user = get_current_user(request) or "system"
    order = repo.order_update_status(
        db,
        order_id,
        OrderStatus.revision.value,
        source="api",
        actor=user,
    )
    repo.audit_log(db, user, "order_rejected", order_id=order_id,
                   details={"feedback": body.feedback})
    return build_order_response(order, db)


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
def update_status(order_id: int, body: StatusUpdate, request: Request, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    old_status = order["status"]
    user = get_current_user(request) or "system"
    order = repo.order_update_status(
        db,
        order_id,
        body.status.value,
        source="api",
        actor=user,
    )
    repo.audit_log(
        db,
        user,
        "order_status_updated",
        order_id=order_id,
        details={"from": old_status, "to": body.status.value},
    )
    return build_order_response(order, db)


@router.get("/orders/{order_id}/audit", response_model=list[AuditLogResponse])
def list_order_audit(order_id: int, db: Session = Depends(get_db)):
    if not repo.order_get(db, order_id):
        raise HTTPException(404, "Pedido nao encontrado")
    return repo.audit_log_list(db, order_id=order_id)


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

@router.get("/orders/{order_id}/preview")
def download_preview(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order or not order.get("preview_jpg"):
        raise HTTPException(404, "Preview nao disponivel")
    path = Path(order["preview_jpg"])
    if not path.exists():
        raise HTTPException(404, "Arquivo de preview nao encontrado")
    return FileResponse(str(path), media_type="image/jpeg")


@router.get("/orders/{order_id}/production")
def download_production(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order or not order.get("cmyk_psd"):
        raise HTTPException(404, "Arquivo de producao nao disponivel. Aprove o pedido primeiro.")
    path = Path(order["cmyk_psd"])
    if not path.exists():
        raise HTTPException(404, "Arquivo CMYK nao encontrado")
    return FileResponse(str(path), media_type="application/octet-stream",
                        filename=f"pedido_{order_id}_producao.psd")


@router.get("/orders/{order_id}/package")
def download_package(order_id: int, db: Session = Depends(get_db)):
    from app.services.production_package import get_package_path
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")
    path = get_package_path(order_id)
    if not path:
        raise HTTPException(404, "Pacote de producao nao disponivel. Aprove o pedido primeiro.")
    return FileResponse(str(path), media_type="application/zip",
                        filename=f"pedido_{order_id}_producao.zip")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_message(message: str) -> dict:
    """Parse a natural language message into edit_data fields."""
    from app.ai.agent import parse_message_to_dict
    return parse_message_to_dict(message)
