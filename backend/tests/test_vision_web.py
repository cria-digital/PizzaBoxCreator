"""The photo-analysis endpoint (vision service patched)."""

from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture
def logged_in(api_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    api_client.post("/login", data={"username": "admin", "password": "test-password-123"},
                    follow_redirects=False)
    return api_client


def test_analyze_photo_requires_login(api_client):
    r = api_client.post("/pedidos/analisar-foto",
                        files={"foto": ("box.jpg", b"data", "image/jpeg")},
                        follow_redirects=False)
    assert r.status_code in (302, 303, 307)


def test_analyze_photo_returns_suggestion(logged_in, db, sample_template, monkeypatch):
    import app.web.views as views

    def fake_analyze(image_bytes, templates, media_type="image/jpeg"):
        return {"template_id": sample_template["id"], "confianca": "alta",
                "telefone": "(11) 98888-7777", "instagram": "@x", "frase": None}

    monkeypatch.setattr(views, "analyze_box_photo", fake_analyze)
    r = logged_in.post("/pedidos/analisar-foto",
                       files={"foto": ("box.jpg", b"jpeg-bytes", "image/jpeg")})
    assert r.status_code == 200
    data = r.json()
    assert data["template_id"] == sample_template["id"]
    assert data["template_name"] == sample_template["display_name"]
    assert data["telefone"] == "(11) 98888-7777"


def test_analyze_photo_reports_vision_unavailable(logged_in, monkeypatch):
    import app.web.views as views
    from app.ai.vision import VisionUnavailable

    def unavailable(*a, **k):
        raise VisionUnavailable("ANTHROPIC_API_KEY nao configurada")

    monkeypatch.setattr(views, "analyze_box_photo", unavailable)
    r = logged_in.post("/pedidos/analisar-foto",
                       files={"foto": ("box.jpg", b"x", "image/jpeg")})
    assert r.status_code == 503
    assert "ANTHROPIC_API_KEY" in r.json()["error"]
