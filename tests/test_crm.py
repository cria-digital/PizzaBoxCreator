from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from app.config import settings


@pytest.fixture
def logged_in(api_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    api_client.post("/login", data={"username": "admin", "password": "test-password-123"})
    return api_client


def test_client_creation_creates_single_crm_profile(db):
    from app.db import repositories as repo

    client = repo.client_create(db, "Pizzaria CRM", "11944443333")
    profile = repo.crm_profile_get(db, client["id"])

    assert profile is not None
    assert profile["classification"] == "new"
    assert profile["lifecycle_stage"] == "lead"

    same_profile = repo.crm_profile_ensure(db, client["id"])
    assert same_profile["id"] == profile["id"]


def test_abandoned_classification_creates_one_reengagement_task(db, sample_client, sample_template):
    from app.db import repositories as repo
    from app.db.models import Order
    from app.services import crm_service

    now = datetime(2026, 9, 2, 12, 0, 0)
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    db.execute(
        update(Order)
        .where(Order.id == order["id"])
        .values(updated_at=now - timedelta(days=15))
    )
    db.commit()

    first = crm_service.classify_client(db, sample_client["id"], now=now)
    second = crm_service.classify_client(db, sample_client["id"], now=now)
    tasks = repo.crm_reengagement_list(db, status="pending", client_id=sample_client["id"])

    assert first["classification"] == "abandoned"
    assert second["classification"] == "abandoned"
    assert len(tasks) == 1
    assert tasks[0]["order_id"] == order["id"]


def test_vip_classification_records_evidence(db, sample_client, sample_template):
    from app.db import repositories as repo
    from app.services import crm_service

    now = datetime(2026, 9, 2, 12, 0, 0)
    for _ in range(3):
        order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
        repo.order_update_status(db, order["id"], "delivered")

    profile = crm_service.classify_client(db, sample_client["id"], now=now)
    events = repo.crm_classification_event_list(db, sample_client["id"])

    assert profile["classification"] == "vip"
    assert profile["classification_reason"] == "criterio_vip_atingido"
    assert events[0]["new_classification"] == "vip"
    assert events[0]["evidence"]["delivered_orders"] == 3


def test_metrics_count_revision_cycles_once_per_client(db, sample_client, sample_template):
    from app.db import repositories as repo
    from app.services import crm_service

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    repo.order_update_status(db, order["id"], "preview_sent")
    repo.order_update_status(db, order["id"], "revision")
    repo.order_update_status(db, order["id"], "preview_sent")
    repo.order_update_status(db, order["id"], "approved")

    metrics = crm_service.crm_metrics(db)

    assert metrics["stage_clients"]["order_created"] == 1
    assert metrics["stage_clients"]["preview_sent"] == 1
    assert metrics["stage_clients"]["revision"] == 1
    assert metrics["stage_clients"]["approved"] == 1
    assert metrics["conversions"]["preview_to_approved"] == 1.0


def test_crm_api_lists_contacts_and_metrics(api_authed_client):
    created = api_authed_client.post(
        "/api/clients",
        json={"name": "Pizzaria API CRM", "phone": "11922221111"},
    ).json()

    contacts = api_authed_client.get("/api/crm/contacts")
    metrics = api_authed_client.get("/api/crm/metrics")
    detail = api_authed_client.get(f"/api/crm/contacts/{created['id']}")

    assert contacts.status_code == 200
    assert any(item["client"]["id"] == created["id"] for item in contacts.json())
    assert metrics.status_code == 200
    assert metrics.json()["contacts_total"] >= 1
    assert detail.status_code == 200
    assert detail.json()["profile"]["client_id"] == created["id"]


def test_crm_funnel_page_renders(logged_in, sample_client):
    r = logged_in.get("/crm/funil")

    assert r.status_code == 200
    assert "CRM e Funil" in r.text
    assert sample_client["name"] in r.text
