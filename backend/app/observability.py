"""Lightweight observability: structured logging, request metrics, and a /metrics endpoint.

Provides:
- JSON structured logging (replaces plain text logs)
- Per-endpoint request count and latency tracking
- A /metrics endpoint exposing basic Prometheus-compatible counters
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


# ---------------------------------------------------------------------------
# Structured JSON logger
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects for easy parsing by log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False)


def setup_structured_logging(level: str = "INFO") -> None:
    """Replace the default logging config with a JSON formatter."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# Request metrics (in-memory, process-lifetime)
# ---------------------------------------------------------------------------

class _Metrics:
    """Simple in-memory metrics store. Good enough for a single-instance deployment."""

    def __init__(self) -> None:
        self.request_count: dict[str, int] = defaultdict(int)
        self.request_errors: dict[str, int] = defaultdict(int)
        self.request_latency_ms: dict[str, list[float]] = defaultdict(list)
        self.ai_preview_count: int = 0
        self.ai_preview_cache_hits: int = 0
        self.orders_created: int = 0
        self.orders_approved: int = 0
        self.started_at: float = time.time()

    def record_request(self, method: str, path: str, status: int, latency_ms: float) -> None:
        key = f"{method} {path}"
        self.request_count[key] += 1
        self.request_latency_ms[key].append(latency_ms)
        if status >= 400:
            self.request_errors[key] += 1

    def to_prometheus(self) -> str:
        """Format metrics in Prometheus text exposition format."""
        lines: list[str] = []
        uptime = time.time() - self.started_at

        lines.append("# HELP pizzabox_uptime_seconds Process uptime in seconds")
        lines.append("# TYPE pizzabox_uptime_seconds gauge")
        lines.append(f"pizzabox_uptime_seconds {uptime:.1f}")

        lines.append("# HELP pizzabox_http_requests_total Total HTTP requests by endpoint")
        lines.append("# TYPE pizzabox_http_requests_total counter")
        for key, count in sorted(self.request_count.items()):
            method, path = key.split(" ", 1)
            lines.append(
                f'pizzabox_http_requests_total{{method="{method}",path="{path}"}} {count}'
            )

        lines.append("# HELP pizzabox_http_errors_total Total HTTP errors (4xx/5xx) by endpoint")
        lines.append("# TYPE pizzabox_http_errors_total counter")
        for key, count in sorted(self.request_errors.items()):
            method, path = key.split(" ", 1)
            lines.append(
                f'pizzabox_http_errors_total{{method="{method}",path="{path}"}} {count}'
            )

        lines.append("# HELP pizzabox_ai_previews_total Total AI preview generations")
        lines.append("# TYPE pizzabox_ai_previews_total counter")
        lines.append(f"pizzabox_ai_previews_total {self.ai_preview_count}")

        lines.append("# HELP pizzabox_ai_cache_hits_total Total AI preview cache hits")
        lines.append("# TYPE pizzabox_ai_cache_hits_total counter")
        lines.append(f"pizzabox_ai_cache_hits_total {self.ai_preview_cache_hits}")

        lines.append("# HELP pizzabox_orders_created_total Total orders created")
        lines.append("# TYPE pizzabox_orders_created_total counter")
        lines.append(f"pizzabox_orders_created_total {self.orders_created}")

        lines.append("# HELP pizzabox_orders_approved_total Total orders approved")
        lines.append("# TYPE pizzabox_orders_approved_total counter")
        lines.append(f"pizzabox_orders_approved_total {self.orders_approved}")

        return "\n".join(lines) + "\n"


metrics = _Metrics()


# ---------------------------------------------------------------------------
# Middleware: request timing + metrics collection
# ---------------------------------------------------------------------------

class MetricsMiddleware(BaseHTTPMiddleware):
    """Track request count, latency, and errors for every endpoint."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Normalize path: strip query params, collapse IDs
        path = request.url.path
        # Replace numeric IDs with {id} for grouping
        import re
        normalized = re.sub(r"/\d+", "/{id}", path)

        metrics.record_request(request.method, normalized, response.status_code, elapsed_ms)

        # Attach timing header
        response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return response
