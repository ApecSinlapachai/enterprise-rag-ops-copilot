# ADR-0001: Hybrid RRF Search via PostgreSQL 16 (`pgvector` + `PyThaiNLP` + `pg_trgm`)

- **Status:** Accepted
- **Date:** 2026-11-26
- **Deciders:** Apec Sinlapachai

---

## 1. Context
Enterprise B2B SaaS operations queries in Thailand mix Thai prose (no whitespace word boundaries), English technical terms, and exact identifiers (`INV-2026-0091`, `ERR-503`, `ERR-AUTH-403`). Pure semantic vector search misses exact SKU/error codes and struggles with Thai compound terms, while hosting a separate managed vector DB adds cost and operational complexity beyond a `$0` free-tier architecture.

## 2. Decision
> We will consolidate vector, lexical, and exact-code retrieval inside **PostgreSQL 16** using **`pgvector` (1536-dim L2-normalized `gemini-embedding-001`) + `PyThaiNLP (newmm)` word-segmented `tsvector` FTS + `pg_trgm` (`~*`) exact-code boosting** fused with **Reciprocal Rank Fusion (RRF: `0.6 / (60 + vec_rank) + 0.4 / (60 + fts_rank)`)** in `sql/002_hybrid_search_query.sql`.

## 3. Alternatives Considered
| Option | Pros | Cons | Why Rejected / Chosen |
| :--- | :--- | :--- | :--- |
| **PostgreSQL 16 (`pgvector` + `PyThaiNLP` + `pg_trgm` RRF) (Chosen)** | Single transactional DB for chunks + telemetry; `$0` on Supabase Free & local Docker; handles Thai segmentation + exact SKUs | Requires explicit Python L2 normalization for truncated 1536-dim embeddings and `PyThaiNLP` lifespan warm-up | Best accuracy, observability, and `$0` operational simplicity |
| **Pure Vector Search (Pinecone / Qdrant)** | Fast semantic lookup | Misses exact error codes/SKUs; adds second database & sync drift with `query_logs` | Rejected due to lexical/SKU recall gaps and multi-DB overhead |
| **BM25 / FTS Only** | Zero embedding cost; strong exact matches | Fails on semantic paraphrases and cross-lingual TH↔EN queries | Rejected; cannot answer English docs from Thai queries reliably |

## 4. Consequences
- **Positive:** Achieved `1.0000` Citation Hit Rate across Thai, English, and code-mixed Golden Eval cases with zero extra infrastructure cost; exact `vec_similarity` is recomputed on final top-5 winners even for FTS-only matches.
- **Negative / Trade-offs:** Requires pre-warming `PyThaiNLP` during FastAPI startup and avoiding literal `%` characters inside `.sql` files executed by `psycopg3`.
- **Reversibility:** Medium — retrieval logic is encapsulated inside `api/app/services/retriever.py` and `sql/002_hybrid_search_query.sql`.
