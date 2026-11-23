"""Integration tests for PostgreSQL 16 pgvector schema and RRF hybrid search SQL."""

from __future__ import annotations

import pathlib
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
HYBRID_SQL_PATH = ROOT_DIR / "sql" / "002_hybrid_search_query.sql"


def _can_connect_postgres(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() == (1,)
    except Exception:
        return False


def test_live_database_schema_and_hybrid_rrf_query() -> None:
    """Verify 001_schema.sql tables, extensions, and 002_hybrid_search_query.sql on PG16."""
    cfg = get_settings()
    if not _can_connect_postgres(cfg.database_url):
        pytest.skip("PostgreSQL container is not running on DATABASE_URL")

    raw_sql = HYBRID_SQL_PATH.read_text(encoding="utf-8")
    psycopg_sql = (
        raw_sql.replace("$1", "%(vec)s")
        .replace("$2", "%(tsq)s")
        .replace("$3", "%(code)s")
    )

    unit_val = 1.0 / (1536**0.5)
    vec_literal = "[" + ",".join(f"{unit_val:.8f}" for _ in range(1536)) + "]"

    with psycopg.connect(cfg.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT extname
                FROM pg_extension
                WHERE extname IN ('vector', 'pg_trgm')
                ORDER BY extname
                """
            )
            extensions = [row[0] for row in cur.fetchall()]
            assert extensions == ["pg_trgm", "vector"]

            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
            for expected_table in (
                "document_chunks",
                "documents",
                "eval_results",
                "eval_runs",
                "query_logs",
                "triage_tickets",
            ):
                assert expected_table in tables

            doc_id = uuid4()
            chunk_id = uuid4()
            cur.execute(
                """
                INSERT INTO documents (id, source_key, title, language, doc_type, content_hash)
                VALUES (%s, %s, %s, 'bilingual', 'sla', 'hash-day2-verify')
                """,
                (doc_id, f"test_sla_{doc_id.hex[:8]}.md", "Enterprise SLA & Refund Policy"),
            )
            cur.execute(
                """
                INSERT INTO document_chunks (
                    id, document_id, chunk_index, section_path, language,
                    content, search_text_tokenized, token_count, embedding
                )
                VALUES (%s, %s, 0, 'SLA > Refund', 'bilingual', %s, %s, 14, %s::vector(1536))
                """,
                (
                    chunk_id,
                    doc_id,
                    "นโยบายการคืนเงิน SLA สำหรับใบแจ้งหนี้ INV-2026-0091 เมื่อเกิดข้อผิดพลาด ERR-503",
                    "นโยบาย การ คืนเงิน sla สำหรับ ใบแจ้งหนี้ inv-2026-0091 เมื่อ เกิด ข้อผิดพลาด err-503",
                    vec_literal,
                ),
            )

            cur.execute(
                psycopg_sql,
                {
                    "vec": vec_literal,
                    "tsq": "คืนเงิน | sla",
                    "code": "INV-2026-0091",
                },
            )
            rows = cur.fetchall()
            assert len(rows) >= 1
            matching = [r for r in rows if r[0] == chunk_id]
            assert len(matching) == 1
            _, _, _, _, _, _, vec_sim, fts_rank, rrf_score = matching[0]
            assert vec_sim > 0.99
            assert fts_rank >= 0.25
            assert rrf_score > 0.0

        conn.rollback()


def test_live_health_endpoint_with_postgres() -> None:
    """Verify FastAPI /health returns status='ok' against live pgvector database."""
    cfg = get_settings()
    if not _can_connect_postgres(cfg.database_url):
        pytest.skip("PostgreSQL container is not running on DATABASE_URL")

    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["database_connected"] is True
