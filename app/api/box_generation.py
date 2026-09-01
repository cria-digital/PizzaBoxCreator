"""Box generation API: create template or AI previews for an order."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.providers import AIUnavailable
from app.api.auth import require_api_user
from app.db import repositories as repo
from app.db.session import get_db
from app.models.commands import OrderResponse, OrderStatus
from app.services.ai_cost_guard import AIRateLimitExceeded
from app.services.order_service import build_order_response, generate_ai_preview, generate_order_preview

router = APIRouter(
    prefix="/box-generation",
    tags=["box-generation"],
    dependencies=[Depends(require_api_user)],
)


class BoxGenerationRequest(BaseModel):
    mode: str = "ai"


@router.post("/orders/{order_id}", response_model=OrderResponse)
def generate_box(order_id: int, body: BoxGenerationRequest | None = None,
                 db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] in (OrderStatus.production.value, OrderStatus.delivered.value):
        raise HTTPException(409, "Pedido ja esta em producao ou entregue")

    mode = (body.mode if body else "ai").strip().lower()
    if mode in {"ai", "image", "ia"}:
        try:
            order, notes = generate_ai_preview(order_id, db)
        except AIUnavailable as e:
            raise HTTPException(503, str(e))
        except AIRateLimitExceeded as e:
            raise HTTPException(429, str(e))
    elif mode in {"template", "deterministic", "gabarito"}:
        order, notes = generate_order_preview(order_id, db)
    else:
        raise HTTPException(400, "mode deve ser ai ou template")

    return build_order_response(order, db, notes)


@router.post("/orders/{order_id}/ai", response_model=OrderResponse)
def generate_ai_box(order_id: int, request: Request, db: Session = Depends(get_db)):
    return generate_box(order_id, BoxGenerationRequest(mode="ai"), db)


@router.post("/orders/{order_id}/template", response_model=OrderResponse)
def generate_template_box(order_id: int, request: Request, db: Session = Depends(get_db)):
    return generate_box(order_id, BoxGenerationRequest(mode="template"), db)
