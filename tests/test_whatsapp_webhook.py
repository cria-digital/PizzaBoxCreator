"""Webhook endpoint security: signature verification and the verify-token handshake.

This is the most exposed surface of the integration -- it's reachable by anyone on the
internet once configured, so its rejection paths matter as much as the happy path.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

SECRET = "test_secret_123"
VERIFY_TOKEN = "test_verify_456"


@pytest.fixture
def whatsapp_creds(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "meta_app_secret", SECRET)
    monkeypatch.setattr(settings, "meta_webhook_verify_token", VERIFY_TOKEN)


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# GET handshake
# ---------------------------------------------------------------------------

def test_verify_handshake_success(api_client, whatsapp_creds):
    r = api_client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "echo123",
    })
    assert r.status_code == 200
    assert r.text == "echo123"


def test_verify_handshake_wrong_token(api_client, whatsapp_creds):
    r = api_client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "echo123",
    })
    assert r.status_code == 403


def test_verify_handshake_without_configured_token(api_client):
    # meta_webhook_verify_token left empty -- must always reject, never echo the challenge
    r = api_client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "subscribe", "hub.verify_token": "anything", "hub.challenge": "echo123",
    })
    assert r.status_code == 403


def test_verify_handshake_wrong_mode(api_client, whatsapp_creds):
    r = api_client.get("/api/webhooks/whatsapp", params={
        "hub.mode": "unsubscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "echo123",
    })
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST receiver
# ---------------------------------------------------------------------------

def test_receive_webhook_rejects_missing_signature(api_client, whatsapp_creds):
    r = api_client.post("/api/webhooks/whatsapp", json={"entry": []})
    assert r.status_code == 403


def test_receive_webhook_rejects_bad_signature(api_client, whatsapp_creds):
    r = api_client.post(
        "/api/webhooks/whatsapp", json={"entry": []},
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert r.status_code == 403


def test_receive_webhook_rejects_when_secret_not_configured(api_client):
    body = json.dumps({"entry": []}).encode()
    r = api_client.post(
        "/api/webhooks/whatsapp", content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 403


def test_receive_webhook_accepts_valid_signature_and_processes_message(
    api_client, whatsapp_creds, db
):
    from app.db import repositories as repo

    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Cliente Webhook"}}],
                    "messages": [{
                        "from": "5511999990000",
                        "id": "wamid.WEBHOOKTEST1",
                        "type": "text",
                        "text": {"body": "oi"},
                    }],
                }
            }]
        }]
    }
    body = json.dumps(payload).encode()

    r = api_client.post(
        "/api/webhooks/whatsapp", content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 200

    client = repo.client_get_by_phone(db, "5511999990000")
    assert client is not None
    assert client["name"] == "Cliente Webhook"

    # the message was claimed for idempotency -- claiming it again must fail
    assert repo.wa_message_claim(db, "wamid.WEBHOOKTEST1") is False


def test_receive_webhook_ignores_status_callbacks(api_client, whatsapp_creds, db):
    """Delivery/read receipts have no `messages` key and must not be queued for processing."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"id": "wamid.STATUS1", "status": "delivered"}],
                }
            }]
        }]
    }
    body = json.dumps(payload).encode()

    r = api_client.post(
        "/api/webhooks/whatsapp", content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert r.status_code == 200
