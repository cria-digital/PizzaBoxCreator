"""Routes inbound WhatsApp messages to the existing order workflow and sends replies.

The "conversation state" is derived from the client's active order status instead of
a separate state machine: whichever order isn't yet in production/delivered is the
one being edited by the current conversation.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from app.ai.agent import parse_message_to_dict
from app.config import settings
from app.db import repositories as repo
from app.integrations.whatsapp_client import WhatsAppClient, WhatsAppOutsideWindowError
from app.models.commands import OrderStatus
from app.services.logo_service import prepare_logo
from app.services.order_service import approve_order, generate_order_preview
from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

APPROVAL_KEYWORDS = ("aprovado", "aprovo", "pode produzir", "confirmo", "ok pode seguir")

FALLBACK_ERROR_MESSAGE = (
    "Desculpa, tive um problema para processar sua mensagem. "
    "Um atendente vai te chamar em breve para continuar por aqui."
)


def handle_inbound_message(db, value: dict) -> None:
    """Process the `value` object of a WhatsApp webhook `messages` change."""
    contacts = value.get("contacts", [])
    contact_name = contacts[0].get("profile", {}).get("name") if contacts else None

    for msg in value.get("messages", []):
        wamid = msg.get("id")
        if not wamid or not repo.wa_message_claim(db, wamid):
            continue  # sem id, ou ja reivindicado por outra entrega/retry da Meta

        phone = normalize_phone(msg.get("from", ""))
        try:
            order_id = _process_message(db, msg, contact_name, phone)
            if order_id is not None:
                repo.wa_message_set_order(db, wamid, order_id)
        except Exception:
            logger.exception("Falha ao processar mensagem WhatsApp %s", wamid)
            _send_fallback_error(phone)


def send_preview_to_whatsapp(db, order_id: int) -> None:
    """Manually push the current preview image to the client (used by the admin UI)."""
    order = repo.order_get(db, order_id)
    if not order or not order.get("preview_jpg"):
        raise ValueError("Pedido nao tem preview gerado.")

    preview_path = Path(order["preview_jpg"])
    if not preview_path.exists():
        raise ValueError("Arquivo de preview nao encontrado.")

    client = repo.client_get(db, order["client_id"])
    try:
        _send_image(client["phone"], preview_path.read_bytes(),
                    "Segue o preview do seu pedido! Responda aqui com o que quiser ajustar, "
                    "ou \"aprovado\" para seguirmos para producao.")
    except WhatsAppOutsideWindowError as e:
        raise ValueError(str(e)) from e
    except RuntimeError as e:
        # WhatsAppClient() raises this when META_WHATSAPP_TOKEN/META_PHONE_NUMBER_ID
        # aren't configured -- surface it the same way as any other send failure
        # instead of letting it bubble up as an unhandled 500.
        raise ValueError(str(e)) from e


# ---------------------------------------------------------------------------
# Internal routing
# ---------------------------------------------------------------------------

def _process_message(db, msg: dict, contact_name: str | None, phone: str) -> int | None:
    client = repo.client_get_by_phone(db, phone)

    if not client:
        client = repo.client_create(db, contact_name or "Cliente WhatsApp", phone)
        _send_catalog(db, phone)
        return None

    order = repo.order_get_active_for_client(db, client["id"])

    if not order:
        return _handle_template_selection(db, client, phone, msg)

    if msg.get("type") == "image":
        return _handle_image_message(db, client, order, phone, msg)

    text = _extract_text(msg)
    if not text:
        _send_text(phone, "Por aqui consigo processar texto ou uma foto da sua logo.")
        return order["id"]

    if order["status"] == OrderStatus.preview_sent.value and _is_approval(text):
        approve_order(order["id"], db)
        _send_text(phone, "Pedido aprovado! Vamos seguir para producao e em breve entramos em contato.")
        return order["id"]

    return _handle_edit_text(db, order, phone, text)


def _handle_template_selection(db, client: dict, phone: str, msg: dict) -> int | None:
    text = _extract_text(msg)
    template = _match_template(db, text) if text else None
    if not template:
        _send_catalog(db, phone)
        return None

    order = repo.order_create(db, client["id"], template["id"], {})
    _send_text(
        phone,
        f"Pedido criado para {template['display_name']}! Agora me conta: quantas caixas voce quer "
        "(ex: 1000 caixas), telefone para contato, instagram, frase personalizada, tema (kraft "
        "tradicional ou preto premium) e se quer o selo de entrega rapida. Pode mandar a logo em foto tambem.",
    )
    return order["id"]


def _handle_image_message(db, client: dict, order: dict, phone: str, msg: dict) -> int:
    media_id = msg.get("image", {}).get("id")
    wa = WhatsAppClient()
    try:
        content = wa.download_media(media_id)
    finally:
        wa.close()

    logo_path = prepare_logo(
        content, settings.logos_dir / f"client_{client['id']}_{uuid.uuid4().hex[:8]}.png"
    )
    repo.client_update(db, client["id"], logo_path=str(logo_path))
    repo.order_update_edit_data(db, order["id"], {"logo_path": str(logo_path)})

    updated_order, changes = generate_order_preview(order["id"], db)
    _send_preview_reply(phone, updated_order, changes)
    return order["id"]


def _handle_edit_text(db, order: dict, phone: str, text: str) -> int:
    quantidade = _extract_quantity(text)
    if quantidade:
        repo.order_update_quantidade(db, order["id"], quantidade)

    fields = parse_message_to_dict(text)
    if not fields:
        if quantidade:
            _send_text(phone, f"Quantidade definida: {quantidade} caixas. Mais alguma coisa?")
            return order["id"]

        latest = repo.revision_get_latest(db, order["id"])
        if latest:
            from sqlalchemy import update
            from app.db.models import OrderRevision
            stmt = (
                update(OrderRevision)
                .where(OrderRevision.id == latest["id"])
                .values(feedback=text)
            )
            db.execute(stmt)
            db.commit()
        repo.order_update_status(db, order["id"], OrderStatus.revision.value)
        _send_text(
            phone,
            "Entendi! Pode me dizer especificamente o que gostaria de mudar? "
            "(quantidade de caixas, telefone, instagram, frase, tema kraft/premium, "
            "selo de entrega, ou uma foto da logo)",
        )
        return order["id"]

    repo.order_update_edit_data(db, order["id"], fields)
    updated_order, changes = generate_order_preview(order["id"], db)
    if quantidade:
        changes.append(f"Quantidade definida: {quantidade} caixas")
    _send_preview_reply(phone, updated_order, changes)
    return order["id"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

QUANTITY_PATTERN = re.compile(r"(\d{1,6})\s*(caixas?|unidades?|pe[cç]as?)", re.IGNORECASE)


def _extract_quantity(text: str) -> int | None:
    """Only matches a number followed by a unit word, so phone numbers etc. aren't mistaken
    for a quantity."""
    match = QUANTITY_PATTERN.search(text)
    return int(match.group(1)) if match else None


def _extract_text(msg: dict) -> str | None:
    if msg.get("type") == "text":
        return msg.get("text", {}).get("body")
    return None


def _is_approval(text: str) -> bool:
    lowered = text.strip().lower()
    return any(keyword in lowered for keyword in APPROVAL_KEYWORDS)


def _match_template(db, text: str | None) -> dict | None:
    if not text:
        return None
    templates = repo.template_list_active(db)
    stripped = text.strip().lstrip("@").strip()

    if stripped.isdigit():
        idx = int(stripped)
        if 1 <= idx <= len(templates):
            return templates[idx - 1]
        return None

    lowered = stripped.lower()
    for t in templates:
        if lowered in t["display_name"].lower():
            return t
    return None


def _send_catalog(db, phone: str) -> None:
    templates = repo.template_list_active(db)
    if not templates:
        _send_text(phone, "Ainda nao temos modelos cadastrados. Em breve um atendente te chama.")
        return

    lines = ["Bem-vindo a Pizza Box! Escolha um modelo respondendo com o numero:"]
    lines += [f"{i}. {t['display_name']}" for i, t in enumerate(templates, start=1)]
    _send_text(phone, "\n".join(lines))


def _send_preview_reply(phone: str, order: dict, changes: list[str]) -> None:
    preview_path = Path(order["preview_jpg"])
    lines = ["Preview atualizado!"]
    if changes:
        lines.append("Alteracoes: " + ", ".join(changes))
    lines.append('Responda "aprovado" para seguir pra producao, ou me diga o que mais quer mudar.')
    _send_image(phone, preview_path.read_bytes(), "\n".join(lines))


def _send_fallback_error(phone: str) -> None:
    try:
        _send_text(phone, FALLBACK_ERROR_MESSAGE)
    except Exception:
        logger.exception("Falha ao enviar mensagem de fallback para %s", phone)


def _send_text(phone: str, body: str) -> None:
    wa = WhatsAppClient()
    try:
        wa.send_text(phone, body)
    finally:
        wa.close()


def _send_image(phone: str, image_bytes: bytes, caption: str) -> None:
    wa = WhatsAppClient()
    try:
        wa.send_image_bytes(phone, image_bytes, caption=caption)
    finally:
        wa.close()
