"""Template management: metadata edit, activate/deactivate, delete (with FK guard)."""

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
    shutil.copy(REAL_TEMPLATE, settings.templates_dir / "caixa_35cm_teste.psd")
    return repo.template_create(db, filename="caixa_35cm_teste.psd",
                                display_name="Caixa Teste", product_type="pizza")


# --- repository layer ---

def test_template_list_all_includes_inactive(db, installed_template):
    repo.template_set_active(db, installed_template["id"], False)
    assert installed_template["id"] in {t["id"] for t in repo.template_list_all(db)}
    assert installed_template["id"] not in {t["id"] for t in repo.template_list_active(db)}


def test_template_update_only_touches_whitelisted_fields(db, installed_template):
    updated = repo.template_update(db, installed_template["id"],
                                   display_name="Novo Nome", size_cm=40,
                                   filename="HACK.psd")  # ignored (not whitelisted)
    assert updated["display_name"] == "Novo Nome" and updated["size_cm"] == 40
    assert updated["filename"] == "caixa_35cm_teste.psd"


# --- web layer ---

def test_edit_metadata_route(logged_in, installed_template, db):
    logged_in.post(f"/catalogo/{installed_template['id']}/editar",
                   data={"display_name": "Editado", "product_type": "hamburger", "size_cm": "30"})
    t = repo.template_get(db, installed_template["id"])
    assert t["display_name"] == "Editado" and t["product_type"] == "hamburger" and t["size_cm"] == 30


def test_deactivate_and_reactivate(logged_in, installed_template, db):
    logged_in.post(f"/catalogo/{installed_template['id']}/ativar", data={"active": "0"})
    assert repo.template_get(db, installed_template["id"])["active"] == 0
    logged_in.post(f"/catalogo/{installed_template['id']}/ativar", data={"active": "1"})
    assert repo.template_get(db, installed_template["id"])["active"] == 1


def test_delete_without_orders_removes_template(logged_in, installed_template, db):
    logged_in.post(f"/catalogo/{installed_template['id']}/excluir")
    assert repo.template_get(db, installed_template["id"]) is None


def test_delete_with_orders_deactivates_instead(logged_in, installed_template, db, sample_client):
    repo.order_create(db, sample_client["id"], installed_template["id"], {})
    logged_in.post(f"/catalogo/{installed_template['id']}/excluir")

    t = repo.template_get(db, installed_template["id"])
    assert t is not None and t["active"] == 0  # kept, just deactivated


def test_management_requires_login(api_client, installed_template):
    r = api_client.post(f"/catalogo/{installed_template['id']}/ativar",
                        data={"active": "0"}, follow_redirects=False)
    assert "/login" in r.headers.get("location", "")
