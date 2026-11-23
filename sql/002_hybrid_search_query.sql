-- ============================================================================
-- enterprise-rag-ops-copilot — Reference Hybrid Search CTE (RRF)
-- Notes:
-- 1) Python (embeddings.py / retriever.py) MUST L2-normalize $1 after
--    1536-dim truncation and validate non-zero L2 norm before executing
--    cosine distance (<=>) so zero vectors never yield NaN.
-- 2) $2 is a domain-stopword-filtered, sanitized OR-joined tsquery string
--    ('tok1 | tok2') built in tokenizer.py (avoiding strict AND collapse on
--    multi-word Thai queries).
-- 3) $3 is an optional regex-escaped exact code/SKU/error token (e.g.,
--    'ERR-503', 'INV-2026-0091', or NULL) extracted in tokenizer.py to boost
--    pg_trgm (~* GIN trigram index) matches cleanly with psycopg3 parameters.
-- 4) For FTS-only winners outside the top-20 vector CTE, the final SELECT
--    computes exact cosine similarity against dc.embedding so vec_similarity
--    is never falsely reported as 0.0 in UI citations.
-- ============================================================================
WITH vec_search AS (
    SELECT
        dc.id AS chunk_id,
        dc.document_id,
        d.source_key,
        d.title AS doc_title,
        dc.section_path,
        dc.content,
        (1.0 - (dc.embedding <=> $1::vector(1536))) AS vec_similarity,
        ROW_NUMBER() OVER (ORDER BY dc.embedding <=> $1::vector(1536) ASC) AS vec_rank
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE d.is_active = TRUE
      AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> $1::vector(1536) ASC
    LIMIT 20
),
fts_query AS (
    SELECT to_tsquery('simple', NULLIF($2, '')) AS q
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
                WHEN NULLIF($3, '') IS NOT NULL
                 AND dc.search_text_tokenized ~* $3
                THEN 0.25
                ELSE 0.0
              END
        ) AS fts_rank,
        ROW_NUMBER() OVER (
            ORDER BY (
                COALESCE(ts_rank_cd(dc.content_tsv, fq.q), 0.0)
                + CASE
                    WHEN NULLIF($3, '') IS NOT NULL
                     AND dc.search_text_tokenized ~* $3
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
              NULLIF($3, '') IS NOT NULL
              AND dc.search_text_tokenized ~* $3
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
            THEN (1.0 - (dc.embedding <=> $1::vector(1536)))
            ELSE 0.0
        END
    ) AS vec_similarity,
    c.fts_rank,
    c.rrf_score
FROM combined c
JOIN document_chunks dc ON dc.id = c.chunk_id
ORDER BY c.rrf_score DESC
LIMIT 5;
