---
source_key: 08_en_enterprise_pricing_tiers.md
title: B2B SaaS Subscription Plans, Quotas, and Enterprise Pricing Guide
language: en
doc_type: pricing
version: "1.9"
---

# B2B SaaS Subscription Plans, Quotas, and Enterprise Pricing Guide

This guide summarizes commercial subscription tiers, API rate quotas, retention limits, and upgrade terms.

## Tier Comparison (Starter, Pro, Enterprise)

| Feature / Entitlement | Starter | Pro (`SKU-PRO-MONTHLY`) | Enterprise (`SKU-ENT-ANNUAL`) |
| :--- | :--- | :--- | :--- |
| **List Price** | **$49 / month** | **$299 / month** | **$1,490 / month** (billed annually at **$17,880 / year**) |
| **User Seats** | Up to 5 seats | Up to 25 seats | Unlimited seats |
| **Monthly API Quota** | 10,000 calls/month | 100,000 calls/month | 1,000,000 calls/month (burst **600 req/min**) |
| **Uptime SLA** | Best-effort (99.00%) | **99.50%** | **99.95%** |
| **Audit Log Retention** | 30 days | **90 days** | **365 days** |
| **SSO (SAML 2.0 / OIDC)** | Not included | Add-on available | Included |
| **Support SLA** | Email (`P3`, 1 business day) | Business hours (`P2` 4h) | Dedicated Slack/LINE + 24/7 (`P0` **15 min**) |

### Public No-Login Live Demo Quota

Public unauthenticated demo visitors are subject to a protective rate limit of **15 requests/minute** and **60 requests/day** per SHA-256 IP hash, with payload caps of **500 characters** for RAG queries and **1,500 characters** for Ticket Triage.

## Overages, Upgrades, and Annual Contract Invoicing

- **Mid-Cycle Upgrades**: Tenants (such as `ORG-DEMO-01`) upgrading from `SKU-PRO-MONTHLY` to `SKU-ENT-ANNUAL` receive immediate feature activation with pro-rated credit applied to their next invoice (`INV-2026-0104`).
- **API Overage Pricing**: Usage beyond monthly plan quotas is billed at **$0.005 per additional 1,000 API calls** unless hard-cap throttling is enabled in the Billing Portal.
- **Enterprise Procurement**: Annual contracts support bank transfer, corporate credit card, and Thai 3% Withholding Tax (`50 ทวิ`) invoicing.
