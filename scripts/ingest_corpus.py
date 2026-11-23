"""CLI script to chunk, tokenize, embed, and upsert data/mock_docs/ into PostgreSQL."""

from __future__ import annotations

import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.config import get_settings  # noqa: E402
from app.db import DatabaseManager  # noqa: E402
from app.services.embeddings import EmbeddingService  # noqa: E402
from app.services.retriever import ingest_markdown_corpus  # noqa: E402


def main() -> int:
    settings = get_settings()
    docs_dir = ROOT_DIR / "data" / "mock_docs"

    db = DatabaseManager(settings.database_url)
    db.open()
    try:
        if not db.check_health():
            print("ERROR: PostgreSQL database is not reachable on DATABASE_URL.", file=sys.stderr)
            return 1

        embedder = EmbeddingService(settings)
        mode = "live_gemini" if embedder.is_live_mode else "deterministic_mock"
        print(f"Starting corpus ingestion from {docs_dir} (embedding_mode={mode})...")

        summary = ingest_markdown_corpus(db=db, embedder=embedder, docs_dir=docs_dir)
        print(
            f"Ingested {summary.documents_processed} documents and "
            f"{summary.chunks_written} chunks successfully."
        )
        for key in summary.source_keys:
            print(f"  - {key}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
