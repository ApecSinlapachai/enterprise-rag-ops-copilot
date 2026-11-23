"""Unit tests for Settings, CORS parsing, and FastAPI /health endpoint."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_settings_cors_origins_list() -> None:
    cfg = Settings(
        cors_origins="http://localhost:3000, https://demo.vercel.app , ",
        database_url="postgresql://postgres:postgres@localhost:5432/rag_ops",
    )
    assert cfg.cors_origins_list == [
        "http://localhost:3000",
        "https://demo.vercel.app",
    ]


def test_health_endpoint_reports_degraded_when_db_offline(monkeypatch) -> None:
    cfg = Settings(database_url="postgresql://postgres:postgres@127.0.0.1:59999/none")
    app = create_app(cfg)

    with TestClient(app) as client:
        monkeypatch.setattr(app.state.db, "check_health", lambda: False)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["database_connected"] is False
        assert body["version"] == cfg.app_version


def test_health_endpoint_reports_ok_when_db_connected(monkeypatch) -> None:
    cfg = Settings()
    app = create_app(cfg)

    with TestClient(app) as client:
        monkeypatch.setattr(app.state.db, "check_health", lambda: True)
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database_connected"] is True
