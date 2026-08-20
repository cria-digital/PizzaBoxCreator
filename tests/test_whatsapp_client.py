"""WhatsAppClient against a faked httpx.Client -- no real Graph API calls are made."""

from __future__ import annotations

import httpx
import pytest


@pytest.fixture
def configured_whatsapp(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "meta_whatsapp_token", "fake-token")
    monkeypatch.setattr(settings, "meta_phone_number_id", "123456")


def test_init_raises_when_not_configured(monkeypatch):
    from app.config import settings
    from app.integrations.whatsapp_client import WhatsAppClient

    monkeypatch.setattr(settings, "meta_whatsapp_token", "")
    monkeypatch.setattr(settings, "meta_phone_number_id", "")

    with pytest.raises(RuntimeError):
        WhatsAppClient()


def test_send_text_success(configured_whatsapp, monkeypatch):
    from app.integrations.whatsapp_client import WhatsAppClient

    def fake_post(self, url, **kwargs):
        return httpx.Response(
            200, json={"messages": [{"id": "wamid.OUT1"}]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = WhatsAppClient()
    result = client.send_text("5511999998888", "ola")
    assert result["messages"][0]["id"] == "wamid.OUT1"


def test_post_message_raises_outside_window_error(configured_whatsapp, monkeypatch):
    from app.integrations.whatsapp_client import WhatsAppClient, WhatsAppOutsideWindowError

    def fake_post(self, url, **kwargs):
        return httpx.Response(
            403,
            json={"error": {"code": 131047, "message": "outside the 24h window"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = WhatsAppClient()
    with pytest.raises(WhatsAppOutsideWindowError):
        client.send_text("5511999998888", "ola")


def test_post_message_generic_error_raises_http_status_error(configured_whatsapp, monkeypatch):
    from app.integrations.whatsapp_client import WhatsAppClient

    def fake_post(self, url, **kwargs):
        return httpx.Response(
            401, json={"error": {"code": 190, "message": "invalid token"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = WhatsAppClient()
    with pytest.raises(httpx.HTTPStatusError):
        client.send_text("5511999998888", "ola")


def test_upload_media_returns_id(configured_whatsapp, monkeypatch):
    from app.integrations.whatsapp_client import WhatsAppClient

    def fake_post(self, url, **kwargs):
        return httpx.Response(200, json={"id": "media-abc-123"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = WhatsAppClient()
    media_id = client.upload_media(b"fake-bytes", "image/jpeg", "logo.jpg")
    assert media_id == "media-abc-123"


def test_send_image_bytes_uploads_then_sends(configured_whatsapp, monkeypatch):
    from app.integrations.whatsapp_client import WhatsAppClient

    calls = []

    def fake_post(self, url, **kwargs):
        calls.append(url)
        if url.endswith("/media"):
            return httpx.Response(200, json={"id": "media-xyz"}, request=httpx.Request("POST", url))
        return httpx.Response(
            200, json={"messages": [{"id": "wamid.IMG1"}]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    client = WhatsAppClient()
    result = client.send_image_bytes("5511999998888", b"jpeg-bytes", caption="oi")
    assert result["messages"][0]["id"] == "wamid.IMG1"
    assert calls[0].endswith("/media")
    assert calls[1].endswith("/messages")


def test_retries_transient_5xx_then_succeeds(configured_whatsapp, monkeypatch):
    import app.integrations.whatsapp_client as wc
    from app.integrations.whatsapp_client import WhatsAppClient

    monkeypatch.setattr(wc.time, "sleep", lambda *_: None)  # no real backoff
    attempts = {"n": 0}

    def flaky_post(self, url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503, text="overloaded", request=httpx.Request("POST", url))
        return httpx.Response(200, json={"messages": [{"id": "wamid.OK"}]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", flaky_post)
    client = WhatsAppClient()
    assert client.send_text("5511999998888", "ola")["messages"][0]["id"] == "wamid.OK"
    assert attempts["n"] == 3


def test_retries_network_error_then_raises(configured_whatsapp, monkeypatch):
    import app.integrations.whatsapp_client as wc
    from app.integrations.whatsapp_client import WhatsAppClient

    monkeypatch.setattr(wc.time, "sleep", lambda *_: None)
    attempts = {"n": 0}

    def broken_post(self, url, **kwargs):
        attempts["n"] += 1
        raise httpx.ConnectError("connection reset", request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", broken_post)
    client = WhatsAppClient()
    with pytest.raises(httpx.ConnectError):
        client.send_text("5511999998888", "ola")
    assert attempts["n"] == 3  # retried up to the limit


def test_does_not_retry_permanent_4xx(configured_whatsapp, monkeypatch):
    import app.integrations.whatsapp_client as wc
    from app.integrations.whatsapp_client import WhatsAppClient

    monkeypatch.setattr(wc.time, "sleep", lambda *_: None)
    attempts = {"n": 0}

    def bad_request(self, url, **kwargs):
        attempts["n"] += 1
        return httpx.Response(400, json={"error": {"code": 100}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx.Client, "post", bad_request)
    client = WhatsAppClient()
    with pytest.raises(httpx.HTTPStatusError):
        client.send_text("5511999998888", "ola")
    assert attempts["n"] == 1  # 4xx is permanent, no retry


def test_download_media_fetches_url_then_content(configured_whatsapp, monkeypatch):
    from app.integrations.whatsapp_client import WhatsAppClient

    calls = []

    def fake_get(self, url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return httpx.Response(
                200, json={"url": "https://lookaside.fbcdn.net/whatever"},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(200, content=b"raw-image-bytes", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    client = WhatsAppClient()
    data = client.download_media("media-id-1")
    assert data == b"raw-image-bytes"
    assert calls[0].endswith("/media-id-1")
    assert calls[1] == "https://lookaside.fbcdn.net/whatever"
