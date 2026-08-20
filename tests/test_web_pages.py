"""Smoke tests for the admin dashboard's page-render routes (dashboard, funil, clientes,
catalogo, pedidos) and the htmx partials they depend on -- none of these had any test
coverage before (only the POST/action routes were tested), which is how the missing
/web/buscar-cliente route went unnoticed: the "buscar cliente" button on Novo Pedido
pointed at a route that never existed, and nothing exercised that page to catch it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.db import repositories as repo
from app.psd.fields import build_editable_fields

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_TEMPLATE = PROJECT_ROOT / "gabaritos" / "caixa_35cm_teste.psd"


@pytest.fixture
def logged_in(api_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    api_client.post("/login", data={"username": "admin", "password": "test-password-123"},
                    follow_redirects=False)
    return api_client


@pytest.fixture
def installed_template(db):
    if not REAL_TEMPLATE.exists():
        pytest.skip("rode `python scripts/create_test_template.py` primeiro")
    shutil.copy(REAL_TEMPLATE, settings.templates_dir / "caixa_35cm_teste.psd")
    psd_path = settings.templates_dir / "caixa_35cm_teste.psd"
    fields = build_editable_fields(psd_path)
    return repo.template_create(db, filename="caixa_35cm_teste.psd",
                                display_name="Caixa Teste", product_type="pizza",
                                editable_fields=fields)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def test_dashboard_requires_login(api_client):
    r = api_client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_dashboard_renders_with_data(logged_in, db, sample_client, sample_template):
    repo.order_create(db, sample_client["id"], sample_template["id"], {})
    r = logged_in.get("/")
    assert r.status_code == 200
    assert "Dashboard" in r.text
    assert sample_client["name"] in r.text  # shows up in "Ultimos Pedidos"


# ---------------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------------

def test_funnel_renders_empty(logged_in):
    r = logged_in.get("/funil")
    assert r.status_code == 200
    assert "Funil" in r.text


def test_funnel_groups_orders_by_status(logged_in, db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    repo.order_update_status(db, order["id"], "revision")

    r = logged_in.get("/funil")
    assert r.status_code == 200
    assert sample_client["name"] in r.text


def test_funnel_filters_by_client_id(logged_in, db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    r = logged_in.get(f"/funil?client_id={sample_client['id']}")
    assert r.status_code == 200
    assert f"Pedido #{order['id']}" in r.text or sample_client["name"] in r.text


# ---------------------------------------------------------------------------
# Order create page
# ---------------------------------------------------------------------------

def test_order_create_page_renders(logged_in):
    r = logged_in.get("/pedidos/novo")
    assert r.status_code == 200
    assert "Novo Pedido" in r.text


def test_order_create_page_prefills_found_client(logged_in, sample_client):
    r = logged_in.get(f"/pedidos/novo?client_phone={sample_client['phone']}")
    assert r.status_code == 200
    assert sample_client["name"] in r.text


def test_order_create_page_with_template_shows_fields(logged_in, sample_template):
    r = logged_in.get(f"/pedidos/novo?template_id={sample_template['id']}")
    assert r.status_code == 200
    assert "Telefone" in r.text  # from sample_template's editable_fields fixture


def test_buscar_cliente_partial_found(logged_in, sample_client):
    r = logged_in.get(f"/web/buscar-cliente?client_phone={sample_client['phone']}")
    assert r.status_code == 200
    assert sample_client["name"] in r.text
    assert f'value="{sample_client["id"]}"' in r.text


def test_buscar_cliente_partial_not_found(logged_in):
    r = logged_in.get("/web/buscar-cliente?client_phone=00000000000")
    assert r.status_code == 200
    assert "Nenhum cliente encontrado" in r.text


def test_buscar_cliente_partial_blank_phone(logged_in):
    r = logged_in.get("/web/buscar-cliente?client_phone=")
    assert r.status_code == 200
    assert "Nenhum cliente encontrado" in r.text


def test_buscar_cliente_partial_escapes_client_name(logged_in, db):
    repo.client_create(db, '<script>alert(1)</script>', "11999990000")
    r = logged_in.get("/web/buscar-cliente?client_phone=11999990000")
    assert "<script>" not in r.text
    assert "&lt;script&gt;" in r.text


def test_buscar_cliente_requires_login(api_client):
    r = api_client.get("/web/buscar-cliente?client_phone=123", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


# ---------------------------------------------------------------------------
# Clients page
# ---------------------------------------------------------------------------

def test_clients_page_renders(logged_in, sample_client):
    r = logged_in.get("/clientes")
    assert r.status_code == 200
    assert sample_client["name"] in r.text


def test_clients_page_search_filters(logged_in, db):
    repo.client_create(db, "Pizzaria Alfa", "11911110000")
    repo.client_create(db, "Pizzaria Beta", "11922220000")

    r = logged_in.get("/clientes?search=Alfa")
    assert "Pizzaria Alfa" in r.text
    assert "Pizzaria Beta" not in r.text


# ---------------------------------------------------------------------------
# Catalog page
# ---------------------------------------------------------------------------

def test_catalog_page_renders(logged_in, sample_template):
    r = logged_in.get("/catalogo")
    assert r.status_code == 200
    assert sample_template["display_name"] in r.text


def test_catalog_page_shows_flash_message(logged_in):
    r = logged_in.get("/catalogo?msg=Template+removido")
    assert "Template removido" in r.text


def test_campos_template_partial_renders_fields(logged_in, sample_template):
    r = logged_in.get(f"/web/campos-template/{sample_template['id']}")
    assert r.status_code == 200
    assert "Telefone" in r.text


def test_campos_template_partial_unknown_template(logged_in):
    r = logged_in.get("/web/campos-template/999999")
    assert r.status_code == 200
    assert "nao encontrado" in r.text


# ---------------------------------------------------------------------------
# Order detail page
# ---------------------------------------------------------------------------

def test_order_detail_renders(logged_in, db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    r = logged_in.get(f"/pedidos/{order['id']}")
    assert r.status_code == 200
    assert sample_client["name"] in r.text


def test_order_detail_missing_order_redirects_to_funnel(logged_in):
    r = logged_in.get("/pedidos/999999", follow_redirects=False)
    assert r.status_code == 307 or r.status_code == 303
    assert r.headers["location"] == "/funil"


def test_order_detail_requires_login(api_client, db, sample_client, sample_template):
    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})
    r = api_client.get(f"/pedidos/{order['id']}", follow_redirects=False)
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


# ---------------------------------------------------------------------------
# Order actions via the web routes (approve/reject/deliver/preview) -- these run the
# real PSD pipeline, so they need the synthetic test template on disk.
# ---------------------------------------------------------------------------

def test_generate_preview_web_route(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"],
                              {"telefone": "(11) 90000-0000"})
    r = logged_in.post(f"/pedidos/{order['id']}/preview", follow_redirects=False)
    assert r.status_code == 303
    assert repo.order_get(db, order["id"])["status"] == "preview_sent"


def test_approve_web_route(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"],
                              {"telefone": "(11) 90000-0000"})
    logged_in.post(f"/pedidos/{order['id']}/preview")
    r = logged_in.post(f"/pedidos/{order['id']}/approve", follow_redirects=False)
    assert r.status_code == 303
    assert repo.order_get(db, order["id"])["status"] == "production"


def test_reject_web_route_sets_revision_and_feedback(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"],
                              {"telefone": "(11) 90000-0000"})
    logged_in.post(f"/pedidos/{order['id']}/preview")
    r = logged_in.post(f"/pedidos/{order['id']}/reject", data={"feedback": "muda a cor"},
                       follow_redirects=False)
    assert r.status_code == 303
    updated = repo.order_get(db, order["id"])
    assert updated["status"] == "revision"
    latest = repo.revision_get_latest(db, order["id"])
    assert latest["feedback"] == "muda a cor"


def test_deliver_web_route(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"],
                              {"telefone": "(11) 90000-0000"})
    logged_in.post(f"/pedidos/{order['id']}/preview")
    logged_in.post(f"/pedidos/{order['id']}/approve")
    r = logged_in.post(f"/pedidos/{order['id']}/deliver", follow_redirects=False)
    assert r.status_code == 303
    assert repo.order_get(db, order["id"])["status"] == "delivered"


def test_send_whatsapp_without_config_shows_error(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"],
                              {"telefone": "(11) 90000-0000"})
    logged_in.post(f"/pedidos/{order['id']}/preview")
    r = logged_in.post(f"/pedidos/{order['id']}/whatsapp/enviar", follow_redirects=False)
    assert r.status_code == 303
    assert "wa_error" in r.headers["location"]
