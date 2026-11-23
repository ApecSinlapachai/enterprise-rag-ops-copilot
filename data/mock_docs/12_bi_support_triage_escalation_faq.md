---
source_key: 12_bi_support_triage_escalation_faq.md
title: Bilingual FAQ — การคัดแยกตั๋วแจ้งปัญหาอัตโนมัติ (AI Ticket Triage) และการส่งต่อทีมปฏิบัติการ
language: bilingual
doc_type: faq
version: "1.6"
---

# Bilingual FAQ — การคัดแยกตั๋วแจ้งปัญหาอัตโนมัติ (AI Ticket Triage)

เอกสารนี้อธิบายหลักการจัดหมวดหมู่ตั๋วแจ้งปัญหา (Pydantic v2 Structured Triage) การกำหนดระดับความสำคัญ และเกณฑ์ส่งต่อทีมผู้เชี่ยวชาญ

## หมวดหมู่ตั๋วแจ้งปัญหาและทีมผู้รับผิดชอบ (Ticket Categories & Target Teams)

ระบบ `POST /api/v1/triage` วิเคราะห์ข้อความภาษาไทย อังกฤษ หรือสองภาษา แล้วส่งออก JSON ที่ผ่านการตรวจสอบ Schema แบบ 1:1 กับฐานข้อมูล `triage_tickets`:

| Category (`category`) | ทีมที่รับผิดชอบ (`suggested_team`) | ตัวอย่างกรณีการใช้งาน (Use Cases) |
| :--- | :--- | :--- |
| `billing_refund` | `billing_ops` | ขอคืนเงิน SLA, ตรวจสอบใบแจ้งหนี้ `INV-2026-0091`, แก้ไขใบกำกับภาษี |
| `technical_incident` | `l2_engineering` | ระบบล่ม `ERR-503`, Query Timeout `ERR-DB-504`, Webhook `ERR-WEBHOOK-502` |
| `account_access` | `l1_support` หรือ `security_ops` | ล็อกอิน SSO ไม่ได้ (`ERR-AUTH-403`), รีเซ็ต MFA, เพิกถอนสิทธิ์พนักงาน |
| `sla_escalation` | `account_management` | เรียกร้องเครดิต SLA ประจำเดือน, ขอรายงาน RCA สำหรับองค์กร `ORG-DEMO-01` |
| `feature_request` | `account_management` | ข้อเสนอแนะฟีเจอร์ใหม่หรือขอขยายโควตา API ชั่วคราว |
| `general_inquiry` | `l1_support` | สอบถามข้อมูลทั่วไป ราคาแพ็กเกจ `SKU-PRO-MONTHLY` / `SKU-ENT-ANNUAL` |
| `prompt_injection_attempt` | `security_ops` | ความพยายามเจาะระบบ Prompt Injection หรือขโมย System Prompt |

## เกณฑ์การให้คะแนนความเร่งด่วน (Urgency Score 1-5 & Human-in-the-Loop Review)

- **Urgency Score `1–5` และ Priority `P0–P3`**:
  - `urgency_score = 5` (`P0`): ระบบล่มทั้งหมด กระทบ Production ทันที หรือพบภัยคุกคามความปลอดภัย
  - `urgency_score = 4` (`P1`): ระบบงานหลักใช้งานไม่ได้ทั้งองค์กร เช่น SSO `ERR-AUTH-403`
  - `urgency_score = 2–3` (`P2`): ปัญหาบางส่วนที่มีทางแก้ชั่วคราว หรือคำขอคืนเงินตามรอบบิล
  - `urgency_score = 1` (`P3`): คำถามทั่วไปหรือข้อเสนอแนะ
- **Human-in-the-Loop (`requires_human_review = true`)**: ระบบจะตั้งค่าให้เจ้าหน้าที่ตรวจสอบเสมอเมื่อตั๋วมีความสำคัญระดับ `P0` หรือ `P1`, เป็นหมวด `billing_refund`, หรือเป็น `prompt_injection_attempt` รวมถึงกรณีที่ระบบใช้ `deterministic_fallback` เมื่อโมเดล AI ไม่พร้อมใช้งาน
