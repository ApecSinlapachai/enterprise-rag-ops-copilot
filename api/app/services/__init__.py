"""Core service modules for Enterprise RAG Ops Copilot."""

from app.services.embeddings import (
    EmbeddingService,
    build_deterministic_embedding,
    format_pgvector_literal,
    l2_normalize_vector,
)
from app.services.generator import GenerationResult, RAGGenerator
from app.services.guardrails import (
    InjectionGateDecision,
    PostLLMGateDecision,
    RetrievalGateDecision,
    apply_post_llm_groundedness_gate,
    check_pre_llm_retrieval_gate,
    check_prompt_injection,
)
from app.services.retriever import (
    CorpusIngestSummary,
    HybridRetriever,
    RetrievalBundle,
    RetrievalChunk,
    ingest_markdown_corpus,
    record_query_log,
)
from app.services.tokenizer import (
    ALL_QUERY_STOPWORDS,
    VALID_DOC_TYPES,
    VALID_LANGUAGES,
    DocumentMetadata,
    MarkdownChunk,
    build_or_tsquery,
    chunk_markdown_document,
    detect_chunk_language,
    detect_language,
    extract_sku_or_error_code,
    parse_markdown_frontmatter,
    tokenize_for_search,
)

__all__ = [
    "ALL_QUERY_STOPWORDS",
    "CorpusIngestSummary",
    "DocumentMetadata",
    "EmbeddingService",
    "GenerationResult",
    "HybridRetriever",
    "InjectionGateDecision",
    "MarkdownChunk",
    "PostLLMGateDecision",
    "RAGGenerator",
    "RetrievalBundle",
    "RetrievalChunk",
    "RetrievalGateDecision",
    "VALID_DOC_TYPES",
    "VALID_LANGUAGES",
    "apply_post_llm_groundedness_gate",
    "build_deterministic_embedding",
    "build_or_tsquery",
    "check_pre_llm_retrieval_gate",
    "check_prompt_injection",
    "chunk_markdown_document",
    "detect_chunk_language",
    "detect_language",
    "extract_sku_or_error_code",
    "format_pgvector_literal",
    "ingest_markdown_corpus",
    "l2_normalize_vector",
    "parse_markdown_frontmatter",
    "record_query_log",
    "tokenize_for_search",
]
