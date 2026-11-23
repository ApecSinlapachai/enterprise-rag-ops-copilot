---
source_key: 09_bi_sso_saml_auth403_runbook.md
title: Bilingual Runbook — การแก้ไขปัญหา SSO SAML 2.0 / OIDC และข้อผิดพลาด ERR-AUTH-403
language: bilingual
doc_type: runbook
version: "2.3"
---

# Bilingual Runbook — การแก้ไขปัญหา SSO และรหัสข้อผิดพลาด ERR-AUTH-403

คู่มือปฏิบัติการสองภาษาสำหรับทีม `l1_support`, `l2_engineering`, และผู้ดูแลระบบองค์กร (Enterprise Tier `SKU-ENT-ANNUAL`) เมื่อพบปัญหาการเข้าสู่ระบบผ่าน SAML 2.0 หรือ OIDC Single Sign-On

## อาการและสาเหตุของรหัสข้อผิดพลาด ERR-AUTH-403 (Symptoms & Root Causes)

ผู้ใช้งานในองค์กร (เช่น `ORG-DEMO-01`) อาจไม่สามารถล็อกอินผ่าน Identity Provider (Okta, Microsoft Entra ID / Azure AD, หรือ Google Workspace) และได้รับหน้าจอแจ้งเตือน `ERR-AUTH-403: SAML Assertion Signature or Group Claim Mismatch` โดยมีสาเหตุหลัก 3 ประการ:

1. **Expired X.509 IdP Signing Certificate**: ใบรับรองความปลอดภัยฝั่ง IdP หมดอายุและยังไม่ได้อัปเดต Metadata XML ใหม่เข้าสู่ระบบ
2. **ACS URL / Audience URI Mismatch**: ค่า Assertion Consumer Service (ACS) URL ใน IdP ไม่ตรงกับค่ามาตรฐาน `https://auth.demo-saas-ops.example/saml/acs`
3. **Clock Skew / Missing Group Claim**: เวลาของเซิร์ฟเวอร์ IdP คลาดเคลื่อนเกิน **180 วินาที** หรือไม่มี Attribute `org_id` และ `role` ส่งมาใน SAML Assertion

## ขั้นตอนการแก้ไขสำหรับผู้ดูแลระบบ (Step-by-Step Troubleshooting)

1. เข้าสู่ **Admin Console > Security > Single Sign-On (SSO)** ด้วยบัญชี `Org Owner` (หรือใช้ Break-glass Backup Login ชั่วคราว)
2. ตรวจสอบ SAML Attribute Mapping ให้ครบถ้วน:
   - `email` -> Primary Corporate Email
   - `role` -> `Workspace Admin`, `Ops Analyst`, หรือ `Read-Only Auditor`
   - `org_id` -> รหัสองค์กรที่ได้รับอนุมัติ (เช่น `ORG-DEMO-01`)
3. อัปโหลด **X.509 Certificate (.pem / .cer)** หรือวาง IdP Metadata URL ใหม่ แล้วกดปุ่ม **Force IdP Metadata Refresh** เพื่อล้าง Cache โทเคนเก่าทันที
4. ทดสอบการล็อกอินผ่านโหมด **Incognito / Private Browser** เพื่อตรวจสอบว่า Error `ERR-AUTH-403` หายไป

## การส่งต่อทีมวิศวกรรม (Escalation to l2_engineering / security_ops)

หากดำเนินการตามขั้นตอนข้างต้นแล้วยังพบ `ERR-AUTH-403` ต่อเนื่องเกิน **15 นาที** และกระทบผู้ใช้งานทั้งองค์กร ให้เปิดตั๋วความสำคัญระดับ **P1** (First Response SLA **30 นาที**) ส่งต่อทีม `l2_engineering` หรือ `security_ops` พร้อมแนบ:
- `request_id` ที่แสดงบนหน้า Error
- SAML Response Trace (ปกปิด Secret/Cookie แล้ว) และ `org_id` (`ORG-DEMO-01`)
