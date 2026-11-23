---
source_key: 11_bi_rag_copilot_guardrails_faq.md
title: Bilingual FAQ — คำถามที่พบบ่อยเกี่ยวกับระบบ Hybrid RAG Copilot และเกณฑ์ความปลอดภัย 3 ด่าน
language: bilingual
doc_type: faq
version: "1.4"
---

# Bilingual FAQ — ระบบ Hybrid RAG Copilot และเกณฑ์ความปลอดภัย 3 ด่าน

คำถามที่พบบ่อยเกี่ยวกับการทำงานของระบบค้นหาเอกสารสองภาษา (Thai–English Hybrid Search) และกลไกป้องกันการสร้างข้อมูลเท็จ (Anti-Hallucination Guardrails)

## ระบบค้นหาเอกสารภาษาไทยและอังกฤษทำงานอย่างไร (How Hybrid Vector + FTS Search Works)

ระบบใช้สถาปัตยกรรม **Hybrid Retrieval + Reciprocal Rank Fusion (RRF)** บน PostgreSQL 16 (`pgvector` + `pg_trgm` + `tsvector`) โดยไม่มีค่าใช้จ่าย Vector DB แยกต่างหาก:

1. **Thai Word Segmentation**: ใช้ไลบรารี `PyThaiNLP` (เอนจิน `newmm`) ตัดคำภาษาไทยและคัดกรองคำฟุ่มเฟือย (Stopwords) เช่น `สอบถาม`, `ครับ`, `ค่ะ`, `ระบบ`, `please`, `help` ก่อนสร้าง `OR`-joined `tsquery`
2. **Exact Code & SKU Trigram Boost**: สกัดรหัสอ้างอิงเฉพาะทาง (เช่น `INV-2026-0091`, `ERR-503`, `ERR-AUTH-403`) เพื่อเพิ่มคะแนนการค้นหาผ่าน GIN Trigram Index (`pg_trgm`)
3. **Dense Vector Search**: ใช้โมเดล `gemini-embedding-001` ที่มิติ **1536 dimensions** (Matryoshka truncation + L2 normalization)
4. **RRF Score Fusion**: รวมอันดับ Top-20 Vector และ Top-20 FTS ด้วยสูตร `0.6 / (60 + vec_rank) + 0.4 / (60 + fts_rank_pos)` เพื่อคัดเลือก Top-5 Chunks

## เกณฑ์การปฏิเสธคำตอบเมื่อหลักฐานไม่เพียงพอ (3-Stage Guardrail & Grounded Refusal Policy)

เพื่อป้องกัน AI Hallucination และควบคุมต้นทุน LLM ระบบตรวจสอบความปลอดภัยครบทั้ง 3 ด่าน:

- **Stage 0 — Injection Gate (`BLOCKED_INJECTION`)**: ตรวจจับคำสั่งโจมตี Prompt Injection (เช่น `ignore previous instructions`, `reveal system prompt`, `ลืมคำสั่งทั้งหมด`) และบล็อกทันทีที่ต้นทุน **$0**
- **Stage 1 — Pre-LLM Retrieval Gate (`REFUSED_LOW_EVIDENCE`)**: หากไม่พบเอกสารที่เกี่ยวข้อง หรือ `max_vec_similarity < 0.58` และ `max_fts_rank < 0.08` ระบบจะปฏิเสธคำตอบทันทีโดยไม่เรียกใช้ LLM (`$0` cost)
- **Stage 2 — Post-LLM Groundedness Gate**: บังคับให้คำตอบจาก `gemini-2.5-flash` ต้องอ้างอิง `cited_chunk_ids` ที่ตรงกับ UUID จากฐานข้อมูลจริง และมีค่า `confidence_score >= 0.55` มิฉะนั้นระบบจะเปลี่ยนเป็นคำปฏิเสธแบบกำหนดไว้ล่วงหน้าและล้าง `citations = []`

## การจัดการเมื่อ Gemini API เกิดโควตาเต็ม (Rate Limit & 429 Fallback)

- **Public Demo Guardrails**: จำกัดอัตราเรียกใช้งานที่ **15 requests/minute** และ **60 requests/day** ต่อ SHA-256 IP Hash พร้อมจำกัดความยาวข้อความไม่เกิน **500 ตัวอักษร** สำหรับ RAG และ **1,500 ตัวอักษร** สำหรับ Ticket Triage
- **429 Resilience**: หากเกิด `429 RESOURCE_EXHAUSTED` จาก Gemini Free Tier ระบบจะใช้ Cached/Replay Fallback เพื่อรักษาเสถียรภาพของ Live Demo
