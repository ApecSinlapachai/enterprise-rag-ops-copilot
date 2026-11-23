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
from app.routers import documents_router, eval_router, rag_router, triage_router
from app.services.embeddings import EmbeddingService
from app.services.generator import RAGGenerator
from app.services.rate_limiter import SlidingWindowRateLimiter
from app.services.retriever import HybridRetriever
from app.services.triage_service import TicketTriageService

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
    embedder = EmbeddingService(cfg)
    retriever = HybridRetriever(db=db_manager, embedder=embedder, settings=cfg)
    generator = RAGGenerator(cfg)
    triage_service = TicketTriageService(settings=cfg, db=db_manager)
    rate_limiter = SlidingWindowRateLimiter(
        per_min=cfg.rate_limit_per_min,
        per_day=cfg.rate_limit_per_day,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = cfg
        app.state.db = db_manager
        app.state.embedder = embedder
        app.state.retriever = retriever
        app.state.generator = generator
        app.state.triage_service = triage_service
        app.state.rate_limiter = rate_limiter
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
    app.state.settings = cfg
    app.state.db = db_manager
    app.state.embedder = embedder
    app.state.retriever = retriever
    app.state.generator = generator
    app.state.triage_service = triage_service
    app.state.rate_limiter = rate_limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
        expose_headers=["Retry-After"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        db_ok = db_manager.check_health()
        return HealthResponse(
            status="ok" if db_ok else "degraded",
            version=cfg.app_version,
            database_connected=db_ok,
        )

    app.include_router(rag_router)
    app.include_router(triage_router)
    app.include_router(documents_router)
    app.include_router(eval_router)

    return app


app = create_app()
