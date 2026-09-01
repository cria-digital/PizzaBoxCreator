"""Cost guard for AI image generation previews.

Implements two protection mechanisms:
1. **Cache**: if the same order has been generated with identical parameters within
   a configurable TTL, return the cached preview instead of calling the API again.
2. **Rate limit**: hard cap on the number of AI previews per order within a rolling
   time window, preventing runaway costs (e.g. the client repeatedly asking for tweaks).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import OrderRevision

logger = logging.getLogger(__name__)


def _compute_prompt_hash(edit_data: dict, template_id: int, client_id: int) -> str:
    """Deterministic hash of the parameters that affect the AI output."""
    payload = json.dumps(
        {"ed": edit_data, "t": template_id, "c": client_id},
        sort_keys=True, ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def find_cached_preview(
    db: Session,
    order_id: int,
    edit_data: dict,
    template_id: int,
    client_id: int,
) -> str | None:
    """Return the path of a cached AI preview if one exists and is still valid.

    A cached preview is considered valid if:
    - It was created by the AI image endpoint, not by the PSD/flat preview path.
    - The prompt hash matches (same inputs).
    - It was generated within the last ``ai_preview_cache_ttl_hours`` hours.
    - The file still exists on disk.

    Returns the file path or ``None``.
    """
    if not settings.ai_preview_cache_enabled:
        return None

    prompt_hash = _compute_prompt_hash(edit_data, template_id, client_id)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.ai_preview_cache_ttl_hours)

    stmt = (
        select(OrderRevision)
        .where(OrderRevision.order_id == order_id)
        .where(OrderRevision.created_at >= cutoff)
        .order_by(OrderRevision.created_at.desc())
    )
    for rev in db.scalars(stmt).all():
        if not rev.preview_jpg or rev.preview_source != "ai":
            continue
        rev_hash = _compute_prompt_hash(
            rev.edit_data, template_id, client_id
        )
        if rev_hash == prompt_hash:
            from pathlib import Path
            if Path(rev.preview_jpg).exists():
                logger.info(
                    "AI preview cache hit: order=%s rev=%s hash=%s",
                    order_id, rev.revision_number, prompt_hash,
                )
                return rev.preview_jpg
    return None


def check_rate_limit(db: Session, order_id: int) -> None:
    """Raise ``AIRateLimitExceeded`` if the order has hit the AI preview cap.

    Counts only AI-generated revisions created within the rolling window
    (``ai_preview_rate_window_hours``). Flat/PSD previews do not spend image
    generation credits and must not consume this budget.
    """
    window = timedelta(hours=settings.ai_preview_rate_window_hours)
    cutoff = datetime.now(timezone.utc) - window

    count = db.scalar(
        select(func.count()).select_from(OrderRevision).where(
            OrderRevision.order_id == order_id,
            OrderRevision.created_at >= cutoff,
            OrderRevision.preview_source == "ai",
        )
    ) or 0

    if count >= settings.ai_preview_max_per_order:
        raise AIRateLimitExceeded(
            f"Limite de {settings.ai_preview_max_per_order} previews atingido "
            f"para este pedido nas ultimas {settings.ai_preview_rate_window_hours}h. "
            f"Aguarde ou edite os dados manualmente."
        )


class AIRateLimitExceeded(Exception):
    """Raised when the AI preview rate limit is hit."""
