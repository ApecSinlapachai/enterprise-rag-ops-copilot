"""Grounded RAG answer generator using Gemini structured JSON output + extractive fallback."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.config import Settings
from app.schemas.rag import RAGAnswerLLMOutput
from app.services.embeddings import _is_placeholder_api_key
from app.services.retriever import RetrievalChunk

logger = logging.getLogger(__name__)

# Approximate Gemini 3.8 Flash public pricing per 1M tokens for cost observability.
_INPUT_USD_PER_M = 0.15
_OUTPUT_USD_PER_M = 0.60

_RAG_SYSTEM_PROMPT = (
    "You are an Enterprise B2B SaaS Operations Copilot. "
    "Answer the user's question strictly using the provided retrieved context chunks. "
    "Rules:\n"
    "1) Match the user's language (respond in Thai for Thai or mixed Thai-English queries, "
    "and in English for English queries).\n"
    "2) Every factual claim must be supported by the retrieved chunks, and `cited_chunk_ids` "
    "MUST contain only exact UUIDs from the provided chunks.\n"
    "3) If the retrieved chunks do not contain enough information to answer accurately, "
    "set `is_answerable = false`, `confidence_score <= 0.3`, `cited_chunk_ids = []`, "
    "and explain briefly why in `refusal_reason`.\n"
    "4) Never fabricate policies, error codes, prices, or chunk UUIDs."
)


@dataclass(frozen=True)
class GenerationResult:
    """Output and token/cost telemetry from RAG generation."""

    llm_output: RAGAnswerLLMOutput
    model_name: str
    generation_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    used_fallback: bool = False


def is_rate_limit_error(exc: Exception) -> bool:
    """Return True if an exception represents a Gemini 429 / RESOURCE_EXHAUSTED error."""
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    msg = str(exc).lower()
    return status_code == 429 or "429" in msg or "resource_exhausted" in msg


def classify_fallback_model_name(model_name: str, exc: Exception) -> str:
    """Distinguish Gemini 429 quota/rate-limit fallbacks from other API errors."""
    if is_rate_limit_error(exc):
        return f"{model_name}-429-fallback"
    return f"{model_name}-error-fallback"


def estimate_llm_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for token usage telemetry."""
    cost = (input_tokens / 1_000_000.0) * _INPUT_USD_PER_M + (
        output_tokens / 1_000_000.0
    ) * _OUTPUT_USD_PER_M
    return round(max(0.0, cost), 6)


def _format_context_prompt(query: str, chunks: Sequence[RetrievalChunk]) -> str:
    blocks: list[str] = [f"User Question: {query}", "", "Retrieved Evidence Chunks:"]
    for idx, item in enumerate(chunks, start=1):
        c = item.citation
        blocks.append(
            f"[{idx}] chunk_id={c.chunk_id} | source_key={c.source_key} | "
            f"section={c.section_path} | vec_sim={c.vec_similarity:.3f} | "
            f"fts_rank={c.fts_rank:.3f}\n"
            f"{item.full_content}"
        )
    return "\n".join(blocks)


def _truncate_cleanly(text: str, max_chars: int) -> str:
    """Truncate text on a word boundary and close/strip dangling Markdown markers."""
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped

    cutoff = stripped.rfind(" ", int(max_chars * 0.6), max_chars)
    if cutoff == -1:
        cutoff = max_chars
    truncated = stripped[:cutoff].rstrip()

    # Avoid leaving an unclosed inline code or bold marker at the end.
    if truncated.count("`") % 2 == 1:
        last_tick = truncated.rfind("`")
        if last_tick != -1:
            truncated = truncated[:last_tick].rstrip()
    if truncated.count("**") % 2 == 1:
        last_bold = truncated.rfind("**")
        if last_bold != -1:
            truncated = truncated[:last_bold].rstrip()

    return f"{truncated}..."


def _build_grounded_extractive_output(
    query: str,
    query_language: str,
    chunks: Sequence[RetrievalChunk],
) -> RAGAnswerLLMOutput:
    """Synthesize a deterministic grounded answer from top retrieved chunks."""
    top_chunks = list(chunks[:2])
    primary = top_chunks[0]
    primary_lines = [
        line.strip()
        for line in primary.full_content.splitlines()
        if line.strip() and not line.strip().startswith("| :")
    ]
    excerpt = _truncate_cleanly(" ".join(primary_lines), 900)

    if len(top_chunks) > 1:
        secondary = top_chunks[1]
        sec_lines = [
            line.strip()
            for line in secondary.full_content.splitlines()
            if line.strip() and not line.strip().startswith("| :")
        ]
        sec_excerpt = _truncate_cleanly(" ".join(sec_lines), 450)
    else:
        secondary = None
        sec_excerpt = ""

    if query_language in ("th", "mixed"):
        answer = (
            f"อ้างอิงจากเอกสาร `{primary.citation.source_key}` "
            f"({primary.citation.section_path}):\n{excerpt}"
        )
        if secondary and sec_excerpt:
            answer += (
                f"\n\nข้อมูลเพิ่มเติมจาก `{secondary.citation.source_key}` "
                f"({secondary.citation.section_path}):\n{sec_excerpt}"
            )
    else:
        answer = (
            f"Based on `{primary.citation.source_key}` "
            f"({primary.citation.section_path}):\n{excerpt}"
        )
        if secondary and sec_excerpt:
            answer += (
                f"\n\nAdditional reference from `{secondary.citation.source_key}` "
                f"({secondary.citation.section_path}):\n{sec_excerpt}"
            )

    best_vec = max(c.citation.vec_similarity for c in top_chunks)
    best_fts = max(c.citation.fts_rank for c in top_chunks)
    confidence = min(0.95, max(0.72, max(best_vec, 0.70 + min(best_fts, 0.25))))

    return RAGAnswerLLMOutput(
        is_answerable=True,
        answer=_truncate_cleanly(answer, 2450),
        confidence_score=round(confidence, 3),
        cited_chunk_ids=[c.citation.chunk_id for c in top_chunks],
        refusal_reason=None,
    )


class RAGGenerator:
    """Generates grounded answers with Gemini structured output + resilient fallback."""

    def __init__(self, settings: Settings, force_mock: bool = False) -> None:
        self._settings = settings
        self.model_name = settings.gemini_chat_model
        self.model_chain = settings.gemini_chat_model_chain
        self._use_live_api = (not force_mock) and (
            not _is_placeholder_api_key(settings.gemini_api_key)
        )
        self._client = (
            genai.Client(api_key=settings.gemini_api_key) if self._use_live_api else None
        )

    @property
    def is_live_mode(self) -> bool:
        """Return True when configured to call the live Gemini Chat API."""
        return self._client is not None

    def generate(
        self,
        *,
        query: str,
        query_language: str,
        chunks: Sequence[RetrievalChunk],
    ) -> GenerationResult:
        """Generate a citation-grounded structured response over retrieved chunks."""
        start_ns = time.perf_counter_ns()
        if not chunks:
            elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
            return GenerationResult(
                llm_output=RAGAnswerLLMOutput(
                    is_answerable=False,
                    answer="Insufficient retrieved evidence.",
                    confidence_score=0.0,
                    cited_chunk_ids=[],
                    refusal_reason="No chunks provided to generator.",
                ),
                model_name=self.model_name,
                generation_ms=elapsed_ms,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=0.0,
                used_fallback=True,
            )

        if self._client is None:
            output = _build_grounded_extractive_output(query, query_language, chunks)
            elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
            return GenerationResult(
                llm_output=output,
                model_name=f"{self.model_name}-extractive-fallback",
                generation_ms=elapsed_ms,
                input_tokens=0,
                output_tokens=0,
                estimated_cost_usd=0.0,
                used_fallback=True,
            )

        prompt = _format_context_prompt(query, chunks)
        last_exc: Exception | None = None
        saw_429 = False
        for idx, model_candidate in enumerate(self.model_chain):
            try:
                response = self._client.models.generate_content(
                    model=model_candidate,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_RAG_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=RAGAnswerLLMOutput,
                        temperature=0.1,
                    ),
                )
                parsed = getattr(response, "parsed", None)
                if isinstance(parsed, RAGAnswerLLMOutput):
                    llm_output = parsed
                else:
                    raw_text = getattr(response, "text", "") or ""
                    llm_output = RAGAnswerLLMOutput.model_validate_json(raw_text)

                usage = getattr(response, "usage_metadata", None)
                in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
                out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
                elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
                return GenerationResult(
                    llm_output=llm_output,
                    model_name=model_candidate,
                    generation_ms=elapsed_ms,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    estimated_cost_usd=estimate_llm_cost_usd(in_tok, out_tok),
                    used_fallback=False,
                )
            except Exception as exc:
                last_exc = exc
                saw_429 = saw_429 or is_rate_limit_error(exc)
                has_next = idx + 1 < len(self.model_chain)
                logger.warning(
                    "Gemini generate_content failed on model %s (%s: %s)%s.",
                    model_candidate,
                    type(exc).__name__,
                    exc,
                    "; trying next fallback model"
                    if has_next
                    else "; no fallback models left",
                )

        assert last_exc is not None
        fallback_model = (
            f"{self.model_name}-429-fallback"
            if saw_429
            else classify_fallback_model_name(self.model_name, last_exc)
        )
        logger.warning(
            "All Gemini chat models failed; using grounded extractive fallback (%s).",
            fallback_model,
        )
        output = _build_grounded_extractive_output(query, query_language, chunks)
        elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
        return GenerationResult(
            llm_output=output,
            model_name=fallback_model,
            generation_ms=elapsed_ms,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            used_fallback=True,
        )
