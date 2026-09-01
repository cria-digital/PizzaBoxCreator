"""Web order create/update forms: field-name mapping and the logo file upload.

Regression coverage for a real bug found while adding logo upload: editable_fields
built from raw PSD layer names (TEXTO_TELEFONE, LOGO_CLIENTE, ...) never matched what
build_edit_command() reads from edit_data (telefone, logo_path, ...), so submitting the
web order form silently did nothing for phone/instagram/frase/logo/selo/forno -- only
tema_fundo happened to work, since that key was already correct by coincidence.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.config import settings
from app.db import repositories as repo
from app.psd.fields import build_editable_fields

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
    psd_path = settings.templates_dir / "caixa_35cm_teste.psd"
    fields = build_editable_fields(psd_path)
    return repo.template_create(db, filename="caixa_35cm_teste.psd",
                                display_name="Caixa Teste", product_type="pizza",
                                editable_fields=fields)


def _fake_image_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_build_editable_fields_uses_editcommand_names(installed_template):
    by_label = {f["label"]: f["name"] for f in installed_template["editable_fields"]}
    assert by_label["Telefone"] == "telefone"
    assert by_label["Instagram"] == "instagram"
    assert by_label["Frase personalizada"] == "frase"
    assert by_label["Logotipo do cliente"] == "logo_path"
    assert by_label["Selo entrega rapida"] == "adicionar_selo_entrega"
    assert by_label["Ilustracao forno a lenha"] == "adicionar_forno_lenha"
    assert by_label["Tema de fundo"] == "tema_fundo"


def test_build_editable_fields_dedupes_mirrored_faces(installed_template):
    """caixa_35cm_teste.psd is a DUPLA template (TEXTO_TELEFONE_2, LOGO_CLIENTE_2, ...).
    Each field must appear once -- the engine already mirrors content to every face,
    so a separate "face 2" field would just be a dead input that maps to nothing."""
    fields = installed_template["editable_fields"]
    names = [f["name"] for f in fields]
    assert len(names) == len(set(names)), f"campos duplicados: {names}"
    assert len(fields) == 7


def test_create_order_via_web_form_applies_phone(logged_in, installed_template, db):
    r = logged_in.post("/pedidos/novo", data={
        "client_phone": "11977776666",
        "client_name": "Pizzaria Form",
        "template_id": str(installed_template["id"]),
        "field_telefone": "(11) 97777-6666",
        "quantidade": "100",
    }, follow_redirects=False)
    assert r.status_code == 303
    order_id = int(r.headers["location"].rstrip("/").split("/")[-1])

    order = repo.order_get(db, order_id)
    assert order["edit_data"]["telefone"] == "(11) 97777-6666"


def test_create_order_via_web_form_uploads_logo(logged_in, installed_template, db):
    files = {"field_logo_path": ("logo.png", _fake_image_bytes(), "image/png")}
    data = {
        "client_phone": "11966665555",
        "client_name": "Pizzaria Logo",
        "template_id": str(installed_template["id"]),
        "field_telefone": "(11) 96666-5555",
        "quantidade": "50",
    }
    r = logged_in.post("/pedidos/novo", data=data, files=files, follow_redirects=False)
    assert r.status_code == 303
    order_id = int(r.headers["location"].rstrip("/").split("/")[-1])

    order = repo.order_get(db, order_id)
    logo_path = order["edit_data"]["logo_path"]
    assert logo_path
    assert Path(logo_path).exists()
    assert Path(logo_path).suffix == ".png"


def test_update_order_replaces_logo(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"], {})

    files = {"logo_path": ("first.png", _fake_image_bytes(), "image/png")}
    r = logged_in.post(f"/pedidos/{order['id']}/update",
                       data={"quantidade": "10"}, files=files, follow_redirects=False)
    assert r.status_code == 303
    first_path = repo.order_get(db, order["id"])["edit_data"]["logo_path"]
    assert Path(first_path).exists()

    files2 = {"logo_path": ("second.png", _fake_image_bytes(), "image/png")}
    logged_in.post(f"/pedidos/{order['id']}/update",
                   data={"quantidade": "10"}, files=files2, follow_redirects=False)
    second_path = repo.order_get(db, order["id"])["edit_data"]["logo_path"]
    assert Path(second_path).exists()
    assert second_path != first_path


def test_update_order_without_new_logo_keeps_existing(logged_in, installed_template, db, sample_client):
    order = repo.order_create(db, sample_client["id"], installed_template["id"], {})
    files = {"logo_path": ("first.png", _fake_image_bytes(), "image/png")}
    logged_in.post(f"/pedidos/{order['id']}/update",
                   data={"quantidade": "10"}, files=files, follow_redirects=False)
    first_path = repo.order_get(db, order["id"])["edit_data"]["logo_path"]

    # Edit again, changing only quantidade, without attaching a new file.
    logged_in.post(f"/pedidos/{order['id']}/update",
                   data={"quantidade": "20", "telefone": "(11) 90000-0000"},
                   follow_redirects=False)
    updated = repo.order_get(db, order["id"])
    assert updated["edit_data"]["logo_path"] == first_path
    assert updated["quantidade"] == 20
