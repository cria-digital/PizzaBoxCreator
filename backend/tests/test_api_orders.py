"""Integration tests through the real FastAPI app (TestClient), against a temp SQLite DB.

These avoid the PSD pipeline by not setting edit_data that would trigger preview
generation -- that pipeline is covered separately in test_full_preview_pipeline below.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def test_orders_api_requires_login(api_client, sample_template):
    r = api_client.post(
        "/api/orders",
        json={"client_id": 1, "template_id": sample_template["id"]},
    )
    assert r.status_code == 401


def test_full_order_lifecycle_without_preview(api_authed_client, db, sample_template):
    r = api_authed_client.post("/api/clients", json={"name": "Pizzaria API", "phone": "11977776666"})
    assert r.status_code == 200
    client = r.json()
    assert client["phone"] == "11977776666"

    r = api_authed_client.post(
        "/api/orders",
        json={"client_id": client["id"], "template_id": sample_template["id"], "quantidade": 800},
    )
    assert r.status_code == 200
    order = r.json()
    assert order["status"] == "draft"
    assert order["quantidade"] == 800

    r = api_authed_client.patch(f"/api/orders/{order['id']}", json={"quantidade": 1200})
    assert r.status_code == 200
    assert r.json()["quantidade"] == 1200

    r = api_authed_client.get(f"/api/orders/{order['id']}")
    assert r.status_code == 200
    assert r.json()["quantidade"] == 1200

    r = api_authed_client.patch(f"/api/orders/{order['id']}/status", json={"status": "revision"})
    assert r.status_code == 200
    assert r.json()["status"] == "revision"

    r = api_authed_client.get(f"/api/orders/{order['id']}/audit")
    assert r.status_code == 200
    actions = [entry["action"] for entry in r.json()]
    assert "order_created" in actions
    assert "order_status_updated" in actions


def test_create_order_requires_known_client_or_phone(api_authed_client, sample_template):
    r = api_authed_client.post(
        "/api/orders",
        json={"client_phone": "11900000000", "template_id": sample_template["id"]},
    )
    assert r.status_code == 404  # no client with that phone exists yet


def test_reject_only_allowed_after_preview_sent(api_authed_client, db, sample_client, sample_template):
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    r = api_authed_client.post(f"/api/orders/{order['id']}/reject", json={"feedback": "mudar cor"})
    assert r.status_code == 409


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_TEST_TEMPLATE = PROJECT_ROOT / "gabaritos" / "caixa_35cm_teste.psd"


@pytest.mark.skipif(
    not REAL_TEST_TEMPLATE.exists(),
    reason="rode `python scripts/create_test_template.py` para gerar o PSD de teste",
)
def test_full_preview_pipeline_with_real_template(api_authed_client, db):
    from app.config import settings
    from app.db import repositories as repo

    dest = settings.templates_dir / REAL_TEST_TEMPLATE.name
    shutil.copy(REAL_TEST_TEMPLATE, dest)

    template = repo.template_create(
        db,
        filename=dest.name,
        display_name="Caixa 35cm Real",
        description="Modelo real de teste",
        size_cm=35,
        product_type="pizza",
        editable_fields=[
            {"name": "telefone", "type": "text", "label": "Telefone", "required": False},
        ],
    )

    r = api_authed_client.post("/api/clients", json={"name": "Pizzaria Real", "phone": "11900001111"})
    client = r.json()

    r = api_authed_client.post(
        "/api/orders",
        json={
            "client_id": client["id"],
            "template_id": template["id"],
            "edit_data": {"telefone": "(11) 98888-7777"},
        },
    )
    assert r.status_code == 200
    order = r.json()
    assert order["status"] == "preview_sent"
    assert order["preview_url"] is not None

    r = api_authed_client.get(f"/api/orders/{order['id']}/preview")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"

    r = api_authed_client.post(f"/api/orders/{order['id']}/approve")
    assert r.status_code == 200
    approved = r.json()
    assert approved["status"] == "production"
    assert approved["cmyk_url"] is not None
