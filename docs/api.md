# API Contract — PetCare `/api/v1`

Base URL ผ่าน Nginx: `http://localhost/api/v1`
OpenAPI: `http://localhost/api/docs`

## การยืนยันตัวตน

- `POST /auth/login` คืน `access_token` (JWT, 60 นาที) และข้อมูลผู้ใช้
- ส่ง header `Authorization: Bearer <token>` ทุก endpoint ที่ต้องล็อกอิน
- JWT บรรจุ `sub` (user id), `role`, `iat`, `exp`

## Error envelope

```json
{ "error": { "code": "SLOT_TAKEN", "message": "สล็อตนี้ถูกจองแล้ว", "details": {} } }
```

| HTTP | ความหมาย |
|---|---|
| 401 | ไม่มี token / token ไม่ถูกต้อง (`UNAUTHORIZED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS`) |
| 403 | ผิดบทบาทหรือไม่ใช่เจ้าของข้อมูล (`FORBIDDEN`) |
| 404 | ไม่พบข้อมูล (`*_NOT_FOUND`) |
| 409 | ชนกันหรือสถานะผิดกฎ (`SLOT_TAKEN`, `PET_SLOT_TAKEN`, `STALE_VERSION`, `INVALID_TRANSITION`, `SHIFT_OVERLAP`, `SHIFT_HAS_APPOINTMENTS`, `EMAIL_TAKEN`, `REQUEST_ALREADY_REVIEWED`) |
| 422 | ข้อมูลผิดรูปแบบหรือผิดกฎธุรกิจ (`VALIDATION_ERROR`, `SLOT_OUT_OF_RANGE`, `CANCEL_WINDOW_CLOSED`, `INVALID_SHIFT`) |

`422 VALIDATION_ERROR` มี `details.fields[]` = `{loc, msg, type}` สำหรับแสดงใต้ช่อง input

## Endpoints

| Method & Path | บทบาท | หมายเหตุ |
|---|---|---|
| POST `/auth/register` | Public | สมัคร OWNER |
| POST `/auth/staff-accounts` | STAFF | สร้าง VET/STAFF |
| POST `/auth/login` | Public | 401 ข้อความเดียวกันทั้งอีเมลผิด/รหัสผิด |
| GET `/auth/me` | ทุกบทบาท | |
| GET/POST `/pets`, GET/PATCH `/pets/{id}` | OWNER | เฉพาะสัตว์ของตัวเอง |
| GET `/pets/{id}/history` | OWNER/VET ที่มีเคส/STAFF | ประวัติ + treatment notes |
| GET `/vets` | ทุกบทบาท | |
| GET `/availability?date=&vet_id=` | ทุกบทบาท | คืน `[]` ถ้าไม่มีกะ |
| POST `/appointments` | OWNER | 201 สำเร็จ, 409 ถ้าชน |
| GET `/appointments` หรือ `/appointments/me` | OWNER | นัดของฉัน |
| GET `/appointments/{id}` | เจ้าของ/VET ที่ได้มอบหมาย/STAFF | |
| POST `/appointments/{id}/cancel` | OWNER, STAFF | OWNER ต้องเหลือ ≥ 2 ชม. |
| GET `/appointments/{id}/queue-position` | OWNER | |
| GET `/queue/live?date=&vet_id=&since=` | ทุกบทบาท | รองรับ `If-None-Match` → 304 |
| GET `/schedule?date=&vet_id=&since=` | VET (ตัวเอง), STAFF | รองรับ ETag |
| PATCH `/appointments/{id}/status` | STAFF | ต้องส่ง `expected_version` |
| PATCH `/appointments/{id}/reschedule` | STAFF | ต้องส่ง `expected_version` |
| POST `/appointments/swap` | STAFF | สลับ 2 นัดของแพทย์/วันเดียวกัน |
| POST `/appointments/{id}/transfer` | STAFF | ปลายทางต้องมีกะและสล็อตว่าง |
| GET/POST `/appointments/{id}/treatment-notes` | อ่าน: เจ้าของ/VET/STAFF, เขียน: VET เจ้าของเคส | version ใหม่ทุกครั้ง |
| POST `/appointments/{id}/reschedule-requests` | VET เจ้าของเคส | reason ว่าง → 422 |
| GET `/reschedule-requests?status=` | STAFF | |
| POST `/reschedule-requests/{id}/approve` / `/reject` | STAFF | ใช้ logic reschedule เดียวกัน |
| GET/POST `/shifts`, PATCH/DELETE `/shifts/{id}` | STAFF (VET ดูของตัวเอง) | |
| GET `/notifications?since=` , POST `/notifications/{id}/read` | ทุกบทบาท | เฉพาะของตัวเอง |
| GET `/audit-logs?entity_id=&action=` | STAFF | append-only |
| GET `/health/live`, `/health/ready`, `/metrics` | Internal | ready เช็ก DB |

## ตัวอย่าง

### จองนัด

```bash
curl -X POST http://localhost/api/v1/appointments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"pet_id":"...","vet_id":"...","slot_start":"2026-11-07T02:00:00Z","symptoms":"ซึม ไม่กินอาหาร"}'
```

`slot_start` เป็น UTC; `2026-11-07T02:00:00Z` = 09:00 น. เวลาไทย

### เปลี่ยนสถานะ (STAFF)

```bash
curl -X PATCH http://localhost/api/v1/appointments/$ID/status \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"status":"CHECKED_IN","expected_version":1}'
```

### Polling คิวสด

```bash
curl -H "Authorization: Bearer $TOKEN" -H 'If-None-Match: W/"..."' \
  "http://localhost/api/v1/queue/live?date=2026-11-07&vet_id=$VET_ID"
```

## State machine

```
BOOKED → CHECKED_IN → IN_TREATMENT → COMPLETED
   │           └──────→ NO_SHOW
   └──────────→ NO_SHOW
   └──────────→ CANCELLED
```
