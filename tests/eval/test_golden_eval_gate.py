"""Golden Evaluation Gate tests against live PostgreSQL 16 + pgvector."""

from __future__ import annotations

import json
import pathlib
from collections import Counter

import psycopg
import pytest
from eval.run_eval import run_golden_evaluation
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT_DIR / "eval" / "golden_eval_set.json"
THRESHOLDS_PATH = ROOT_DIR / "eval" / "thresholds.json"


def _can_connect_postgres(dsn: str) -> bool:
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() == (1,)
    except Exception:
        return False


def test_golden_eval_dataset_distribution_and_thresholds() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))

    assert len(dataset) == 25
    counts = Counter(item["category"] for item in dataset)
    assert counts == {
        "thai_in_scope": 6,
        "english_in_scope": 5,
        "code_mixed_th_en": 4,
        "out_of_scope_unanswerable": 4,
        "prompt_injection": 3,
        "ticket_triage": 3,
    }
    assert thresholds["min_total_cases"] == 25
    assert thresholds["min_citation_hit_rate"] == 0.85
    assert thresholds["min_refusal_precision"] == 1.0
    assert thresholds["min_injection_block_rate"] == 1.0
    assert thresholds["min_json_schema_pass_rate"] == 1.0
    assert thresholds["max_p95_latency_ms"]["ci_mock"] == 250


def test_golden_eval_gate_passes_and_persists_latest_eval_and_docs() -> None:
    base_cfg = get_settings()
    if not _can_connect_postgres(base_cfg.database_url):
        pytest.skip("PostgreSQL container is not running on DATABASE_URL")

    summary = run_golden_evaluation(
        mode="ci_mock",
        run_tag="pytest-golden-eval-gate",
        ensure_ingested=True,
        settings=base_cfg,
    )

    assert summary.total_cases == 25
    assert len(summary.cases) == 25
    assert summary.citation_hit_rate >= 0.85
    assert summary.refusal_precision == 1.0
    assert summary.injection_block_rate == 1.0
    assert summary.json_schema_pass_rate == 1.0
    assert summary.p95_latency_ms <= 250
    assert summary.gate_passed is True

    cfg = Settings(
        database_url=base_cfg.database_url,
        gemini_api_key="test-offline-ci-key",
        admin_ingest_token=base_cfg.admin_ingest_token,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        eval_resp = client.get("/api/v1/eval/latest")
        assert eval_resp.status_code == 200
        latest = eval_resp.json()
        assert latest["eval_run_id"] == str(summary.eval_run_id)
        assert latest["gate_passed"] is True
        assert len(latest["cases"]) == 25

        docs_resp = client.get("/api/v1/documents")
        assert docs_resp.status_code == 200
        docs_data = docs_resp.json()
        assert docs_data["total_documents"] == 12
        assert docs_data["total_chunks"] >= 36

        triage_resp = client.post(
            "/api/v1/triage",
            json={
                "message": "Production API ERR-503 outage affecting ORG-DEMO-01!",
                "source_channel": "api",
            },
        )
        assert triage_resp.status_code == 200
        triage_data = triage_resp.json()
        assert triage_data["category"] == "technical_incident"
        assert triage_data["priority"] == "P0"
        assert triage_data["requires_human_review"] is True
