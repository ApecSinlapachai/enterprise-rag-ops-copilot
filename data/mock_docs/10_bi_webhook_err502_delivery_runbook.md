---
source_key: 10_bi_webhook_err502_delivery_runbook.md
title: Bilingual Runbook — ระบบส่งข้อมูล Webhook ล้มเหลว (ERR-WEBHOOK-502) และนโยบาย Retry Queue
language: bilingual
doc_type: runbook
version: "1.7"
---

# Bilingual Runbook — การแก้ไขปัญหา Webhook (ERR-WEBHOOK-502) และ Retry Policy

เอกสารนี้อธิบายสาเหตุของข้อผิดพลาด `ERR-WEBHOOK-502` ในระบบแจ้งเตือนเหตุการณ์ (Event Webhooks) รวมถึงตารางการส่งซ้ำอัตโนมัติ (Exponential Backoff) และการตรวจสอบลายเซ็นความปลอดภัย

## สาเหตุของ ERR-WEBHOOK-502 (Bad Gateway / Destination Timeout)

รหัสข้อผิดพลาด `ERR-WEBHOOK-502` เกิดขึ้นเมื่อ Webhook Dispatcher ส่ง HTTP `POST` Payload ไปยัง Endpoint ของลูกค้า (เช่น `ORG-DEMO-01`) แล้วเกิดเงื่อนไขอย่างใดอย่างหนึ่งต่อไปนี้:

- **Destination Timeout**: ปลายทางไม่ตอบกลับสถานะ HTTP `2xx` (`200 OK` หรือ `202 Accepted`) ภายในระยะเวลา **10 วินาที**
- **TLS / Reverse Proxy Error**: เซิร์ฟเวอร์ปลายทาง (Nginx / Cloudflare / API Gateway) ตอบกลับ `502 Bad Gateway` หรือใบรับรอง SSL/TLS ไม่ถูกต้อง

## นโยบายการส่งซ้ำอัตโนมัติ (Exponential Backoff Retry Schedule)

เมื่อเกิด `ERR-WEBHOOK-502` หรือ HTTP `5xx` ระบบจะนำ Event เข้าคิวส่งซ้ำอัตโนมัติสูงสุด **5 ครั้ง** ตามตาราง Exponential Backoff ดังนี้:

1. **Retry #1**: หลังเกิดข้อผิดพลาด **30 วินาที**
2. **Retry #2**: **2 นาที**
3. **Retry #3**: **10 นาที**
4. **Retry #4**: **1 ชั่วโมง**
5. **Retry #5**: **6 ชั่วโมง**

หากส่งซ้ำครบ 5 ครั้งแล้วยังไม่สำเร็จ Event จะถูกย้ายไปยัง **Dead-Letter Queue (DLQ)** พร้อมส่งการแจ้งเตือนไปยังผู้ดูแลระบบ (`Workspace Admin`) และบันทึกสถานะเป็นความผิดพลาดระดับ **P2** หากพบปัญหาต่อเนื่อง

## การตรวจสอบลายเซ็นความปลอดภัย (HMAC-SHA256 Signature Verification & Manual Replay)

เพื่อป้องกันการปลอมแปลง Request และกู้คืนข้อมูลที่ตกหล่น:

- **Signature Header**: ทุก Webhook Request จะแนบเฮดเดอร์ `X-Copilot-Signature-256` ที่คำนวณด้วยอัลกอริทึม **HMAC-SHA256** จาก Webhook Secret ขององค์กรร่วมกับ Timestamp
- **Manual Replay Window**: ลูกค้าสามารถแก้ไข Endpoint ปลายทางแล้วกดส่งข้อมูลซ้ำจาก DLQ ย้อนหลังได้ภายใน **7 วัน** ผ่านเมนู **Developer > Webhooks > Replay DLQ**
