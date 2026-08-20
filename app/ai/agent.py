"""LLM agent that converts natural language to structured EditCommands."""

from __future__ import annotations

import json
import logging

import pydantic

from app.ai.prompts import SYSTEM_PROMPT
from app.ai.providers import ai_configured, text_completion
from app.models.commands import EditCommand

logger = logging.getLogger(__name__)


class DesignAgent:
    def parse_message(self, message: str, logo_path: str | None = None) -> EditCommand:
        """Send the user message to the configured AI, return an EditCommand."""
        raw = text_completion(SYSTEM_PROMPT, message)
        logger.info("LLM response: %s", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("LLM retornou JSON invalido: %s", raw)
            raise ValueError("Nao foi possivel interpretar a resposta do assistente") from e

        if not isinstance(data, dict):
            logger.error("LLM retornou JSON que nao e um objeto: %s", raw)
            raise ValueError("A resposta do assistente nao bateu com os campos esperados")

        if "erro" in data:
            raise ValueError(f"LLM escalou para humano: {data.get('motivo', 'sem motivo')}")

        if logo_path:
            data["logo_path"] = logo_path

        try:
            return EditCommand(**data)
        except pydantic.ValidationError as e:
            logger.error("LLM retornou campos invalidos: %s", data)
            raise ValueError("A resposta do assistente nao bateu com os campos esperados") from e


def parse_message_to_dict(message: str) -> dict:
    """Parse natural language into an edit_data dict, using the AI when configured."""
    if ai_configured():
        cmd = DesignAgent().parse_message(message)
    else:
        cmd = parse_message_offline(message)

    return {k: v for k, v in cmd.model_dump().items() if v is not None and v is not False}


def parse_message_offline(message: str) -> EditCommand:
    """Fallback parser using simple keyword matching (no LLM needed)."""
    msg = message.lower()
    cmd: dict = {}

    import re

    tel_match = re.search(r"\(?\d{2}\)?\s*\d{4,5}[-.\s]?\d{4}", message)
    if tel_match:
        cmd["telefone"] = tel_match.group()

    ig_match = re.search(r"@[\w.]+", message)
    if ig_match:
        cmd["instagram"] = ig_match.group()

    if any(k in msg for k in ["premium", "preto", "escuro", "elegante"]):
        cmd["tema_fundo"] = "premium"
    elif any(k in msg for k in ["kraft", "tradicional", "marrom"]):
        cmd["tema_fundo"] = "tradicional"

    if any(k in msg for k in ["entrega", "delivery", "selo"]):
        cmd["adicionar_selo_entrega"] = True

    if any(k in msg for k in ["forno", "lenha", "artesanal"]):
        cmd["adicionar_forno_lenha"] = True

    frase_patterns = [
        r"frase[:\s]+[\"'](.+?)[\"']",
        r"slogan[:\s]+[\"'](.+?)[\"']",
        r"escrever[:\s]+[\"'](.+?)[\"']",
    ]
    for pat in frase_patterns:
        m = re.search(pat, message, re.IGNORECASE)
        if m:
            cmd["frase"] = m.group(1)
            break

    return EditCommand(**cmd)
