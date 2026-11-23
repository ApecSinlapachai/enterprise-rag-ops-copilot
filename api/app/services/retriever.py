"""Hybrid pgvector + FTS + pg_trgm RRF retriever and corpus ingestion service."""

from __future__ import annotations

import hashlib
import logging
import pathlib
import time
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from psycopg.types.json import Jsonb

from app.config import Settings
from app.db import DatabaseManager
from app.schemas.rag import CitationItem, format_citation_snippet
from app.services.embeddings import EmbeddingService, format_pgvector_literal
from app.services.tokenizer import (
    build_or_tsquery,
    chunk_markdown_document,
    extract_sku_or_error_code,
)

logger = logging.getLogger(__name__)

_DEFAULT_HYBRID_SQL_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "sql" / "002_hybrid_search_query.sql"
)
_SQL_PATH_CANDIDATES: tuple[pathlib.Path, ...] = (
    _DEFAULT_HYBRID_SQL_PATH,
    pathlib.Path.cwd() / "sql" / "002_hybrid_search_query.sql",
    pathlib.Path("/app/sql/002_hybrid_search_query.sql"),
)

_FALLBACK_HYBRID_SQL = """
WITH vec_search AS (
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        d.source_key,
        d.title AS doc_title,
        dc.section_path,
        dc.content,
        (1.0 - (dc.embedding <=> %(vec)s::vector(1536))) AS vec_similarity,
        ROW_NUMBER() OVER (ORDER BY dc.embedding <=> %(vec)s::vector(1536) ASC) AS vec_rank
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE d.is_active = TRUE
      AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> %(vec)s::vector(1536) ASC
    LIMIT 20
),
fts_query AS (
    SELECT to_tsquery('simple', NULLIF(%(tsq)s, '')) AS q
),
fts_search AS (
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        d.source_key,
        d.title AS doc_title,
        dc.section_path,
        dc.content,
        (
            COALESCE(ts_rank_cd(dc.content_tsv, fq.q), 0.0)
            + CASE
                WHEN NULLIF(%(code)s, '') IS NOT NULL
                 AND dc.search_text_tokenized ~* %(code)s
                THEN 0.25
                ELSE 0.0
              END
        ) AS fts_rank,
        ROW_NUMBER() OVER (
            ORDER BY (
                COALESCE(ts_rank_cd(dc.content_tsv, fq.q), 0.0)
                + CASE
                    WHEN NULLIF(%(code)s, '') IS NOT NULL
                     AND dc.search_text_tokenized ~* %(code)s
                    THEN 0.25
                    ELSE 0.0
                  END
            ) DESC
        ) AS fts_rank_pos
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    CROSS JOIN fts_query fq
    WHERE d.is_active = TRUE
      AND (
          (fq.q IS NOT NULL AND dc.content_tsv @@ fq.q)
          OR (
              NULLIF(%(code)s, '') IS NOT NULL
              AND dc.search_text_tokenized ~* %(code)s
          )
      )
    ORDER BY fts_rank DESC
    LIMIT 20
),
combined AS (
    SELECT
        COALESCE(v.chunk_id, f.chunk_id) AS chunk_id,
        COALESCE(v.document_id, f.document_id) AS document_id,
        COALESCE(v.source_key, f.source_key) AS source_key,
        COALESCE(v.doc_title, f.doc_title) AS doc_title,
        COALESCE(v.section_path, f.section_path) AS section_path,
        COALESCE(v.content, f.content) AS content,
        v.vec_similarity AS precomputed_vec_sim,
        COALESCE(f.fts_rank, 0.0) AS fts_rank,
        (
            COALESCE(0.6 / (60.0 + v.vec_rank), 0.0)
            + COALESCE(0.4 / (60.0 + f.fts_rank_pos), 0.0)
        ) AS rrf_score
    FROM vec_search v
    FULL OUTER JOIN fts_search f ON v.chunk_id = f.chunk_id
)
SELECT
    c.chunk_id,
    c.document_id,
    c.source_key,
    c.doc_title,
    c.section_path,
    c.content,
    COALESCE(
        c.precomputed_vec_sim,
        CASE
            WHEN dc.embedding IS NOT NULL
            THEN (1.0 - (dc.embedding <=> %(vec)s::vector(1536)))
            ELSE 0.0
        END
    ) AS vec_similarity,
    c.fts_rank,
    c.rrf_score
FROM combined c
JOIN document_chunks dc ON dc.id = c.chunk_id
ORDER BY c.rrf_score DESC
LIMIT 5;
"""


def _load_hybrid_sql(sql_path: pathlib.Path | None = None) -> str:
    """Load sql/002_hybrid_search_query.sql and convert $1/$2/$3 to psycopg3 named params."""
    candidates = (sql_path,) if sql_path is not None else _SQL_PATH_CANDIDATES
    for candidate in candidates:
        if candidate.is_file():
            raw_sql = candidate.read_text(encoding="utf-8")
            return (
                raw_sql.replace("$1", "%(vec)s")
                .replace("$2", "%(tsq)s")
                .replace("$3", "%(code)s")
            )
    return _FALLBACK_HYBRID_SQL


@dataclass(frozen=True)
class RetrievalChunk:
    """Internal full-content retrieved chunk paired with its public CitationItem."""

    citation: CitationItem
    full_content: str


@dataclass(frozen=True)
class RetrievalBundle:
    """Hybrid search outputs and timing telemetry."""

    chunks: list[RetrievalChunk]
    citations: list[CitationItem]
    max_vec_similarity: float
    max_fts_rank: float
    top_rrf_score: float
    retrieval_ms: int
    tsquery_used: str
    code_token_used: str | None


@dataclass(frozen=True)
class CorpusIngestSummary:
    """Summary returned after ingesting markdown documents into PostgreSQL."""

    documents_processed: int
    chunks_written: int
    source_keys: list[str]


class HybridRetriever:
    """Executes Thai-English Hybrid RRF search against PostgreSQL 16 + pgvector."""

    def __init__(
        self,
        db: DatabaseManager,
        embedder: EmbeddingService,
        settings: Settings,
        sql_path: pathlib.Path | None = None,
    ) -> None:
        self._db = db
        self._embedder = embedder
        self._settings = settings
        self._hybrid_sql = _load_hybrid_sql(sql_path)

    def retrieve(self, query: str) -> RetrievalBundle:
        """Run 1536-dim vector + PyThaiNLP FTS + pg_trgm RRF retrieval."""
        start_ns = time.perf_counter_ns()
        query_vec = self._embedder.embed_query(query)
        vec_literal = format_pgvector_literal(
            query_vec, expected_dim=self._settings.gemini_embed_dim
        )
        tsq = build_or_tsquery(query)
        code_token = extract_sku_or_error_code(query)

        with self._db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                self._hybrid_sql,
                {"vec": vec_literal, "tsq": tsq, "code": code_token},
            )
            rows = cur.fetchall()

        retrieved_chunks: list[RetrievalChunk] = []
        citations: list[CitationItem] = []

        for row in rows:
            raw_content = str(row["content"])
            citation = CitationItem(
                chunk_id=row["chunk_id"],
                source_key=str(row["source_key"]),
                doc_title=str(row["doc_title"]),
                section_path=str(row["section_path"] or ""),
                snippet=format_citation_snippet(
                    raw_content, max_chars=self._settings.citation_snippet_max_chars
                ),
                vec_similarity=float(row["vec_similarity"] or 0.0),
                fts_rank=float(row["fts_rank"] or 0.0),
                rrf_score=float(row["rrf_score"] or 0.0),
            )
            citations.append(citation)
            retrieved_chunks.append(RetrievalChunk(citation=citation, full_content=raw_content))

        elapsed_ms = max(0, int((time.perf_counter_ns() - start_ns) // 1_000_000))
        max_vec = max((c.vec_similarity for c in citations), default=0.0)
        max_fts = max((c.fts_rank for c in citations), default=0.0)
        top_rrf = max((c.rrf_score for c in citations), default=0.0)

        return RetrievalBundle(
            chunks=retrieved_chunks,
            citations=citations,
            max_vec_similarity=max_vec,
            max_fts_rank=max_fts,
            top_rrf_score=top_rrf,
            retrieval_ms=elapsed_ms,
            tsquery_used=tsq,
            code_token_used=code_token,
        )


def ingest_markdown_corpus(
    db: DatabaseManager,
    embedder: EmbeddingService,
    docs_dir: pathlib.Path,
) -> CorpusIngestSummary:
    """Chunk, tokenize, embed, and upsert all Markdown files from `docs_dir`."""
    md_files = sorted(docs_dir.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No markdown documents found in {docs_dir}")

    docs_processed = 0
    total_chunks = 0
    source_keys: list[str] = []

    with db.connection() as conn:
        with conn.cursor() as cur:
            for path in md_files:
                raw_md = path.read_text(encoding="utf-8")
                content_hash = hashlib.sha256(raw_md.encode("utf-8")).hexdigest()
                meta, chunks = chunk_markdown_document(raw_md, fallback_source_key=path.name)
                if not chunks:
                    continue

                cur.execute(
                    """
                    INSERT INTO documents (
                        source_key, title, language, doc_type, version,
                        content_hash, is_active, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
                    ON CONFLICT (source_key) DO UPDATE SET
                        title = EXCLUDED.title,
                        language = EXCLUDED.language,
                        doc_type = EXCLUDED.doc_type,
                        version = EXCLUDED.version,
                        content_hash = EXCLUDED.content_hash,
                        is_active = TRUE,
                        metadata = EXCLUDED.metadata
                    RETURNING id
                    """,
                    (
                        meta.source_key,
                        meta.title,
                        meta.language,
                        meta.doc_type,
                        meta.version,
                        content_hash,
                        Jsonb({"file_name": path.name}),
                    ),
                )
                doc_row = cur.fetchone()
                if not doc_row:
                    raise RuntimeError(f"Failed to upsert document {meta.source_key}")
                doc_id = doc_row["id"]

                cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc_id,))

                for chunk in chunks:
                    embed_input = f"{meta.title}\n{chunk.section_path}\n{chunk.content}"
                    vec = embedder.embed_document(embed_input, title=meta.title)
                    vec_literal = format_pgvector_literal(vec, expected_dim=embedder.embed_dim)
                    cur.execute(
                        """
                        INSERT INTO document_chunks (
                            document_id, chunk_index, section_path, language,
                            content, search_text_tokenized, token_count, embedding, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector(1536), %s)
                        """,
                        (
                            doc_id,
                            chunk.chunk_index,
                            chunk.section_path,
                            chunk.language,
                            chunk.content,
                            chunk.search_text_tokenized,
                            chunk.token_count,
                            vec_literal,
                            Jsonb({"source_key": meta.source_key, "doc_type": meta.doc_type}),
                        ),
                    )
                    total_chunks += 1

                docs_processed += 1
                source_keys.append(meta.source_key)

        conn.commit()

    return CorpusIngestSummary(
        documents_processed=docs_processed,
        chunks_written=total_chunks,
        source_keys=source_keys,
    )


def record_query_log(
    db: DatabaseManager,
    *,
    request_id: str,
    query_text: str,
    query_language: str,
    grounding_status: str,
    refusal_reason: str | None,
    max_vec_similarity: float | None,
    max_fts_rank: float | None,
    top_rrf_score: float | None,
    confidence_score: float | None,
    answer_text: str,
    cited_chunk_ids: Sequence[UUID],
    retrieval_ms: int,
    generation_ms: int,
    total_latency_ms: int,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    client_ip_hash: str | None,
) -> None:
    """Persist RAG query telemetry and groundedness status to PostgreSQL query_logs."""
    try:
        with db.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_logs (
                    request_id, query_text, query_language, grounding_status, refusal_reason,
                    max_vec_similarity, max_fts_rank, top_rrf_score, confidence_score,
                    answer_text, cited_chunk_ids, retrieval_ms, generation_ms,
                    total_latency_ms, model_name, input_tokens, output_tokens,
                    estimated_cost_usd, client_ip_hash
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s::uuid[], %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    request_id,
                    query_text,
                    query_language,
                    grounding_status,
                    refusal_reason,
                    max_vec_similarity,
                    max_fts_rank,
                    top_rrf_score,
                    confidence_score,
                    answer_text,
                    [str(cid) for cid in cited_chunk_ids],
                    retrieval_ms,
                    generation_ms,
                    total_latency_ms,
                    model_name,
                    input_tokens,
                    output_tokens,
                    round(estimated_cost_usd, 6),
                    client_ip_hash,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to record query_logs telemetry for %s: %s", request_id, exc)
