"""Thin wrapper around the WhatsApp Cloud API (Meta Graph API)."""

from __future__ import annotations

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

OUTSIDE_WINDOW_ERROR_CODE = 131047

# Statuses worth retrying: Meta rate limit + transient server errors. 4xx (bad request,
# auth, outside-window) are permanent and must NOT be retried.
_RETRY_STATUS = {429, 500, 502, 503, 504}


class WhatsAppOutsideWindowError(Exception):
    """Meta rejected a free-form message: more than 24h since the customer last wrote.

    Outside that window WhatsApp only allows pre-approved template messages.
    """


class WhatsAppClient:
    def __init__(self):
        if not settings.whatsapp_enabled:
            raise RuntimeError(
                "WhatsApp nao configurado: defina META_WHATSAPP_TOKEN e META_PHONE_NUMBER_ID no .env"
            )
        self.phone_number_id = settings.meta_phone_number_id
        self.base_url = f"https://graph.facebook.com/{settings.meta_api_version}"
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {settings.meta_whatsapp_token}"},
            timeout=30.0,
        )

    def send_text(self, to: str, body: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        return self._post_message(payload)

    def send_image_bytes(self, to: str, image_bytes: bytes, caption: str | None = None,
                         filename: str = "preview.jpg") -> dict:
        media_id = self.upload_media(image_bytes, "image/jpeg", filename)
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": {"id": media_id, **({"caption": caption} if caption else {})},
        }
        return self._post_message(payload)

    def upload_media(self, content: bytes, mime_type: str, filename: str) -> str:
        url = f"{self.base_url}/{self.phone_number_id}/media"
        files = {"file": (filename, content, mime_type)}
        data = {"messaging_product": "whatsapp"}
        resp = self._request("POST", url, data=data, files=files)
        resp.raise_for_status()
        return resp.json()["id"]

    def download_media(self, media_id: str) -> bytes:
        meta_resp = self._request("GET", f"{self.base_url}/{media_id}")
        meta_resp.raise_for_status()
        media_url = meta_resp.json()["url"]

        file_resp = self._request("GET", media_url)
        file_resp.raise_for_status()
        return file_resp.content

    def _request(self, method: str, url: str, *, attempts: int = 3, backoff: float = 0.5,
                 **kwargs) -> httpx.Response:
        """Issue an HTTP request, retrying only transient failures (network errors, 429, 5xx).

        Permanent 4xx responses are returned as-is for the caller to handle (e.g. the
        outside-24h-window error), never retried.
        """
        caller = self._client.post if method == "POST" else self._client.get
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = caller(url, **kwargs)
            except httpx.TransportError as exc:  # connection reset, DNS, read/connect timeout
                last_exc = exc
                if attempt >= attempts:
                    raise
                logger.warning("WhatsApp %s falhou (rede) tentativa %d/%d: %s",
                               method, attempt, attempts, exc)
                time.sleep(backoff * attempt)
                continue

            if resp.status_code in _RETRY_STATUS and attempt < attempts:
                logger.warning("WhatsApp %s status %s, retry %d/%d",
                               method, resp.status_code, attempt, attempts)
                time.sleep(backoff * attempt)
                continue
            return resp

        raise last_exc  # pragma: no cover - only reached if attempts exhausted on TransportError

    def mark_as_read(self, message_id: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        self._post_message(payload)

    def _post_message(self, payload: dict) -> dict:
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        resp = self._request("POST", url, json=payload)
        if resp.status_code >= 400:
            logger.error("WhatsApp API error %s: %s", resp.status_code, resp.text)
            try:
                error_code = resp.json().get("error", {}).get("code")
            except ValueError:
                error_code = None
            if error_code == OUTSIDE_WINDOW_ERROR_CODE:
                raise WhatsAppOutsideWindowError(
                    "Mais de 24h desde a ultima mensagem do cliente -- "
                    "so e possivel responder com um template pre-aprovado pela Meta."
                )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
