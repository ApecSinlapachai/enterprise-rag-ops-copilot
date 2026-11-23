# 🤖 Enterprise RAG Ops Copilot (`enterprise-rag-ops-copilot`)

> **Status:** Active Build — PostgreSQL 16 (`pgvector` + `pg_trgm`) RRF Hybrid Search, 12 Thai/EN/Bilingual Ops Mock Docs (52 chunks ingested), 1536-dim L2-Normalized Embeddings, 3-Stage Anti-Hallucination Guardrails, and `POST /api/v1/rag/query` verified (24/24 tests passing).

A production-minded **Thai–English Hybrid RAG Copilot** and **Pydantic v2 Ticket Triage API** built with `FastAPI`, `PostgreSQL 16 (pgvector + FTS + pg_trgm)`, `PyThaiNLP`, and `Gemini API`, featuring dual-stage hallucination refusal, a 25-case Golden Eval Gate, and a No-Login Next.js live demo.

## 🏗️ Repository Layout

```text
enterprise-rag-ops-copilot/
├── sql/
│   ├── 001_schema.sql                  # PostgreSQL 16 + pgvector + pg_trgm DDL
│   └── 002_hybrid_search_query.sql     # Reference RRF hybrid search CTE
├── data/
│   └── mock_docs/                      # 12 Thai/EN/bilingual B2B SaaS Ops knowledge docs
├── api/
│   ├── Dockerfile                      # Multi-stage python:3.12-slim container
│   ├── pyproject.toml                  # Dependencies, Ruff, Pytest config
│   └── app/
│       ├── config.py                   # Pydantic BaseSettings & guardrail thresholds
│       ├── db.py                       # psycopg3 ConnectionPool + health probe
│       ├── main.py                     # FastAPI app, CORS, /health, RAG router
│       ├── routers/
│       │   └── rag.py                  # POST /api/v1/rag/query (sync threadpool + IP hash)
│       ├── schemas/                    # Pydantic v2 contracts (1:1 with SQL CHECKs)
│       └── services/
│           ├── tokenizer.py            # PyThaiNLP newmm segmentation, tsquery builder, code extractor & Markdown chunker
│           ├── embeddings.py           # 1536-dim L2-normalized Gemini embeddings + offline fallback
│           ├── guardrails.py           # 3-stage Injection / Pre-LLM Retrieval / Post-LLM UUID Citation gates
│           ├── retriever.py            # Hybrid RRF search, corpus ingestion, and query_logs telemetry
│           └── generator.py            # Structured Gemini RAG generation + grounded extractive fallback
├── scripts/
│   └── ingest_corpus.py                # CLI to chunk, tokenize, embed, and upsert data/mock_docs/
├── tests/
│   ├── unit/                           # Schema, snippet, config, health, tokenizer, embeddings & guardrails unit tests (21 tests)
│   └── integration/                    # Live PG16 pgvector + RRF + end-to-end RAG pipeline integration tests (3 tests)
├── docker-compose.yml                  # pgvector/pgvector:pg16 + FastAPI service
└── .env.example                        # Safe configuration placeholders
```

## 🚀 Local Quickstart

```bash
# 1. Start PostgreSQL 16 + pgvector
docker compose up -d postgres

# 2. Ingest mock corpus & run API tests locally
cd api
uv venv --python 3.13
uv pip install -e ".[dev]"
python ../scripts/ingest_corpus.py
pytest -v
ruff check app ../tests ../scripts
```
