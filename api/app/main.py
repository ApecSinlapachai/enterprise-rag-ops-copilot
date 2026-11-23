"""FastAPI application entrypoint, lifespan management, and health endpoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pythainlp.tokenize import word_tokenize

from app.config import Settings, get_settings
from app.db import DatabaseManager

logger = logging.getLogger(__name__)


def _prewarm_thai_tokenizer() -> None:
    """Pre-load PyThaiNLP newmm dictionary at startup to eliminate first-request latency."""
    try:
        word_tokenize("ทดสอบระบบค้นหาเอกสารภาษาไทย", engine="newmm")
    except Exception as exc:
        logger.warning("PyThaiNLP pre-warm failed: %s", exc)


class HealthResponse(BaseModel):
    """Response payload for GET /health."""

    status: str
    version: str
    database_connected: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = settings or get_settings()
    db_manager = DatabaseManager(cfg.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = cfg
        app.state.db = db_manager
        _prewarm_thai_tokenizer()
        db_manager.open()
        try:
            yield
        finally:
            db_manager.close()

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        db_ok = db_manager.check_health()
        return HealthResponse(
            status="ok" if db_ok else "degraded",
            version=cfg.app_version,
            database_connected=db_ok,
        )

    return app


app = create_app()
