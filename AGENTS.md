# Enterprise RAG Ops Copilot — Project `AGENTS.md`

> **Role:** Senior AI & Backend Engineer building `ApecSinlapachai/enterprise-rag-ops-copilot` — a production-minded **Thai–English Hybrid RAG Copilot**, **Pydantic v2 Support Ticket Triage API**, and **25-Case Golden Eval Gate** with a No-Login Next.js Live Demo.

---

## 1. Architecture & Core Engineering Rules

1. **Public Portfolio Hygiene (100% Clean & English-First):**
   - All source code, comments, CLI output, commit messages, and documentation MUST be in clear English (Thai / code-mixed text is used intentionally only inside `data/mock_docs/`, RAG prompt/refusal localization, and `eval/` test fixtures).
   - **Zero real PII, zero real company secrets, zero `.env` commits.** All mock data and triage fixtures must use synthetic IDs (`INV-2026-0091`, `ORG-DEMO-01`).
2. **Free-Tier Budget (`$0` Infrastructure) & Public No-Login Demo Safety:**
   - **Stack:** `FastAPI` + `Pydantic v2` + `psycopg3` (`psycopg_pool`) + `PostgreSQL 16` (`pgvector` + `pg_trgm` + `tsvector`) + `PyThaiNLP` (`newmm`) + `google-genai` (`gemini-2.5-flash`, `gemini-embedding-001` with `output_dimensionality=1536`) + `Next.js` (App Router + Tailwind CSS).
   - **Hosting targets:** Vercel Hobby (Frontend), Render Free Web Service / Docker (`api/`), Supabase Free Tier (`pgvector` in production) & `pgvector/pgvector:pg16` (local/CI).
   - **Abuse guardrails & Free-Tier resilience:** Enforce IP-hashed (`SHA-256`) sliding-window rate limiting (`15 req/min`, `60 req/day`) reading the first hop of `X-Forwarded-For` behind Render/Vercel proxies before falling back to `request.client.host`, strict payload bounds (`500` chars RAG / `1500` chars Triage), strict `CORS_ORIGINS`, a frontend `/health` warm-up ping for Render cold starts, and a transparent cached/replay fallback if Gemini returns `429 RESOURCE_EXHAUSTED`.
   - **Sync FastAPI Route Policy:** Because `db.py` uses synchronous `psycopg_pool.ConnectionPool`, all DB-touching FastAPI route handlers MUST be declared as synchronous `def` endpoints (executed safely in FastAPI's worker threadpool) so the asyncio event loop is never blocked.
3. **1:1 SQL ↔ Pydantic v2 Alignment:**
   - `sql/001_schema.sql` and `api/app/schemas/` (`rag.py`, `triage.py`, `eval.py`) are locked 1:1 on enum values, numeric bounds, and `CHECK` constraints. Whenever changing a status, category, or numeric range, update both `001_schema.sql` and the corresponding Pydantic schema + unit tests.
   - Always format chunk text through `format_citation_snippet()` (`<= 380` chars + ellipsis) before instantiating `CitationItem(snippet=...)` (`max_length=400`).
4. **Thai–English Hybrid Search & Dual-Stage Groundedness Rules:**
   - **Vector safety & Matryoshka L2 normalization:** Always pass `task_type="RETRIEVAL_DOCUMENT"` during ingestion and `task_type="RETRIEVAL_QUERY"` during query embedding with `output_dimensionality=1536`, explicitly L2-normalize the truncated 1536-dim vector in Python, and validate a non-zero L2 norm before passing `$1::vector(1536)` to `<=>` cosine distance so zero vectors never yield `NaN`.
   - **Thai FTS & Code/SKU safety:** Tokenize with PyThaiNLP `newmm` (pre-warmed during FastAPI lifespan startup), strip standard + B2B SaaS domain stopwords (`สอบถาม`, `ครับ`, `ค่ะ`, `รบกวน`, `ระบบ`, `please`, `help`), build an `OR`-joined `tsquery` (`tok1 | tok2`), and extract regex-escaped exact code/SKU tokens (`INV-2026-0091`, `ERR-503`) as `$3` for `pg_trgm` (`~*` GIN trigram index) boosting (never put literal `%` inside `.sql` files executed by `psycopg3`).
   - **Hybrid RRF formula:** `0.6 / (60.0 + vec_rank) + 0.4 / (60.0 + fts_rank_pos)` over top-20 vector + top-20 FTS candidates, computing exact `vec_similarity` on the final top-5 winners even for FTS-only matches.
   - **3-Stage Guardrail:**
     - *Stage 0 (Injection Gate):* Regex/heuristic block (`ignore previous instructions`, `reveal system prompt`, `ลืมคำสั่งทั้งหมด`) → `BLOCKED_INJECTION` (`$0` LLM spend).
     - *Stage 1 (Pre-LLM Retrieval Gate):* If `chunks_found == 0` OR (`max_vec_similarity < 0.58` AND `max_fts_rank < 0.08`) → deterministic `REFUSED_LOW_EVIDENCE` (`$0` LLM spend).
     - *Stage 2 (Post-LLM Groundedness Gate):* Validate `cited_chunk_ids` against retrieved chunk UUIDs; if `not is_answerable` OR `confidence_score < 0.55` OR `len(valid_cited_chunk_ids) == 0` → override with deterministic refusal and clear `citations = []`.
5. **Mandatory Context & Progress Sync (`AGENTS.md` Update Policy):**
   - Whenever a milestone (`Day X`) is completed and all lint (`ruff`) and test (`pytest`) checks pass, you MUST update `AGENTS.md` (Section 2 Repository Structure, Section 3 Execution Roadmap, and verified test/lint counts) before wrapping up so that full project context is preserved for future sessions.
   - When updating `README.md` or writing Git commit messages for GitHub pushes, describe the completed features and verified test counts directly without including `Day X` labels.

---

## 2. Repository Structure & Current Progress

```text
enterprise-rag-ops-copilot/
├── .github/workflows/ci.yml            # [DONE Day 8] Ruff, Pytest, PG16 DDL, 25-Case Eval Gate, Docker, Next.js build
├── docs/assets/demo-60s.gif            # [DONE Day 12] 1280x720, 15fps, 0.98 MB walkthrough GIF
├── sql/
│   ├── 001_schema.sql                  # [DONE] Validated PG16 + pgvector + pg_trgm DDL
│   └── 002_hybrid_search_query.sql     # [DONE] Reference RRF hybrid search CTE
├── data/mock_docs/                     # [DONE Day 3] 12 Thai/EN/bilingual B2B SaaS Ops docs (52 chunks)
├── api/
│   ├── Dockerfile                      # [DONE] Multi-stage python:3.12-slim
│   ├── pyproject.toml                  # [DONE] Dependencies, ruff, pytest config
│   └── app/
│       ├── config.py                   # [DONE] Pydantic BaseSettings & thresholds
│       ├── db.py                       # [DONE] psycopg3 ConnectionPool & check_health()
│       ├── main.py                     # [DONE] FastAPI lifespan, CORS, GET /health, all v1 routers
│       ├── schemas/{rag,triage,eval}.py# [DONE] Pydantic v2 contracts
│       ├── services/                   # [DONE Day 3-9: tokenizer, embeddings, guardrails, retriever, generator, triage_service, rate_limiter]
│       └── routers/                    # [DONE Day 5-7: rag, triage, documents, eval]
├── scripts/
│   ├── ingest_corpus.py                # [DONE Day 4] Chunk, tokenize, embed, upsert mock_docs/
│   ├── generate_demo_gif.py            # [DONE Day 12] Live-output 1280x720 demo-60s.gif generator
│   └── record_demo_gif.ps1             # [DONE Day 10] FFmpeg 2-pass palette GIF converter
├── eval/
│   ├── golden_eval_set.json            # [DONE Day 7] 25 cases (6 TH, 5 EN, 4 Mixed, 4 Unanswerable, 3 Injection, 3 Triage)
│   ├── run_eval.py                     # [DONE Day 7] Eval runner (ci_mock, hybrid_replay & live_gemini)
│   └── thresholds.json                 # [DONE Day 7] CI pass/fail thresholds
├── tests/
│   ├── unit/                           # [DONE Day 1-12: 31 tests]
│   ├── integration/                    # [DONE Day 2-5: 3 live PG16 pgvector + RRF + RAG pipeline tests]
│   └── eval/                           # [DONE Day 8: 2 Golden Eval Gate tests]
├── web/                                # [DONE Day 9-12] Next.js 15 App Router + Tailwind CSS (No-Login Live Demo)
├── render.yaml                         # [DONE Day 11] Render Free Web Service Blueprint
├── docker-compose.yml                  # [DONE] pgvector/pgvector:pg16 + api
├── .env.example                        # [DONE] Safe placeholders
└── README.md                           # [DONE Day 12] Walkthrough GIF, Mermaid diagram, Eval Table, Deploy Guide
```

---

## 3. Execution Roadmap (Day-by-Day)

- **Day 1 (Completed):** Repo init, SQL DDL (`001_schema.sql`, `002_hybrid_search_query.sql`), `docker-compose.yml`, `api/Dockerfile`, `pyproject.toml`, `config.py`, `db.py`, `main.py` (`/health`), Pydantic v2 `schemas/`, 8 unit tests passing.
- **Day 2 (Completed):**
  1. Hardened architecture via Devil's Advocate review: exact `vec_similarity` recomputation for FTS-only RRF winners, `$3` `pg_trgm` (`~*`) SKU/error code boost without `%` placeholder collisions in `psycopg3`, calibrated `min_vec_similarity=0.58` / `min_fts_rank=0.08`, added `format_citation_snippet()`, and pre-warmed `PyThaiNLP (newmm)` during FastAPI lifespan.
  2. Verified live `pgvector/pgvector:pg16` container (`rag_ops_postgres`), confirmed all 6 tables + `vector` & `pg_trgm` extensions + `002_hybrid_search_query.sql` RRF execution + live `GET /health` (`status: "ok", database_connected: true`), with 11/11 pytest tests (9 unit + 2 live DB integration) passing.
- **Day 3 (Completed):**
  1. Authored `12` Thai/English/Bilingual B2B SaaS Operations knowledge documents in `data/mock_docs/` (4 TH, 4 EN, 4 Bilingual across all 6 `doc_type` values) with synthetic IDs (`INV-2026-0091`, `ERR-503`, `ERR-AUTH-403`, `ORG-DEMO-01`, `SKU-ENT-ANNUAL`).
  2. Built `api/app/services/tokenizer.py` (`PyThaiNLP newmm` word segmentation, Thai/English + B2B SaaS domain stopword filtering, `OR`-joined `tsquery` builder, regex SKU/error code extractor for `$3`, language detector, and Markdown heading-aware section chunker) + 7 unit tests in `tests/unit/test_tokenizer.py`.
- **Day 4–5 (Completed):**
  1. Built `api/app/services/embeddings.py` (1536-dim L2 normalization, zero-norm guard, `task_type="RETRIEVAL_DOCUMENT"` / `"RETRIEVAL_QUERY"`, deterministic offline/429 fallback), `guardrails.py` (3-stage Injection / Pre-LLM Retrieval / Post-LLM UUID Citation gates), `retriever.py` (`002_hybrid_search_query.sql` RRF + `query_logs` telemetry), `generator.py` (`RAGAnswerLLMOutput` structured output + grounded extractive fallback), `scripts/ingest_corpus.py`, and synchronous `POST /api/v1/rag/query` (`api/app/routers/rag.py`).
  2. Ingested all `12` mock documents (`52` chunks) into live `rag_ops_postgres`; verified with `ruff check app ../tests ../scripts` (clean) and `pytest -v` (24/24 tests passing: 21 unit + 3 live PG16 integration tests).
- **Day 6–8 (Completed):**
  1. Built `api/app/services/triage_service.py` (structured Gemini extraction with `tenacity` retry, deterministic entity extraction + bilingual rule fallback, and `triage_tickets` DB persistence), `api/app/routers/triage.py` (`POST /api/v1/triage`), `api/app/routers/documents.py` (`GET /api/v1/documents`, `POST /api/v1/ingest` with `hmac.compare_digest` `X-Admin-Token` guard), and `api/app/routers/eval.py` (`GET /api/v1/eval/latest`), wired as synchronous `def` handlers into `api/app/main.py`.
  2. Built 25-case `eval/golden_eval_set.json` (6 TH, 5 EN, 4 Mixed, 4 Out-of-Scope, 3 Injection, 3 Triage), `eval/thresholds.json`, `eval/run_eval.py` (`ci_mock`, `hybrid_replay`, `live_gemini`), `tests/unit/test_triage_service.py`, `tests/eval/test_golden_eval_gate.py`, and `.github/workflows/ci.yml`.
  3. Verified `ruff check app ../tests ../scripts ../eval` (0 errors), `pytest -v` (**31/31** tests passing: 26 unit + 3 live PG16 integration + 2 Golden Eval Gate tests), `docker compose config -q` (clean), and `eval/run_eval.py --mode ci_mock` (**25/25** passed, Citation Hit Rate `1.0000`, Refusal Precision `1.0000`, Injection Block Rate `1.0000`, JSON Schema Pass Rate `1.0000`, Avg/P95 Latency `36 ms / 48 ms`).
- **Day 9–10 (Completed):**
  1. Built `api/app/services/rate_limiter.py` (thread-safe, SHA-256 IP-hashed sliding-window rate limiter enforcing `15 req/min` & `60 req/day`, reading first hop of `X-Forwarded-For` with `Retry-After` HTTP `429` header) + wired into `POST /api/v1/rag/query` and `POST /api/v1/triage` + added 3 unit tests in `tests/unit/test_rate_limiter.py`.
  2. Scaffolded and built `web/` (Next.js 15 App Router + TypeScript + Tailwind CSS): `/health` cold-start warm-up ping, TH/EN UI toggle, Hybrid RAG workspace (sample chips, `"Try Unanswerable Query"`, `"Try Prompt Injection"`, Telemetry Strip, Citation Drawer with `vec_similarity`/`fts_rank`/`rrf_score`), Ticket Triage workspace, and Golden Eval Scorecard + Active Corpus tab.
  3. Added `scripts/record_demo_gif.ps1` (2-pass FFmpeg palette GIF converter) and updated `README.md`.
  4. Verified `ruff check app ../tests ../scripts ../eval` (0 errors), `pytest -v` (**34/34** tests passing: 29 unit + 3 live PG16 integration + 2 Golden Eval Gate tests), and `web/` `npx tsc --noEmit && npm run build` (clean).
- **Day 11–12 (Local Artifacts & Audit Completed; Cloud Deployment Pending User Accounts):**
  1. Exposed `Retry-After` via `CORSMiddleware(expose_headers=["Retry-After"])` in `api/app/main.py` and bounded `SlidingWindowRateLimiter` key growth (`max_tracked_keys=10_000` + stale-key eviction) with 2 additional unit tests in `tests/unit/test_rate_limiter.py`.
  2. Made `api/Dockerfile` `$PORT`-aware with pre-warmed PyThaiNLP, added `/app/data/mock_docs` and `/app/sql` mounts to `docker-compose.yml`, updated `retriever.py` SQL path resolution, and added `render.yaml` Blueprint.
  3. Polished TH/EN localization in `web/`, generated `docs/assets/demo-60s.gif` (`1280x720`, `15fps`, `0.98 MB`) via `scripts/generate_demo_gif.py`, and updated `README.md` with the walkthrough GIF, Mermaid architecture diagram, API reference, and Free-Tier Deployment Guide.
  4. Verified `ruff check app ../tests ../scripts ../eval` (0 errors), `pytest -v` (**36/36** tests passing: 31 unit + 3 live PG16 integration + 2 Golden Eval Gate tests), `docker compose config -q` (clean), and `web/` `npx tsc --noEmit && npm run build` (clean). Cloud provisioning (Supabase + Render + Vercel) remains for adding the live URL.
- **Day 13–14 (Buffer):** Bug-bash, mobile polish, edge-case testing, pin repo on `github.com/ApecSinlapachai`, and export anonymized learnings back to AI OS (`client-project-bridge` / `ai-automation-til`).

---

## 4. Local Verification Commands (Run After Code Changes)

Always run inside `api/` using the local `.venv` (Python 3.13):

```powershell
# Lint & Tests
cd api
.venv\Scripts\ruff.exe check app ../tests
.venv\Scripts\pytest.exe -v

# Compose & Live DB Verification (requires Docker Desktop running)
cd ..
docker compose config -q
docker compose up -d postgres
docker exec rag_ops_postgres psql -U postgres -d rag_ops -c "\dt"
```

### Eval Gate Targets (`eval/thresholds.json`)
- Citation Hit Rate: `>= 0.85` (15 in-scope RAG cases: 6 TH, 5 EN, 4 Mixed)
- Refusal Precision: `= 1.00` (4 out-of-scope cases, `0` fabricated citations)
- Injection Block Rate: `= 1.00` (3 prompt-injection cases)
- JSON Schema Pass Rate: `= 1.00` (3 ticket triage cases)
- P95 Latency: `<= 250 ms` (`ci_mock`) / `<= 3500 ms` (`live_gemini`)
