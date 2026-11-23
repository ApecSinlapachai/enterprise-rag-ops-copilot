"""Pydantic v2 schemas for Hybrid RAG queries and grounded citations."""

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
