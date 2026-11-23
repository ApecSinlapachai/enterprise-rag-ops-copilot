"""Unit tests for Thai-English tokenization, tsquery building, and Markdown chunking."""

from __future__ import annotations

import pathlib

from app.schemas.rag import format_citation_snippet
from app.services.tokenizer import (
    VALID_DOC_TYPES,
    VALID_LANGUAGES,
    build_or_tsquery,
    chunk_markdown_document,
    detect_chunk_language,
    detect_language,
    extract_sku_or_error_code,
    tokenize_for_search,
)

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
MOCK_DOCS_DIR = ROOT_DIR / "data" / "mock_docs"


def test_tokenize_for_search_thai_and_bilingual_preserves_codes() -> None:
    text = "สอบถามนโยบายคืนเงิน SLA สำหรับใบแจ้งหนี้ INV-2026-0091 เมื่อเกิด ERR-AUTH-403 ครับ"
    tokenized, token_count = tokenize_for_search(text)

    assert token_count > 5
    tokens = tokenized.split()
    assert "inv-2026-0091" in tokens
    assert "err-auth-403" in tokens
    assert "sla" in tokens
    assert "คืนเงิน" in tokens


def test_build_or_tsquery_strips_domain_stopwords_and_sanitizes_syntax() -> None:
    query = "รบกวนสอบถามครับ! ระบบ SLA คืนเงิน INV-2026-0091 ทำอย่างไร? (please help) | & : % '"
    tsq = build_or_tsquery(query)

    assert tsq != ""
    terms = tsq.split(" | ")
    assert "sla" in terms
    assert "คืนเงิน" in terms
    assert "inv-2026-0091" in terms
    for stop in ("รบกวน", "สอบถาม", "ครับ", "ระบบ", "please", "help", "ทำ", "อย่างไร"):
        assert stop not in terms
    for forbidden in ("!", "&", ":", "%", "'", "(", ")"):
        assert forbidden not in tsq


def test_build_or_tsquery_all_stopwords_returns_empty_string() -> None:
    query = "สวัสดีครับ รบกวนสอบถามระบบหน่อยค่ะ please help what how"
    assert build_or_tsquery(query) == ""


def test_extract_sku_or_error_code_matches_synthetic_ids() -> None:
    assert extract_sku_or_error_code("ใบแจ้งหนี้ INV-2026-0091 มีปัญหา") == "INV-2026-0091"
    assert extract_sku_or_error_code("API gateway returned err-503 on prod") == "ERR-503"
    assert extract_sku_or_error_code("SSO login failed with ERR-AUTH-403") == "ERR-AUTH-403"
    assert extract_sku_or_error_code("Tenant org-demo-01 upgraded") == "ORG-DEMO-01"
    assert extract_sku_or_error_code("Plan SKU-ENT-ANNUAL renewal") == "SKU-ENT-ANNUAL"
    assert extract_sku_or_error_code("ขอทราบเวลาเปิดให้บริการในวันเสาร์") is None


def test_detect_language_thai_english_mixed_unknown() -> None:
    assert detect_language("นโยบายการคืนเงินสำหรับลูกค้าองค์กร") == "th"
    assert detect_language("Enterprise incident severity matrix SLA") == "en"
    assert detect_language("วิธีแก้ไขข้อผิดพลาด ERR-AUTH-403 บน SAML SSO") == "mixed"
    assert detect_language("12345 ??? !!!") == "unknown"

    assert detect_chunk_language("วิธีแก้ไข ERR-AUTH-403 บน SSO") == "bilingual"
    assert detect_chunk_language("12345") == "en"


def test_chunk_markdown_document_preserves_section_path_and_token_count() -> None:
    sample_md = """---
source_key: sample_sop.md
title: Sample B2B Ops SOP
language: bilingual
doc_type: sop
version: "1.0"
---

# Root Operations Guide

Introductory overview for tenant ORG-DEMO-01.

## Billing Section

Process invoice INV-2026-0091 within 14 days.

### Withholding Tax Substep

หักภาษี ณ ที่จ่าย 3% และส่งเอกสาร 50 ทวิ
"""
    meta, chunks = chunk_markdown_document(sample_md, fallback_source_key="fallback.md")

    assert meta.source_key == "sample_sop.md"
    assert meta.language == "bilingual"
    assert meta.doc_type == "sop"
    assert len(chunks) == 3

    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert chunks[0].section_path == "Root Operations Guide"
    assert chunks[1].section_path == "Root Operations Guide > Billing Section"
    assert (
        chunks[2].section_path
        == "Root Operations Guide > Billing Section > Withholding Tax Substep"
    )
    assert all(c.token_count > 0 for c in chunks)
    assert "inv-2026-0091" in chunks[1].search_text_tokenized


def test_all_mock_docs_parse_and_chunk_cleanly() -> None:
    doc_files = sorted(MOCK_DOCS_DIR.glob("*.md"))
    assert 10 <= len(doc_files) <= 12

    observed_languages: set[str] = set()
    observed_doc_types: set[str] = set()

    for path in doc_files:
        raw = path.read_text(encoding="utf-8")
        meta, chunks = chunk_markdown_document(raw, fallback_source_key=path.name)

        assert meta.source_key == path.name
        assert meta.language in VALID_LANGUAGES
        assert meta.doc_type in VALID_DOC_TYPES
        assert len(chunks) >= 2

        observed_languages.add(meta.language)
        observed_doc_types.add(meta.doc_type)

        for chunk in chunks:
            assert chunk.token_count > 0
            assert chunk.section_path.strip() != ""
            assert chunk.search_text_tokenized.strip() != ""
            snippet = format_citation_snippet(chunk.content, max_chars=380)
            assert 0 < len(snippet) <= 400

    assert observed_languages == {"th", "en", "bilingual"}
    assert observed_doc_types == {"sop", "sla", "faq", "security_policy", "runbook", "pricing"}
