"""Pizza Box Agent — FastAPI entry point."""

import logging

from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse

from app.api.routes import router
from app.api.catalog import router as catalog_router
from app.api.clients import router as clients_router
from app.api.orders import router as orders_router
from app.api.stats import router as stats_router
from app.api.whatsapp import router as whatsapp_router
from app.web.views import router as web_router
from app.config import settings
from app.db.session import init_db, get_db
from app.observability import MetricsMiddleware, metrics, setup_structured_logging
from app.services.whatsapp_config import apply_whatsapp_config

setup_structured_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()

    db = next(get_db())
    try:
        apply_whatsapp_config(db)
    finally:
        db.close()

    logging.info("Database: %s", settings.database_url)
    logging.info("Templates dir: %s", settings.templates_dir.resolve())
    logging.info("API key configured: %s", bool(settings.anthropic_api_key))
    logging.info("WhatsApp integration enabled: %s", settings.whatsapp_enabled)
    yield


app = FastAPI(
    title="Pizza Box Agent",
    description="AI-powered pizza box packaging design automation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware)

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

app.include_router(router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(clients_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(whatsapp_router, prefix="/api")
app.include_router(web_router)


@app.get("/health", tags=["health"])
def health():
    """Liveness/readiness probe: confirms the process is up and the database is reachable."""
    db_ok = True
    try:
        db = next(get_db())
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "database": db_ok, "whatsapp_enabled": settings.whatsapp_enabled}


@app.get("/metrics", tags=["observability"])
def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain")


def run():
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)


if __name__ == "__main__":
    run()
