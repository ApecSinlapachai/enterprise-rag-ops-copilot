"""Synchronous FastAPI route handlers for knowledge documents and admin ingestion."""

from __future__ import annotations

import hmac
import pathlib

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import Settings
from app.db import DatabaseManager
from app.schemas.rag import (
    CorpusIngestResponse,
    DocumentListItem,
    DocumentListResponse,
)
from app.services.embeddings import EmbeddingService
from app.services.retriever import ingest_markdown_corpus

router = APIRouter(prefix="/api/v1", tags=["documents"])


def _resolve_mock_docs_dir() -> pathlib.Path:
    candidates = (
        pathlib.Path(__file__).resolve().parents[3] / "data" / "mock_docs",
        pathlib.Path.cwd() / "data" / "mock_docs",
        pathlib.Path("/app/data/mock_docs"),
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Knowledge corpus directory data/mock_docs was not found.",
    )


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    """List active knowledge documents and chunk counts from PostgreSQL (sync threadpool)."""
    db: DatabaseManager = request.app.state.db
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                d.id AS document_id,
                d.source_key,
                d.title,
                d.language,
                d.doc_type,
                d.version,
                d.is_active,
                COUNT(dc.id)::INTEGER AS chunk_count,
                d.updated_at
            FROM documents d
            LEFT JOIN document_chunks dc ON dc.document_id = d.id
            WHERE d.is_active = TRUE
            GROUP BY d.id
            ORDER BY d.source_key ASC
            """
        )
        rows = cur.fetchall()

    items = [
        DocumentListItem(
            document_id=row["document_id"],
            source_key=str(row["source_key"]),
            title=str(row["title"]),
            language=row["language"],
            doc_type=row["doc_type"],
            version=str(row["version"]),
            is_active=bool(row["is_active"]),
            chunk_count=int(row["chunk_count"] or 0),
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
    total_chunks = sum(item.chunk_count for item in items)
    return DocumentListResponse(
        total_documents=len(items),
        total_chunks=total_chunks,
        documents=items,
    )


@router.post("/ingest", response_model=CorpusIngestResponse)
def ingest_documents(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> CorpusIngestResponse:
    """Re-ingest data/mock_docs/ into PostgreSQL after constant-time admin token check."""
    settings: Settings = request.app.state.settings
    expected_token = settings.admin_ingest_token.strip()
    if (
        not x_admin_token
        or not expected_token
        or not hmac.compare_digest(x_admin_token.strip(), expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Token header.",
        )

    db: DatabaseManager = request.app.state.db
    embedder: EmbeddingService = request.app.state.embedder
    docs_dir = _resolve_mock_docs_dir()
    summary = ingest_markdown_corpus(db=db, embedder=embedder, docs_dir=docs_dir)
    return CorpusIngestResponse(
        status="ingested",
        documents_processed=summary.documents_processed,
        chunks_written=summary.chunks_written,
        source_keys=summary.source_keys,
    )
