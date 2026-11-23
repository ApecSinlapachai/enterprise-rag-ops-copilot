"""Pydantic v2 schemas for Golden Eval runs and per-case results."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EvalCaseResult(BaseModel):
    """Single Golden Eval case outcome aligned with eval_results table."""

    case_id: str
    category: Literal[
        "thai_in_scope",
        "english_in_scope",
        "code_mixed_th_en",
        "out_of_scope_unanswerable",
        "prompt_injection",
        "ticket_triage",
    ]
    language: Literal["th", "en", "mixed"]
    expected_outcome: Literal[
        "ANSWERED",
        "REFUSED_LOW_EVIDENCE",
        "BLOCKED_INJECTION",
        "VALID_TRIAGE_JSON",
    ]
    actual_outcome: Literal[
        "ANSWERED",
        "REFUSED_LOW_EVIDENCE",
        "BLOCKED_INJECTION",
        "VALID_TRIAGE_JSON",
        "FAILED",
    ]
    passed: bool
    citation_hit: bool | None = None
    schema_valid: bool | None = None
    expected_source_keys: list[str] = Field(default_factory=list)
    actual_source_keys: list[str] = Field(default_factory=list)
    latency_ms: int = Field(..., ge=0)
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    estimated_cost_usd: float = Field(0.0, ge=0.0, allow_inf_nan=False)
    failure_reason: str | None = None


class EvalSummaryResponse(BaseModel):
    """Summary of an evaluation run aligned with eval_runs table."""

    eval_run_id: UUID
    run_tag: str
    git_sha: str | None = None
    eval_mode: Literal["live_gemini", "ci_mock", "hybrid_replay"]
    model_name: str
    embedding_model: str
    total_cases: int = Field(..., gt=0)
    passed_cases: int = Field(..., ge=0)
    citation_hit_rate: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    refusal_precision: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    injection_block_rate: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    json_schema_pass_rate: float = Field(..., ge=0.0, le=1.0, allow_inf_nan=False)
    avg_latency_ms: int = Field(..., ge=0)
    p95_latency_ms: int = Field(..., ge=0)
    total_cost_usd: float = Field(0.0, ge=0.0, allow_inf_nan=False)
    cost_per_1k_requests_usd: float = Field(0.0, ge=0.0, allow_inf_nan=False)
    gate_passed: bool
    notes: str | None = None
    created_at: datetime
    cases: list[EvalCaseResult] = Field(default_factory=list)
