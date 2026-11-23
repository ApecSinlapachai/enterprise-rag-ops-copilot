"""Synchronous FastAPI route handler for Hybrid RAG queries."""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi import APIRouter, Request

from app.config import Settings
from app.db import DatabaseManager
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from app.services.generator import RAGGenerator
from app.services.guardrails import (
    apply_post_llm_groundedness_gate,
    check_pre_llm_retrieval_gate,
    check_prompt_injection,
)
from app.services.rate_limiter import enforce_rate_limit
from app.services.retriever import HybridRetriever, record_query_log
from app.services.tokenizer import detect_language

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(payload: RAGQueryRequest, request: Request) -> RAGQueryResponse:
    """Execute 3-stage guarded Thai-English Hybrid RAG query (sync threadpool)."""
    start_ns = time.perf_counter_ns()
    ip_hash = enforce_rate_limit(request)
    request_id = f"rag-{uuid4().hex[:12]}"
    settings: Settings = request.app.state.settings
    db: DatabaseManager = request.app.state.db
    retriever: HybridRetriever = request.app.state.retriever
    generator: RAGGenerator = request.app.state.generator

    query_language = (
        detect_language(payload.query)
        if payload.language_hint == "auto"
        else payload.language_hint
    )

    # Stage 0: Prompt Injection Gate ($0 LLM spend).
    injection_decision = check_prompt_injection(payload.query, query_language=query_language)
    if injection_decision.blocked:
        total_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
        answer_text = injection_decision.message or "Blocked by Stage 0 Injection Gate."
        record_query_log(
            db,
            request_id=request_id,
            query_text=payload.query,
            query_language=query_language,
            grounding_status="BLOCKED_INJECTION",
            refusal_reason=injection_decision.refusal_reason,
            max_vec_similarity=None,
            max_fts_rank=None,
            top_rrf_score=None,
            confidence_score=0.0,
            answer_text=answer_text,
            cited_chunk_ids=[],
            retrieval_ms=0,
            generation_ms=0,
            total_latency_ms=total_ms,
            model_name=settings.gemini_chat_model,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            client_ip_hash=ip_hash,
        )
        return RAGQueryResponse(
            request_id=request_id,
            query_language=query_language,
            grounding_status="BLOCKED_INJECTION",
            answer=answer_text,
            refusal_reason=injection_decision.refusal_reason,
            confidence_score=0.0,
            citations=[],
            retrieval_ms=0,
            generation_ms=0,
            total_latency_ms=total_ms,
            model_name=settings.gemini_chat_model,
        )

    # Hybrid Retrieval (pgvector + PyThaiNLP FTS + pg_trgm RRF).
    bundle = retriever.retrieve(payload.query)

    # Stage 1: Pre-LLM Retrieval Gate ($0 LLM spend).
    retrieval_gate = check_pre_llm_retrieval_gate(
        bundle.citations,
        min_vec_similarity=settings.min_vec_similarity,
        min_fts_rank=settings.min_fts_rank,
        query_language=query_language,
    )
    if not retrieval_gate.passed:
        total_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
        answer_text = retrieval_gate.message or "Refused due to low retrieval evidence."
        record_query_log(
            db,
            request_id=request_id,
            query_text=payload.query,
            query_language=query_language,
            grounding_status="REFUSED_LOW_EVIDENCE",
            refusal_reason=retrieval_gate.refusal_reason,
            max_vec_similarity=bundle.max_vec_similarity,
            max_fts_rank=bundle.max_fts_rank,
            top_rrf_score=bundle.top_rrf_score,
            confidence_score=0.0,
            answer_text=answer_text,
            cited_chunk_ids=[],
            retrieval_ms=bundle.retrieval_ms,
            generation_ms=0,
            total_latency_ms=total_ms,
            model_name=settings.gemini_chat_model,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            client_ip_hash=ip_hash,
        )
        return RAGQueryResponse(
            request_id=request_id,
            query_language=query_language,
            grounding_status="REFUSED_LOW_EVIDENCE",
            answer=answer_text,
            refusal_reason=retrieval_gate.refusal_reason,
            confidence_score=0.0,
            citations=[],
            retrieval_ms=bundle.retrieval_ms,
            generation_ms=0,
            total_latency_ms=total_ms,
            model_name=settings.gemini_chat_model,
        )

    # Grounded Answer Generation (Gemini structured output + resilient fallback).
    gen_result = generator.generate(
        query=payload.query,
        query_language=query_language,
        chunks=bundle.chunks,
    )

    # Stage 2: Post-LLM Groundedness Gate (UUID citation + confidence check).
    post_gate = apply_post_llm_groundedness_gate(
        gen_result.llm_output,
        bundle.citations,
        min_confidence=settings.min_llm_confidence,
        query_language=query_language,
    )
    total_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
    cited_ids = [c.chunk_id for c in post_gate.citations]

    record_query_log(
        db,
        request_id=request_id,
        query_text=payload.query,
        query_language=query_language,
        grounding_status=post_gate.grounding_status,
        refusal_reason=post_gate.refusal_reason,
        max_vec_similarity=bundle.max_vec_similarity,
        max_fts_rank=bundle.max_fts_rank,
        top_rrf_score=bundle.top_rrf_score,
        confidence_score=post_gate.confidence_score,
        answer_text=post_gate.answer,
        cited_chunk_ids=cited_ids,
        retrieval_ms=bundle.retrieval_ms,
        generation_ms=gen_result.generation_ms,
        total_latency_ms=total_ms,
        model_name=gen_result.model_name,
        input_tokens=gen_result.input_tokens,
        output_tokens=gen_result.output_tokens,
        estimated_cost_usd=gen_result.estimated_cost_usd,
        client_ip_hash=ip_hash,
    )

    return RAGQueryResponse(
        request_id=request_id,
        query_language=query_language,
        grounding_status=post_gate.grounding_status,
        answer=post_gate.answer,
        refusal_reason=post_gate.refusal_reason,
        confidence_score=post_gate.confidence_score,
        citations=post_gate.citations,
        retrieval_ms=bundle.retrieval_ms,
        generation_ms=gen_result.generation_ms,
        total_latency_ms=total_ms,
        model_name=gen_result.model_name,
        input_tokens=gen_result.input_tokens,
        output_tokens=gen_result.output_tokens,
        estimated_cost_usd=gen_result.estimated_cost_usd,
    )
