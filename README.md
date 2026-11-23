# 🤖 Enterprise RAG Ops Copilot (`enterprise-rag-ops-copilot`)

> **Status:** Active Build — PostgreSQL 16 (`pgvector` + `pg_trgm`) RRF Hybrid Search, FastAPI `/health` with PyThaiNLP pre-warm, and Pydantic v2 Contracts verified (11/11 tests passing).

A production-minded **Thai–English Hybrid RAG Copilot** and **Pydantic v2 Ticket Triage API** built with `FastAPI`, `PostgreSQL 16 (pgvector + FTS + pg_trgm)`, `PyThaiNLP`, and `Gemini API`, featuring dual-stage hallucination refusal, a 25-case Golden Eval Gate, and a No-Login Next.js live demo.

## 🏗️ Repository Layout

```text
enterprise-rag-ops-copilot/
├── sql/
│   ├── 001_schema.sql                  # PostgreSQL 16 + pgvector + pg_trgm DDL
│   └── 002_hybrid_search_query.sql     # Reference RRF hybrid search CTE
├── api/
│   ├── Dockerfile                      # Multi-stage python:3.12-slim container
│   ├── pyproject.toml                  # Dependencies, Ruff, Pytest config
│   └── app/
│       ├── config.py                   # Pydantic BaseSettings & guardrail thresholds
│       ├── db.py                       # psycopg3 ConnectionPool + health probe
│       ├── main.py                     # FastAPI app, CORS, /health
│       └── schemas/                    # Pydantic v2 contracts (1:1 with SQL CHECKs)
├── tests/
│   ├── unit/                           # Schema, snippet truncation, config, and health unit tests (9 tests)
│   └── integration/                    # Live PG16 pgvector + RRF hybrid search & /health integration tests (2 tests)
├── docker-compose.yml                  # pgvector/pgvector:pg16 + FastAPI service
└── .env.example                        # Safe configuration placeholders
```

## 🚀 Local Quickstart

```bash
# 1. Start PostgreSQL 16 + pgvector
docker compose up -d postgres

# 2. Run API tests locally
cd api
uv venv --python 3.13
uv pip install -e ".[dev]"
pytest
ruff check app ../tests
```
