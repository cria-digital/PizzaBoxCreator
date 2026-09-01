"""WhatsApp Cloud API webhook: verification handshake + inbound message receiver."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.db.session import get_db
from app.services.whatsapp_service import handle_inbound_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"])


@router.get("/webhooks/whatsapp")
def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")

    if (settings.meta_webhook_verify_token and mode == "subscribe"
            and hmac.compare_digest(token or "", settings.meta_webhook_verify_token)):
        return PlainTextResponse(challenge)
    raise HTTPException(403, "Verificacao de webhook invalida")


@router.post("/webhooks/whatsapp")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    if not _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(403, "Assinatura invalida")

    payload = json.loads(raw_body)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if value.get("messages"):
                background_tasks.add_task(_process_value, value)

    # Meta espera 200 rapido -- o processamento pesado roda em background.
    return {"status": "ok"}


def _verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.meta_app_secret:
        logger.warning("META_APP_SECRET nao configurado -- rejeitando webhook")
        return False
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(settings.meta_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, provided)


def _process_value(value: dict) -> None:
    from app.db.session import _get_session_factory
    db = _get_session_factory()()
    try:
        handle_inbound_message(db, value)
    finally:
        db.close()
