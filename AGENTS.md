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

---

## 2. Repository Structure & Current Progress

```text
enterprise-rag-ops-copilot/
├── .github/workflows/ci.yml            # [TODO Day 8] Ruff, Pytest, PG16 DDL, Eval Gate, Docker, Next.js build
├── docs/assets/demo-60s.gif            # [TODO Day 12] 1280x720, 15fps, <= 8MB walkthrough GIF
├── sql/
│   ├── 001_schema.sql                  # [DONE] Validated PG16 + pgvector + pg_trgm DDL
│   └── 002_hybrid_search_query.sql     # [DONE] Reference RRF hybrid search CTE
├── data/mock_docs/                     # [TODO Day 3] 10-12 Thai/EN/bilingual B2B SaaS Ops docs
├── api/
│   ├── Dockerfile                      # [DONE] Multi-stage python:3.12-slim
│   ├── pyproject.toml                  # [DONE] Dependencies, ruff, pytest config
│   └── app/
│       ├── config.py                   # [DONE] Pydantic BaseSettings & thresholds
│       ├── db.py                       # [DONE] psycopg3 ConnectionPool & check_health()
│       ├── main.py                     # [DONE] FastAPI lifespan, CORS, GET /health
│       ├── schemas/{rag,triage,eval}.py# [DONE] Pydantic v2 contracts
│       ├── services/                   # [TODO Day 3-7] tokenizer, embeddings, retriever, guardrails, generator, triage_service, rate_limiter
│       └── routers/                    # [TODO Day 5-7] rag, triage, documents, eval
├── scripts/
│   ├── ingest_corpus.py                # [TODO Day 4] Chunk, tokenize, embed, upsert mock_docs/
│   └── record_demo_gif.ps1             # [TODO Day 12] Playwright/FFmpeg capture script
├── eval/
│   ├── golden_eval_set.json            # [TODO Day 7] 25 cases (6 TH, 5 EN, 4 Mixed, 4 Unanswerable, 3 Injection, 3 Triage)
│   ├── run_eval.py                     # [TODO Day 7] Eval runner (ci_mock & live_gemini)
│   └── thresholds.json                 # [TODO Day 7] CI pass/fail thresholds
├── tests/
│   ├── unit/                           # [DONE Day 1-2: 9 tests] + [TODO Day 3-7: tokenizer, guardrails, rrf]
│   ├── integration/                    # [DONE Day 2: 2 live PG16 pgvector + RRF tests]
│   └── eval/                           # [TODO Day 8] test_golden_eval_gate.py
├── web/                                # [TODO Day 9-11] Next.js App Router (Vercel No-Login Live Demo)
├── docker-compose.yml                  # [DONE] pgvector/pgvector:pg16 + api
├── .env.example                        # [DONE] Safe placeholders
└── README.md                           # [DONE Day 1 starter] -> [Update Day 12 with GIF, Live URL, Mermaid, Eval Table]
```

---

## 3. Execution Roadmap (Day-by-Day)

- **Day 1 (Completed):** Repo init, SQL DDL (`001_schema.sql`, `002_hybrid_search_query.sql`), `docker-compose.yml`, `api/Dockerfile`, `pyproject.toml`, `config.py`, `db.py`, `main.py` (`/health`), Pydantic v2 `schemas/`, 8 unit tests passing.
- **Day 2 (Completed):**
  1. Hardened architecture via Devil's Advocate review: exact `vec_similarity` recomputation for FTS-only RRF winners, `$3` `pg_trgm` (`~*`) SKU/error code boost without `%` placeholder collisions in `psycopg3`, calibrated `min_vec_similarity=0.58` / `min_fts_rank=0.08`, added `format_citation_snippet()`, and pre-warmed `PyThaiNLP (newmm)` during FastAPI lifespan.
  2. Verified live `pgvector/pgvector:pg16` container (`rag_ops_postgres`), confirmed all 6 tables + `vector` & `pg_trgm` extensions + `002_hybrid_search_query.sql` RRF execution + live `GET /health` (`status: "ok", database_connected: true`), with 11/11 pytest tests (9 unit + 2 live DB integration) passing.
- **Day 3 (Next Immediate Step):**
  1. Author `10–12` realistic Thai/English/Bilingual B2B SaaS Operations knowledge documents in `data/mock_docs/` (SOPs, SLAs, refund policy, error code runbooks, security/PDPA FAQ, pricing tiers) using synthetic IDs (`INV-2026-0091`, `ERR-503`, `ORG-DEMO-01`).
  2. Build `api/app/services/tokenizer.py` (`PyThaiNLP newmm` word segmentation, Thai/English + B2B SaaS domain stopword filtering, `OR`-joined `tsquery` builder, regex SKU/error code extractor for `$3`, and Markdown heading-aware section chunker) + unit tests in `tests/unit/test_tokenizer.py`.
- **Day 4–5:** Build `embeddings.py` (with explicit 1536-dim L2 normalization + `task_type`), `scripts/ingest_corpus.py`, `retriever.py`, `guardrails.py`, `generator.py`, and `POST /api/v1/rag/query`.
- **Day 6–8:** Build `triage_service.py` + `POST /api/v1/triage` (`tenacity` retry + deterministic fallback), `GET /api/v1/documents`, `POST /api/v1/ingest`, `GET /api/v1/eval/latest`, 25-case `eval/golden_eval_set.json`, `eval/run_eval.py`, `pgvector` integration tests, and `.github/workflows/ci.yml`.
- **Day 9–12:** Build `web/` (Next.js App Router: TH/EN toggle, `"Try Unanswerable Query"` button, Citation Drawer, Telemetry Strip, Ticket Triage tab, Eval Scorecard tab), `rate_limiter.py`, deploy Supabase + Render + Vercel, record `docs/assets/demo-60s.gif`, and finalize recruiter-ready `README.md`.
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
