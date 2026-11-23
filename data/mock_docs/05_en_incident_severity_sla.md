---
source_key: 05_en_incident_severity_sla.md
title: Enterprise Incident Severity Matrix & Response Time SLA
language: en
doc_type: sla
version: "3.0"
---

# Enterprise Incident Severity Matrix & Response Time SLA

This policy defines incident severity levels (`P0` through `P3`), guaranteed initial response times, update cadences, and Root Cause Analysis (RCA) commitments for B2B SaaS customers.

## Severity Classification (P0 to P3)

Support and engineering teams classify all incoming incidents using the following severity matrix:

### P0 — Critical Production Outage

- **Definition**: Complete platform unavailability, severe data loss risk, or confirmed security breach affecting all users or production API endpoints (for example, platform-wide `ERR-503` or `ERR-DB-504`).
- **First Response SLA**: **15 minutes** (24/7/365 coverage for `SKU-ENT-ANNUAL` customers).
- **Status Update Cadence**: Every **30 minutes** until service restoration.
- **Target Mitigation**: **2 hours**.
- **Target Routing**: `l2_engineering` or `security_ops`.

### P1 — High Impact Degradation

- **Definition**: Critical workflow failure or authentication outage (such as enterprise SAML SSO error `ERR-AUTH-403`) blocking an entire tenant like `ORG-DEMO-01` with no viable workaround.
- **First Response SLA**: **30 minutes**.
- **Status Update Cadence**: Every **2 hours**.
- **Target Mitigation**: **4 hours**.
- **Target Routing**: `l2_engineering` or `security_ops`.

### P2 — Moderate Issue

- **Definition**: Non-critical feature degradation, intermittent webhook delivery failure (`ERR-WEBHOOK-502`), or elevated latency where a temporary workaround is available.
- **First Response SLA**: **4 business hours**.
- **Target Resolution**: **24 business hours**.
- **Target Routing**: `l1_support` or `l2_engineering`.

### P3 — Low Impact / General Inquiry

- **Definition**: Minor UI issue, documentation clarification, billing question, or feature request.
- **First Response SLA**: **1 business day**.
- **Target Routing**: `l1_support` or `account_management`.

## Escalation Path & Post-Incident Review (RCA)

- Any `P0` or `P1` ticket automatically sets `requires_human_review = true` and pages the on-call engineer.
- If an Enterprise tenant (`ORG-DEMO-01`) experiences a `P0` or `P1` outage, a formal **Root Cause Analysis (RCA)** report is delivered by `account_management` and `l2_engineering` within **5 business days** of resolution.
- SLA credit claims triggered by downtime must reference the incident ID (e.g., `INC-2026-0412`) and invoice ID (`INV-2026-0091`).
