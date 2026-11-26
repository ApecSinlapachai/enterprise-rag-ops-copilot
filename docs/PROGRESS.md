# PROGRESS — enterprise-rag-ops-copilot

- **Last Updated:** 2026-11-26
- **Current Phase:** Shipped & Live in Production (6-Layer AI-Native SSOT Standardized)

> **Handoff Rule:** Keep this file crisp and factual. Update it immediately after every completed task (alongside `git commit`) so any new model or chat session can resume in < 10 seconds.

---

## Completed
- [x] **Core Schema, Hybrid RRF Retriever & Bilingual Corpus:** PG16 + `pgvector` (1536-dim L2-normalized) + `PyThaiNLP (newmm)` FTS + `pg_trgm` SKU/error-code boost (`sql/001_schema.sql`, `sql/002_hybrid_search_query.sql`, `data/mock_docs/` 12 docs / 52 chunks, `scripts/ingest_corpus.py`).
- [x] **3-Stage Guardrails & Tiered Gemini 3.x Routing:** Stage 0 Injection Gate (`$0`), Stage 1 Pre-LLM Retrieval Gate (`$0`), Stage 2 Post-LLM UUID Citation Gate (`api/app/services/guardrails.py`), and Fast/Complex/Fallback Gemini 3.x routing with deterministic extractive fallback (`api/app/services/generator.py`).
- [x] **Pydantic v2 Ticket Triage & Admin/Eval Endpoints:** `POST /api/v1/triage` with `TriageTicketLLMOutput`, `tenacity` retry, deterministic entity extraction, `GET /api/v1/documents`, `POST /api/v1/ingest` (`X-Admin-Token`), and `GET /api/v1/eval/latest`.
- [x] **25-Case Golden Eval Gate & GitHub Actions CI:** `eval/golden_eval_set.json`, `eval/run_eval.py` (`25/25` in both `ci_mock` and live Supabase `production-baseline`), and `.github/workflows/ci.yml` (`ruff`, `pytest`, PG16 DDL, Eval Gate, Docker, Next.js build).
- [x] **No-Login Next.js Demo, Same-Origin Proxy & Cloud Rollout:** Deployed to Supabase Free + Render Free + Vercel Hobby; migrated browser calls to same-origin `/backend/*` proxy (`web/next.config.mjs`) with 10×5s cold-start `/health` polling (`web/src/app/page.tsx`) and SHA-256 IP-hashed rate limiting (`api/app/services/rate_limiter.py`).
- [x] **6-Layer AI-Native SSOT Standardization:** Refactored `AGENTS.md` to concise entrypoint, added `CLAUDE.md`, `.editorconfig`, `docs/SPEC.md`, `docs/PROGRESS.md`, and `docs/adr/0001..0003`.

## In Progress / Next Up
1. Maintain `eval/golden_eval_set.json` and `docs/adr/` as new retrieval or model routing enhancements are introduced.
2. Keep live portfolio links synchronized with `https://apec-ai-portfolio.vercel.app/demos/rag-copilot`.

## Blockers / Gotchas for Next Agent
- **Vector-Space Consistency:** Running `eval/run_eval.py --mode ci_mock` against a DB populated with live `gemini-embedding-001` vectors causes a vector-space mismatch (`19/25`). Use `--mode live_gemini --no-ingest` against live-embedded Supabase corpora, and `--mode ci_mock` against fresh local/CI databases.
- **Sync `psycopg_pool`:** Keep all DB-touching FastAPI routes as synchronous `def` endpoints.
- **No Literal `%` in SQL:** Never place literal `%` in `.sql` files executed by `psycopg3`; use `$3` with `pg_trgm` `~*` regex matching.

## Last Verified Commands
```bash
# Inside api/
ruff check app ../tests ../scripts ../eval
pytest -v
# Repo root
docker compose config -q
# Inside web/
npx tsc --noEmit && npm run build
```
