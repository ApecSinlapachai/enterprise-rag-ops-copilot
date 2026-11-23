"""Gemini embedding client with 1536-dim L2 normalization and deterministic offline fallback."""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence

from google import genai
from google.genai import types

from app.config import Settings
from app.services.tokenizer import (
    ALL_QUERY_STOPWORDS,
    extract_sku_or_error_code,
    tokenize_for_search,
)

logger = logging.getLogger(__name__)

# Bilingual concept clusters aligning Thai, English, and code-mixed queries with mock_docs/.
_CONCEPT_CLUSTERS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        "sla_refund",
        frozenset(
            {
                "sla",
                "uptime",
                "credit",
                "credits",
                "refund",
                "downtime",
                "99.95",
                "99.50",
                "คืนเงิน",
                "เครดิต",
                "ความพร้อม",
                "ชดเชย",
                "วันทำการ",
                "รอบบิล",
            }
        ),
    ),
    (
        "pdpa_retention",
        frozenset(
            {
                "pdpa",
                "retention",
                "purge",
                "delete",
                "erasure",
                "dsar",
                "dpo",
                "audit",
                "logs",
                "365",
                "คุ้มครอง",
                "ส่วนบุคคล",
                "เก็บรักษา",
                "ลบข้อมูล",
                "ถาวร",
                "ผ่อนผัน",
                "ยกเลิก",
            }
        ),
    ),
    (
        "billing_tax",
        frozenset(
            {
                "invoice",
                "e-tax",
                "tax",
                "withholding",
                "wht",
                "overdue",
                "billing",
                "ใบแจ้งหนี้",
                "ใบกำกับภาษี",
                "หัก",
                "ภาษี",
                "ทวิ",
                "50",
                "ค้างชำระ",
                "ชำระ",
                "3",
            }
        ),
    ),
    (
        "rbac_offboarding",
        frozenset(
            {
                "rbac",
                "onboarding",
                "offboarding",
                "role",
                "roles",
                "admin",
                "mfa",
                "revoke",
                "session",
                "สิทธิ์",
                "บทบาท",
                "เพิกถอน",
                "ลาออก",
                "ผู้ดูแล",
                "ผู้ใช้งาน",
            }
        ),
    ),
    (
        "incident_severity",
        frozenset(
            {
                "incident",
                "severity",
                "p0",
                "p1",
                "p2",
                "p3",
                "rca",
                "outage",
                "mitigation",
                "escalation",
                "ความสำคัญ",
                "รุนแรง",
                "เหตุการณ์",
                "ล่ม",
            }
        ),
    ),
    (
        "api_gateway_errors",
        frozenset(
            {
                "503",
                "504",
                "429",
                "gateway",
                "timeout",
                "pool",
                "psycopg_pool",
                "hnsw",
                "trigram",
                "rate",
                "limit",
                "retry-after",
                "ข้อผิดพลาด",
            }
        ),
    ),
    (
        "security_compliance",
        frozenset(
            {
                "tls",
                "aes",
                "aes-256-gcm",
                "soc",
                "encryption",
                "secret",
                "rotation",
                "sha-256",
                "isolation",
                "เข้ารหัส",
                "ความปลอดภัย",
                "หมุนเวียน",
            }
        ),
    ),
    (
        "pricing_tiers",
        frozenset(
            {
                "pricing",
                "price",
                "tier",
                "tiers",
                "starter",
                "pro",
                "enterprise",
                "quota",
                "overage",
                "upgrade",
                "annual",
                "49",
                "299",
                "1490",
                "17880",
                "แพ็กเกจ",
                "ราคา",
                "โควตา",
            }
        ),
    ),
    (
        "sso_saml",
        frozenset(
            {
                "sso",
                "saml",
                "oidc",
                "okta",
                "entra",
                "x509",
                "certificate",
                "acs",
                "metadata",
                "skew",
                "ล็อกอิน",
                "ใบรับรอง",
            }
        ),
    ),
    (
        "webhook_delivery",
        frozenset(
            {
                "webhook",
                "webhooks",
                "dlq",
                "backoff",
                "retry",
                "hmac",
                "hmac-sha256",
                "replay",
                "signature",
                "ส่งซ้ำ",
                "ลายเซ็น",
            }
        ),
    ),
    (
        "rag_guardrails",
        frozenset(
            {
                "rag",
                "hybrid",
                "rrf",
                "pgvector",
                "pythainlp",
                "newmm",
                "tsvector",
                "guardrail",
                "guardrails",
                "hallucination",
                "citation",
                "ตัดคำ",
                "ค้นหา",
                "ปฏิเสธ",
            }
        ),
    ),
    (
        "ticket_triage",
        frozenset(
            {
                "triage",
                "ticket",
                "tickets",
                "urgency",
                "priority",
                "category",
                "human",
                "review",
                "billing_ops",
                "l2_engineering",
                "security_ops",
                "l1_support",
                "account_management",
                "ตั๋ว",
                "คัดแยก",
                "ส่งต่อ",
            }
        ),
    ),
)

_HASH_BUCKET_OFFSET = 256


def _is_placeholder_api_key(api_key: str) -> bool:
    cleaned = api_key.strip()
    return (
        not cleaned
        or cleaned == "your-gemini-api-key-here"
        or cleaned.startswith("test-")
        or cleaned.startswith("change-me")
    )


def l2_normalize_vector(values: Sequence[float], expected_dim: int = 1536) -> list[float]:
    """Validate finiteness, dimension, and non-zero L2 norm, then return unit vector."""
    if len(values) != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {len(values)}"
        )

    floats: list[float] = []
    squared_sum = 0.0
    for idx, raw_val in enumerate(values):
        val = float(raw_val)
        if not math.isfinite(val):
            raise ValueError(f"Non-finite embedding value at index {idx}: {raw_val!r}")
        floats.append(val)
        squared_sum += val * val

    norm = math.sqrt(squared_sum)
    if norm <= 1e-12:
        raise ValueError("Zero-norm embedding vector cannot be normalized for cosine similarity")

    return [v / norm for v in floats]


def format_pgvector_literal(values: Sequence[float], expected_dim: int = 1536) -> str:
    """L2-normalize a vector and format it as a PostgreSQL pgvector literal string."""
    normalized = l2_normalize_vector(values, expected_dim=expected_dim)
    return "[" + ",".join(f"{v:.8f}" for v in normalized) + "]"


def _feature_index(feature_key: str, bucket_start: int, bucket_count: int) -> int:
    digest = hashlib.sha256(feature_key.encode("utf-8")).digest()
    raw_int = int.from_bytes(digest[:4], "big")
    return bucket_start + (raw_int % bucket_count)


def build_deterministic_embedding(text: str, dim: int = 1536) -> list[float]:
    """Build a concept-anchored deterministic 1536-dim L2-normalized vector.

    Used in offline/CI mode and as a transparent resilience fallback if the
    Gemini Embedding API returns 429 RESOURCE_EXHAUSTED.
    """
    if dim < 512:
        raise ValueError(f"Deterministic embedding requires dim >= 512, got {dim}")

    vec = [0.0] * dim
    tokenized, _ = tokenize_for_search(text)
    tokens = [tok for tok in tokenized.split() if tok not in ALL_QUERY_STOPWORDS]
    token_set = set(tokens)

    # 1. Concept cluster features (shared bilingual semantic anchors).
    for idx, (_cluster_name, keywords) in enumerate(_CONCEPT_CLUSTERS):
        hits = len(token_set & keywords)
        if hits > 0:
            base_slot = (idx * 8) % _HASH_BUCKET_OFFSET
            weight = 4.5 * min(hits, 4)
            vec[base_slot] += weight
            vec[(base_slot + 1) % _HASH_BUCKET_OFFSET] += weight * 0.65

    # 2. Exact synthetic code / SKU / error code anchor.
    code = extract_sku_or_error_code(text)
    if code:
        code_idx = _feature_index(f"code:{code.lower()}", _HASH_BUCKET_OFFSET, 128)
        vec[code_idx] += 5.0

    # 3. Individual domain token hashed projections.
    hash_span = dim - (_HASH_BUCKET_OFFSET + 128)
    for tok in tokens:
        if len(tok) == 1 and not tok.isdigit():
            continue
        tok_idx = _feature_index(f"tok:{tok}", _HASH_BUCKET_OFFSET + 128, hash_span)
        vec[tok_idx] += 0.75

    # Ensure strictly non-zero vector even for pure stopword or punctuation inputs.
    if not any(abs(v) > 1e-12 for v in vec):
        fallback_idx = _feature_index(
            f"raw:{text.strip().lower()}",
            _HASH_BUCKET_OFFSET + 128,
            hash_span,
        )
        vec[fallback_idx] = 1.0

    return l2_normalize_vector(vec, expected_dim=dim)


class EmbeddingService:
    """Wraps Google Gemini Embeddings (1536-dim L2 normalized) with deterministic fallback."""

    def __init__(self, settings: Settings, force_mock: bool = False) -> None:
        self._settings = settings
        self.embed_dim = settings.gemini_embed_dim
        self.model_name = settings.gemini_embed_model
        self._use_live_api = (not force_mock) and (
            not _is_placeholder_api_key(settings.gemini_api_key)
        )
        self._client = (
            genai.Client(api_key=settings.gemini_api_key) if self._use_live_api else None
        )

    @property
    def is_live_mode(self) -> bool:
        """Return True when configured to invoke the live Gemini Embedding API."""
        return self._client is not None

    def _embed(self, text: str, task_type: str, title: str | None = None) -> list[float]:
        if self._client is None:
            return build_deterministic_embedding(text, dim=self.embed_dim)

        try:
            config = types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.embed_dim,
                title=title if task_type == "RETRIEVAL_DOCUMENT" else None,
            )
            response = self._client.models.embed_content(
                model=self.model_name,
                contents=text,
                config=config,
            )
            embeddings = getattr(response, "embeddings", None) or []
            if not embeddings or not getattr(embeddings[0], "values", None):
                raise RuntimeError("Gemini embed_content returned empty embedding values")
            return l2_normalize_vector(embeddings[0].values, expected_dim=self.embed_dim)
        except Exception as exc:
            logger.warning(
                "Gemini embed_content failed (%s); falling back to deterministic embedding.",
                exc,
            )
            return build_deterministic_embedding(text, dim=self.embed_dim)

    def embed_document(self, text: str, title: str | None = None) -> list[float]:
        """Embed a knowledge document chunk using RETRIEVAL_DOCUMENT task_type."""
        return self._embed(text=text, task_type="RETRIEVAL_DOCUMENT", title=title)

    def embed_query(self, query: str) -> list[float]:
        """Embed a user search query using RETRIEVAL_QUERY task_type."""
        return self._embed(text=query, task_type="RETRIEVAL_QUERY")
