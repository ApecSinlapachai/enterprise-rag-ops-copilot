"""Pydantic v2 schemas for Hybrid RAG queries, grounded citations, and document inventory."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MAX_CITATION_SNIPPET_LENGTH = 400


def format_citation_snippet(text: str, max_chars: int = 380) -> str:
    """Safely normalize whitespace and truncate chunk text to fit CitationItem.snippet."""
    cleaned = " ".join(text.split())
    safe_limit = min(max(max_chars, 50), MAX_CITATION_SNIPPET_LENGTH - 3)
    if len(cleaned) <= safe_limit:
        return cleaned
    truncated = cleaned[:safe_limit].rsplit(" ", 1)[0]
    if not truncated or len(truncated) < safe_limit // 2:
        truncated = cleaned[:safe_limit]
    return f"{truncated}..."


class RAGQueryRequest(BaseModel):
    """Inbound RAG question payload (bounded for public no-login demo)."""

    query: str = Field(..., min_length=1, max_length=500)
    language_hint: Literal["auto", "th", "en"] = "auto"


class CitationItem(BaseModel):
    """Single retrieved document chunk supporting a grounded RAG answer."""

    chunk_id: UUID
    source_key: str
    doc_title: str
    section_path: str = ""
    snippet: str = Field(..., max_length=400)
    vec_similarity: float = Field(..., ge=-1.0, le=1.0, allow_inf_nan=False)
    fts_rank: float = Field(..., ge=0.0, allow_inf_nan=False)
    rrf_score: float = Field(..., ge=0.0, allow_inf_nan=False)


class RAGAnswerLLMOutput(BaseModel):
    """Structured output contract enforced on Gemini RAG responses."""

    is_answerable: bool
    answer: str = Field(..., min_length=1, max_length=2500)
    confidence_score: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    cited_chunk_ids: list[UUID] = Field(default_factory=list)
    refusal_reason: str | None = None


class RAGQueryResponse(BaseModel):
    """Public RAG API response aligned 1:1 with query_logs CHECK constraints."""

    request_id: str
    query_language: Literal["th", "en", "mixed", "unknown"]
    grounding_status: Literal[
        "ANSWERED",
        "REFUSED_LOW_EVIDENCE",
        "BLOCKED_INJECTION",
        "ERROR_FALLBACK",
    ]
    answer: str
    refusal_reason: str | None = Field(default=None, max_length=500)
    confidence_score: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    citations: list[CitationItem] = Field(default_factory=list)
    retrieval_ms: int = Field(..., ge=0)
    generation_ms: int = Field(..., ge=0)
    total_latency_ms: int = Field(..., ge=0)
    model_name: str
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    estimated_cost_usd: float = Field(0.0, ge=0.0, allow_inf_nan=False)


class DocumentListItem(BaseModel):
    """Active knowledge document summary returned by GET /api/v1/documents."""

    document_id: UUID
    source_key: str
    title: str
    language: Literal["th", "en", "bilingual"]
    doc_type: Literal["sop", "sla", "faq", "security_policy", "runbook", "pricing"]
    version: str
    is_active: bool
    chunk_count: int = Field(..., ge=0)
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Knowledge base document inventory summary."""

    total_documents: int = Field(..., ge=0)
    total_chunks: int = Field(..., ge=0)
    documents: list[DocumentListItem] = Field(default_factory=list)


class CorpusIngestResponse(BaseModel):
    """Admin corpus ingestion result returned by POST /api/v1/ingest."""

    status: Literal["ingested"] = "ingested"
    documents_processed: int = Field(..., ge=0)
    chunks_written: int = Field(..., ge=0)
    source_keys: list[str] = Field(default_factory=list)
