"""End-to-end tests of the conversation router (handle_inbound_message), with the real
WhatsAppClient swapped for a fake that records what would have been sent instead of
calling the Graph API.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_TEST_TEMPLATE = PROJECT_ROOT / "gabaritos" / "caixa_35cm_teste.psd"


@pytest.fixture
def fake_whatsapp(monkeypatch):
    from app.services import whatsapp_service

    sent = []

    class FakeClient:
        def send_text(self, to, body):
            sent.append({"to": to, "type": "text", "body": body})

        def send_image_bytes(self, to, image_bytes, caption=None, filename="preview.jpg"):
            sent.append({"to": to, "type": "image", "caption": caption, "bytes_len": len(image_bytes)})

        def download_media(self, media_id):
            return b"not-a-real-image-but-thats-fine-for-this-test"

        def close(self):
            pass

    monkeypatch.setattr(whatsapp_service, "WhatsAppClient", FakeClient)
    return sent


@pytest.fixture
def real_template(db):
    if not REAL_TEST_TEMPLATE.exists():
        pytest.skip("rode `python scripts/create_test_template.py` primeiro")

    from app.config import settings
    from app.db import repositories as repo

    dest = settings.templates_dir / REAL_TEST_TEMPLATE.name
    shutil.copy(REAL_TEST_TEMPLATE, dest)
    return repo.template_create(
        db, filename=dest.name, display_name="Caixa Real", description="d",
        size_cm=35, product_type="pizza", editable_fields=[],
    )


def _text_message(phone: str, wamid: str, body: str) -> dict:
    return {"messages": [{"from": phone, "id": wamid, "type": "text", "text": {"body": body}}]}


# ---------------------------------------------------------------------------
# New client -> catalog
# ---------------------------------------------------------------------------

def test_new_client_is_created_and_receives_catalog(db, sample_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    value = {
        "contacts": [{"profile": {"name": "Joao"}}],
        "messages": [{"from": "5511988887777", "id": "wamid.1", "type": "text", "text": {"body": "oi"}}],
    }
    handle_inbound_message(db, value)

    client = repo.client_get_by_phone(db, "5511988887777")
    assert client is not None
    assert client["name"] == "Joao"
    assert len(fake_whatsapp) == 1
    assert "Bem-vindo" in fake_whatsapp[0]["body"]


# ---------------------------------------------------------------------------
# Template selection
# ---------------------------------------------------------------------------

def test_existing_client_selects_template_by_number(db, sample_client, sample_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    handle_inbound_message(db, _text_message(sample_client["phone"], "wamid.2", "1"))

    order = repo.order_get_active_for_client(db, sample_client["id"])
    assert order is not None
    assert order["template_id"] == sample_template["id"]
    assert any("Pedido criado" in m["body"] for m in fake_whatsapp)


def test_existing_client_selects_template_by_at_reference(
    db, sample_client, sample_template, fake_whatsapp
):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    handle_inbound_message(
        db,
        _text_message(
            sample_client["phone"],
            "wamid.2ref",
            f"@{sample_template['display_name']}",
        ),
    )

    order = repo.order_get_active_for_client(db, sample_client["id"])
    assert order is not None
    assert order["template_id"] == sample_template["id"]


def test_unmatched_template_selection_resends_catalog(db, sample_client, sample_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    handle_inbound_message(db, _text_message(sample_client["phone"], "wamid.2b", "modelo que nao existe"))

    assert repo.order_get_active_for_client(db, sample_client["id"]) is None
    assert any("Bem-vindo" in m["body"] for m in fake_whatsapp)


# ---------------------------------------------------------------------------
# Editing an active order
# ---------------------------------------------------------------------------

def test_edit_text_updates_order_and_sends_preview(db, sample_client, real_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    order = repo.order_create(db, sample_client["id"], real_template["id"], {})

    handle_inbound_message(
        db, _text_message(sample_client["phone"], "wamid.3", "meu telefone e (11) 98888-7777")
    )

    updated = repo.order_get(db, order["id"])
    assert updated["status"] == "preview_sent"
    assert updated["edit_data"]["telefone"] == "(11) 98888-7777"
    assert any(m["type"] == "image" for m in fake_whatsapp)


def test_quantity_only_message_does_not_trigger_revision(db, sample_client, sample_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    handle_inbound_message(db, _text_message(sample_client["phone"], "wamid.4", "quero 1000 caixas"))

    updated = repo.order_get(db, order["id"])
    assert updated["quantidade"] == 1000
    assert updated["status"] == "draft"
    assert any("1000 caixas" in m["body"] for m in fake_whatsapp)


def test_unrecognized_feedback_marks_order_for_revision(db, sample_client, sample_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    order = repo.order_create(db, sample_client["id"], sample_template["id"], {})

    handle_inbound_message(db, _text_message(sample_client["phone"], "wamid.4b", "nao gostei, mudar tudo"))

    updated = repo.order_get(db, order["id"])
    assert updated["status"] == "revision"


# ---------------------------------------------------------------------------
# Approval flow
# ---------------------------------------------------------------------------

def test_approval_message_moves_order_to_production(db, sample_client, real_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    order = repo.order_create(db, sample_client["id"], real_template["id"], {})
    handle_inbound_message(
        db, _text_message(sample_client["phone"], "wamid.5a", "telefone (11) 98888-7777")
    )
    handle_inbound_message(db, _text_message(sample_client["phone"], "wamid.5b", "aprovado"))

    final = repo.order_get(db, order["id"])
    assert final["status"] == "production"


# ---------------------------------------------------------------------------
# Image (logo) messages
# ---------------------------------------------------------------------------

def test_image_message_saves_logo_and_keeps_order_usable(db, sample_client, real_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    order = repo.order_create(db, sample_client["id"], real_template["id"], {})
    value = {
        "messages": [{
            "from": sample_client["phone"], "id": "wamid.img1", "type": "image",
            "image": {"id": "media123"},
        }],
    }
    handle_inbound_message(db, value)

    updated = repo.order_get(db, order["id"])
    assert "logo_path" in updated["edit_data"]
    # the fake bytes aren't a real image, but that must produce a warning, not a crash
    assert updated["preview_jpg"] is not None


def test_image_without_active_order_starts_ai_pilot(db, sample_client, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import AI_REFERENCES_KEY, AI_WORKFLOW, AI_WORKFLOW_KEY, handle_inbound_message

    value = {
        "messages": [{
            "from": sample_client["phone"], "id": "wamid.ai-img1", "type": "image",
            "image": {"id": "media-ai-1", "mime_type": "image/jpeg"},
        }],
    }
    handle_inbound_message(db, value)

    order = repo.order_get_active_for_client(db, sample_client["id"])
    assert order is not None
    assert order["created_by"] == "whatsapp_ai"
    assert order["edit_data"][AI_WORKFLOW_KEY] == AI_WORKFLOW
    ref_path = Path(order["edit_data"][AI_REFERENCES_KEY][0])
    assert ref_path.exists()
    assert ref_path.read_bytes() == b"not-a-real-image-but-thats-fine-for-this-test"
    assert any("arte IA" in m["body"] for m in fake_whatsapp)


def test_ai_pilot_text_collects_context_without_generating(db, sample_client, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import AI_WORKFLOW, AI_WORKFLOW_KEY, handle_inbound_message

    handle_inbound_message(
        db,
        _text_message(sample_client["phone"], "wamid.ai-start", "criar arte ia"),
    )
    order = repo.order_get_active_for_client(db, sample_client["id"])

    handle_inbound_message(
        db,
        _text_message(
            sample_client["phone"],
            "wamid.ai-context",
            'nome: Pizza Norte, telefone (11) 95555-4444, instagram @pizzanorte, '
            'frase "Pizza quente chega melhor", quero 1000 caixas',
        ),
    )

    updated = repo.order_get(db, order["id"])
    client = repo.client_get(db, sample_client["id"])
    assert updated["edit_data"][AI_WORKFLOW_KEY] == AI_WORKFLOW
    assert updated["quantidade"] == 1000
    assert updated["edit_data"]["telefone"] == "(11) 95555-4444"
    assert updated["edit_data"]["instagram"] == "@pizzanorte"
    assert client["name"] == "Pizza Norte"
    assert any("Para gerar o preview" in m["body"] for m in fake_whatsapp)


def test_ai_pilot_generate_runs_pipeline_and_sends_preview(
    db, sample_client, fake_whatsapp, tmp_path, monkeypatch
):
    from app.config import settings
    from app.db import repositories as repo
    from app.services import whatsapp_service
    from app.services.whatsapp_service import AI_ARTIFACTS_KEY, handle_inbound_message

    spec = tmp_path / "spec.json"
    die = tmp_path / "faca.pdf"
    preview = tmp_path / "preview.jpg"
    spec.write_text("{}", encoding="utf-8")
    die.write_bytes(b"pdf")
    preview.write_bytes(b"jpg-preview")
    monkeypatch.setattr(settings, "gemini_api_key", "gemini-test")
    monkeypatch.setattr(settings, "ai_pilot_spec_path", str(spec))
    monkeypatch.setattr(settings, "ai_pilot_die_pdf_path", str(die))

    def fake_pipeline(**kwargs):
        return {
            "job_id": "wa-test",
            "model": "gemini-3-pro-image",
            "generated": str(tmp_path / "generated.png"),
            "master": {"master": str(tmp_path / "master.png"), "approval_preview": str(preview)},
            "preflight": str(tmp_path / "overlay.jpg"),
            "pdf": {"pdf": str(tmp_path / "arte.pdf")},
            "metadata": str(tmp_path / "pipeline.json"),
        }

    monkeypatch.setattr(whatsapp_service, "run_ai_art_pipeline", fake_pipeline)

    handle_inbound_message(db, {
        "messages": [{
            "from": sample_client["phone"], "id": "wamid.ai-ref", "type": "image",
            "image": {"id": "media-ai-ref", "mime_type": "image/jpeg"},
        }],
    })
    order = repo.order_get_active_for_client(db, sample_client["id"])

    handle_inbound_message(
        db,
        _text_message(sample_client["phone"], "wamid.ai-generate", "gerar arte"),
    )

    updated = repo.order_get(db, order["id"])
    latest = repo.revision_get_latest(db, order["id"])
    assert updated["status"] == "preview_sent"
    assert updated["preview_jpg"] == str(preview)
    assert updated["edit_data"][AI_ARTIFACTS_KEY]["job_id"] == "wa-test"
    assert latest["preview_source"] == "ai_whatsapp"
    assert any(m["type"] == "image" and m["bytes_len"] == len(b"jpg-preview") for m in fake_whatsapp)


# ---------------------------------------------------------------------------
# Idempotency and error fallback
# ---------------------------------------------------------------------------

def test_handle_inbound_message_is_idempotent(db, sample_template, fake_whatsapp):
    from app.db import repositories as repo
    from app.services.whatsapp_service import handle_inbound_message

    value = {
        "contacts": [{"profile": {"name": "Joao"}}],
        "messages": [{"from": "5511988880000", "id": "wamid.dup", "type": "text", "text": {"body": "oi"}}],
    }
    handle_inbound_message(db, value)
    handle_inbound_message(db, value)

    clients = [c for c in repo.client_list(db) if c["phone"] == "5511988880000"]
    assert len(clients) == 1


def test_processing_error_sends_fallback_message(db, sample_client, sample_template, fake_whatsapp):
    """sample_template points at a .psd that doesn't exist on disk, so editing it always
    fails inside generate_order_preview -- this is what exercises the fallback path."""
    from app.db import repositories as repo
    from app.services.whatsapp_service import FALLBACK_ERROR_MESSAGE, handle_inbound_message

    repo.order_create(db, sample_client["id"], sample_template["id"], {})

    handle_inbound_message(
        db, _text_message(sample_client["phone"], "wamid.err1", "meu telefone e (11) 98888-7777")
    )

    assert any(
        m["type"] == "text" and m["body"] == FALLBACK_ERROR_MESSAGE for m in fake_whatsapp
    )
