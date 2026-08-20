"""Provider-agnostic LLM access: routes text/vision calls to Claude, Gemini or Ollama.

Both `app.ai.agent` (message parsing) and `app.ai.vision` (box-photo analysis) go through here,
so the app works with whichever provider is configured. Selection is driven by settings:
- ai_provider="anthropic" -> Claude only
- ai_provider="gemini"    -> Gemini only
- ai_provider="ollama"    -> local/self-hosted Llama via Ollama for text only
- ai_provider="auto"      -> use whichever key is set (Claude preferred if both).

Each provider SDK is imported lazily and is optional; a missing SDK/key/server raises AIUnavailable.
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ANTHROPIC_TEXT_MODEL = "claude-haiku-4-5"
ANTHROPIC_VISION_MODEL = "claude-haiku-4-5"
GEMINI_MODEL = "gemini-2.5-flash"  # handles both text and vision


class AIUnavailable(RuntimeError):
    """No usable AI provider (no key configured, or the provider SDK isn't installed)."""


def ai_configured() -> bool:
    """True if the selected provider has a key available."""
    try:
        active_provider()
        return True
    except AIUnavailable:
        return False


def active_provider() -> str:
    """Return the provider to use ('anthropic' | 'gemini' | 'ollama'), or raise AIUnavailable."""
    choice = (settings.ai_provider or "auto").lower()
    if choice == "anthropic":
        if settings.anthropic_api_key:
            return "anthropic"
    elif choice == "gemini":
        if settings.gemini_api_key:
            return "gemini"
    elif choice == "ollama":
        if settings.ollama_base_url and settings.ollama_model:
            return "ollama"
    else:  # auto — prefer Anthropic when both are set
        if settings.anthropic_api_key:
            return "anthropic"
        if settings.gemini_api_key:
            return "gemini"
    raise AIUnavailable(
        "Nenhuma IA configurada. Defina ANTHROPIC_API_KEY, GEMINI_API_KEY ou "
        "AI_PROVIDER=ollama com Ollama rodando "
        f"(AI_PROVIDER={choice})."
    )


def text_completion(system: str, user_text: str) -> str:
    """Send a system+user prompt, return the model's raw text response."""
    provider = active_provider()
    if provider == "anthropic":
        return _anthropic_text(system, user_text)
    if provider == "ollama":
        return _ollama_text(system, user_text)
    return _gemini_text(system, user_text)


def vision_completion(system: str, image_bytes: bytes, media_type: str, prompt: str) -> str:
    """Send an image + prompt, return the model's raw text response."""
    provider = active_provider()
    if provider == "anthropic":
        return _anthropic_vision(system, image_bytes, media_type, prompt)
    if provider == "ollama":
        raise AIUnavailable(
            "Ollama/Llama esta configurado apenas para texto. Para analise de foto, "
            "use ANTHROPIC_API_KEY ou GEMINI_API_KEY."
        )
    return _gemini_vision(system, image_bytes, media_type, prompt)


def image_generation(prompt: str, reference: tuple[bytes, str] | None = None) -> bytes:
    """Generate an image from a prompt, returning raw image bytes (PNG).

    Only Gemini generates images here (Claude has no image output), so this needs
    GEMINI_API_KEY regardless of ai_provider. `reference` is an optional (bytes, media_type)
    layout/style guide image passed alongside the prompt.
    """
    if not settings.gemini_api_key:
        raise AIUnavailable("Geracao de imagem requer GEMINI_API_KEY no .env")
    client, types = _gemini()
    parts: list = []
    if reference:
        data, media_type = reference
        parts.append(types.Part.from_bytes(data=data, mime_type=media_type))
    parts.append(prompt)

    resp = client.models.generate_content(
        model=settings.gemini_image_model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_modalities=["Image"],
            image_config=types.ImageConfig(aspect_ratio=settings.ai_preview_aspect_ratio),
        ),
    )

    candidate = resp.candidates[0]
    for part in candidate.content.parts:
        inline = getattr(part, "inline_data", None)
        if inline and inline.data:
            return inline.data
    raise AIUnavailable(
        f"A IA nao retornou imagem (finish_reason={getattr(candidate, 'finish_reason', '?')})"
    )


# --- Anthropic (Claude) ------------------------------------------------------

def _anthropic_client():
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover - anthropic is a core dep
        raise AIUnavailable("SDK 'anthropic' nao instalado") from e
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _anthropic_text(system: str, user_text: str) -> str:
    resp = _anthropic_client().messages.create(
        model=ANTHROPIC_TEXT_MODEL, max_tokens=512, system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    return resp.content[0].text.strip()


def _anthropic_vision(system: str, image_bytes: bytes, media_type: str, prompt: str) -> str:
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    resp = _anthropic_client().messages.create(
        model=ANTHROPIC_VISION_MODEL, max_tokens=512, system=system,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return resp.content[0].text.strip()


# --- Ollama (local/self-hosted Llama) ---------------------------------------

def _ollama_text(system: str, user_text: str) -> str:
    """Call Ollama's local REST API for text-only Llama models."""
    base_url = settings.ollama_base_url.rstrip("/")
    try:
        resp = httpx.post(
            f"{base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text},
                ],
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=60,
        )
        resp.raise_for_status()
    except httpx.RequestError as e:
        raise AIUnavailable(
            f"Ollama indisponivel em {base_url}. Rode `ollama serve` e "
            f"`ollama pull {settings.ollama_model}`."
        ) from e
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:300]
        raise AIUnavailable(f"Ollama retornou erro {e.response.status_code}: {detail}") from e

    payload = resp.json()
    content = payload.get("message", {}).get("content") or payload.get("response") or ""
    if not content.strip():
        raise AIUnavailable("Ollama nao retornou texto.")
    return content.strip()


# --- Gemini (Google) ---------------------------------------------------------

def _gemini():
    """Return (client, types) from the google-genai SDK, or raise AIUnavailable."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise AIUnavailable(
            "SDK do Gemini nao instalado. Rode: pip install -e .[gemini]"
        ) from e
    return genai.Client(api_key=settings.gemini_api_key), types


def _gemini_config(types, system: str):
    """Config compartilhada: sem 'thinking' (extracao estruturada nao precisa; economiza token)."""
    return types.GenerateContentConfig(
        system_instruction=system,
        max_output_tokens=512,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )


def _gemini_text(system: str, user_text: str) -> str:
    client, types = _gemini()
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_text,
        config=_gemini_config(types, system),
    )
    return (resp.text or "").strip()


def _gemini_vision(system: str, image_bytes: bytes, media_type: str, prompt: str) -> str:
    client, types = _gemini()
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=media_type), prompt],
        config=_gemini_config(types, system),
    )
    return (resp.text or "").strip()
