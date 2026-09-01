"""Loads WhatsApp Cloud API credentials configured via the settings screen onto the
live `settings` object, so values saved through /configuracoes/whatsapp take effect
immediately (no restart) and are picked up by WhatsAppClient / the webhook exactly like
the .env-based ones -- both ultimately just set attributes on the same settings instance.
"""

from __future__ import annotations

from app.config import settings
from app.db import repositories as repo

_FIELDS = ("token", "phone_number_id", "verify_token", "app_secret", "api_version")

_SETTINGS_ATTR = {
    "token": "meta_whatsapp_token",
    "phone_number_id": "meta_phone_number_id",
    "verify_token": "meta_webhook_verify_token",
    "app_secret": "meta_app_secret",
    "api_version": "meta_api_version",
}


def apply_whatsapp_config(db) -> None:
    """Overlay DB-saved credentials (if any) onto `settings`. Called at startup and
    right after a save, so .env stays the fallback and the DB is the override."""
    row = repo.whatsapp_config_get(db)
    if not row:
        return
    for field, attr in _SETTINGS_ATTR.items():
        value = row.get(field)
        if value:
            setattr(settings, attr, value)


def merge_blank_with_existing(db, token: str, phone_number_id: str,
                              verify_token: str, app_secret: str, api_version: str) -> dict:
    """Blank secret fields in the form mean "keep what's saved", not "clear it" --
    the masked display never shows the real value to retype."""
    existing = repo.whatsapp_config_get(db) or {}
    return {
        "token": token or existing.get("token") or "",
        "phone_number_id": phone_number_id or existing.get("phone_number_id") or "",
        "verify_token": verify_token or existing.get("verify_token") or "",
        "app_secret": app_secret or existing.get("app_secret") or "",
        "api_version": api_version or existing.get("api_version") or "v21.0",
    }


def mask_secret(value: str | None) -> str:
    """Show only the last 4 characters, so the settings page never displays a full
    token/secret back to the screen (e.g. in a client-facing screenshot)."""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]
