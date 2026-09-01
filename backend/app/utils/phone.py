"""Phone number normalization shared by the web forms, API and WhatsApp webhook."""

from __future__ import annotations

import re


def normalize_phone(raw: str) -> str:
    """Strip everything but digits so numbers from different sources can be matched."""
    return re.sub(r"\D", "", raw or "")
