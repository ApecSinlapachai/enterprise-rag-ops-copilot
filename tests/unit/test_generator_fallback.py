"""Unit tests for RAG fallback truncation, Markdown safety, and model fallback chain."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.config import Settings
from app.schemas.rag import CitationItem, RAGAnswerLLMOutput
from app.services.generator import (
    RAGGenerator,
    _truncate_cleanly,
    classify_fallback_model_name,
    should_use_complex_rag_model,
)
from app.services.retriever import RetrievalChunk


class _StubApiError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def test_classify_fallback_model_name_distinguishes_429_and_other_errors() -> None:
    assert (
        classify_fallback_model_name(
            "gemini-3.8-flash",
            _StubApiError("Quota exceeded", code=429),
        )
        == "gemini-3.8-flash-429-fallback"
    )
    assert (
        classify_fallback_model_name(
            "gemini-3.8-flash",
            RuntimeError("429 RESOURCE_EXHAUSTED: rate limit reached"),
        )
        == "gemini-3.8-flash-429-fallback"
    )
    assert (
        classify_fallback_model_name(
            "gemini-3.8-flash",
            _StubApiError("404 NOT_FOUND: model not found", code=404),
        )
        == "gemini-3.8-flash-error-fallback"
    )


def test_truncate_cleanly_preserves_short_text() -> None:
    text = "Short grounded answer with `INV-2026-0091` and **SLA**."
    assert _truncate_cleanly(text, 120) == text


def test_truncate_cleanly_breaks_on_word_boundary_and_strips_dangling_markers() -> None:
    text = (
        "Enterprise SLA guarantees **99.95% uptime** across all regions with `ERR-503` "
        "failover and **automated escalation** within 15 minutes for P1 incidents."
    )
    truncated = _truncate_cleanly(text, 105)
    assert truncated.endswith("...")
    assert len(truncated) <= 108
    # No unclosed bold or backtick markers
    assert truncated.count("**") % 2 == 0
    assert truncated.count("`") % 2 == 0
    # Must not cut mid-word ("incidents" or "within" etc.)
    assert not truncated.endswith("wi...")


def _sample_retrieval_chunk(
    *,
    source_key: str = "01_th_sla_refund_policy.md",
    vec_similarity: float = 0.86,
    fts_rank: float = 0.28,
    rrf_score: float = 0.016,
) -> RetrievalChunk:
    chunk_id = uuid4()
    return RetrievalChunk(
        citation=CitationItem(
            chunk_id=chunk_id,
            source_key=source_key,
            doc_title="Enterprise SLA & Refund Policy",
            section_path="SLA Credit Tiers",
            snippet="Enterprise SLA guarantees 99.95% uptime with 10% credit below 99.9%.",
            vec_similarity=vec_similarity,
            fts_rank=fts_rank,
            rrf_score=rrf_score,
        ),
        full_content="Enterprise SLA guarantees 99.95% uptime with 10% credit below 99.9%.",
    )


def test_settings_gemini_chat_model_chain_deduplicates_and_allows_empty() -> None:
    cfg = Settings(
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_complex_model="gemini-3.8-flash",
        gemini_fallback_models="gemini-3.1-flash-lite, gemini-3.5-flash-lite, ",
    )
    assert cfg.gemini_chat_model_chain == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    ]
    assert cfg.gemini_complex_model_chain == [
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]

    empty_cfg = Settings(
        gemini_chat_model="gemini-3.5-flash-lite",
        gemini_complex_model="gemini-3.8-flash",
        gemini_fallback_models="",
    )
    assert empty_cfg.gemini_chat_model_chain == [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
    ]


def test_should_use_complex_rag_model_routing_signals() -> None:
    strong_single = _sample_retrieval_chunk(vec_similarity=0.86, fts_rank=0.28, rrf_score=0.016)
    assert (
        should_use_complex_rag_model("What is the enterprise uptime SLA?", [strong_single])
        is False
    )

    # Comparison / synthesis keyword triggers complex tier
    assert (
        should_use_complex_rag_model(
            "เปรียบเทียบ Pro และ Enterprise ต่างกันอย่างไร", [strong_single]
        )
        is True
    )

    # Multi-document close RRF triggers complex tier
    second_doc = _sample_retrieval_chunk(
        source_key="02_en_pricing_and_tiers.md",
        vec_similarity=0.82,
        fts_rank=0.20,
        rrf_score=0.014,
    )
    assert should_use_complex_rag_model("Enterprise SLA?", [strong_single, second_doc]) is True

    # Gray-zone vector similarity + weak FTS triggers complex tier
    gray_chunk = _sample_retrieval_chunk(vec_similarity=0.61, fts_rank=0.10, rrf_score=0.010)
    assert should_use_complex_rag_model("Enterprise SLA?", [gray_chunk]) is True


def test_rag_generator_fails_over_to_fallback_model_on_429() -> None:
    cfg = Settings(gemini_api_key="live-placeholder-for-mocked-client")
    generator = RAGGenerator(cfg, force_mock=False)
    chunk = _sample_retrieval_chunk()

    ok_output = RAGAnswerLLMOutput(
        is_answerable=True,
        answer="Enterprise SLA guarantees 99.95% uptime.",
        confidence_score=0.92,
        cited_chunk_ids=[chunk.citation.chunk_id],
        refusal_reason=None,
    )
    usage = SimpleNamespace(prompt_token_count=180, candidates_token_count=32)
    ok_response = SimpleNamespace(parsed=ok_output, text="", usage_metadata=usage)

    mock_models = MagicMock()
    mock_models.generate_content.side_effect = [
        _StubApiError("429 RESOURCE_EXHAUSTED: daily quota reached", code=429),
        ok_response,
    ]
    generator._client = SimpleNamespace(models=mock_models)  # type: ignore[assignment]

    result = generator.generate(
        query="What is the enterprise uptime SLA?",
        query_language="en",
        chunks=[chunk],
    )

    called_models = [c.kwargs["model"] for c in mock_models.generate_content.call_args_list]
    assert called_models == ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
    assert result.model_name == "gemini-3.1-flash-lite"
    assert result.used_fallback is False
    assert result.input_tokens == 180
    assert result.output_tokens == 32
    assert result.estimated_cost_usd > 0.0


def test_rag_generator_routes_complex_query_to_complex_model_first() -> None:
    cfg = Settings(gemini_api_key="live-placeholder-for-mocked-client")
    generator = RAGGenerator(cfg, force_mock=False)
    chunk = _sample_retrieval_chunk()

    ok_output = RAGAnswerLLMOutput(
        is_answerable=True,
        answer="Comparison between Pro and Enterprise SLA tiers.",
        confidence_score=0.94,
        cited_chunk_ids=[chunk.citation.chunk_id],
        refusal_reason=None,
    )
    usage = SimpleNamespace(prompt_token_count=240, candidates_token_count=64)
    ok_response = SimpleNamespace(parsed=ok_output, text="", usage_metadata=usage)

    mock_models = MagicMock()
    mock_models.generate_content.return_value = ok_response
    generator._client = SimpleNamespace(models=mock_models)  # type: ignore[assignment]

    result = generator.generate(
        query="เปรียบเทียบเงื่อนไข SLA ของ Pro และ Enterprise ต่างกันอย่างไร",
        query_language="th",
        chunks=[chunk],
    )

    called_models = [c.kwargs["model"] for c in mock_models.generate_content.call_args_list]
    assert called_models == ["gemini-3.8-flash"]
    assert result.model_name == "gemini-3.8-flash"
    assert result.used_fallback is False


def test_rag_generator_falls_back_to_extractive_when_all_models_429() -> None:
    cfg = Settings(gemini_api_key="live-placeholder-for-mocked-client")
    generator = RAGGenerator(cfg, force_mock=False)
    chunk = _sample_retrieval_chunk()

    mock_models = MagicMock()
    mock_models.generate_content.side_effect = [
        _StubApiError("429 RESOURCE_EXHAUSTED", code=429),
        _StubApiError("429 RESOURCE_EXHAUSTED", code=429),
        _StubApiError("429 RESOURCE_EXHAUSTED", code=429),
    ]
    generator._client = SimpleNamespace(models=mock_models)  # type: ignore[assignment]

    result = generator.generate(
        query="What is the enterprise uptime SLA?",
        query_language="en",
        chunks=[chunk],
    )

    called_models = [c.kwargs["model"] for c in mock_models.generate_content.call_args_list]
    assert called_models == [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    ]
    assert result.model_name == "gemini-3.5-flash-lite-429-fallback"
    assert result.used_fallback is True
    assert result.estimated_cost_usd == 0.0
    assert result.llm_output.cited_chunk_ids == [chunk.citation.chunk_id]
