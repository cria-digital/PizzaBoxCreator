from __future__ import annotations


def test_box_generation_requires_login(api_client):
    r = api_client.post("/api/box-generation/orders/1", json={"mode": "ai"})
    assert r.status_code == 401


def test_box_generation_ai_route(api_authed_client, db, sample_client, sample_template, monkeypatch):
    from app.api import box_generation
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    def fake_generate(order_id, session):
        return repo.order_update_status(session, order_id, "preview_sent"), ["Preview IA fake"]

    monkeypatch.setattr(box_generation, "generate_ai_preview", fake_generate)

    r = api_authed_client.post(f"/api/box-generation/orders/{order['id']}", json={"mode": "ai"})

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "preview_sent"
    assert data["changes_applied"] == ["Preview IA fake"]


def test_box_generation_template_route(api_authed_client, db, sample_client, sample_template, monkeypatch):
    from app.api import box_generation
    from app.db import repositories as repo

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    def fake_generate(order_id, session):
        return repo.order_update_status(session, order_id, "preview_sent"), ["Preview template fake"]

    monkeypatch.setattr(box_generation, "generate_order_preview", fake_generate)

    r = api_authed_client.post(f"/api/box-generation/orders/{order['id']}/template")

    assert r.status_code == 200
    assert r.json()["changes_applied"] == ["Preview template fake"]
