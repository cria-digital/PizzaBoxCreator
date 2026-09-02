"""Stats API: dashboard statistics, disk monitoring, and cleanup."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import require_api_user
from app.db.session import get_db
from app.db.models import Client, Order, Template
from app.services import storage_service

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    username: str = Depends(require_api_user),
):
    orders_by_status = {}
    for status_val, cnt in db.execute(
        select(Order.status, func.count()).group_by(Order.status)
    ).fetchall():
        orders_by_status[status_val.value] = cnt

    total_orders = db.scalar(select(func.count()).select_from(Order))
    total_clients = db.scalar(select(func.count()).select_from(Client))
    total_templates = db.scalar(
        select(func.count()).select_from(Template).where(Template.active == True)  # noqa: E712
    )

    recent_orders = []
    rows = db.execute(
        select(
            Order.id,
            Order.status,
            Order.created_at,
            Order.updated_at,
            Client.name.label("client_name"),
            Template.display_name.label("template_name"),
        )
        .join(Client, Order.client_id == Client.id)
        .join(Template, Order.template_id == Template.id)
        .order_by(Order.updated_at.desc())
        .limit(10)
    ).fetchall()
    for row in rows:
        recent_orders.append({
            "id": row.id,
            "status": row.status.value,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "client_name": row.client_name,
            "template_name": row.template_name,
        })

    disk_usage = storage_service.get_storage_snapshot(
        db,
        emit_alerts=False,
        username=username,
    )

    return {
        "orders_by_status": orders_by_status,
        "total_orders": total_orders,
        "total_clients": total_clients,
        "total_templates": total_templates,
        "recent_orders": recent_orders,
        "disk_usage": disk_usage,
    }


@router.get("/cleanup/preview")
def cleanup_preview(
    db: Session = Depends(get_db),
    username: str = Depends(require_api_user),
):
    """Preview what cleanup would delete, without actually deleting."""
    return storage_service.cleanup_preview(db, username=username)


@router.post("/cleanup/execute")
def cleanup_execute(
    db: Session = Depends(get_db),
    username: str = Depends(require_api_user),
):
    """Delete files from delivered orders and temp directory."""
    return storage_service.cleanup_execute(db, username=username)


@router.get("/storage")
def storage_snapshot(
    db: Session = Depends(get_db),
    username: str = Depends(require_api_user),
):
    return storage_service.get_storage_snapshot(db, emit_alerts=True, username=username)


@router.get("/storage/cleanup/preview")
def storage_cleanup_preview(
    db: Session = Depends(get_db),
    username: str = Depends(require_api_user),
):
    return storage_service.cleanup_preview(db, username=username)


@router.post("/storage/cleanup/execute")
def storage_cleanup_execute(
    db: Session = Depends(get_db),
    username: str = Depends(require_api_user),
):
    return storage_service.cleanup_execute(db, username=username)
