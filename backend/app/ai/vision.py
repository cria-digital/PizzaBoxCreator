"""Vision analysis of a customer's pizza-box photo using Claude.

Given a photo the customer sends, Claude (a) picks the closest model in our catalog and
(b) reads any contact info already printed on the box (phone / instagram / slogan), so the
order can be pre-filled automatically. It does NOT turn the photo into a print file — printing
still needs a prepared gabarito; this only routes the photo to the right one and extracts data.
"""

from __future__ import annotations

import json
import logging

from app.ai.providers import AIUnavailable, vision_completion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Voce analisa a FOTO de uma caixa de pizza enviada por um cliente de uma \
fabrica de embalagens. Sua tarefa:
1. Escolher, entre os modelos disponiveis, qual mais se parece com a caixa da foto.
2. Ler qualquer dado de contato ja impresso na caixa: telefone, @instagram, frase/slogan.

Responda APENAS com um objeto JSON valido, sem texto extra, neste formato:
{"template_id": <numero do modelo ou null>, "confianca": "alta|media|baixa",
 "telefone": <string ou null>, "instagram": <string ou null>, "frase": <string ou null>}

Se nenhum modelo combinar, use template_id null. So inclua um dado se estiver legivel na foto."""


# Kept for API stability (views/tests import this); vision failures surface as VisionUnavailable.
VisionUnavailable = AIUnavailable


def analyze_box_photo(image_bytes: bytes, templates: list[dict],
                      media_type: str = "image/jpeg") -> dict:
    """Analyze a box photo against the active catalog via the configured AI provider.

    Returns a dict with template_id, confianca, telefone, instagram, frase. Raises
    AIUnavailable (aka VisionUnavailable) when no provider is configured/installed.
    """
    catalog = "\n".join(f'{t["id"]}: {t["display_name"]}' for t in templates)
    system = f"{SYSTEM_PROMPT}\n\nModelos disponiveis:\n{catalog or '(nenhum)'}"

    raw = vision_completion(system, image_bytes, media_type, "Analise esta foto de caixa de pizza.")
    return _coerce(_parse_json(raw), templates)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):  # strip ```json ... ``` fences
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as e:
        logger.error("Visao retornou JSON invalido: %s", raw)
        raise VisionUnavailable("A IA nao retornou um resultado interpretavel") from e
    if not isinstance(data, dict):
        raise VisionUnavailable("A IA retornou um formato inesperado")
    return data


def _coerce(data: dict, templates: list[dict]) -> dict:
    """Normalize the model output and drop a template_id that isn't in the catalog."""
    valid_ids = {t["id"] for t in templates}
    tid = data.get("template_id")
    try:
        tid = int(tid) if tid is not None else None
    except (TypeError, ValueError):
        tid = None
    if tid not in valid_ids:
        tid = None

    def clean(v):
        return v.strip() if isinstance(v, str) and v.strip() else None

    return {
        "template_id": tid,
        "confianca": data.get("confianca") if data.get("confianca") in ("alta", "media", "baixa") else None,
        "telefone": clean(data.get("telefone")),
        "instagram": clean(data.get("instagram")),
        "frase": clean(data.get("frase")),
    }
