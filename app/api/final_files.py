"""Final file export API for approved pizza-box jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.auth import require_api_user
from app.db import repositories as repo
from app.db.session import get_db
from app.models.commands import OrderResponse, OrderStatus
from app.services.order_service import approve_order, build_order_response
from app.services.production_package import get_package_path

router = APIRouter(
    prefix="/final-files",
    tags=["final-files"],
    dependencies=[Depends(require_api_user)],
)


@router.post("/orders/{order_id}/export", response_model=OrderResponse)
def export_final_file(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    if order["status"] in (OrderStatus.preview_sent.value, OrderStatus.revision.value):
        order, warnings = approve_order(order_id, db)
        return build_order_response(order, db, warnings)

    if order["status"] == OrderStatus.production.value:
        return build_order_response(order, db, ["Arquivo final ja exportado"])

    raise HTTPException(409, "Gere e aprove um preview antes de exportar o arquivo final")


@router.get("/orders/{order_id}/download")
def download_final_file(order_id: int, db: Session = Depends(get_db)):
    order = repo.order_get(db, order_id)
    if not order:
        raise HTTPException(404, "Pedido nao encontrado")

    package_path = get_package_path(order_id)
    if package_path:
        return FileResponse(
            str(package_path),
            media_type="application/zip",
            filename=f"pedido_{order_id}_producao.zip",
        )

    cmyk_path = order.get("cmyk_psd")
    if cmyk_path:
        return FileResponse(
            str(cmyk_path),
            media_type="application/octet-stream",
            filename=f"pedido_{order_id}_producao.psd",
        )

    raise HTTPException(404, "Arquivo final nao disponivel")
