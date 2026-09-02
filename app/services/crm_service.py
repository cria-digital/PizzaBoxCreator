"""CRM domain service: profile lifecycle, classification and funnel metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import repositories as repo
from app.db.models import (
    Client,
    CrmInteraction,
    CrmProfile,
    CrmReengagementTask,
    Order,
    OrderStatusEvent,
)
from app.services import reengagement_service


FUNNEL_STAGES = [
    "lead",
    "qualified",
    "order_created",
    "preview_sent",
    "revision",
    "approved",
    "production",
    "delivered",
]

STATUS_TO_STAGE = {
    "draft": "order_created",
    "preview_sent": "preview_sent",
    "revision": "revision",
    "approved": "approved",
    "production": "production",
    "delivered": "delivered",
}

REENGAGEMENT_CLASSIFICATIONS = {"at_risk", "abandoned", "inactive"}


@dataclass(frozen=True)
class CrmRuleParams:
    vip_delivered_orders: int = settings.crm_vip_delivered_orders
    vip_boxes: int = settings.crm_vip_boxes
    vip_window_days: int = settings.crm_vip_window_days
    at_risk_days: int = settings.crm_at_risk_days
    abandoned_days: int = settings.crm_abandoned_days
    active_days: int = settings.crm_active_days
    inactive_days: int = settings.crm_inactive_days
    rule_version: str = settings.crm_rule_version


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_profile(db: Session, client_id: int, *, classify: bool = True) -> dict:
    profile = repo.crm_profile_ensure(db, client_id)
    if classify:
        return classify_client(db, client_id)
    return profile


def record_interaction(
    db: Session,
    *,
    client_id: int,
    event_type: str,
    channel: str,
    direction: str,
    order_id: int | None = None,
    payload: dict | None = None,
    occurred_at: datetime | None = None,
    idempotency_key: str | None = None,
    classify: bool = True,
) -> dict:
    ensure_profile(db, client_id, classify=False)
    interaction = repo.crm_interaction_create(
        db,
        client_id=client_id,
        order_id=order_id,
        channel=channel,
        direction=direction,
        event_type=event_type,
        payload=payload or {},
        occurred_at=occurred_at or now_utc(),
        idempotency_key=idempotency_key,
    )
    if classify:
        classify_client(db, client_id)
    return interaction


def record_order_created(
    db: Session,
    *,
    order_id: int,
    client_id: int,
    source: str,
    actor: str | None = None,
) -> None:
    ensure_profile(db, client_id, classify=False)
    repo.order_status_event_create(
        db,
        order_id=order_id,
        from_status=None,
        to_status="draft",
        source=source,
        actor=actor,
    )
    record_interaction(
        db,
        client_id=client_id,
        order_id=order_id,
        channel=source if source in {"web", "api", "whatsapp"} else "system",
        direction="internal",
        event_type="order_created",
        payload={"order_id": order_id},
        idempotency_key=f"crm:order:{order_id}:created",
        classify=False,
    )
    classify_client(db, client_id)


def record_order_status_change(
    db: Session,
    *,
    order_id: int,
    client_id: int,
    from_status: str | None,
    to_status: str,
    source: str,
    actor: str | None = None,
) -> None:
    ensure_profile(db, client_id, classify=False)
    status_event = repo.order_status_event_create(
        db,
        order_id=order_id,
        from_status=from_status,
        to_status=to_status,
        source=source,
        actor=actor,
    )
    record_interaction(
        db,
        client_id=client_id,
        order_id=order_id,
        channel=source if source in {"web", "api", "whatsapp"} else "system",
        direction="internal",
        event_type=_event_type_for_status(to_status),
        payload={"from_status": from_status, "to_status": to_status},
        idempotency_key=f"crm:order:{order_id}:status:{to_status}:{status_event['id']}",
        classify=False,
    )
    classify_client(db, client_id)


def classify_client(
    db: Session,
    client_id: int,
    *,
    now: datetime | None = None,
    params: CrmRuleParams | None = None,
) -> dict:
    params = params or CrmRuleParams()
    current_time = now or now_utc()
    existing = repo.crm_profile_ensure(db, client_id)
    evidence = _classification_evidence(db, client_id, current_time, params)
    classification, reason = _choose_classification(evidence)
    serializable_evidence = _json_evidence(evidence)
    lifecycle_stage = evidence["lifecycle_stage"]
    last_contact_at = evidence["last_contact_at"]
    last_order_at = evidence["last_order_at"]
    next_reengagement_at = _next_reengagement_at(classification, current_time, params)

    previous = existing.get("classification")
    updated = repo.crm_profile_update(
        db,
        client_id,
        classification=classification,
        lifecycle_stage=lifecycle_stage,
        last_contact_at=last_contact_at,
        last_order_at=last_order_at,
        last_classified_at=current_time,
        next_reengagement_at=next_reengagement_at,
        classification_reason=reason,
        classification_data=serializable_evidence,
        rule_version=params.rule_version,
    )
    if previous != classification:
        repo.crm_classification_event_create(
            db,
            client_id=client_id,
            previous_classification=previous,
            new_classification=classification,
            reason=reason,
            evidence=serializable_evidence,
            rule_version=params.rule_version,
        )

    if classification in REENGAGEMENT_CLASSIFICATIONS and not updated["reengagement_paused"]:
        stale_order_id = evidence.get("stale_order_id")
        reengagement_service.ensure_reengagement_task(
            db,
            client_id=client_id,
            order_id=stale_order_id,
            reason=f"{classification}:{reason}",
            scheduled_for=next_reengagement_at or current_time,
        )
    elif classification in {"active", "vip"}:
        reengagement_service.skip_recovery_tasks(db, client_id=client_id)

    return updated


def reclassify_all(db: Session, *, now: datetime | None = None) -> dict:
    client_ids = repo.crm_all_client_ids(db)
    changed = 0
    for client_id in client_ids:
        before = repo.crm_profile_get(db, client_id)
        after = classify_client(db, client_id, now=now)
        if not before or before.get("classification") != after.get("classification"):
            changed += 1
    return {"evaluated": len(client_ids), "changed": changed}


def backfill_crm(db: Session) -> dict:
    created_profiles = 0
    created_order_events = 0
    for client_id in repo.crm_all_client_ids(db):
        if not repo.crm_profile_get(db, client_id):
            repo.crm_profile_ensure(db, client_id)
            created_profiles += 1

    orders = db.scalars(select(Order).order_by(Order.id)).all()
    for order in orders:
        events = repo.order_status_event_list(db, order.id)
        if not events:
            repo.order_status_event_create(
                db,
                order_id=order.id,
                from_status=None,
                to_status=order.status.value if hasattr(order.status, "value") else str(order.status),
                source="backfill",
            )
            created_order_events += 1
        record_interaction(
            db,
            client_id=order.client_id,
            order_id=order.id,
            channel="system",
            direction="internal",
            event_type="order_backfilled",
            payload={"status": order.status.value if hasattr(order.status, "value") else str(order.status)},
            occurred_at=order.created_at or now_utc(),
            idempotency_key=f"crm:order:{order.id}:backfill",
            classify=False,
        )

    reclassify_all(db)
    return {"profiles_created": created_profiles, "order_events_created": created_order_events}


def contact_detail(db: Session, client_id: int) -> dict | None:
    client = repo.client_get(db, client_id)
    if not client:
        return None
    ensure_profile(db, client_id)
    return {
        "client": client,
        "profile": repo.crm_profile_get(db, client_id),
        "orders": repo.order_list(db, client_id=client_id, limit=100),
        "interactions": repo.crm_interaction_list(db, client_id, limit=100),
        "classification_events": repo.crm_classification_event_list(db, client_id, limit=100),
        "reengagement_tasks": repo.crm_reengagement_list(db, client_id=client_id, limit=100),
    }


def crm_metrics(db: Session, *, start: datetime | None = None, end: datetime | None = None) -> dict:
    _ensure_profiles_for_metrics(db)

    profile_stmt = select(CrmProfile)
    if start:
        profile_stmt = profile_stmt.where(CrmProfile.created_at >= start)
    if end:
        profile_stmt = profile_stmt.where(CrmProfile.created_at <= end)
    profiles = list(db.scalars(profile_stmt))

    contacts_total = len(profiles)
    new_contacts = contacts_total
    by_classification = {c: 0 for c in ["new", "active", "vip", "at_risk", "abandoned", "inactive"]}
    by_stage = {s: 0 for s in FUNNEL_STAGES}
    for profile in profiles:
        classification = _value(profile.classification)
        stage = _value(profile.lifecycle_stage)
        by_classification[classification] = by_classification.get(classification, 0) + 1
        by_stage[stage] = by_stage.get(stage, 0) + 1

    stage_clients = _clients_by_recorded_stage(db, start=start, end=end)
    conversions = {
        "lead_to_order": _rate(stage_clients["order_created"], max(contacts_total, stage_clients["lead"])),
        "order_to_preview": _rate(stage_clients["preview_sent"], stage_clients["order_created"]),
        "preview_to_approved": _rate(stage_clients["approved"], stage_clients["preview_sent"]),
        "approved_to_delivered": _rate(stage_clients["delivered"], stage_clients["approved"]),
    }

    reengagement_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(CrmReengagementTask.status, func.count()).group_by(CrmReengagementTask.status)
        ).all()
    }

    return {
        "timezone": "UTC",
        "unit": "clientes_unicos",
        "contacts_total": contacts_total,
        "new_contacts": new_contacts,
        "by_classification": by_classification,
        "by_stage": by_stage,
        "stage_clients": stage_clients,
        "conversions": conversions,
        "abandoned_count": by_classification.get("abandoned", 0),
        "abandoned_rate": _rate(by_classification.get("abandoned", 0), contacts_total),
        "vip_count": by_classification.get("vip", 0),
        "reengagement": {
            _value(status): count for status, count in reengagement_counts.items()
        },
        "median_stage_minutes": _median_stage_minutes(db, start=start, end=end),
    }


def _classification_evidence(
    db: Session,
    client_id: int,
    current_time: datetime,
    params: CrmRuleParams,
) -> dict:
    orders = list(
        db.scalars(
            select(Order)
            .where(Order.client_id == client_id)
            .order_by(Order.updated_at.desc(), Order.id.desc())
        )
    )
    last_interaction_at = repo.crm_interaction_last_at(db, client_id)
    last_order_at = max((order.updated_at for order in orders if order.updated_at), default=None)
    last_contact_at = max((d for d in [last_interaction_at, last_order_at] if d), default=None)

    delivered_cutoff = current_time - timedelta(days=params.vip_window_days)
    delivered_orders = [
        order for order in orders
        if _value(order.status) == "delivered" and (order.updated_at or order.created_at) >= delivered_cutoff
    ]
    delivered_boxes = sum(order.quantidade or 0 for order in delivered_orders)

    stale = _stale_order(orders, current_time)
    latest_relevant = next(
        (order for order in orders if _value(order.status) != "delivered"),
        orders[0] if orders else None,
    )
    lifecycle_stage = STATUS_TO_STAGE.get(_value(latest_relevant.status), "lead") if latest_relevant else "lead"

    return {
        "delivered_orders": len(delivered_orders),
        "delivered_boxes": delivered_boxes,
        "open_orders": sum(1 for order in orders if _value(order.status) != "delivered"),
        "last_contact_at": last_contact_at,
        "last_order_at": last_order_at,
        "current_time": current_time,
        "stale_order_id": stale["order_id"] if stale else None,
        "stale_order_status": stale["status"] if stale else None,
        "stale_days": stale["days"] if stale else None,
        "lifecycle_stage": lifecycle_stage,
        "params": {
            "vip_delivered_orders": params.vip_delivered_orders,
            "vip_boxes": params.vip_boxes,
            "vip_window_days": params.vip_window_days,
            "at_risk_days": params.at_risk_days,
            "abandoned_days": params.abandoned_days,
            "active_days": params.active_days,
            "inactive_days": params.inactive_days,
        },
    }


def _choose_classification(evidence: dict) -> tuple[str, str]:
    params = evidence["params"]
    if (
        evidence["delivered_orders"] >= params["vip_delivered_orders"]
        or evidence["delivered_boxes"] >= params["vip_boxes"]
    ):
        return "vip", "criterio_vip_atingido"

    stale_days = evidence.get("stale_days")
    stale_status = evidence.get("stale_order_status")
    if stale_days is not None and stale_status in {"draft", "preview_sent", "revision"}:
        if stale_days >= params["abandoned_days"]:
            return "abandoned", "pedido_sem_avanco_alem_do_limite"
        if stale_status in {"preview_sent", "revision"} and stale_days >= params["at_risk_days"]:
            return "at_risk", "pedido_sem_resposta"

    if evidence["open_orders"]:
        return "active", "pedido_aberto"

    last_contact_at = evidence.get("last_contact_at")
    if not evidence["last_order_at"]:
        if last_contact_at and (evidence["current_time"] - last_contact_at).days >= params["inactive_days"]:
            return "inactive", "sem_interacao_recente"
        return "new", "cliente_sem_pedido"

    if last_contact_at:
        age_days = (evidence["current_time"] - last_contact_at).days
        if age_days <= params["active_days"]:
            return "active", "atividade_recente"
        if age_days >= params["inactive_days"]:
            return "inactive", "sem_interacao_recente"

    return "inactive", "sem_pedido_aberto"


def _stale_order(orders: list[Order], current_time: datetime) -> dict | None:
    monitored = {"draft", "preview_sent", "revision"}
    stale_orders = []
    for order in orders:
        status = _value(order.status)
        if status not in monitored:
            continue
        changed_at = _last_status_change_at(order)
        days = (current_time - changed_at).days
        stale_orders.append({"order_id": order.id, "status": status, "days": days})
    return max(stale_orders, key=lambda item: item["days"]) if stale_orders else None


def _last_status_change_at(order: Order) -> datetime:
    return order.updated_at or order.created_at or now_utc()


def _next_reengagement_at(
    classification: str,
    current_time: datetime,
    params: CrmRuleParams,
) -> datetime | None:
    if classification == "at_risk":
        return current_time
    if classification == "abandoned":
        return current_time
    if classification == "inactive":
        return current_time + timedelta(days=1)
    return None


def _event_type_for_status(status: str) -> str:
    return {
        "draft": "order_created",
        "preview_sent": "preview_sent",
        "revision": "revision_requested",
        "approved": "order_approved",
        "production": "production_started",
        "delivered": "order_delivered",
    }.get(status, "order_status_changed")


def _ensure_profiles_for_metrics(db: Session) -> None:
    missing = list(
        db.scalars(
            select(Client.id)
            .outerjoin(CrmProfile, CrmProfile.client_id == Client.id)
            .where(CrmProfile.id.is_(None))
        )
    )
    for client_id in missing:
        ensure_profile(db, client_id)


def _clients_by_recorded_stage(
    db: Session,
    *,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, int]:
    counts = {stage: 0 for stage in FUNNEL_STAGES}
    counts["lead"] = db.scalar(select(func.count()).select_from(Client)) or 0

    status_stmt = (
        select(OrderStatusEvent.to_status, func.count(func.distinct(Order.client_id)))
        .join(Order, OrderStatusEvent.order_id == Order.id)
        .group_by(OrderStatusEvent.to_status)
    )
    if start:
        status_stmt = status_stmt.where(OrderStatusEvent.created_at >= start)
    if end:
        status_stmt = status_stmt.where(OrderStatusEvent.created_at <= end)
    for status, count in db.execute(status_stmt):
        stage = STATUS_TO_STAGE.get(_value(status))
        if stage:
            counts[stage] = max(counts.get(stage, 0), count)

    profile_stmt = select(CrmProfile.lifecycle_stage, func.count()).group_by(CrmProfile.lifecycle_stage)
    for stage, count in db.execute(profile_stmt):
        stage_value = _value(stage)
        counts[stage_value] = max(counts.get(stage_value, 0), count)
    return counts


def _median_stage_minutes(
    db: Session,
    *,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, float | None]:
    stmt = select(OrderStatusEvent).order_by(OrderStatusEvent.order_id, OrderStatusEvent.created_at)
    if start:
        stmt = stmt.where(OrderStatusEvent.created_at >= start)
    if end:
        stmt = stmt.where(OrderStatusEvent.created_at <= end)
    by_order: dict[int, list[OrderStatusEvent]] = {}
    for event in db.scalars(stmt):
        by_order.setdefault(event.order_id, []).append(event)

    durations: dict[str, list[float]] = {
        "lead_to_order": [],
        "order_to_preview": [],
        "preview_to_approved": [],
        "approved_to_delivered": [],
    }
    for events in by_order.values():
        first_by_stage = {}
        for event in events:
            stage = STATUS_TO_STAGE.get(_value(event.to_status))
            if stage and stage not in first_by_stage:
                first_by_stage[stage] = event.created_at
        _append_duration(durations["order_to_preview"], first_by_stage, "order_created", "preview_sent")
        _append_duration(durations["preview_to_approved"], first_by_stage, "preview_sent", "approved")
        _append_duration(durations["approved_to_delivered"], first_by_stage, "approved", "delivered")

    return {key: _median(values) for key, values in durations.items()}


def _append_duration(
    out: list[float],
    first_by_stage: dict[str, datetime],
    start_stage: str,
    end_stage: str,
) -> None:
    if start_stage in first_by_stage and end_stage in first_by_stage:
        minutes = (first_by_stage[end_stage] - first_by_stage[start_stage]).total_seconds() / 60
        if minutes >= 0:
            out.append(minutes)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return round(values[mid], 2)
    return round((values[mid - 1] + values[mid]) / 2, 2)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _json_evidence(evidence: dict) -> dict:
    data = {}
    for key, value in evidence.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, dict):
            data[key] = _json_evidence(value)
        else:
            data[key] = value
    return data
