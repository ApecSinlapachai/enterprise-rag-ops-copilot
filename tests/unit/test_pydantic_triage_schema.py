"""Unit tests for Pydantic v2 RAG and Ticket Triage schema contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    CitationItem,
    RAGAnswerLLMOutput,
    RAGQueryRequest,
    RAGQueryResponse,
    TriageTicketExtraction,
    TriageTicketRequest,
    format_citation_snippet,
)


def test_triage_extraction_accepts_valid_thai_en_payload() -> None:
    ticket = TriageTicketExtraction(
        language_detected="mixed",
        category="billing_refund",
        urgency_score=4,
        priority="P1",
        sentiment="negative",
        summary="Customer requests a refund after SLA delay on enterprise invoice.",
        suggested_action="Verify invoice status and escalate to billing operations.",
        suggested_team="billing_ops",
        requires_human_review=True,
        extracted_entities={"invoice_id": "INV-2026-0091"},
    )
    assert ticket.urgency_score == 4
    assert ticket.priority == "P1"


def test_triage_extraction_rejects_non_strict_int_urgency() -> None:
    with pytest.raises(ValidationError):
        TriageTicketExtraction(
            language_detected="en",
            category="technical_incident",
            urgency_score="5",  # type: ignore[arg-type]
            priority="P0",
            sentiment="negative",
            summary="Production API returning 503 errors across all endpoints.",
            suggested_action="Page on-call engineer immediately and check DB pool.",
            suggested_team="l2_engineering",
        )


def test_triage_extraction_rejects_invalid_team_or_category() -> None:
    with pytest.raises(ValidationError):
        TriageTicketExtraction(
            language_detected="th",
            category="unknown_category",  # type: ignore[arg-type]
            urgency_score=2,
            priority="P2",
            sentiment="neutral",
            summary="สอบถามข้อมูลทั่วไปเกี่ยวกับแพ็กเกจองค์กร",
            suggested_action="ตอบกลับข้อมูลแพ็กเกจมาตรฐานให้ลูกค้า",
            suggested_team="l1_support",
        )


def test_rag_schemas_reject_nan_and_out_of_bounds_scores() -> None:
    with pytest.raises(ValidationError):
        CitationItem(
            chunk_id=uuid4(),
            source_key="th_refund_sla_policy.md",
            doc_title="Refund Policy",
            snippet="Valid snippet",
            vec_similarity=float("nan"),
            fts_rank=0.1,
            rrf_score=0.01,
        )

    with pytest.raises(ValidationError):
        RAGAnswerLLMOutput(
            is_answerable=True,
            answer="Grounded answer",
            confidence_score=1.2,
            cited_chunk_ids=[uuid4()],
        )


def test_rag_and_triage_request_length_bounds() -> None:
    with pytest.raises(ValidationError):
        RAGQueryRequest(query="x" * 501)

    with pytest.raises(ValidationError):
        TriageTicketRequest(message="hi")

    valid_resp = RAGQueryResponse(
        request_id="req-001",
        query_language="th",
        grounding_status="REFUSED_LOW_EVIDENCE",
        answer="ไม่พบข้อมูลอ้างอิงที่เพียงพอในเอกสารองค์กร",
        refusal_reason="Evidence below threshold",
        confidence_score=0.0,
        citations=[],
        retrieval_ms=12,
        generation_ms=0,
        total_latency_ms=12,
        model_name="gemini-3.8-flash",
    )
    assert valid_resp.estimated_cost_usd == 0.0


def test_format_citation_snippet_enforces_400_char_pydantic_bound() -> None:
    long_thai_en_chunk = (
        "นโยบายการคืนเงินสำหรับลูกค้า Enterprise B2B SaaS (SLA Refund Policy): " * 15
    )
    assert len(long_thai_en_chunk) > 800

    snippet = format_citation_snippet(long_thai_en_chunk, max_chars=380)
    assert len(snippet) <= 400
    assert snippet.endswith("...")

    citation = CitationItem(
        chunk_id=uuid4(),
        source_key="th_refund_sla_policy.md",
        doc_title="Refund SLA Policy",
        snippet=snippet,
        vec_similarity=0.72,
        fts_rank=0.25,
        rrf_score=0.015,
    )
    assert len(citation.snippet) <= 400
