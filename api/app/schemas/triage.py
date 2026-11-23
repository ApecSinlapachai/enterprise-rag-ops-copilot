"""Pydantic v2 schemas for structured support ticket triage."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, StrictInt


class TriageTicketRequest(BaseModel):
    """Inbound support message payload (bounded for public no-login demo)."""

    message: str = Field(..., min_length=5, max_length=1500)
    source_channel: Literal["web_demo", "line", "email", "api", "eval"] = "web_demo"


class TriageTicketExtraction(BaseModel):
    """Structured triage fields aligned 1:1 with triage_tickets CHECK constraints."""

    language_detected: Literal["th", "en", "mixed"]
    category: Literal[
        "billing_refund",
        "technical_incident",
        "account_access",
        "sla_escalation",
        "feature_request",
        "general_inquiry",
        "prompt_injection_attempt",
    ]
    urgency_score: StrictInt = Field(..., ge=1, le=5)
    priority: Literal["P0", "P1", "P2", "P3"]
    sentiment: Literal["negative", "neutral", "positive"]
    summary: str = Field(..., min_length=10, max_length=400)
    suggested_action: str = Field(..., min_length=10, max_length=400)
    suggested_team: Literal[
        "l1_support",
        "l2_engineering",
        "billing_ops",
        "security_ops",
        "account_management",
    ]
    requires_human_review: bool = False
    extracted_entities: dict[str, str] = Field(default_factory=dict)


class TriageTicketResponse(TriageTicketExtraction):
    """Persisted ticket triage API response."""

    ticket_id: UUID
    request_id: str
    validation_status: Literal[
        "pydantic_passed",
        "repaired_retry",
        "deterministic_fallback",
    ]
    model_name: str
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    estimated_cost_usd: float = Field(0.0, ge=0.0, allow_inf_nan=False)
    latency_ms: int = Field(..., ge=0)
