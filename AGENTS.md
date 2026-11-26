# AGENTS.md — enterprise-rag-ops-copilot

> **Role:** Entrypoint & working rules for AI coding agents in this repository.
> **Rule:** Keep this file short (< 150 lines). Do NOT duplicate schemas, specs, daily logs, or linter rules here — point to their SSOT instead.

## 1. Project Snapshot
- **Purpose:** Production-minded Thai–English Hybrid RAG Copilot (`pgvector` + `PyThaiNLP` FTS + `pg_trgm` RRF), Pydantic v2 Support Ticket Triage API, and 25-Case Golden Eval Gate with a No-Login Next.js Live Demo (`$0` Free-Tier Stack).
- **Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, `psycopg3` (`psycopg_pool`), PostgreSQL 16 (`pgvector`, `pg_trgm`), `PyThaiNLP` (`newmm`), `google-genai` (Tiered Gemini 3.x + `gemini-embedding-001`), Next.js 15 (App Router, TypeScript, Tailwind CSS), Docker.
- **Primary Language:** Code, comments, commits, and docs in English (Thai / code-mixed text is used intentionally only inside `data/mock_docs/`, RAG prompt/refusal localization, UI toggle, and `eval/` fixtures).

## 2. Single Sources of Truth (SSOT Map)
Read these on-demand before making architectural or scope changes:
- **Live Task State & Handoff:** `docs/PROGRESS.md` *(Read at start of every session)*
- **Feature Scope & Requirements:** `docs/SPEC.md`
- **Architecture Decisions (Why):** `docs/adr/`
- **Environment Variables:** `.env.example` & `web/.env.example`
- **Database Schema & RRF SQL:** `sql/001_schema.sql` & `sql/002_hybrid_search_query.sql` *(Executable SSOT)*
- **API & Pydantic Contracts:** `api/app/schemas/` & `api/app/routers/` *(Executable SSOT)*
- **Eval Thresholds:** `eval/thresholds.json` *(Executable SSOT)*
- **Linter & Test Config:** `api/pyproject.toml` & `.github/workflows/ci.yml`

## 3. Standard Commands
Always run verification commands before reporting a task as done:
```bash
# Backend lint & tests (inside api/)
ruff check app ../tests ../scripts ../eval
pytest -v

# Standalone 25-case Golden Eval Gate (repo root)
python eval/run_eval.py --mode ci_mock

# Docker Compose validation (repo root)
docker compose config -q

# Frontend typecheck & production build (inside web/)
npx tsc --noEmit && npm run build
```

## 4. Repository Map
```text
enterprise-rag-ops-copilot/
├── api/app/          # FastAPI backend (config, db, main, routers/, schemas/, services/)
├── web/              # Next.js 15 App Router No-Login Demo (/backend/* same-origin proxy)
├── sql/              # PG16 + pgvector + pg_trgm DDL & reference RRF query
├── data/mock_docs/   # 12 synthetic TH/EN/Bilingual B2B SaaS Ops docs (52 chunks)
├── eval/             # 25-case golden eval set, runner (ci_mock/live_gemini), thresholds
├── scripts/          # Corpus ingestion & motion demo exporters
├── tests/            # unit/, integration/ (live PG16), eval/ (Golden Eval Gate)
├── docs/             # SPEC.md, PROGRESS.md, adr/ (0001..NNNN), assets/
└── .github/workflows/ci.yml
```

## 5. Hard Guardrails (Non-Negotiable)
- **Secrets & PDPA:** Never hardcode API keys, tokens, or real PII. All fixtures must use synthetic IDs (`INV-2026-0091`, `ORG-DEMO-01`, `ERR-503`).
- **1:1 SQL ↔ Pydantic v2 Alignment:** `sql/001_schema.sql` and `api/app/schemas/` must stay locked on enum values, numeric bounds, and `CHECK` constraints. Format citation snippets via `format_citation_snippet()` (`<= 380` chars).
- **Sync FastAPI Route Policy:** Because `db.py` uses synchronous `psycopg_pool.ConnectionPool`, all DB-touching route handlers must be synchronous `def` endpoints (never block the asyncio loop).
- **3-Stage Guardrails & Vector Safety:** Always L2-normalize 1536-dim vectors and guard zero-norm before `<=>`. Never bypass Stage 0 (Injection), Stage 1 (Pre-LLM Retrieval), or Stage 2 (Post-LLM UUID Citation) gates. Never put literal `%` in `.sql` files executed by `psycopg3`.
- **Zero Cross-Origin Browser Calls:** Browser code in `web/` must call `/backend/*` (proxied via `web/next.config.mjs`), never `*.onrender.com` directly.
- **No Unapproved Stack Changes:** Check `docs/adr/` before changing DB, vector strategy, LLM SDK (`google-genai`), or proxy architecture; record new trade-offs in a new ADR.
- **Verify Before Finishing:** Run lint, tests, and build after code changes. Never claim checks pass without running them.

## 6. Session Continuity & Git Conventions
- **Start of every session:** Read `docs/PROGRESS.md` and run `git status` + `git log -n 5 --oneline` before editing code.
- **After completing each task:** Run verification -> `git commit` -> update `docs/PROGRESS.md`.
- **Commits:** Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`). Do not include `Day X` labels in commits or `README.md`.
- **New Decisions:** Record significant architectural trade-offs in `docs/adr/NNNN-short-title.md` (MADR format).
