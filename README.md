# 🤖 Enterprise RAG Ops Copilot (`enterprise-rag-ops-copilot`)

> **Status:** Backend & 25-Case Golden Eval Gate Verified — PostgreSQL 16 (`pgvector` + `pg_trgm`) RRF Hybrid Search, 12 Thai/EN/Bilingual Ops Mock Docs (52 chunks), 3-Stage Anti-Hallucination Guardrails, Pydantic v2 Ticket Triage API (`tenacity` retry + fallback), Admin-Protected Document Ingestion, GitHub Actions CI, and **31/31 tests + 25/25 Golden Eval Gate passing**.

A production-minded **Thai–English Hybrid RAG Copilot** and **Pydantic v2 Ticket Triage API** built with `FastAPI`, `PostgreSQL 16 (pgvector + FTS + pg_trgm)`, `PyThaiNLP`, and `Gemini API`, featuring dual-stage hallucination refusal, a 25-case Golden Eval Gate, and a No-Login Next.js live demo.

## 📊 Golden Evaluation Gate (`ci_mock` Mode Verified)

| Metric | Target | Verified Result |
| :--- | :---: | :---: |
| **Total Cases** | `25` (6 TH, 5 EN, 4 Mixed, 4 OOS, 3 Injection, 3 Triage) | **25 / 25** |
| **Citation Hit Rate** | `>= 0.8500` | **1.0000** |
| **Refusal Precision** | `= 1.0000` | **1.0000** |
| **Injection Block Rate** | `= 1.0000` | **1.0000** |
| **JSON Schema Pass Rate** | `= 1.0000` | **1.0000** |
| **Avg / P95 Latency** | `<= 250 ms` | **36 ms / 48 ms** |

## 🏗️ Repository Layout

```text
enterprise-rag-ops-copilot/
├── .github/workflows/
│   └── ci.yml                          # Ruff, Pytest, PG16 DDL, 25-Case Eval Gate, Docker, Next.js build
├── sql/
│   ├── 001_schema.sql                  # PostgreSQL 16 + pgvector + pg_trgm DDL
│   └── 002_hybrid_search_query.sql     # Reference RRF hybrid search CTE
├── data/
│   └── mock_docs/                      # 12 Thai/EN/bilingual B2B SaaS Ops knowledge docs
├── eval/
│   ├── golden_eval_set.json            # 25-case Thai/EN/Mixed/OOS/Injection/Triage benchmark
│   ├── thresholds.json                 # CI pass/fail thresholds
│   └── run_eval.py                     # CLI & programmatic eval runner (ci_mock, hybrid_replay, live_gemini)
├── api/
│   ├── Dockerfile                      # Multi-stage python:3.12-slim container
│   ├── pyproject.toml                  # Dependencies, Ruff, Pytest config
│   └── app/
│       ├── config.py                   # Pydantic BaseSettings & guardrail thresholds
│       ├── db.py                       # psycopg3 ConnectionPool + health probe
│       ├── main.py                     # FastAPI app, CORS, /health, all v1 routers
│       ├── routers/
│       │   ├── rag.py                  # POST /api/v1/rag/query (sync threadpool + IP hash)
│       │   ├── triage.py               # POST /api/v1/triage (Pydantic v2 structured triage)
│       │   ├── documents.py            # GET /api/v1/documents & POST /api/v1/ingest (X-Admin-Token)
│       │   └── eval.py                 # GET /api/v1/eval/latest (latest eval_runs + eval_results)
│       ├── schemas/                    # Pydantic v2 contracts (1:1 with SQL CHECKs)
│       └── services/
│           ├── tokenizer.py            # PyThaiNLP newmm segmentation, tsquery builder, code extractor & chunker
│           ├── embeddings.py           # 1536-dim L2-normalized Gemini embeddings + offline fallback
│           ├── guardrails.py           # 3-stage Injection / Pre-LLM Retrieval / Post-LLM UUID Citation gates
│           ├── retriever.py            # Hybrid RRF search, corpus ingestion, and query_logs telemetry
│           ├── generator.py            # Structured Gemini RAG generation + grounded extractive fallback
│           └── triage_service.py       # Gemini Ticket Triage (tenacity retry + deterministic fallback)
├── scripts/
│   └── ingest_corpus.py                # CLI to chunk, tokenize, embed, and upsert data/mock_docs/
├── tests/
│   ├── unit/                           # Schema, config, tokenizer, embeddings, guardrails & triage tests (26 tests)
│   ├── integration/                    # Live PG16 pgvector + RRF + end-to-end RAG pipeline tests (3 tests)
│   └── eval/                           # Live 25-case Golden Eval Gate & API persistence tests (2 tests)
├── docker-compose.yml                  # pgvector/pgvector:pg16 + FastAPI service
└── .env.example                        # Safe configuration placeholders
```

## 🚀 Local Quickstart

```bash
# 1. Start PostgreSQL 16 + pgvector
docker compose up -d postgres

# 2. Ingest mock corpus, run tests & Golden Eval Gate
cd api
uv venv --python 3.13
uv pip install -e ".[dev]"
python ../scripts/ingest_corpus.py
pytest -v
python ../eval/run_eval.py --mode ci_mock
ruff check app ../tests ../scripts ../eval
```
