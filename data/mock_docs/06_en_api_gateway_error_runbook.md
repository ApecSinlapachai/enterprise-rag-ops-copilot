---
source_key: 06_en_api_gateway_error_runbook.md
title: Production Runbook — API Gateway Error Codes ERR-503, ERR-DB-504, and ERR-RATE-429
language: en
doc_type: runbook
version: "2.2"
---

# Production Runbook — API Gateway Error Codes

This runbook guides `l2_engineering` on-call responders when triaging HTTP gateway and database saturation errors in production.

## ERR-503 (Upstream Service Unavailable / Connection Pool Exhaustion)

- **Root Cause**: Occurs when FastAPI worker processes or synchronous `psycopg_pool` database connections reach 100% saturation during traffic spikes or cold-start storms.
- **Diagnostic Steps**:
  1. Check `GET /health` to verify `database_connected` status and inspect active connection counts in PostgreSQL `pg_stat_activity`.
  2. Review worker memory and CPU utilization on the container service.
- **Mitigation**:
  1. Terminate idle-in-transaction queries exceeding 15 seconds.
  2. Temporarily raise `max_size` on `ConnectionPool` only within Supabase free-tier session limits, or enable cached replay fallback mode.
  3. Scale API worker replicas and notify affected tenants (`ORG-DEMO-01`) if downtime exceeds 5 minutes.

## ERR-DB-504 (Database Vector/FTS Query Timeout)

- **Root Cause**: Triggered when a PostgreSQL hybrid search CTE (`002_hybrid_search_query.sql`) exceeds the `5000 ms` statement timeout due to sequential table scans or lock contention.
- **Diagnostic Steps**:
  1. Run `EXPLAIN (ANALYZE, BUFFERS)` on the failing query to confirm index usage on `idx_document_chunks_embedding_hnsw` and `idx_document_chunks_search_trgm_gin`.
  2. Verify that `pgvector` HNSW `ef_search` is not set excessively high and no long-running `VACUUM FULL` or ingestion transaction is blocking reads.
- **Mitigation**: Rebuild stale planner statistics with `ANALYZE document_chunks;` and retry failed requests with jittered backoff.

## ERR-RATE-429 (Tenant or IP Rate Limit Exceeded)

- **Root Cause**: Returned when a caller exceeds `15 requests/minute` or `60 requests/day` on the public no-login demo API, or exceeds `600 requests/minute` on an authenticated `SKU-ENT-ANNUAL` API key.
- **Mitigation**:
  1. Direct callers to inspect the HTTP `Retry-After` response header and implement exponential backoff with jitter.
  2. For legitimate enterprise traffic bursts (`ORG-DEMO-01`), `account_management` may approve a temporary quota burst override after verifying plan entitlements.
