"""Storage monitoring, alerting, and retention policy execution."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import repositories as repo
from app.db.models import AuditLog, Order, OrderRevision, OrderStatus


SYSTEM_USER = "system"


@dataclass(frozen=True)
class StoragePolicy:
    warning_threshold_percent: float
    critical_threshold_percent: float
    cleanup_enabled: bool
    dry_run: bool
    retention_delivered_days: int
    retention_temp_hours: int
    backup_max_files: int
    alert_cooldown_hours: int


def get_storage_policy(
    *,
    dry_run: bool | None = None,
    retention_delivered_days: int | None = None,
    retention_temp_hours: int | None = None,
    backup_max_files: int | None = None,
) -> StoragePolicy:
    return StoragePolicy(
        warning_threshold_percent=settings.storage_warning_threshold_percent,
        critical_threshold_percent=settings.storage_critical_threshold_percent,
        cleanup_enabled=settings.storage_cleanup_enabled,
        dry_run=settings.storage_cleanup_dry_run if dry_run is None else dry_run,
        retention_delivered_days=(
            settings.storage_retention_delivered_days
            if retention_delivered_days is None
            else retention_delivered_days
        ),
        retention_temp_hours=(
            settings.storage_retention_temp_hours
            if retention_temp_hours is None
            else retention_temp_hours
        ),
        backup_max_files=settings.storage_backup_max_files if backup_max_files is None else backup_max_files,
        alert_cooldown_hours=settings.storage_alert_cooldown_hours,
    )


def get_storage_snapshot(
    db: Session | None = None,
    *,
    emit_alerts: bool = False,
    username: str = SYSTEM_USER,
) -> dict:
    settings.ensure_dirs()
    disk = shutil.disk_usage(str(settings.output_dir.resolve()))
    percent_used = round(disk.used / disk.total * 100, 1) if disk.total else 0.0
    policy = get_storage_policy()
    status = storage_status(percent_used, policy)
    breakdown = _storage_breakdown()
    plan = build_cleanup_plan(db, policy=policy) if db is not None else _empty_plan(policy)

    alert = None
    if emit_alerts and db is not None:
        alert = evaluate_storage_alerts(db, percent_used, policy=policy, username=username)

    storage_breakdown = {f"{item['category']}_mb": item["size_mb"] for item in breakdown}
    storage_breakdown.update({
        "output_psd_mb": storage_breakdown.get("output_mb", 0.0),
        "preview_jpg_mb": storage_breakdown.get("preview_mb", 0.0),
        "temp_mb": storage_breakdown.get("temp_mb", 0.0),
        "templates_mb": storage_breakdown.get("templates_mb", 0.0),
        "thumbnails_mb": storage_breakdown.get("thumbnails_mb", 0.0),
    })

    return {
        "status": status,
        "checked_at": _now().isoformat(),
        "total_gb": round(disk.total / (1024**3), 1),
        "used_gb": round(disk.used / (1024**3), 1),
        "free_gb": round(disk.free / (1024**3), 1),
        "percent_used": percent_used,
        "thresholds": {
            "warning": policy.warning_threshold_percent,
            "critical": policy.critical_threshold_percent,
        },
        "breakdown": breakdown,
        "storage_breakdown": storage_breakdown,
        "top_items": _top_storage_items(limit=10),
        "cleanup_estimate": _plan_summary(plan),
        "policy": _policy_dict(policy),
        "alert": alert,
    }


def storage_status(percent_used: float, policy: StoragePolicy | None = None) -> str:
    policy = policy or get_storage_policy()
    if percent_used >= policy.critical_threshold_percent:
        return "critical"
    if percent_used >= policy.warning_threshold_percent:
        return "warning"
    return "ok"


def evaluate_storage_alerts(
    db: Session,
    percent_used: float,
    *,
    policy: StoragePolicy | None = None,
    username: str = SYSTEM_USER,
) -> dict:
    policy = policy or get_storage_policy()
    status = storage_status(percent_used, policy)
    if status == "ok":
        return {"emitted": False, "status": "ok", "action": None}

    action = "storage_alert_critical" if status == "critical" else "storage_alert_warning"
    if _within_alert_cooldown(db, action, policy.alert_cooldown_hours):
        return {"emitted": False, "status": status, "action": action, "reason": "cooldown"}

    repo.audit_log(
        db,
        username,
        action,
        order_id=None,
        details={
            "percent_used": percent_used,
            "thresholds": {
                "warning": policy.warning_threshold_percent,
                "critical": policy.critical_threshold_percent,
            },
            "checked_at": _now().isoformat(),
        },
    )
    return {"emitted": True, "status": status, "action": action}


def build_cleanup_plan(db: Session | None, *, policy: StoragePolicy | None = None) -> dict:
    policy = policy or get_storage_policy()
    files: list[dict] = []
    skipped: list[dict] = []

    files.extend(_temp_file_candidates(policy, skipped))
    files.extend(_backup_candidates(policy, skipped))

    delivered_orders = 0
    if db is not None:
        delivered_orders, order_files, order_skipped = _delivered_order_file_candidates(db, policy)
        files.extend(order_files)
        skipped.extend(order_skipped)

    total_bytes = sum(item["size_bytes"] for item in files)
    return {
        "dry_run": policy.dry_run,
        "policy": _policy_dict(policy),
        "delivered_orders": delivered_orders,
        "files": files,
        "skipped": skipped,
        "total_files": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 1),
        "files_from_delivered": sum(1 for item in files if item.get("order_id") is not None),
        "temp_files": sum(1 for item in files if item["category"] == "temp"),
        "backup_files": sum(1 for item in files if item["category"] == "backups"),
    }


def execute_cleanup(
    db: Session | None,
    *,
    policy: StoragePolicy | None = None,
    username: str = SYSTEM_USER,
    force: bool = False,
) -> dict:
    policy = policy or get_storage_policy()
    if policy.dry_run and not force:
        plan = build_cleanup_plan(db, policy=policy)
        _audit_cleanup(db, username, "storage_cleanup_previewed", plan, errors=[])
        return {
            "dry_run": True,
            "deleted_files": 0,
            "freed_mb": 0.0,
            "planned_files": plan["total_files"],
            "planned_mb": plan["total_mb"],
            "errors": [],
        }

    plan = build_cleanup_plan(db, policy=policy)
    deleted_count = 0
    freed_bytes = 0
    errors: list[dict] = []
    deleted_order_fields: dict[int, set[str]] = {}
    deleted_revision_ids: set[int] = set()

    for item in plan["files"]:
        path = Path(item["path"])
        try:
            resolved = path.resolve()
            if not _is_deletable_path(resolved, item["category"]):
                errors.append({"path": str(path), "error": "path fora da allowlist"})
                continue
            if not resolved.exists():
                continue
            size = resolved.stat().st_size
            resolved.unlink()
            deleted_count += 1
            freed_bytes += size
            if item.get("order_id") and item.get("field"):
                deleted_order_fields.setdefault(int(item["order_id"]), set()).add(item["field"])
            if item.get("revision_id"):
                deleted_revision_ids.add(int(item["revision_id"]))
        except Exception as exc:
            errors.append({"path": str(path), "error": str(exc)})

    if db is not None:
        _clear_deleted_order_paths(db, deleted_order_fields, deleted_revision_ids)
        db.commit()

    result = {
        "dry_run": False,
        "deleted_files": deleted_count,
        "freed_mb": round(freed_bytes / (1024 * 1024), 1),
        "planned_files": plan["total_files"],
        "planned_mb": plan["total_mb"],
        "errors": errors,
    }
    _audit_cleanup(
        db,
        username,
        "storage_cleanup_failed" if errors else "storage_cleanup_executed",
        plan,
        result=result,
        errors=errors,
    )
    return result


def cleanup_preview(db: Session | None = None, *, username: str = SYSTEM_USER) -> dict:
    policy = get_storage_policy(dry_run=True)
    plan = build_cleanup_plan(db, policy=policy)
    _audit_cleanup(db, username, "storage_cleanup_previewed", plan, errors=[])
    return plan


def cleanup_execute(
    db: Session | None = None,
    *,
    username: str = SYSTEM_USER,
    retention_delivered_days: int | None = None,
    retention_temp_hours: int | None = None,
    backup_max_files: int | None = None,
) -> dict:
    policy = get_storage_policy(
        dry_run=False,
        retention_delivered_days=retention_delivered_days,
        retention_temp_hours=retention_temp_hours,
        backup_max_files=backup_max_files,
    )
    return execute_cleanup(db, policy=policy, username=username, force=True)


def _managed_categories() -> dict[str, Path]:
    return {
        "templates": settings.templates_dir,
        "output": settings.output_dir,
        "art_masters": settings.art_masters_dir,
        "preview": settings.preview_dir,
        "thumbnails": settings.thumbnails_dir,
        "logos": settings.logos_dir,
        "temp": settings.temp_dir,
        "backups": settings.backups_dir,
        "logs": settings.logs_dir,
    }


def _deletable_roots() -> dict[str, tuple[Path, ...]]:
    return {
        "output": (settings.output_dir,),
        "preview": (settings.preview_dir,),
        "temp": (settings.temp_dir,),
        "backups": (settings.backups_dir,),
        "thumbnails": (settings.thumbnails_dir,),
    }


def _storage_breakdown() -> list[dict]:
    items = []
    for category, path in _managed_categories().items():
        size_bytes = _dir_size_bytes(path)
        items.append({
            "category": category,
            "path": str(path),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 1),
            "treatment": _category_treatment(category),
        })
    db_size = _file_size_bytes(settings.db_path)
    items.append({
        "category": "database",
        "path": str(settings.db_path),
        "size_bytes": db_size,
        "size_mb": round(db_size / (1024 * 1024), 1),
        "treatment": "preservar",
    })
    return items


def _category_treatment(category: str) -> str:
    if category in {"templates", "database", "logos", "art_masters"}:
        return "preservar"
    if category in {"temp", "backups", "preview", "output", "thumbnails"}:
        return "limpavel por politica"
    return "monitorar"


def _top_storage_items(limit: int = 10) -> list[dict]:
    files: list[dict] = []
    for category, root in _managed_categories().items():
        if not root.exists():
            continue
        for path in _iter_files(root):
            size = _file_size_bytes(path)
            if size:
                files.append({
                    "category": category,
                    "path": str(path),
                    "size_bytes": size,
                    "size_mb": round(size / (1024 * 1024), 1),
                })
    files.sort(key=lambda item: item["size_bytes"], reverse=True)
    return files[:limit]


def _temp_file_candidates(policy: StoragePolicy, skipped: list[dict]) -> list[dict]:
    cutoff = _now() - timedelta(hours=policy.retention_temp_hours)
    files = []
    if not settings.temp_dir.exists():
        return files
    for path in _iter_files(settings.temp_dir):
        if path.name == ".gitkeep":
            continue
        if _mtime(path) > cutoff:
            skipped.append({"path": str(path), "category": "temp", "reason": "retencao_temporaria"})
            continue
        item = _candidate(path, "temp", "arquivo temporario acima da retencao")
        if item:
            files.append(item)
    return files


def _backup_candidates(policy: StoragePolicy, skipped: list[dict]) -> list[dict]:
    if not settings.backups_dir.exists() or policy.backup_max_files < 0:
        return []
    backups = [
        path for path in _iter_files(settings.backups_dir)
        if path.name.startswith("pizzabox_") and path.suffix == ".gz"
    ]
    backups.sort(key=lambda path: _mtime(path), reverse=True)
    keep = backups[: policy.backup_max_files]
    for path in keep:
        skipped.append({"path": str(path), "category": "backups", "reason": "dentro_do_limite"})
    return [
        item for item in (
            _candidate(path, "backups", f"excede limite de {policy.backup_max_files} backups")
            for path in backups[policy.backup_max_files :]
        )
        if item
    ]


def _delivered_order_file_candidates(
    db: Session,
    policy: StoragePolicy,
) -> tuple[int, list[dict], list[dict]]:
    cutoff = _now() - timedelta(days=policy.retention_delivered_days)
    orders = db.execute(select(Order).where(Order.status == OrderStatus.delivered)).scalars().all()
    files: list[dict] = []
    skipped: list[dict] = []

    for order in orders:
        if _as_aware(order.updated_at) > cutoff:
            skipped.append({
                "order_id": order.id,
                "category": "order",
                "reason": "pedido_entregue_dentro_da_retencao",
            })
            continue
        for field in ("output_psd", "preview_jpg", "cmyk_psd"):
            path_str = getattr(order, field)
            if not path_str:
                continue
            category = "preview" if field == "preview_jpg" else "output"
            item = _candidate(
                Path(path_str),
                category,
                f"pedido entregue ha mais de {policy.retention_delivered_days} dias",
                order_id=order.id,
                field=field,
            )
            if item:
                files.append(item)

        revisions = db.execute(
            select(OrderRevision).where(OrderRevision.order_id == order.id)
        ).scalars().all()
        for rev in revisions:
            if not rev.preview_jpg:
                continue
            item = _candidate(
                Path(rev.preview_jpg),
                "preview",
                f"revisao de pedido entregue ha mais de {policy.retention_delivered_days} dias",
                order_id=order.id,
                revision_id=rev.id,
                field="preview_jpg",
            )
            if item:
                files.append(item)

    return len(orders), files, skipped


def _candidate(
    path: Path,
    category: str,
    reason: str,
    *,
    order_id: int | None = None,
    revision_id: int | None = None,
    field: str | None = None,
) -> dict | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    if not _is_deletable_path(resolved, category):
        return None
    size = resolved.stat().st_size
    return {
        "category": category,
        "path": str(resolved),
        "size_bytes": size,
        "size_kb": round(size / 1024, 1),
        "size_mb": round(size / (1024 * 1024), 1),
        "modified_at": _mtime(resolved).isoformat(),
        "reason": reason,
        "order_id": order_id,
        "revision_id": revision_id,
        "field": field,
    }


def _is_deletable_path(path: Path, category: str) -> bool:
    roots = _deletable_roots().get(category, ())
    return any(_is_relative_to(path, root.resolve()) for root in roots)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _clear_deleted_order_paths(
    db: Session,
    order_fields: dict[int, set[str]],
    revision_ids: Iterable[int],
) -> None:
    for order_id, fields in order_fields.items():
        order = db.get(Order, order_id)
        if not order:
            continue
        for field in fields:
            if field in {"output_psd", "preview_jpg", "cmyk_psd"}:
                setattr(order, field, None)
    for revision_id in revision_ids:
        revision = db.get(OrderRevision, revision_id)
        if revision:
            revision.preview_jpg = None


def _audit_cleanup(
    db: Session | None,
    username: str,
    action: str,
    plan: dict,
    *,
    result: dict | None = None,
    errors: list[dict],
) -> None:
    if db is None:
        return
    repo.audit_log(
        db,
        username,
        action,
        order_id=None,
        details={
            "dry_run": plan["dry_run"],
            "total_files": plan["total_files"],
            "total_mb": plan["total_mb"],
            "policy": plan["policy"],
            "result": result,
            "errors": errors[:20],
        },
    )


def _within_alert_cooldown(db: Session, action: str, cooldown_hours: int) -> bool:
    latest = db.scalar(
        select(AuditLog)
        .where(AuditLog.action == action)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    if not latest or not latest.created_at:
        return False
    return _as_aware(latest.created_at) >= _now() - timedelta(hours=cooldown_hours)


def _plan_summary(plan: dict) -> dict:
    return {
        "files": plan["total_files"],
        "freed_mb": plan["total_mb"],
        "dry_run": plan["dry_run"],
    }


def _empty_plan(policy: StoragePolicy) -> dict:
    return {
        "dry_run": policy.dry_run,
        "policy": _policy_dict(policy),
        "delivered_orders": 0,
        "files": [],
        "skipped": [],
        "total_files": 0,
        "total_bytes": 0,
        "total_mb": 0.0,
        "files_from_delivered": 0,
        "temp_files": 0,
        "backup_files": 0,
    }


def _policy_dict(policy: StoragePolicy) -> dict:
    return {
        "warning_threshold_percent": policy.warning_threshold_percent,
        "critical_threshold_percent": policy.critical_threshold_percent,
        "cleanup_enabled": policy.cleanup_enabled,
        "dry_run": policy.dry_run,
        "retention_delivered_days": policy.retention_delivered_days,
        "retention_temp_hours": policy.retention_temp_hours,
        "backup_max_files": policy.backup_max_files,
        "alert_cooldown_hours": policy.alert_cooldown_hours,
    }


def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(_file_size_bytes(file_path) for file_path in _iter_files(path))


def _file_size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size if path.exists() and path.is_file() else 0
    except OSError:
        return 0


def _iter_files(root: Path) -> Iterable[Path]:
    try:
        yield from (path for path in root.rglob("*") if path.is_file())
    except OSError:
        return


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _as_aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)
