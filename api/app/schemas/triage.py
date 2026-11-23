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


class TriageExtractedEntitiesLLM(BaseModel):
    """Explicit entity fields for Gemini structured output (no additionalProperties)."""

    invoice_id: str | None = None
    org_id: str | None = None
    error_code: str | None = None
    sku: str | None = None
    incident_id: str | None = None

    def to_dict(self) -> dict[str, str]:
        """Convert non-empty entity fields into a clean string dictionary."""
        raw = {
            "invoice_id": self.invoice_id,
            "org_id": self.org_id,
            "error_code": self.error_code,
            "sku": self.sku,
            "incident_id": self.incident_id,
        }
        return {k: v.strip() for k, v in raw.items() if isinstance(v, str) and v.strip()}


class TriageTicketLLMOutput(BaseModel):
    """Gemini-compatible structured output schema free of dict/additionalProperties."""

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
    urgency_score: int = Field(..., ge=1, le=5)
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
    extracted_entities: TriageExtractedEntitiesLLM = Field(
        default_factory=TriageExtractedEntitiesLLM
    )

    def to_extraction(self) -> TriageTicketExtraction:
        """Convert Gemini LLM output into the strict 1:1 SQL/API TriageTicketExtraction."""
        return TriageTicketExtraction(
            language_detected=self.language_detected,
            category=self.category,
            urgency_score=int(self.urgency_score),
            priority=self.priority,
            sentiment=self.sentiment,
            summary=self.summary,
            suggested_action=self.suggested_action,
            suggested_team=self.suggested_team,
            requires_human_review=self.requires_human_review,
            extracted_entities=self.extracted_entities.to_dict(),
        )


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
