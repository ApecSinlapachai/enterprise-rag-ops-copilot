"""3-stage anti-hallucination and prompt-injection guardrails for Hybrid RAG."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.schemas.rag import CitationItem, RAGAnswerLLMOutput

GroundingStatus = Literal[
    "ANSWERED",
    "REFUSED_LOW_EVIDENCE",
    "BLOCKED_INJECTION",
    "ERROR_FALLBACK",
]

# Stage 0: Bilingual regex patterns for prompt injection, jailbreaks, and secret exfiltration.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b", re.IGNORECASE),
    re.compile(
        r"\bdisregard\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions?|rules?|prompt)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reveal|show|print|dump|leak|output|display)\s+(?:your\s+|the\s+)?"
        r"(?:system\s+prompt|hidden\s+instructions?|developer\s+prompt|api\s+keys?|secrets?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:print|dump|expose|leak)\s+(?:all\s+)?(?:environment\s+variables?|env\s+vars?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:enable|enter)\s+(?:developer|jailbreak|dan|unrestricted)\s+mode\b",
        re.IGNORECASE,
    ),
    re.compile(r"\byou\s+are\s+now\s+(?:in\s+)?(?:dan|jailbreak|unfiltered)\b", re.IGNORECASE),
    re.compile(r"ลืมคำสั่ง(?:ทั้งหมด|ก่อนหน้า|เดิม)"),
    re.compile(r"เพิกเฉย(?:ต่อ)?คำสั่ง(?:ก่อนหน้า|ทั้งหมด|ระบบ)"),
    re.compile(r"(?:เปิดเผย|แสดง|พิมพ์|ขอดู)(?:คำสั่งระบบ|พรอมต์ระบบ|system\s*prompt|รหัสลับ)"),
    re.compile(r"ยกเลิก(?:กฎ|ข้อจำกัด)ความปลอดภัย"),
)


@dataclass(frozen=True)
class InjectionGateDecision:
    """Result of Stage 0 prompt-injection screening."""

    blocked: bool
    grounding_status: GroundingStatus
    refusal_reason: str | None
    message: str | None


@dataclass(frozen=True)
class RetrievalGateDecision:
    """Result of Stage 1 pre-LLM retrieval threshold check."""

    passed: bool
    grounding_status: GroundingStatus
    refusal_reason: str | None
    message: str | None
    max_vec_similarity: float
    max_fts_rank: float


@dataclass(frozen=True)
class PostLLMGateDecision:
    """Result of Stage 2 post-LLM groundedness and citation UUID verification."""

    passed: bool
    grounding_status: GroundingStatus
    answer: str
    confidence_score: float
    citations: list[CitationItem]
    refusal_reason: str | None


def localized_injection_refusal(query_language: str) -> str:
    """Return a clean Thai or English refusal message for blocked injections."""
    if query_language in ("th", "mixed"):
        return (
            "คำขอถูกระงับโดยระบบความปลอดภัย (Stage 0 Injection Gate): "
            "ไม่อนุญาตให้เข้าถึงคำสั่งระบบ ข้อมูลลับ หรือข้ามกฎความปลอดภัยขององค์กร"
        )
    return (
        "Request blocked by Stage 0 Injection Gate: system prompt disclosure, "
        "credential exfiltration, and instruction override attempts are prohibited."
    )


def localized_low_evidence_refusal(query_language: str) -> str:
    """Return a deterministic Thai or English refusal when evidence is insufficient."""
    if query_language in ("th", "mixed"):
        return (
            "ขออภัย ไม่พบหลักฐานอ้างอิงที่เพียงพอในคลังเอกสารองค์กรเพื่อยืนยันคำตอบนี้ได้อย่างถูกต้อง "
            "กรุณาติดต่อทีมสนับสนุนหรือระบุรหัสเอกสาร/รายละเอียดเพิ่มเติม"
        )
    return (
        "Insufficient verified evidence found in the enterprise knowledge base to answer "
        "this question safely. Please contact support or provide a specific policy or error code."
    )


def check_prompt_injection(query: str, query_language: str = "en") -> InjectionGateDecision:
    """Stage 0 Gate: Deterministically block prompt-injection attempts at $0 LLM cost."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            return InjectionGateDecision(
                blocked=True,
                grounding_status="BLOCKED_INJECTION",
                refusal_reason="Prompt injection or system prompt exfiltration pattern detected.",
                message=localized_injection_refusal(query_language),
            )
    return InjectionGateDecision(
        blocked=False,
        grounding_status="ANSWERED",
        refusal_reason=None,
        message=None,
    )


def check_pre_llm_retrieval_gate(
    citations: Sequence[CitationItem],
    min_vec_similarity: float = 0.58,
    min_fts_rank: float = 0.08,
    query_language: str = "en",
) -> RetrievalGateDecision:
    """Stage 1 Gate: Refuse before calling LLM if retrieved evidence falls below thresholds."""
    if not citations:
        return RetrievalGateDecision(
            passed=False,
            grounding_status="REFUSED_LOW_EVIDENCE",
            refusal_reason="No matching document chunks found in PostgreSQL hybrid retrieval.",
            message=localized_low_evidence_refusal(query_language),
            max_vec_similarity=0.0,
            max_fts_rank=0.0,
        )

    max_vec = max(c.vec_similarity for c in citations)
    max_fts = max(c.fts_rank for c in citations)

    if max_vec < min_vec_similarity and max_fts < min_fts_rank:
        return RetrievalGateDecision(
            passed=False,
            grounding_status="REFUSED_LOW_EVIDENCE",
            refusal_reason=(
                f"Low retrieval evidence: max_vec_similarity={max_vec:.3f} "
                f"(< {min_vec_similarity}) and max_fts_rank={max_fts:.3f} (< {min_fts_rank})."
            ),
            message=localized_low_evidence_refusal(query_language),
            max_vec_similarity=max_vec,
            max_fts_rank=max_fts,
        )

    return RetrievalGateDecision(
        passed=True,
        grounding_status="ANSWERED",
        refusal_reason=None,
        message=None,
        max_vec_similarity=max_vec,
        max_fts_rank=max_fts,
    )


def apply_post_llm_groundedness_gate(
    llm_output: RAGAnswerLLMOutput,
    retrieved_citations: Sequence[CitationItem],
    min_confidence: float = 0.55,
    query_language: str = "en",
) -> PostLLMGateDecision:
    """Stage 2 Gate: Verify cited chunk UUIDs exist in retrieved rows and meet confidence."""
    retrieved_by_id = {c.chunk_id: c for c in retrieved_citations}
    valid_citations: list[CitationItem] = []
    seen_ids = set()

    for cid in llm_output.cited_chunk_ids:
        if cid in retrieved_by_id and cid not in seen_ids:
            seen_ids.add(cid)
            valid_citations.append(retrieved_by_id[cid])

    if (
        not llm_output.is_answerable
        or llm_output.confidence_score < min_confidence
        or len(valid_citations) == 0
    ):
        reason = llm_output.refusal_reason or (
            "Post-LLM groundedness check failed: unanswerable, low confidence, "
            "or no valid retrieved chunk_id citations."
        )
        return PostLLMGateDecision(
            passed=False,
            grounding_status="REFUSED_LOW_EVIDENCE",
            answer=localized_low_evidence_refusal(query_language),
            confidence_score=min(llm_output.confidence_score, 0.45),
            citations=[],
            refusal_reason=reason,
        )

    return PostLLMGateDecision(
        passed=True,
        grounding_status="ANSWERED",
        answer=llm_output.answer,
        confidence_score=llm_output.confidence_score,
        citations=valid_citations,
        refusal_reason=None,
    )
