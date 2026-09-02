"""Assisted reengagement queue for CRM contacts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db import repositories as repo


def ensure_reengagement_task(
    db: Session,
    *,
    client_id: int,
    reason: str,
    scheduled_for: datetime,
    order_id: int | None = None,
) -> dict:
    return repo.crm_reengagement_create(
        db,
        client_id=client_id,
        order_id=order_id,
        reason=reason,
        scheduled_for=scheduled_for,
    )


def mark_task_sent(db: Session, task_id: int, *, now: datetime | None = None) -> dict | None:
    task = repo.crm_reengagement_get(db, task_id)
    if not task or task["status"] != "pending":
        return task
    sent_at = now or datetime.utcnow()
    updated = repo.crm_reengagement_update(
        db,
        task_id,
        status="sent",
        sent_at=sent_at,
        attempt_count=(task.get("attempt_count") or 0) + 1,
        last_error=None,
    )
    if updated:
        repo.crm_interaction_create(
            db,
            client_id=updated["client_id"],
            order_id=updated.get("order_id"),
            channel="system",
            direction="internal",
            event_type="reengagement_sent",
            payload={"task_id": task_id, "reason": updated["reason"], "mode": "assisted"},
            occurred_at=sent_at,
            idempotency_key=f"crm:reengagement:{task_id}:sent",
        )
    return updated


def skip_task(
    db: Session,
    task_id: int,
    *,
    note: str = "Ignorado pelo operador",
    now: datetime | None = None,
) -> dict | None:
    task = repo.crm_reengagement_get(db, task_id)
    if not task or task["status"] != "pending":
        return task
    skipped_at = now or datetime.utcnow()
    updated = repo.crm_reengagement_update(
        db,
        task_id,
        status="skipped",
        last_error=note,
    )
    if updated:
        repo.crm_interaction_create(
            db,
            client_id=updated["client_id"],
            order_id=updated.get("order_id"),
            channel="system",
            direction="internal",
            event_type="reengagement_skipped",
            payload={"task_id": task_id, "reason": updated["reason"], "note": note},
            occurred_at=skipped_at,
            idempotency_key=f"crm:reengagement:{task_id}:skipped",
        )
    return updated


def skip_recovery_tasks(db: Session, *, client_id: int) -> int:
    return repo.crm_reengagement_skip_pending_for_client(db, client_id=client_id)
