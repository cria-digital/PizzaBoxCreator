"""Web routes for the calibration tool: the editor page and the save endpoint."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.db import repositories as repo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATE = PROJECT_ROOT / "gabaritos" / "caixa_35cm_teste.psd"

pytestmark = pytest.mark.skipif(
    not REAL_TEMPLATE.exists(), reason="rode `python scripts/create_test_template.py` primeiro"
)


@pytest.fixture
def logged_in(api_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    api_client.post("/login", data={"username": "admin", "password": "test-password-123"},
                    follow_redirects=False)
    return api_client


@pytest.fixture
def installed_template(db):
    """A template row whose PSD actually exists in the (tmp) templates dir."""
    dest = settings.templates_dir / "caixa_35cm_teste.psd"
    shutil.copy(REAL_TEMPLATE, dest)
    return repo.template_create(db, filename="caixa_35cm_teste.psd",
                                display_name="Caixa Teste", product_type="pizza")


def test_calibrate_page_renders_with_boxes(logged_in, installed_template):
    r = logged_in.get(f"/catalogo/{installed_template['id']}/calibrar")
    assert r.status_code == 200
    assert "Calibrar campos" in r.text
    assert "TEXTO_TELEFONE" in r.text  # boxes serialized into the page JS


def test_calibrate_save_persists_calibration(logged_in, installed_template, db):
    payload = {
        "TEXTO_TELEFONE": {"x": 700, "y": 1500, "width": 600, "height": 90, "font_size": 72},
        "LOGO_CLIENTE": {"x": 1500, "y": 900, "width": 500, "height": 400},
    }
    r = logged_in.post(f"/catalogo/{installed_template['id']}/calibrar", json=payload)
    assert r.status_code == 200
    assert r.json()["saved"] == 2

    saved = repo.template_get(db, installed_template["id"])["calibration"]
    assert saved["TEXTO_TELEFONE"]["font_size"] == 72
    assert saved["LOGO_CLIENTE"]["width"] == 500


def test_calibrate_save_ignores_junk_entries(logged_in, installed_template, db):
    r = logged_in.post(f"/catalogo/{installed_template['id']}/calibrar",
                       json={"TEXTO_TELEFONE": "not-a-dict", "LOGO_CLIENTE": {"x": 10, "y": 20}})
    assert r.status_code == 200
    saved = repo.template_get(db, installed_template["id"])["calibration"]
    assert "TEXTO_TELEFONE" not in saved
    assert saved["LOGO_CLIENTE"] == {"x": 10, "y": 20}


def test_calibrate_page_requires_login(api_client, installed_template):
    r = api_client.get(f"/catalogo/{installed_template['id']}/calibrar", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "/login" in r.headers.get("location", "")


def test_test_preview_returns_jpeg(logged_in, installed_template):
    payload = {"TEXTO_TELEFONE": {"x": 200, "y": 800, "width": 600, "height": 90, "font_size": 40}}
    r = logged_in.post(f"/catalogo/{installed_template['id']}/test-preview", json=payload)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_test_preview_works_without_calibration_body(logged_in, installed_template):
    r = logged_in.post(f"/catalogo/{installed_template['id']}/test-preview", json={})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
