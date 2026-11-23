"""Thai-English tokenization, stopword filtering, code extraction, and Markdown chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pythainlp.tokenize import word_tokenize

LanguageType = Literal["th", "en", "bilingual"]
QueryLanguageType = Literal["th", "en", "mixed", "unknown"]
DocType = Literal["sop", "sla", "faq", "security_policy", "runbook", "pricing"]

VALID_LANGUAGES: frozenset[str] = frozenset({"th", "en", "bilingual"})
VALID_DOC_TYPES: frozenset[str] = frozenset(
    {"sop", "sla", "faq", "security_policy", "runbook", "pricing"}
)

# Curated Thai function words and B2B SaaS conversational filler tokens.
THAI_DOMAIN_STOPWORDS: frozenset[str] = frozenset(
    {
        "สอบถาม",
        "ครับ",
        "ค่ะ",
        "คะ",
        "นะ",
        "นะครับ",
        "นะคะ",
        "รบกวน",
        "ต้องการ",
        "อยาก",
        "ทราบ",
        "ถาม",
        "หน่อย",
        "เรื่อง",
        "เกี่ยวกับ",
        "ระบบ",
        "ทำไม",
        "อย่างไร",
        "ยังไง",
        "อะไร",
        "ไหม",
        "มั้ย",
        "ช่วย",
        "ขอ",
        "แจ้ง",
        "ปัญหา",
        "การใช้งาน",
        "สวัสดี",
        "ขอบคุณ",
        "ของ",
        "ที่",
        "ใน",
        "และ",
        "หรือ",
        "จาก",
        "ให้",
        "ได้",
        "มี",
        "เป็น",
        "ไป",
        "มา",
        "จะ",
        "ต้อง",
        "ทำ",
        "กับ",
        "แก่",
        "แด่",
        "ต่อ",
        "โดย",
        "ด้วย",
        "เพื่อ",
        "สำหรับ",
        "แบบ",
        "นี้",
        "นั้น",
        "นี่",
        "นั่น",
        "อยู่",
        "แล้ว",
        "ก็",
        "ยัง",
        "ไม่",
        "ใช่",
        "เลย",
        "มาก",
        "บ้าง",
        "ทุก",
        "บาง",
        "แต่ละ",
        "ถ้า",
        "หาก",
        "เมื่อ",
        "เพราะ",
        "แต่",
        "ซึ่ง",
        "อัน",
        "ผู้",
        "ทาง",
        "ด้าน",
        "กรณี",
        "ข้อมูล",
    }
)

# English function words and B2B SaaS conversational filler tokens.
ENGLISH_DOMAIN_STOPWORDS: frozenset[str] = frozenset(
    {
        "please",
        "help",
        "what",
        "how",
        "why",
        "when",
        "where",
        "who",
        "which",
        "can",
        "could",
        "would",
        "should",
        "will",
        "shall",
        "may",
        "might",
        "is",
        "are",
        "was",
        "were",
        "am",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "the",
        "a",
        "an",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "about",
        "from",
        "as",
        "into",
        "like",
        "through",
        "after",
        "over",
        "between",
        "out",
        "against",
        "during",
        "without",
        "before",
        "under",
        "around",
        "among",
        "and",
        "or",
        "but",
        "if",
        "then",
        "so",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "system",
        "question",
        "ask",
        "asking",
        "need",
        "want",
        "tell",
        "me",
        "us",
        "my",
        "our",
        "you",
        "your",
        "we",
        "i",
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank",
        "issue",
        "problem",
        "info",
        "information",
    }
)


def _load_pythainlp_stopwords() -> frozenset[str]:
    """Load PyThaiNLP standard stopwords safely, falling back cleanly offline."""
    try:
        from pythainlp.corpus.common import thai_stopwords

        # Keep domain-critical words even if present in generic stopword lists.
        protected = {"คืนเงิน", "ยกเลิก", "ระงับ", "ล่ม", "ช้า"}
        return frozenset(thai_stopwords()) - protected
    except Exception:
        return frozenset()


ALL_QUERY_STOPWORDS: frozenset[str] = (
    THAI_DOMAIN_STOPWORDS | ENGLISH_DOMAIN_STOPWORDS | _load_pythainlp_stopwords()
)

# Structured synthetic/enterprise code patterns (invoices, error codes, SKUs, org IDs).
_STRUCTURED_CODE_RE = re.compile(
    r"\b(?:(?:INV|ERR|ORG|SKU|INC|REQ|TICKET|DOC)-[A-Za-z0-9]{2,12}(?:-[A-Za-z0-9]{2,12})?"
    r"|[A-Za-z]{2,8}-\d{2,6}(?:-[A-Za-z0-9]{2,8})?)\b",
    re.IGNORECASE,
)

_CODE_SPAN_SPLIT_RE = re.compile(
    r"(\b(?:(?:INV|ERR|ORG|SKU|INC|REQ|TICKET|DOC)-[A-Za-z0-9]{2,12}(?:-[A-Za-z0-9]{2,12})?"
    r"|[A-Za-z]{2,8}-\d{2,6}(?:-[A-Za-z0-9]{2,8})?)\b)",
    re.IGNORECASE,
)

_THAI_CHAR_RE = re.compile(r"[\u0e00-\u0e7f]")
_LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
_SAFE_TOKEN_CHAR_RE = re.compile(r"[^a-z0-9\u0e00-\u0e7f_-]+")
_HAS_WORD_CHAR_RE = re.compile(r"[a-z0-9\u0e00-\u0e7f]")
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_FRONTMATTER_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?", re.DOTALL)


@dataclass(frozen=True)
class DocumentMetadata:
    """Validated metadata extracted from a Markdown document's frontmatter."""

    source_key: str
    title: str
    language: LanguageType
    doc_type: DocType
    version: str = "1.0"


@dataclass(frozen=True)
class MarkdownChunk:
    """Heading-aware Markdown chunk prepared for PostgreSQL pgvector + FTS ingestion."""

    chunk_index: int
    section_path: str
    language: LanguageType
    content: str
    search_text_tokenized: str
    token_count: int


def extract_sku_or_error_code(text: str) -> str | None:
    """Extract the first exact invoice, SKU, org, or error code as a regex-safe string.

    Returned value is intended for parameter $3 (`search_text_tokenized ~* $3`)
    in `sql/002_hybrid_search_query.sql`.
    """
    if not text:
        return None
    match = _STRUCTURED_CODE_RE.search(text)
    if not match:
        return None
    return re.sub(r"[^A-Z0-9-]", "", match.group(0).upper())


def detect_language(text: str) -> QueryLanguageType:
    """Detect whether text is primarily Thai, English, code-mixed, or unknown."""
    thai_count = len(_THAI_CHAR_RE.findall(text))
    latin_count = len(_LATIN_CHAR_RE.findall(text))
    total = thai_count + latin_count
    if total == 0:
        return "unknown"
    if thai_count > 0 and latin_count == 0:
        return "th"
    if latin_count > 0 and thai_count == 0:
        return "en"

    minority = min(thai_count, latin_count)
    if minority / total >= 0.15 or minority >= 3:
        return "mixed"
    return "th" if thai_count >= latin_count else "en"


def detect_chunk_language(text: str) -> LanguageType:
    """Map detected script distribution to document_chunks.language CHECK values."""
    lang = detect_language(text)
    if lang == "mixed":
        return "bilingual"
    if lang == "unknown":
        return "en"
    return lang


def _clean_token(raw_token: str) -> str:
    """Normalize a single token to lowercase and strip unsafe characters."""
    lowered = raw_token.strip().lower()
    cleaned = _SAFE_TOKEN_CHAR_RE.sub("", lowered)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    return cleaned


def tokenize_for_search(text: str) -> tuple[str, int]:
    """Segment Thai/English text with PyThaiNLP newmm while preserving SKU/error codes.

    Returns `(search_text_tokenized, token_count)`. Non-empty inputs always yield
    `token_count >= 1` to satisfy `document_chunks.token_count > 0`.
    """
    stripped = text.strip()
    if not stripped:
        return "", 0

    tokens: list[str] = []
    segments = _CODE_SPAN_SPLIT_RE.split(stripped)
    for segment in segments:
        if not segment or not segment.strip():
            continue
        if _STRUCTURED_CODE_RE.fullmatch(segment.strip()):
            code_tok = _clean_token(segment)
            if code_tok:
                tokens.append(code_tok)
            continue

        for piece in word_tokenize(segment, engine="newmm", keep_whitespace=False):
            tok = _clean_token(piece)
            if tok and _HAS_WORD_CHAR_RE.search(tok):
                tokens.append(tok)

    if not tokens:
        fallback = _clean_token(stripped) or "doc"
        tokens = [fallback]

    return " ".join(tokens), len(tokens)


def build_or_tsquery(query: str, max_terms: int = 16) -> str:
    """Build a sanitized OR-joined PostgreSQL `tsquery` string with domain stopwords removed.

    Returns an empty string when all tokens are filtered out so PostgreSQL
    `NULLIF($2, '')` evaluates to NULL rather than granting a false FTS boost.
    """
    tokenized, _ = tokenize_for_search(query)
    if not tokenized:
        return ""

    selected: list[str] = []
    seen: set[str] = set()
    for raw_tok in tokenized.split():
        tok = _clean_token(raw_tok)
        if not tok or tok in ALL_QUERY_STOPWORDS:
            continue
        if len(tok) == 1 and not tok.isdigit():
            continue
        if tok in seen:
            continue
        seen.add(tok)
        selected.append(tok)
        if len(selected) >= max_terms:
            break

    return " | ".join(selected)


def parse_markdown_frontmatter(
    raw_markdown: str,
    fallback_source_key: str = "unknown.md",
) -> tuple[DocumentMetadata, str]:
    """Parse key-value YAML frontmatter and return validated metadata + body."""
    meta_dict: dict[str, str] = {}
    body = raw_markdown

    match = _FRONTMATTER_RE.match(raw_markdown)
    if match:
        frontmatter_block = match.group(1)
        body = raw_markdown[match.end() :]
        for line in frontmatter_block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, val = line.split(":", 1)
            meta_dict[key.strip().lower()] = val.strip().strip('"').strip("'")

    source_key = meta_dict.get("source_key") or fallback_source_key
    title = meta_dict.get("title") or source_key
    raw_lang = meta_dict.get("language", "").lower()
    language: LanguageType = (
        raw_lang  # type: ignore[assignment]
        if raw_lang in VALID_LANGUAGES
        else detect_chunk_language(body or title)
    )
    raw_doc_type = meta_dict.get("doc_type", "sop").lower()
    doc_type: DocType = (
        raw_doc_type  # type: ignore[assignment]
        if raw_doc_type in VALID_DOC_TYPES
        else "sop"
    )
    version = meta_dict.get("version") or "1.0"

    return (
        DocumentMetadata(
            source_key=source_key,
            title=title,
            language=language,
            doc_type=doc_type,
            version=version,
        ),
        body.strip(),
    )


def _split_long_section(section_body: str, max_chunk_chars: int) -> list[str]:
    """Split an oversized Markdown section along paragraph boundaries."""
    if len(section_body) <= max_chunk_chars:
        return [section_body]

    paragraphs = [p.strip() for p in re.split(r"\r?\n\s*\r?\n", section_body) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current and current_len + para_len + 2 > max_chunk_chars:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len + (2 if len(current) > 1 else 0)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_markdown_document(
    raw_markdown: str,
    fallback_source_key: str = "unknown.md",
    max_chunk_chars: int = 1200,
) -> tuple[DocumentMetadata, list[MarkdownChunk]]:
    """Split Markdown into heading-aware chunks preserving `H1 > H2 > H3` section_path."""
    metadata, body = parse_markdown_frontmatter(
        raw_markdown, fallback_source_key=fallback_source_key
    )
    if not body:
        return metadata, []

    heading_stack: dict[int, str] = {}
    sections: list[tuple[str, str]] = []
    buffer: list[str] = []

    def _current_section_path() -> str:
        parts = [heading_stack[lvl] for lvl in sorted(heading_stack) if heading_stack[lvl]]
        return " > ".join(parts) if parts else metadata.title

    def _flush_buffer() -> None:
        text = "\n".join(buffer).strip()
        buffer.clear()
        if text:
            sections.append((_current_section_path(), text))

    for line in body.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            _flush_buffer()
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()
            heading_stack[level] = heading_text
            for deeper in [k for k in heading_stack if k > level]:
                del heading_stack[deeper]
        else:
            buffer.append(line)

    _flush_buffer()

    chunks: list[MarkdownChunk] = []
    chunk_index = 0
    for section_path, section_text in sections:
        for piece in _split_long_section(section_text, max_chunk_chars=max_chunk_chars):
            tokenized_text, token_count = tokenize_for_search(f"{section_path}\n{piece}")
            if token_count <= 0:
                continue
            chunks.append(
                MarkdownChunk(
                    chunk_index=chunk_index,
                    section_path=section_path,
                    language=metadata.language,
                    content=piece,
                    search_text_tokenized=tokenized_text,
                    token_count=token_count,
                )
            )
            chunk_index += 1

    return metadata, chunks
