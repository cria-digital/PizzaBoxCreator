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
from app.ai.providers import AIUnavailable
from app.config import settings
from app.db import repositories as repo
from app.integrations.whatsapp_client import WhatsAppClient, WhatsAppOutsideWindowError
from app.models.commands import OrderStatus
from app.print_specs.ai_art_pipeline import run_ai_art_pipeline
from app.print_specs.pilot_config import (
    pilot_die_pdf_path,
    pilot_readiness_errors,
    pilot_spec_path,
)
from app.services.logo_service import prepare_logo
from app.services.order_service import approve_order, generate_order_preview
from app.services import crm_service
from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

APPROVAL_KEYWORDS = ("aprovado", "aprovo", "pode produzir", "confirmo", "ok pode seguir")
AI_TRIGGER_KEYWORDS = (
    "gerar arte",
    "gerar a arte",
    "criar arte",
    "criar a arte",
    "gerar caixa",
    "criar caixa",
    "arte ia",
    "ia caixa",
    "piloto ia",
)
AI_WORKFLOW = "ai_box_pilot"
AI_WORKFLOW_KEY = "_workflow"
AI_REFERENCES_KEY = "_reference_paths"
AI_ARTIFACTS_KEY = "_ai_artifacts"

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
    text = _extract_text(msg)

    if not client:
        client = repo.client_create(db, contact_name or "Cliente WhatsApp", phone)
        crm_service.record_interaction(
            db,
            client_id=client["id"],
            channel="whatsapp",
            direction="inbound",
            event_type="message_received",
            payload={"message_type": msg.get("type")},
            idempotency_key=f"wa:{msg.get('id')}:inbound",
            classify=True,
        )
        if _should_start_ai_pilot(msg, text):
            return _start_ai_pilot_order(db, client, phone, msg, text)
        _send_catalog(db, phone)
        crm_service.record_interaction(
            db,
            client_id=client["id"],
            channel="whatsapp",
            direction="outbound",
            event_type="catalog_sent",
            idempotency_key=f"wa:{msg.get('id')}:catalog",
            classify=True,
        )
        return None

    order = repo.order_get_active_for_client(db, client["id"])
    crm_service.record_interaction(
        db,
        client_id=client["id"],
        order_id=order["id"] if order else None,
        channel="whatsapp",
        direction="inbound",
        event_type="message_received",
        payload={"message_type": msg.get("type")},
        idempotency_key=f"wa:{msg.get('id')}:inbound",
        classify=True,
    )

    if not order:
        if _should_start_ai_pilot(msg, text):
            return _start_ai_pilot_order(db, client, phone, msg, text)
        return _handle_template_selection(db, client, phone, msg)

    if _is_ai_pilot_order(order):
        if msg.get("type") == "image":
            return _handle_ai_pilot_image(db, client, order, phone, msg)
        if text:
            return _handle_ai_pilot_text(db, client, order, phone, text)
        _send_text(phone, "Por aqui consigo processar texto ou imagem de referencia da caixa.")
        return order["id"]

    if msg.get("type") == "image":
        return _handle_image_message(db, client, order, phone, msg)

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

    order = repo.order_create(db, client["id"], template["id"], {}, source="whatsapp")
    crm_service.record_interaction(
        db,
        client_id=client["id"],
        order_id=order["id"],
        channel="whatsapp",
        direction="inbound",
        event_type="model_selected",
        payload={"template_id": template["id"]},
        classify=True,
    )
    _send_text(
        phone,
        f"Pedido criado para {template['display_name']}! Agora me conta: quantas caixas voce quer "
        "(ex: 1000 caixas), telefone para contato, instagram, frase personalizada, tema (kraft "
        "tradicional ou preto premium) e se quer o selo de entrega rapida. Pode mandar a logo em foto tambem.",
    )
    return order["id"]


def _start_ai_pilot_order(
    db,
    client: dict,
    phone: str,
    msg: dict,
    text: str | None,
) -> int:
    template = _get_or_create_ai_pilot_template(db)
    edit_data = {
        AI_WORKFLOW_KEY: AI_WORKFLOW,
        "telefone": client.get("phone") or phone,
        "tema_fundo": "premium",
    }
    if client.get("instagram"):
        edit_data["instagram"] = client["instagram"]
    parsed_fields = _parse_edit_fields(text) if text else {}
    if parsed_fields:
        edit_data.update(parsed_fields)

    order = repo.order_create(
        db,
        client["id"],
        template["id"],
        edit_data,
        created_by="whatsapp_ai",
        source="whatsapp",
    )

    if text:
        _apply_client_fields_from_text(db, client, text, order["id"], parsed_fields)
        order = repo.order_get(db, order["id"])

    if msg.get("type") == "image":
        order = _store_ai_reference_from_message(db, client, order, msg)

    if text and _has_ai_trigger(text):
        _generate_ai_pilot_and_send(db, order["id"], phone)
    else:
        _send_text(
            phone,
            "Recebi seu atendimento de arte IA para caixa. Envie uma imagem de referencia/logo "
            "e os dados que precisam aparecer: nome, telefone, Instagram, frase e tema. "
            'Quando estiver tudo certo, responda "gerar arte".',
        )
    return order["id"]


def _handle_ai_pilot_image(db, client: dict, order: dict, phone: str, msg: dict) -> int:
    updated = _store_ai_reference_from_message(db, client, order, msg)
    caption = _extract_text(msg)
    if caption:
        _handle_ai_pilot_text(db, client, updated, phone, caption)
    else:
        total = len(updated["edit_data"].get(AI_REFERENCES_KEY, []))
        _send_text(
            phone,
            f"Imagem recebida como referencia da arte ({total} arquivo(s)). "
            'Quando terminar de mandar os dados, responda "gerar arte".',
        )
    return order["id"]


def _handle_ai_pilot_text(db, client: dict, order: dict, phone: str, text: str) -> int:
    quantidade = _extract_quantity(text)
    if quantidade:
        repo.order_update_quantidade(db, order["id"], quantidade)

    fields = _parse_edit_fields(text)
    if fields:
        repo.order_update_edit_data(db, order["id"], fields)

    _apply_client_fields_from_text(db, client, text, order["id"], fields)

    if _has_ai_trigger(text):
        _generate_ai_pilot_and_send(db, order["id"], phone)
        return order["id"]

    notes = []
    if quantidade:
        notes.append(f"{quantidade} caixas")
    if fields:
        notes.extend(_field_labels(fields))
    if notes:
        _send_text(
            phone,
            "Anotei: " + ", ".join(notes) + '. Para gerar o preview, responda "gerar arte".',
        )
    else:
        _send_text(
            phone,
            'Me mande nome da marca, telefone, Instagram, frase, tema e referencia visual. '
            'Quando estiver pronto, responda "gerar arte".',
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


def _get_or_create_ai_pilot_template(db) -> dict:
    spec = pilot_spec_path()
    display_name = "Piloto IA - Caixa Pizza 35"
    filename = f"ai-pilot:{spec.name}"
    existing = repo.template_get_by_filename(db, filename)
    if existing:
        return existing
    return repo.template_create(
        db,
        filename=filename,
        display_name=display_name,
        description="Fluxo WhatsApp/IA baseado na faca tecnica do piloto.",
        size_cm=35,
        product_type="pizza",
        editable_fields=[],
    )


def _should_start_ai_pilot(msg: dict, text: str | None) -> bool:
    return msg.get("type") == "image" or bool(text and _has_ai_trigger(text))


def _is_ai_pilot_order(order: dict) -> bool:
    return order.get("edit_data", {}).get(AI_WORKFLOW_KEY) == AI_WORKFLOW


def _has_ai_trigger(text: str) -> bool:
    lowered = text.strip().lower()
    return any(keyword in lowered for keyword in AI_TRIGGER_KEYWORDS)


def _parse_edit_fields(text: str) -> dict:
    if _is_generation_command_only(text):
        return {}
    return parse_message_to_dict(text)


def _is_generation_command_only(text: str) -> bool:
    cleaned = text.strip().lower()
    for keyword in AI_TRIGGER_KEYWORDS:
        cleaned = cleaned.replace(keyword, " ")
    cleaned = re.sub(r"[\s.!?,;:-]+", " ", cleaned).strip()
    return not cleaned or cleaned in {"por favor", "pf", "agora"}


def _store_ai_reference_from_message(db, client: dict, order: dict, msg: dict) -> dict:
    media = msg.get("image", {})
    media_id = media.get("id")
    if not media_id:
        raise ValueError("Mensagem de imagem sem media_id.")

    wa = WhatsAppClient()
    try:
        content = wa.download_media(media_id)
    finally:
        wa.close()

    suffix = _image_suffix(media.get("mime_type"))
    ref_dir = settings.temp_dir / "whatsapp_ai_refs"
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_path = ref_dir / f"client_{client['id']}_{uuid.uuid4().hex[:8]}{suffix}"
    ref_path.write_bytes(content)

    edit_data = order["edit_data"]
    refs = list(edit_data.get(AI_REFERENCES_KEY, []))
    refs.append(str(ref_path))
    return repo.order_update_edit_data(db, order["id"], {
        AI_WORKFLOW_KEY: AI_WORKFLOW,
        AI_REFERENCES_KEY: refs,
    })


def _image_suffix(mime_type: str | None) -> str:
    if mime_type == "image/png":
        return ".png"
    if mime_type == "image/webp":
        return ".webp"
    return ".jpg"


def _apply_client_fields_from_text(
    db,
    client: dict,
    text: str,
    order_id: int,
    parsed: dict | None = None,
) -> None:
    fields: dict[str, str] = {}
    name = _extract_business_name(text)
    if name:
        fields["name"] = name

    parsed = parsed if parsed is not None else _parse_edit_fields(text)
    if parsed.get("instagram"):
        fields["instagram"] = parsed["instagram"]

    if fields:
        repo.client_update(db, client["id"], **fields)
        edit_data = {}
        if fields.get("instagram"):
            edit_data["instagram"] = fields["instagram"]
        repo.order_update_edit_data(db, order_id, edit_data)


BUSINESS_NAME_PATTERNS = (
    re.compile(r"(?:nome|marca|pizzaria)\s*(?:da\s+pizzaria|da\s+marca)?\s*[:=-]\s*([^\n,;]+)", re.IGNORECASE),
    re.compile(r"(?:chama|se chama)\s+([^\n,;]+)", re.IGNORECASE),
)


def _extract_business_name(text: str) -> str | None:
    for pattern in BUSINESS_NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip().strip("\"'")
            if 2 <= len(name) <= 80:
                return name
    return None


def _field_labels(fields: dict) -> list[str]:
    labels = {
        "telefone": "telefone",
        "instagram": "Instagram",
        "frase": "frase",
        "tema_fundo": "tema",
        "adicionar_selo_entrega": "selo de entrega",
        "adicionar_forno_lenha": "forno a lenha",
        "logo_path": "logo",
    }
    return [labels.get(key, key) for key in fields.keys()]


def _generate_ai_pilot_and_send(db, order_id: int, phone: str) -> None:
    order = repo.order_get(db, order_id)
    client = repo.client_get(db, order["client_id"])
    template = repo.template_get(db, order["template_id"])
    edit_data = order["edit_data"]

    errors = pilot_readiness_errors()
    if errors:
        _send_text(
            phone,
            "Ainda nao consigo gerar a arte por IA porque falta configuracao do piloto: "
            + "; ".join(errors)
            + ".",
        )
        return

    reference_paths = [
        Path(path) for path in edit_data.get(AI_REFERENCES_KEY, [])
        if Path(path).exists()
    ]
    if not reference_paths:
        _send_text(
            phone,
            "Preciso de pelo menos uma imagem de referencia ou logo antes de gerar a arte.",
        )
        return

    _send_text(phone, "Vou gerar a arte da caixa agora. Isso pode levar alguns minutos.")

    try:
        result = run_ai_art_pipeline(
            job_id=f"wa_order_{order_id}_{uuid.uuid4().hex[:8]}",
            spec_path=pilot_spec_path(),
            die_pdf_path=pilot_die_pdf_path(),
            client=client,
            template=template,
            edit_data=edit_data,
            reference_paths=reference_paths,
            fit_mode="cover",
            tac_max=300,
        )
    except AIUnavailable as e:
        _send_text(phone, f"Nao consegui acionar a IA: {e}")
        return
    except Exception:
        logger.exception("Falha ao gerar arte IA via WhatsApp para pedido %s", order_id)
        _send_text(phone, FALLBACK_ERROR_MESSAGE)
        return

    preview = result.get("master", {}).get("approval_preview")
    if not preview:
        _send_text(phone, "A arte foi processada, mas o preview nao foi encontrado.")
        return

    artifacts = _ai_artifact_summary(result)
    repo.order_set_paths(db, order_id, preview_jpg=preview)
    repo.order_update_status(db, order_id, OrderStatus.preview_sent.value)
    repo.order_update_edit_data(db, order_id, {AI_ARTIFACTS_KEY: artifacts})

    rev_num = repo.revision_count(db, order_id) + 1
    repo.revision_create(
        db,
        order_id,
        rev_num,
        repo.order_get(db, order_id)["edit_data"],
        preview,
        preview_source="ai_whatsapp",
    )

    caption = (
        "Preview da arte IA gerado. Confira texto, telefone, Instagram e posicionamento. "
        'Responda "aprovado" para seguir para producao ou mande os ajustes.'
    )
    _send_image(phone, Path(preview).read_bytes(), caption)


def _ai_artifact_summary(result: dict) -> dict:
    return {
        "job_id": result.get("job_id"),
        "model": result.get("model"),
        "generated": result.get("generated"),
        "master": result.get("master", {}).get("master"),
        "preview": result.get("master", {}).get("approval_preview"),
        "preflight": result.get("preflight"),
        "pdf": result.get("pdf", {}).get("pdf"),
        "metadata": result.get("metadata"),
    }


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
    if msg.get("type") == "image":
        return msg.get("image", {}).get("caption")
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
