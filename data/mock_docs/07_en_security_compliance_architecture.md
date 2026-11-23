---
source_key: 07_en_security_compliance_architecture.md
title: Enterprise Security, Encryption, and SOC 2 Type II Compliance Policy
language: en
doc_type: security_policy
version: "2.0"
---

# Enterprise Security, Encryption, and SOC 2 Type II Compliance Policy

This document outlines the technical security controls, encryption standards, and AI safety boundaries protecting enterprise tenants.

## Encryption Standards (In-Transit and At-Rest)

- **In-Transit Encryption**: All public API, Next.js web traffic, and database connections enforce **TLS 1.3** (with strict HTTPS redirect and HSTS enabled).
- **At-Rest Encryption**: PostgreSQL storage volumes, `pgvector` embeddings, and encrypted automated snapshots use **AES-256-GCM** encryption at rest.
- **IP Privacy**: Public demo rate-limiting and `query_logs` store only a one-way **SHA-256** hash (`client_ip_hash`), never raw client IP addresses.

## AI Prompt Injection & Data Isolation Guardrails

- **Zero Foundation Model Training**: Customer documents, support tickets, and queries sent to Gemini API endpoints are never used to train public foundation models.
- **Tenant Isolation**: Knowledge retrieval queries filter strictly on active documents (`is_active = TRUE`) and scoped tenant boundaries (`ORG-DEMO-01`).
- **3-Stage Groundedness Pipeline**:
  1. Stage 0 (`BLOCKED_INJECTION`) rejects prompt-injection attempts deterministically before any LLM call (`$0` cost).
  2. Stage 1 (`REFUSED_LOW_EVIDENCE`) enforces minimum hybrid retrieval thresholds (`max_vec_similarity >= 0.58` or `max_fts_rank >= 0.08`).
  3. Stage 2 verifies `cited_chunk_ids` against retrieved PostgreSQL UUIDs and enforces `confidence_score >= 0.55`.

## Vulnerability Disclosure & Secret Rotation Policy

- Production API keys, database credentials, and `X-Admin-Token` secrets must be rotated every **90 days**.
- Suspected credential exposure must be escalated to `security_ops` immediately and revoked within **1 hour**.
- External security researchers can report vulnerabilities to `security@demo-saas-ops.example` under our coordinated 90-day disclosure policy.
