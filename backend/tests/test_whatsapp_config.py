"""WhatsApp settings screen: persisting Meta credentials via the DB instead of .env,
overlaying them onto the live settings object, and the test-connection action."""

from __future__ import annotations

import pytest

from app.config import settings
from app.db import repositories as repo
from app.services.whatsapp_config import apply_whatsapp_config, mask_secret, merge_blank_with_existing


@pytest.fixture(autouse=True)
def _restore_settings(monkeypatch):
    """apply_whatsapp_config mutates the live settings singleton directly (by design --
    that's how a saved config takes effect without a restart). Register each attribute
    with monkeypatch up front so it's restored after the test regardless of who set it."""
    for attr in ("meta_whatsapp_token", "meta_phone_number_id", "meta_webhook_verify_token",
                "meta_app_secret", "meta_api_version"):
        monkeypatch.setattr(settings, attr, getattr(settings, attr))


@pytest.fixture
def logged_in(api_client, monkeypatch):
    monkeypatch.setattr(settings, "admin_user", "admin")
    monkeypatch.setattr(settings, "admin_password", "test-password-123")
    api_client.post("/login", data={"username": "admin", "password": "test-password-123"},
                    follow_redirects=False)
    return api_client


def test_mask_secret():
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("abcd") == "****"
    assert mask_secret("EAAGtokenlong1234") == "*" * 13 + "1234"


def test_config_set_and_get_roundtrip(db):
    repo.whatsapp_config_set(
        db, token="tok-1", phone_number_id="123", verify_token="verify-1",
        app_secret="secret-1", api_version="v21.0",
    )
    row = repo.whatsapp_config_get(db)
    assert row["token"] == "tok-1"
    assert row["phone_number_id"] == "123"
    assert row["api_version"] == "v21.0"


def test_config_set_upserts_single_row(db):
    repo.whatsapp_config_set(db, token="tok-1", phone_number_id="123", verify_token="v",
                             app_secret="s", api_version="v21.0")
    repo.whatsapp_config_set(db, token="tok-2", phone_number_id="456", verify_token="v2",
                             app_secret="s2", api_version="v22.0")
    row = repo.whatsapp_config_get(db)
    assert row["token"] == "tok-2"
    assert row["phone_number_id"] == "456"
    from sqlalchemy import text
    assert db.execute(text("SELECT COUNT(*) AS n FROM whatsapp_config")).mappings().fetchone()["n"] == 1


def test_merge_blank_keeps_existing_secret(db):
    repo.whatsapp_config_set(db, token="tok-1", phone_number_id="123", verify_token="v1",
                             app_secret="secret-1", api_version="v21.0")
    merged = merge_blank_with_existing(db, "", "456", "", "", "")
    assert merged["token"] == "tok-1"  # blank -> kept
    assert merged["phone_number_id"] == "456"  # provided -> replaced
    assert merged["verify_token"] == "v1"
    assert merged["app_secret"] == "secret-1"
    assert merged["api_version"] == "v21.0"


def test_merge_blank_with_nothing_saved_yet(db):
    merged = merge_blank_with_existing(db, "", "", "", "", "")
    assert merged["api_version"] == "v21.0"
    assert merged["token"] == ""


def test_apply_whatsapp_config_overlays_settings(db, monkeypatch):
    monkeypatch.setattr(settings, "meta_whatsapp_token", "")
    monkeypatch.setattr(settings, "meta_phone_number_id", "")
    repo.whatsapp_config_set(db, token="db-token", phone_number_id="db-phone-id",
                             verify_token="db-verify", app_secret="db-secret",
                             api_version="v23.0")

    apply_whatsapp_config(db)

    assert settings.meta_whatsapp_token == "db-token"
    assert settings.meta_phone_number_id == "db-phone-id"
    assert settings.meta_webhook_verify_token == "db-verify"
    assert settings.meta_app_secret == "db-secret"
    assert settings.meta_api_version == "v23.0"
    assert settings.whatsapp_enabled is True


def test_apply_whatsapp_config_noop_when_unconfigured(db, monkeypatch):
    monkeypatch.setattr(settings, "meta_whatsapp_token", "env-token")
    apply_whatsapp_config(db)  # no row saved yet
    assert settings.meta_whatsapp_token == "env-token"  # untouched


def test_settings_page_requires_login(api_client):
    r = api_client.get("/configuracoes/whatsapp", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "/login" in r.headers["location"]


def test_settings_page_renders(logged_in):
    r = logged_in.get("/configuracoes/whatsapp")
    assert r.status_code == 200
    assert "Integracao WhatsApp" in r.text or "WhatsApp" in r.text


def test_save_persists_and_masks_on_reload(logged_in, db):
    r = logged_in.post("/configuracoes/whatsapp", data={
        "token": "EAAsupersecrettoken",
        "phone_number_id": "999888777",
        "verify_token": "my-verify",
        "app_secret": "app-secret-value",
        "api_version": "v21.0",
    }, follow_redirects=False)
    assert r.status_code == 303

    row = repo.whatsapp_config_get(db)
    assert row["token"] == "EAAsupersecrettoken"
    assert row["phone_number_id"] == "999888777"

    page = logged_in.get("/configuracoes/whatsapp")
    assert "EAAsupersecrettoken" not in page.text  # never echoed back in full
    assert mask_secret("EAAsupersecrettoken") in page.text  # only last 4 chars shown


def test_save_blank_token_keeps_previous_value(logged_in, db):
    logged_in.post("/configuracoes/whatsapp", data={
        "token": "original-token", "phone_number_id": "111", "verify_token": "v",
        "app_secret": "s", "api_version": "v21.0",
    })
    logged_in.post("/configuracoes/whatsapp", data={
        "token": "", "phone_number_id": "222", "verify_token": "v",
        "app_secret": "", "api_version": "v21.0",
    })
    row = repo.whatsapp_config_get(db)
    assert row["token"] == "original-token"
    assert row["phone_number_id"] == "222"


def test_send_test_message_success(logged_in, monkeypatch):
    logged_in.post("/configuracoes/whatsapp", data={
        "token": "tok", "phone_number_id": "123", "verify_token": "v",
        "app_secret": "s", "api_version": "v21.0",
    })

    # Patch WhatsAppClient.send_text itself rather than httpx.Client.post: the TestClient
    # used to drive these web requests is itself httpx-based, so patching the transport
    # layer globally would also break the test client's own requests to the app.
    import app.integrations.whatsapp_client as wc
    monkeypatch.setattr(wc.WhatsAppClient, "send_text",
                       lambda self, to, body: {"messages": [{"id": "wamid.1"}]})

    r = logged_in.post("/configuracoes/whatsapp/testar",
                       data={"telefone_teste": "5511999998888"}, follow_redirects=False)
    assert r.status_code == 303
    assert "msg=" in r.headers["location"]


def test_send_test_message_without_config_shows_error(logged_in, monkeypatch):
    monkeypatch.setattr(settings, "meta_whatsapp_token", "")
    monkeypatch.setattr(settings, "meta_phone_number_id", "")
    r = logged_in.post("/configuracoes/whatsapp/testar",
                       data={"telefone_teste": "5511999998888"}, follow_redirects=False)
    assert r.status_code == 303
    assert "error=" in r.headers["location"]


def test_send_test_message_outside_window(logged_in, monkeypatch):
    logged_in.post("/configuracoes/whatsapp", data={
        "token": "tok", "phone_number_id": "123", "verify_token": "v",
        "app_secret": "s", "api_version": "v21.0",
    })

    import app.integrations.whatsapp_client as wc

    def raise_outside_window(self, to, body):
        raise wc.WhatsAppOutsideWindowError("fora da janela")
    monkeypatch.setattr(wc.WhatsAppClient, "send_text", raise_outside_window)

    r = logged_in.post("/configuracoes/whatsapp/testar",
                       data={"telefone_teste": "5511999998888"}, follow_redirects=False)
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
