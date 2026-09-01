"""Shared configuration helpers for the AI box pilot."""

from __future__ import annotations

from pathlib import Path

from app.config import settings


def pilot_spec_path() -> Path:
    return Path(settings.ai_pilot_spec_path)


def pilot_die_pdf_path() -> Path:
    configured = (settings.ai_pilot_die_pdf_path or "").strip()
    if configured:
        return Path(configured)
    return Path.home() / "Downloads" / "Pizzabox" / "COD. PA 35 008 - CX. PIZZA ALCAPIZZA 35.pdf"


def pilot_readiness_errors(*, require_gemini: bool = True) -> list[str]:
    errors: list[str] = []
    if require_gemini and not settings.gemini_api_key:
        errors.append("GEMINI_API_KEY nao esta configurada")
    if not pilot_spec_path().exists():
        errors.append(f"spec da faca nao encontrada: {pilot_spec_path()}")
    if not pilot_die_pdf_path().exists():
        errors.append(f"PDF da faca nao encontrado: {pilot_die_pdf_path()}")
    return errors
