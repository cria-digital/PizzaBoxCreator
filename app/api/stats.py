"""Stats API: dashboard statistics, disk monitoring, and cleanup."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.db.models import Client, Order, OrderRevision, Template

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stats"])


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 1)


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
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

    disk = shutil.disk_usage(str(settings.output_dir.resolve()))

    return {
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
                "output_psd_mb": _dir_size_mb(settings.output_dir),
                "preview_jpg_mb": _dir_size_mb(settings.preview_dir),
                "templates_mb": _dir_size_mb(settings.templates_dir),
                "thumbnails_mb": _dir_size_mb(settings.thumbnails_dir),
                "temp_mb": _dir_size_mb(settings.temp_dir),
            },
        },
    }


@router.get("/cleanup/preview")
def cleanup_preview(db: Session = Depends(get_db)):
    """Preview what cleanup would delete, without actually deleting."""
    delivered = db.execute(
        select(Order).where(Order.status == "delivered")
    ).scalars().all()

    files_to_delete = []
    total_bytes = 0

    for order in delivered:
        for field in ("output_psd", "preview_jpg", "cmyk_psd"):
            path_str = getattr(order, field)
            if path_str:
                p = Path(path_str)
                if p.exists():
                    size = p.stat().st_size
                    files_to_delete.append({"path": str(p), "size_kb": round(size / 1024, 1)})
                    total_bytes += size

        revisions = db.execute(
            select(OrderRevision).where(OrderRevision.order_id == order.id)
        ).scalars().all()
        for rev in revisions:
            if rev.preview_jpg:
                p = Path(rev.preview_jpg)
                if p.exists():
                    size = p.stat().st_size
                    files_to_delete.append({"path": str(p), "size_kb": round(size / 1024, 1)})
                    total_bytes += size

    temp_files = []
    for f in settings.temp_dir.rglob("*"):
        if f.is_file() and f.name != ".gitkeep":
            size = f.stat().st_size
            temp_files.append({"path": str(f), "size_kb": round(size / 1024, 1)})
            total_bytes += size

    return {
        "delivered_orders": len(delivered),
        "files_from_delivered": len(files_to_delete),
        "temp_files": len(temp_files),
        "total_files": len(files_to_delete) + len(temp_files),
        "total_mb": round(total_bytes / (1024 * 1024), 1),
    }


@router.post("/cleanup/execute")
def cleanup_execute(db: Session = Depends(get_db)):
    """Delete files from delivered orders and temp directory."""
    delivered = db.execute(
        select(Order).where(Order.status == "delivered")
    ).scalars().all()

    deleted_count = 0
    freed_bytes = 0

    for order in delivered:
        for field in ("output_psd", "preview_jpg", "cmyk_psd"):
            path_str = getattr(order, field)
            if path_str:
                p = Path(path_str)
                if p.exists():
                    freed_bytes += p.stat().st_size
                    p.unlink()
                    deleted_count += 1

        revisions = db.execute(
            select(OrderRevision).where(OrderRevision.order_id == order.id)
        ).scalars().all()
        for rev in revisions:
            if rev.preview_jpg:
                p = Path(rev.preview_jpg)
                if p.exists():
                    freed_bytes += p.stat().st_size
                    p.unlink()
                    deleted_count += 1

        order.output_psd = None
        order.preview_jpg = None
        order.cmyk_psd = None

    for f in settings.temp_dir.rglob("*"):
        if f.is_file() and f.name != ".gitkeep":
            freed_bytes += f.stat().st_size
            f.unlink()
            deleted_count += 1

    db.commit()
    logger.info("Cleanup: %d files deleted, %.1f MB freed", deleted_count, freed_bytes / 1024 / 1024)

    return {
        "deleted_files": deleted_count,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1),
    }
