-- ============================================================================
-- enterprise-rag-ops-copilot — PostgreSQL 16 + pgvector Schema
-- Target: PostgreSQL 16+ with pgvector (>= 0.7.0) and pg_trgm
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Shared updated_at trigger function
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 1. Source Knowledge Documents (SOPs, SLAs, Runbooks, Policies)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key      TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    language        TEXT NOT NULL CHECK (language IN ('th', 'en', 'bilingual')),
    doc_type        TEXT NOT NULL CHECK (doc_type IN ('sop', 'sla', 'faq', 'security_policy', 'runbook', 'pricing')),
    version         TEXT NOT NULL DEFAULT '1.0',
    content_hash    TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_documents_active_type
    ON documents (is_active, doc_type);

-- ----------------------------------------------------------------------------
-- 2. Thai-English Document Chunks (Vector + Word-Segmented FTS + Trigram)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_chunks (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id             UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index             INTEGER NOT NULL CHECK (chunk_index >= 0),
    section_path            TEXT NOT NULL DEFAULT '',
    language                TEXT NOT NULL CHECK (language IN ('th', 'en', 'bilingual')),
    content                 TEXT NOT NULL,
    search_text_tokenized   TEXT NOT NULL,
    token_count             INTEGER NOT NULL CHECK (token_count > 0),
    embedding               vector(1536),
    content_tsv             tsvector GENERATED ALWAYS AS (
                                to_tsvector('simple', coalesce(search_text_tokenized, ''))
                            ) STORED,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id
    ON document_chunks (document_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_document_chunks_content_tsv_gin
    ON document_chunks USING gin (content_tsv);

CREATE INDEX IF NOT EXISTS idx_document_chunks_search_trgm_gin
    ON document_chunks USING gin (search_text_tokenized gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata_gin
    ON document_chunks USING gin (metadata);

-- ----------------------------------------------------------------------------
-- 3. RAG Query Telemetry, Groundedness Decisions & Cost Logs
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS query_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id          TEXT NOT NULL UNIQUE,
    query_text          TEXT NOT NULL,
    query_language      TEXT NOT NULL CHECK (query_language IN ('th', 'en', 'mixed', 'unknown')),
    grounding_status    TEXT NOT NULL CHECK (
                            grounding_status IN (
                                'ANSWERED',
                                'REFUSED_LOW_EVIDENCE',
                                'BLOCKED_INJECTION',
                                'ERROR_FALLBACK'
                            )
                        ),
    refusal_reason      TEXT,
    max_vec_similarity  DOUBLE PRECISION CHECK (
                            max_vec_similarity IS NULL
                            OR (max_vec_similarity >= -1.0 AND max_vec_similarity <= 1.0)
                        ),
    max_fts_rank        DOUBLE PRECISION CHECK (max_fts_rank IS NULL OR max_fts_rank >= 0.0),
    top_rrf_score       DOUBLE PRECISION CHECK (top_rrf_score IS NULL OR top_rrf_score >= 0.0),
    confidence_score    DOUBLE PRECISION CHECK (
                            confidence_score IS NULL
                            OR (confidence_score >= 0.0 AND confidence_score <= 1.0)
                        ),
    answer_text         TEXT NOT NULL,
    cited_chunk_ids     UUID[] NOT NULL DEFAULT '{}'::uuid[],
    retrieval_ms        INTEGER NOT NULL CHECK (retrieval_ms >= 0),
    generation_ms       INTEGER NOT NULL CHECK (generation_ms >= 0),
    total_latency_ms    INTEGER NOT NULL CHECK (total_latency_ms >= 0),
    model_name          TEXT NOT NULL,
    input_tokens        INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens       INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    estimated_cost_usd  NUMERIC(10, 6) NOT NULL DEFAULT 0.000000 CHECK (estimated_cost_usd >= 0),
    client_ip_hash      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_logs_status_created
    ON query_logs (grounding_status, created_at DESC);

-- ----------------------------------------------------------------------------
-- 4. Pydantic-Validated AI Ticket Triage Records
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS triage_tickets (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id              TEXT NOT NULL UNIQUE,
    raw_message             TEXT NOT NULL,
    source_channel          TEXT NOT NULL DEFAULT 'web_demo' CHECK (
                                source_channel IN ('web_demo', 'line', 'email', 'api', 'eval')
                            ),
    language_detected       TEXT NOT NULL CHECK (language_detected IN ('th', 'en', 'mixed')),
    category                TEXT NOT NULL CHECK (
                                category IN (
                                    'billing_refund',
                                    'technical_incident',
                                    'account_access',
                                    'sla_escalation',
                                    'feature_request',
                                    'general_inquiry',
                                    'prompt_injection_attempt'
                                )
                            ),
    urgency_score           INTEGER NOT NULL CHECK (urgency_score BETWEEN 1 AND 5),
    priority                TEXT NOT NULL CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    sentiment               TEXT NOT NULL CHECK (sentiment IN ('negative', 'neutral', 'positive')),
    summary                 TEXT NOT NULL,
    suggested_action        TEXT NOT NULL,
    suggested_team          TEXT NOT NULL CHECK (
                                suggested_team IN (
                                    'l1_support',
                                    'l2_engineering',
                                    'billing_ops',
                                    'security_ops',
                                    'account_management'
                                )
                            ),
    requires_human_review   BOOLEAN NOT NULL DEFAULT FALSE,
    extracted_entities      JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_name              TEXT NOT NULL,
    input_tokens            INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens           INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    estimated_cost_usd      NUMERIC(10, 6) NOT NULL DEFAULT 0.000000 CHECK (estimated_cost_usd >= 0),
    latency_ms              INTEGER NOT NULL CHECK (latency_ms >= 0),
    validation_status       TEXT NOT NULL DEFAULT 'pydantic_passed' CHECK (
                                validation_status IN (
                                    'pydantic_passed',
                                    'repaired_retry',
                                    'deterministic_fallback'
                                )
                            ),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_triage_tickets_priority_created
    ON triage_tickets (priority, created_at DESC);

-- ----------------------------------------------------------------------------
-- 5. Golden Evaluation Runs & Per-Case Results (25 Cases + Cost Metrics)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eval_runs (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_tag                     TEXT NOT NULL,
    git_sha                     TEXT,
    eval_mode                   TEXT NOT NULL CHECK (eval_mode IN ('live_gemini', 'ci_mock', 'hybrid_replay')),
    model_name                  TEXT NOT NULL,
    embedding_model             TEXT NOT NULL,
    total_cases                 INTEGER NOT NULL CHECK (total_cases > 0),
    passed_cases                INTEGER NOT NULL CHECK (passed_cases >= 0 AND passed_cases <= total_cases),
    citation_hit_rate           NUMERIC(5, 4) NOT NULL CHECK (citation_hit_rate >= 0 AND citation_hit_rate <= 1),
    refusal_precision           NUMERIC(5, 4) NOT NULL CHECK (refusal_precision >= 0 AND refusal_precision <= 1),
    injection_block_rate        NUMERIC(5, 4) NOT NULL CHECK (injection_block_rate >= 0 AND injection_block_rate <= 1),
    json_schema_pass_rate       NUMERIC(5, 4) NOT NULL CHECK (json_schema_pass_rate >= 0 AND json_schema_pass_rate <= 1),
    avg_latency_ms              INTEGER NOT NULL CHECK (avg_latency_ms >= 0),
    p95_latency_ms              INTEGER NOT NULL CHECK (p95_latency_ms >= 0),
    total_cost_usd              NUMERIC(10, 6) NOT NULL DEFAULT 0.000000 CHECK (total_cost_usd >= 0),
    cost_per_1k_requests_usd    NUMERIC(10, 4) NOT NULL DEFAULT 0.0000 CHECK (cost_per_1k_requests_usd >= 0),
    gate_passed                 BOOLEAN NOT NULL,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eval_results (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_run_id             UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    case_id                 TEXT NOT NULL,
    category                TEXT NOT NULL CHECK (
                                category IN (
                                    'thai_in_scope',
                                    'english_in_scope',
                                    'code_mixed_th_en',
                                    'out_of_scope_unanswerable',
                                    'prompt_injection',
                                    'ticket_triage'
                                )
                            ),
    language                TEXT NOT NULL CHECK (language IN ('th', 'en', 'mixed')),
    input_payload           TEXT NOT NULL,
    expected_outcome        TEXT NOT NULL CHECK (
                                expected_outcome IN (
                                    'ANSWERED',
                                    'REFUSED_LOW_EVIDENCE',
                                    'BLOCKED_INJECTION',
                                    'VALID_TRIAGE_JSON'
                                )
                            ),
    actual_outcome          TEXT NOT NULL CHECK (
                                actual_outcome IN (
                                    'ANSWERED',
                                    'REFUSED_LOW_EVIDENCE',
                                    'BLOCKED_INJECTION',
                                    'VALID_TRIAGE_JSON',
                                    'FAILED'
                                )
                            ),
    passed                  BOOLEAN NOT NULL,
    citation_hit            BOOLEAN,
    schema_valid            BOOLEAN,
    expected_source_keys    TEXT[] NOT NULL DEFAULT '{}'::text[],
    actual_source_keys      TEXT[] NOT NULL DEFAULT '{}'::text[],
    latency_ms              INTEGER NOT NULL CHECK (latency_ms >= 0),
    input_tokens            INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens           INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    estimated_cost_usd      NUMERIC(10, 6) NOT NULL DEFAULT 0.000000 CHECK (estimated_cost_usd >= 0),
    failure_reason          TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (eval_run_id, case_id)
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run_category
    ON eval_results (eval_run_id, category);
