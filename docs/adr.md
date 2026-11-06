# สถาปัตยกรรมและ ADR — PetCare System

เอกสารนี้อธิบายการตัดสินใจทางสถาปัตยกรรม (Architecture Decision Records) ที่ใช้ในโค้ดจริง
อ้างอิงจาก Masterplan ข้อ 0

| # | ประเด็น | การตัดสินใจ | ที่เห็นในโค้ด |
|---|---|---|---|
| ADR-1 | Backend stack | Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic + Pydantic v2 | `backend/pyproject.toml`, `backend/app` |
| ADR-2 | Frontend stack | React 18 + Vite + TypeScript + TanStack Query + Tailwind | `frontend/` |
| ADR-3 | Real-time | Polling ทุก 3–5 วินาที รองรับ `?since=` และ `ETag`/304 | `app/api/v1/queue.py`, `app/api/v1/schedule.py`, `frontend/src/pages/*` |
| ADR-4 | Auth | JWT access token 60 นาที + Argon2id | `app/core/security.py`, `app/core/deps.py` |
| ADR-5 | Notifications | Transactional outbox + `FOR UPDATE SKIP LOCKED` + unique `(event_id, recipient_id)` | `app/models/outbox.py`, `app/worker/outbox_worker.py` |
| ADR-6 | Vet selection | OWNER เลือกสล็อตที่ผูกกับสัตวแพทย์ (availability แสดงชื่อแพทย์) | `app/services/availability_service.py` |
| ADR-7 | Timezone | เก็บ `timestamptz` (UTC) แสดงผล Asia/Bangkok | `app/core/time.py`, `frontend/src/lib/format.ts` |
| ADR-8 | Reminder | ส่งทันทีหลังจอง + อีกครั้ง 1 ชม. ก่อนนัด | `booking_service.py`, `outbox_worker.py` |
| ADR-9 | Booking horizon | ไม่เกิน 30 วัน | `core/config.py`, `core/time.py` |
| ADR-10 | Cancel window | กฎ 2 ชม. ใช้กับ OWNER เท่านั้น STAFF ยกเลิกได้ทุกเวลา | `booking_service.cancel_appointment` |

## หลักการที่บังคับใช้

1. **DB เป็นแหล่งความจริงเดียว** — การกันจองซ้ำใช้ partial unique index
   `uq_vet_slot_active` และ `uq_pet_slot_active` ไม่ใช่การเช็กใน Python
2. **Stateless backend** — ไม่มี session/in-memory state; ทั้ง web1 และ web2 ทำงานเหมือนกัน
3. **Atomic state change** — ทุกการเปลี่ยนสถานะเขียน `appointments` + `audit_logs` +
   `outbox_events` ใน transaction เดียวกัน
4. **Two-layer authorization** — ตรวจบทบาท (`require_roles`) และความเป็นเจ้าของข้อมูล
   (`assert_can_view_appointment`, `assert_can_view_pet`)
5. **Idempotent delivery** — worker ใช้ `ON CONFLICT (event_id, recipient_id) DO NOTHING`
   และตรวจ reminder ซ้ำก่อนส่ง

## หมายเหตุการ implement

- `vet_shifts` ใช้ `EXCLUDE USING gist` ร่วมกับ `btree_gist` เพื่อกันกะซ้อนที่ระดับ DB
- `audit_logs` มี trigger `prevent_audit_log_changes` ปฏิเสธ UPDATE/DELETE (append-only)
- การสลับคิว (swap) ย้ายนัดผ่าน slot ชั่วคราวภายใน transaction เพื่อให้ partial unique index
  ทั้งสองตัวยังคง satisfied ตลอดเวลา
- Optimistic locking ใช้ `version` ใน `appointments`; endpoint ของ STAFF ต้องส่ง
  `expected_version`
- Worker มี heartbeat file เพื่อให้ Docker healthcheck และ autoheal ทำงานได้
