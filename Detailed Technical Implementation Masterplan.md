## Detailed Technical Implementation Masterplan: PetCare System

**เอกสารต้นทาง:** DevTools Report — ระบบจองและนัดหมายคลินิกสัตว์เลี้ยง
**ใช้สำหรับ:** สั่ง AI Coder (DeepSeek) เขียนโค้ดทีละเฟส แต่ละเฟสต้องรันได้และทดสอบผ่านก่อนเริ่มเฟสถัดไป

---

### 0. สรุปผลวิเคราะห์เอกสาร และช่องว่างที่ต้องปิดก่อนเริ่มเขียนโค้ด

**สิ่งที่เอกสารกำหนดไว้ชัดเจน:**
- **ขอบเขต:** FR-01 ถึง FR-15, NFR-01 ถึง 04 และ NFR-10, User Story US-1 ถึง US-17
- **บทบาทผู้ใช้ (RBAC):** มี 3 บทบาท คือ OWNER, VET และ STAFF ถ้าผู้ใช้พยายามเข้าถึงข้อมูลนอกสิทธิ์ ให้ตอบ 403 ถ้าจองซ้ำหรือเปลี่ยนสถานะผิดกฎ ให้ตอบ 409
- **โครงสร้างพื้นฐาน:** Docker Compose, Nginx (พอร์ต 80, กระจายโหลดแบบ Round-Robin), Backend 2 ตัว (web1, web2 พอร์ต 8000), PostgreSQL (เก็บข้อมูลใน Named Volume), Worker สำหรับส่งแจ้งเตือน, Prometheus + Grafana + Node Exporter
- **CI/CD:** Jenkins 4 ขั้น คือ Checkout → Build & Verify → Deploy → Post-Deployment Verification
- **การทดสอบที่ต้องผ่าน:** Concurrency Locking, Worker Failure Recovery และ RBAC Boundary

**สิ่งที่เอกสารไม่ได้ระบุ ผมจึงกำหนดเป็นค่าเริ่มต้น (ADR) ไว้ก่อน ถ้าต้องการแบบอื่นแก้ได้ก่อนเริ่ม Phase 1:**

| # | ประเด็น | ค่าเริ่มต้นที่เลือก | เหตุผล |
|---|---|---|---|
| ADR-1 | ภาษาและเฟรมเวิร์กฝั่ง Backend | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 | พอร์ต 8000 เป็นค่ามาตรฐานของ Uvicorn, AI Coder เขียนได้แม่นยำ, ทำ Transaction ได้ดี |
| ADR-2 | Frontend | React 18 + Vite + TypeScript + TanStack Query + Tailwind | ตั้ง refetchInterval เพื่อให้ข้อมูลอัปเดตใน 5 วินาทีได้ง่าย |
| ADR-3 | วิธีอัปเดตข้อมูลแบบ Real-time (NFR-01) | Polling ทุก 3 วินาที โดยส่ง cursor `?since=` ไปด้วย | ไม่ต้องเก็บ state จึงทำงานกับ Round-Robin 2 instance ได้โดยไม่ต้องทำ sticky session (เปลี่ยนเป็น SSE ภายหลังได้) |
| ADR-4 | การยืนยันตัวตน | JWT Access Token (60 นาที) + hash รหัสผ่านด้วย Argon2id | ไม่ต้องเก็บ session บนเซิร์ฟเวอร์ จึงเหมาะกับการมี Backend 2 ตัว |
| ADR-5 | การส่งแจ้งเตือนแบบไม่หายและไม่ซ้ำ (NFR-04) | ใช้ Transactional Outbox บน PostgreSQL + Worker ดึงงานด้วย `FOR UPDATE SKIP LOCKED` + ใช้ Unique `(event_id, recipient_id)` | ไม่ต้องเพิ่ม Message Broker และทำให้ส่งครบหนึ่งครั้งตามที่ NFR-04 กำหนด |
| ADR-6 | การเลือกสัตวแพทย์ | OWNER เลือกสล็อตที่ผูกกับสัตวแพทย์ (สล็อตแสดงชื่อแพทย์) | สล็อตมาจากกะของแพทย์ (US-14) |
| ADR-7 | เขตเวลา | เก็บเป็น `timestamptz` (UTC) และแสดงผลเป็น Asia/Bangkok | กันปัญหาเวลาคลาดเคลื่อน |
| ADR-8 | เวลาส่งแจ้งเตือนล่วงหน้า (US-5) | ส่งทันทีหลังจองสำเร็จ และส่งอีกครั้ง 1 ชม. ก่อนนัด | เอกสารไม่ได้ระบุ |
| ADR-9 | จองล่วงหน้าได้นานแค่ไหน | ไม่เกิน 30 วัน | เอกสารไม่ได้ระบุ |
| ADR-10 | STAFF ยกเลิกนัดในช่วงน้อยกว่า 2 ชม. ได้หรือไม่ | ได้ (กฎ 2 ชม. ใช้กับ OWNER เท่านั้น) | ตามการทำงานจริงของคลินิก |

> ⚠️ ควรยืนยัน ADR-6, 8, 9, 10 กับเจ้าของโปรเจกต์ เพราะกระทบ Business Logic โดยตรง

---

### 1. สถาปัตยกรรมระบบ (Target Architecture)

```text
                 ┌──────────────────────────────────────────────┐
 Browser ──:80──▶│ nginx (static React build + reverse proxy)   │
                 │  /        → SPA (3 portals)                  │
                 │  /api/*   → upstream backend (round-robin)   │
                 └───────────────┬───────────────┬──────────────┘
                                 ▼               ▼
                          web1:8000        web2:8000   (FastAPI, stateless, /metrics)
                                 └──────┬────────┘
                                        ▼
                 worker ───────▶ postgres:5432 (volume: pgdata)
                 (outbox → notifications, reminders)
 migrate (one-shot alembic upgrade head) ─▶ postgres

 prometheus ◀─ scrape: web1, web2, node-exporter:9100, cadvisor:8080
 grafana    ◀─ datasource: prometheus (provisioned dashboards)
 autoheal   ─▶ restart containers ที่สถานะ unhealthy
```

**หลักการสำคัญที่ AI Coder ต้องทำตามทุกเฟส:**
1. ใช้ข้อมูลใน DB เป็นข้อมูลจริงเพียงแหล่งเดียว การกันจองซ้ำต้องทำด้วย DB Constraint ห้ามใช้แค่การเช็กในโค้ด
2. Backend ต้องไม่เก็บ state ไว้ในหน่วยความจำ เพราะ Request ถัดไปอาจไปลงอีก instance หนึ่ง
3. ทุกครั้งที่เปลี่ยนสถานะนัด ให้เปลี่ยนสถานะ บันทึก Audit Log และเขียน Outbox Event ใน Transaction เดียวกัน
4. ตรวจสิทธิ์ 2 ชั้น คือตรวจบทบาท และตรวจความเป็นเจ้าของข้อมูล (เช่น VET เปิดได้เฉพาะเคสที่ได้รับมอบหมาย)

---

### 2. Repository Structure (สัญญาร่วมทุกเฟส)

```text
petcare/
├── docker-compose.yml
├── .env.example                # ห้าม commit .env จริง
├── Jenkinsfile
├── .gitleaks.toml
├── .pre-commit-config.yaml
├── nginx/
│   ├── Dockerfile              # multi-stage: build frontend → nginx
│   └── nginx.conf
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py             # app factory, routers, /metrics, /health
│   │   ├── core/               # config.py, security.py, deps.py, errors.py, time.py
│   │   ├── db/                 # session.py, base.py
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic DTOs
│   │   ├── repositories/
│   │   ├── services/           # business logic (booking, queue, shift, notify, audit)
│   │   ├── api/v1/             # auth, pets, availability, appointments, queue,
│   │   │                       # shifts, reschedule_requests, treatment_notes,
│   │   │                       # notifications, audit, staff
│   │   └── worker/             # outbox_worker.py, reminder_scheduler.py
│   ├── scripts/seed.py, create_staff.py
│   └── tests/ unit/, integration/, concurrency/, rbac/, recovery/
├── frontend/
│   └── src/ api/, auth/, components/, portals/{owner,vet,staff}/, hooks/, routes.tsx
├── monitoring/
│   ├── prometheus/prometheus.yml
│   └── grafana/provisioning/{datasources,dashboards}/ + petcare-overview.json
└── docs/ adr.md, api.md, runbook.md
```

---

### 3. Data Model (PostgreSQL)

**Enums:**
- `user_role`: OWNER, VET, STAFF
- `appointment_status`: BOOKED, CHECKED_IN, IN_TREATMENT, COMPLETED, NO_SHOW, CANCELLED
- `reschedule_status`: PENDING, APPROVED, REJECTED

```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email CITEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT NOT NULL,
  phone TEXT,
  role user_role NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES users(id),
  name TEXT NOT NULL, species TEXT NOT NULL, breed TEXT,
  sex TEXT, birth_date DATE, weight_kg NUMERIC(5,2), medical_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vet_shifts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vet_id UUID NOT NULL REFERENCES users(id),
  shift_date DATE NOT NULL,
  start_time TIME NOT NULL, end_time TIME NOT NULL,
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (start_time >= '09:00' AND end_time <= '17:00' AND start_time < end_time),
  CHECK (EXTRACT(MINUTE FROM start_time) IN (0,30) AND EXTRACT(MINUTE FROM end_time) IN (0,30)),
  EXCLUDE USING gist (vet_id WITH =,
    tsrange(shift_date + start_time, shift_date + end_time) WITH &&)   -- กะห้ามซ้อนกัน
);

CREATE TABLE appointments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES users(id),
  pet_id UUID NOT NULL REFERENCES pets(id),
  vet_id UUID NOT NULL REFERENCES users(id),
  shift_id UUID NOT NULL REFERENCES vet_shifts(id),
  slot_start TIMESTAMPTZ NOT NULL,
  slot_end   TIMESTAMPTZ NOT NULL,
  status appointment_status NOT NULL DEFAULT 'BOOKED',
  symptoms TEXT NOT NULL,
  cancel_reason TEXT, cancelled_at TIMESTAMPTZ,
  version INT NOT NULL DEFAULT 1,            -- optimistic locking
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (slot_end = slot_start + interval '30 minutes')
);
-- หัวใจของการกันจองซ้ำ (FR-05, US-1, 5.2 Concurrency Locking)
CREATE UNIQUE INDEX uq_vet_slot_active ON appointments(vet_id, slot_start)
  WHERE status <> 'CANCELLED';
CREATE UNIQUE INDEX uq_pet_slot_active ON appointments(pet_id, slot_start)
  WHERE status <> 'CANCELLED';
CREATE INDEX ix_appt_vet_day ON appointments(vet_id, slot_start);
CREATE INDEX ix_appt_updated ON appointments(updated_at);   -- polling cursor

CREATE TABLE treatment_notes (            -- FR-13 Version Control
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appointment_id UUID NOT NULL REFERENCES appointments(id),
  version INT NOT NULL,
  content TEXT NOT NULL CHECK (length(trim(content)) > 0),
  created_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (appointment_id, version)
);

CREATE TABLE reschedule_requests (        -- FR-12, US-10
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appointment_id UUID NOT NULL REFERENCES appointments(id),
  requested_by UUID NOT NULL REFERENCES users(id),
  proposed_slot_start TIMESTAMPTZ NOT NULL,
  reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
  status reschedule_status NOT NULL DEFAULT 'PENDING',
  reviewed_by UUID REFERENCES users(id), reviewed_at TIMESTAMPTZ, review_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (                 -- NFR-10 (append-only)
  id BIGSERIAL PRIMARY KEY,
  actor_id UUID, actor_role user_role,
  entity_type TEXT NOT NULL, entity_id UUID NOT NULL,
  action TEXT NOT NULL,                   -- e.g. STATUS_CHANGE, RESCHEDULE, TRANSFER, SWAP, CANCEL
  before JSONB, after JSONB, request_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- trigger: RAISE EXCEPTION on UPDATE/DELETE ของ audit_logs

CREATE TABLE outbox_events (              -- NFR-02, NFR-04
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type TEXT NOT NULL,               -- APPOINTMENT_BOOKED, ..._CANCELLED, ..._STATUS_CHANGED,
                                          -- ..._TRANSFERRED, ..._RESCHEDULED, RESCHEDULE_REVIEWED,
                                          -- TREATMENT_NOTE_ADDED, APPOINTMENT_REMINDER
  aggregate_id UUID NOT NULL,
  payload JSONB NOT NULL,                 -- รวม recipient_ids
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),   -- ใช้ตั้งเวลา reminder
  processed_at TIMESTAMPTZ,
  attempts INT NOT NULL DEFAULT 0, last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_outbox_pending ON outbox_events(available_at) WHERE processed_at IS NULL;

CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES outbox_events(id),
  recipient_id UUID NOT NULL REFERENCES users(id),
  type TEXT NOT NULL, title TEXT NOT NULL, message TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (event_id, recipient_id)          -- กันส่งซ้ำ (NFR-04)
);
```

---

### 4. Business Rules ที่ต้องเขียนเป็นโค้ด

**4.1 State Machine ของนัดหมาย (US-12):** ถ้าเปลี่ยนสถานะนอกตารางนี้ ให้ตอบ 409 `INVALID_TRANSITION`

| สถานะปัจจุบัน | เปลี่ยนเป็นได้ | ใครทำได้ |
|---|---|---|
| BOOKED | CHECKED_IN, NO_SHOW | STAFF |
| BOOKED | CANCELLED | OWNER (ต้องเหลือเวลา ≥ 2 ชม. ก่อนนัด) / STAFF (ทำได้ทุกเวลา) |
| CHECKED_IN | IN_TREATMENT, NO_SHOW | STAFF |
| IN_TREATMENT | COMPLETED | STAFF |
| COMPLETED / NO_SHOW / CANCELLED | ไม่มี (สถานะสิ้นสุด) | ไม่มี |

**4.2 กฎของสล็อต (FR-04, US-13, US-14):**
- สล็อตยาว 30 นาที ต้องเริ่มที่นาทีที่ 00 หรือ 30 และอยู่ในช่วง 09:00–17:00 (สล็อตสุดท้ายเริ่ม 16:30)
- สล็อตต้องอยู่ในกะของแพทย์ ต้องเป็นเวลาในอนาคต และต้องไม่เกิน 30 วันข้างหน้า
- ถ้าละเมิดข้อใดข้อหนึ่ง ให้ตอบ 422 `SLOT_OUT_OF_RANGE`

**4.3 ขั้นตอนการจอง (FR-05) ทำทั้งหมดใน Transaction เดียว:**
1. ตรวจว่าสัตว์เลี้ยงเป็นของ OWNER คนนี้ ถ้าไม่ใช่ตอบ 403
2. `SELECT ... FROM vet_shifts WHERE ... FOR SHARE` เพื่อยืนยันว่าสล็อตอยู่ในกะ
3. `INSERT appointments` ถ้าชน `uq_vet_slot_active` จะเกิด IntegrityError ให้ rollback แล้วตอบ 409 `SLOT_TAKEN`
4. เขียน `audit_logs` (CREATE)
5. เขียน `outbox_events` 2 รายการ คือ BOOKED (ส่งทันที) และ REMINDER (`available_at = slot_start - 1h`)
6. COMMIT แล้วตอบ 201

**4.4 การยกเลิก (US-3):**
- ถ้า `now() > slot_start - 2h` ตอบ 422 `CANCEL_WINDOW_CLOSED` (กฎนี้ใช้กับ OWNER)
- ถ้ายกเลิกได้ ให้เปลี่ยนสถานะเป็น CANCELLED สล็อตจะว่างทันทีเพราะ Unique Index เป็นแบบ partial

**4.5 การลบกะ (US-14):** ถ้ากะมีนัดที่ยังไม่จบ (BOOKED, CHECKED_IN, IN_TREATMENT) ตอบ 409 `SHIFT_HAS_APPOINTMENTS`

**4.6 คิวสด (US-6):** แสดงนัดของแพทย์คนนั้นในวันนั้นที่สถานะเป็น BOOKED, CHECKED_IN หรือ IN_TREATMENT เรียงตาม `slot_start`
- `ahead_count` คือจำนวนคิวที่อยู่ก่อนหน้า
- `estimated_start = max(slot_start, now + ahead_count × 30 นาที)`
- เคสที่จบแล้วไม่ต้องแสดงเวลา (`estimated_start = null`)

**4.7 Optimistic Locking:** Endpoint ฝั่ง STAFF ที่แก้ไขนัดต้องส่ง `expected_version` มาด้วย ถ้าไม่ตรงกับค่าใน DB ตอบ 409 `STALE_VERSION` เพื่อกันกรณี STAFF 2 คนแก้นัดเดียวกันพร้อมกัน

**4.8 รูปแบบ Error มาตรฐาน:**
```json
{ "error": { "code": "SLOT_TAKEN", "message": "สล็อตนี้ถูกจองแล้ว", "details": {} } }
```
- **401:** ไม่ได้ส่ง token หรือ token ไม่ถูกต้อง
- **403:** ไม่มีสิทธิ์ (ผิดบทบาท หรือไม่ใช่เจ้าของข้อมูล)
- **404:** ไม่พบข้อมูล
- **409:** ข้อมูลชนกันหรือสถานะผิดกฎ
- **422:** ข้อมูลที่ส่งมาไม่ถูกต้อง หรือผิดกฎธุรกิจ

---

### 5. API Contract (`/api/v1`)

| Method & Path | บทบาท | ทำอะไร | FR/US |
|---|---|---|---|
| POST `/auth/register` | Public | OWNER สมัครสมาชิก | FR-01, US-7 |
| POST `/auth/staff-accounts` | STAFF | สร้างบัญชี VET/STAFF | US-16 |
| POST `/auth/login` | Public | รับ JWT กลับไป (ล็อกอินผิดตอบ 401) | FR-02, US-17 |
| GET `/auth/me` | ทุกบทบาท | ดูโปรไฟล์และบทบาทของตัวเอง | US-17 |
| GET/POST `/pets` · GET/PATCH `/pets/{id}` | OWNER (เฉพาะสัตว์ของตัวเอง) | จัดการข้อมูลสัตว์เลี้ยง | FR-06, US-4 |
| GET `/vets` | ทุกบทบาท | รายชื่อสัตวแพทย์ | FR-04 |
| GET `/availability?date=&vet_id=` | ทุกบทบาท | สล็อตว่าง | FR-04, US-2 |
| POST `/appointments` | OWNER | จองนัด (สำเร็จ 201, ชน 409) | FR-05, US-1 |
| GET `/appointments/me` | OWNER | นัดของฉัน | US-2 |
| GET `/appointments/{id}` | เจ้าของ / VET ที่ได้รับมอบหมาย / STAFF | รายละเอียดนัด (นอกเหนือจากนี้ตอบ 403) | FR-10, US-8 |
| POST `/appointments/{id}/cancel` | OWNER, STAFF | ยกเลิกนัด | FR-07, US-3 |
| GET `/queue/live?date=&vet_id=&since=` | ทุกบทบาท | คิวสด | FR-09, US-6 |
| GET `/appointments/{id}/queue-position` | OWNER | ลำดับคิวและเวลาประเมิน | US-6 |
| GET `/schedule?date=&vet_id=&since=` | VET (ดูได้เฉพาะตัวเอง) / STAFF (กรองได้) | ตารางงานเรียงตามเวลา | FR-11, US-9 |
| PATCH `/appointments/{id}/status` | STAFF | เปลี่ยนสถานะ | FR-14, US-12 |
| PATCH `/appointments/{id}/reschedule` | STAFF | เลื่อนนัด | US-13 |
| POST `/appointments/swap` | STAFF | สลับคิว 2 นัด | US-13 |
| POST `/appointments/{id}/transfer` | STAFF | โอนเคสไปแพทย์อื่น | FR-15, US-15 |
| GET/POST `/shifts` · PATCH/DELETE `/shifts/{id}` | STAFF (VET ดูได้อย่างเดียว) | จัดกะ | FR-15, US-14 |
| POST `/appointments/{id}/reschedule-requests` | VET (เฉพาะเคสตัวเอง) | ขอปรับเวลา (reason ว่างตอบ 422) | FR-12, US-10 |
| GET `/reschedule-requests?status=` | STAFF | ดูคำขอปรับเวลา | US-10 |
| POST `/reschedule-requests/{id}/approve` · `/reject` | STAFF | อนุมัติหรือปฏิเสธ | US-10 |
| GET/POST `/appointments/{id}/treatment-notes` | VET ที่ได้รับมอบหมายเขียนได้ / OWNER และ STAFF อ่านได้ | คำแนะนำการรักษาแบบมีเวอร์ชัน | FR-13, US-11 |
| GET `/pets/{id}/history` | OWNER / VET ที่มีเคสกับสัตว์ตัวนี้ / STAFF | ประวัติการรักษา | FR-10, US-8 |
| GET `/notifications?since=` · POST `/notifications/{id}/read` | ทุกบทบาท (เฉพาะของตัวเอง) | การแจ้งเตือน In-App | NFR-02, US-5 |
| GET `/audit-logs?entity_id=` | STAFF | ดูประวัติย้อนหลัง | NFR-10 |
| GET `/health/live`, `/health/ready`, `/metrics` | Internal | สถานะระบบและ Metrics | NFR-03 |

---

### 6. แผนพัฒนาทีละเฟส (Phase Plan)

> **กติกา:** ทำเฟสละ 1 session ใน DeepSeek ถ้ายังไม่ผ่าน Definition of Done (DoD) ห้ามเริ่มเฟสถัดไป

#### Phase 1: Foundation และ Docker Skeleton
- **เป้าหมาย:** สั่ง `docker compose up` แล้วเรียก `http://localhost/api/v1/health/live` ได้ และเห็นว่า Request สลับกันไป web1 กับ web2
- **ไฟล์ที่ต้องได้:**
  - `docker-compose.yml` (postgres, migrate, web1, web2, nginx)
  - `.env.example`, `backend/Dockerfile` (non-root user, มี healthcheck)
  - `app/main.py`, `core/config.py`, `nginx/nginx.conf`
- **สเปกสำคัญ:**
  - Nginx `upstream backend { server web1:8000 max_fails=2 fail_timeout=10s; server web2:8000 max_fails=2 fail_timeout=10s; }` และตั้ง `proxy_next_upstream error timeout http_502 http_503`
  - Response ต้องมี header `X-Instance-Id` บอกว่ามาจาก instance ไหน
  - ทุก service ตั้ง `restart: unless-stopped` และใช้ Named Volume `pgdata`
  - service `migrate` รัน `alembic upgrade head` แล้วจบ ส่วน web1/web2 ใช้ `depends_on: condition: service_completed_successfully`
- **DoD:** curl 10 ครั้งแล้วเห็น `X-Instance-Id` สลับกัน ลบ container แล้วสร้างใหม่ข้อมูลใน DB ยังอยู่

#### Phase 2: Database Schema, Migrations และ Seed
- **เป้าหมาย:** สร้าง Schema ทั้งหมดตามข้อ 3 ด้วย Alembic
- **ไฟล์ที่ต้องได้:** `models/*`, `alembic/versions/0001_initial.py`, trigger กันแก้ไข audit, `scripts/seed.py` (STAFF 1, VET 2, OWNER 2, สัตว์เลี้ยง 3, กะ 7 วัน)
- **DoD:**
  - `alembic upgrade head` และ `downgrade base` ผ่านทั้งคู่
  - test ยืนยันว่า INSERT นัดซ้ำสล็อตเดิมแล้วเกิด IntegrityError
  - test ยืนยันว่า UPDATE `audit_logs` แล้วเกิด error

#### Phase 3: Authentication และ RBAC (FR-01–03, US-7, 16, 17)
- **ไฟล์ที่ต้องได้:** `core/security.py` (Argon2id, JWT), `core/deps.py` (`get_current_user`, `require_roles(*roles)`), `api/v1/auth.py`, `scripts/create_staff.py` (ใช้สร้าง STAFF คนแรก)
- **สเปกสำคัญ:**
  - JWT เก็บ `sub`, `role`, `exp`
  - ถ้า role ไม่ตรงตอบ 403 ถ้าไม่มี token ตอบ 401
  - ข้อความตอนล็อกอินผิดต้องเหมือนกันทั้งกรณีอีเมลผิดและรหัสผ่านผิด
- **DoD:** test ยืนยันว่าใน DB รหัสผ่านขึ้นต้นด้วย `$argon2id$` และมี test RBAC matrix ครบทั้ง 3 บทบาท

#### Phase 4: Shifts และ Availability (FR-04, FR-15, US-14)
- **ไฟล์ที่ต้องได้:** `services/shift_service.py`, `services/availability_service.py`, `api/v1/shifts.py`, `api/v1/availability.py`
- **สเปกสำคัญ:**
  - สร้างสล็อตจากกะทีละ 30 นาที แล้วตัดสล็อตที่มีนัด (ยกเว้นนัดที่ CANCELLED) ออก
  - กะซ้อนกันตอบ 409 `SHIFT_OVERLAP`
  - ลบกะที่มีนัดค้างตอบ 409
- **DoD:** วันที่ไม่มีกะต้องคืนรายการว่าง `[]` (US-2) และ test กฎ 09:00–17:00 ผ่าน

#### Phase 5: Booking Core, Pets และ Cancel (FR-05–08, US-1, 3, 4)
- **ไฟล์ที่ต้องได้:** `services/booking_service.py`, `services/audit_service.py`, `services/outbox_service.py`, `api/v1/pets.py`, `api/v1/appointments.py`
- **สเปกสำคัญ:** ทำตามข้อ 4.3–4.4 ทุกครั้งที่ทำงานต้องเขียน audit และ outbox ใน Transaction เดียวกัน
- **DoD (สำคัญที่สุด):** `tests/concurrency/test_double_booking.py` ใช้ `asyncio.gather` ยิง 20 Request เข้าสล็อตเดียวกันผ่าน Nginx ต้องได้ 201 จำนวน 1 ครั้ง และ 409 จำนวน 19 ครั้ง และใน DB ต้องมีนัดนั้นเพียง 1 แถว

#### Phase 6: Queue Operations และ Audit (FR-09, FR-14, US-6, 12, 13, 15, NFR-10)
- **ไฟล์ที่ต้องได้:** `services/queue_service.py` (state machine และคิวสด), `api/v1/queue.py`, endpoint สำหรับ status/reschedule/swap/transfer
- **สเปกสำคัญ:**
  - Swap ต้อง lock ทั้ง 2 แถวด้วย `SELECT ... FOR UPDATE ORDER BY id` เพื่อกัน deadlock และใช้ deferrable constraint หรือย้ายผ่านสล็อตชั่วคราวภายใน Transaction
  - Transfer ต้องเช็กว่าแพทย์ปลายทางมีกะครอบสล็อตนั้นและสล็อตว่าง ถ้าไม่ว่างตอบ 409
  - Endpoint ที่ใช้ polling ต้องรองรับ `?since=` (ใช้ `updated_at`) และ ETag ถ้าไม่มีข้อมูลเปลี่ยนตอบ 304
- **DoD:** test ครบทุก transition ที่ถูกและผิด (ผิดต้องตอบ 409) และทุกการเปลี่ยนแปลงต้องมีแถวใน `audit_logs`

#### Phase 7: Vet Module (FR-10–13, US-8, 9, 10, 11)
- **ไฟล์ที่ต้องได้:** `api/v1/schedule.py`, `api/v1/reschedule_requests.py`, `api/v1/treatment_notes.py`, `services/ownership.py` (ฟังก์ชัน `assert_can_view_appointment(user, appt)`)
- **สเปกสำคัญ:**
  - Treatment note ทุกครั้งที่บันทึกให้ INSERT เป็นเวอร์ชันใหม่ (`version = max + 1`) โดย lock แถวของนัดก่อน และห้าม UPDATE ทับของเดิม
  - เมื่อ STAFF อนุมัติคำขอปรับเวลา ให้ใช้ logic เดียวกับ reschedule ใน Phase 6 (ถ้าชนตอบ 409)
- **DoD:** test ที่ VET A เปิดเคสของ VET B ต้องได้ 403 และ test ที่ส่ง reason ว่างต้องได้ 422

#### Phase 8: Notification Worker (NFR-02, NFR-04, US-5)
- **ไฟล์ที่ต้องได้:** `worker/outbox_worker.py`, เพิ่ม service `worker` ใน compose, `api/v1/notifications.py`
- **อัลกอริทึม:** วนทำงานทุก 5 วินาที
  1. `BEGIN; SELECT * FROM outbox_events WHERE processed_at IS NULL AND available_at <= now() ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED`
  2. สร้างแจ้งเตือนผู้รับแต่ละคนด้วย `INSERT notifications ... ON CONFLICT (event_id, recipient_id) DO NOTHING`
  3. `UPDATE processed_at = now(); COMMIT`
  4. ถ้าเกิด error ให้เพิ่ม `attempts` เก็บ `last_error` และลองใหม่แบบ backoff
  5. ก่อน insert reminder ให้เช็กว่านัดยังเป็น BOOKED อยู่หรือไม่ ถ้าถูกยกเลิกไปแล้วให้ข้าม
- **DoD (ตรงกับ 5.2 Worker Failure):**
  1. `docker compose stop worker`
  2. จองหรือเปลี่ยนสถานะ 10 ครั้ง
  3. `start worker`
  4. ภายใน 2 นาทีต้องมีแจ้งเตือนครบ 10 รายการ ไม่มีซ้ำ (เช็กด้วย query `GROUP BY event_id, recipient_id HAVING count > 1` ต้องได้ 0 แถว)

#### Phase 9: Frontend 3 Portals (NFR-01, UI ทุก US)
- **ไฟล์ที่ต้องได้:** โครงสร้าง `frontend/src/*`, `nginx/Dockerfile` แบบ multi-stage
- **หน้าจอ:**
  - **Owner:** Login/Register, My Pets, Book (Date Picker → สล็อตแยกตามแพทย์ → เลือกสัตว์ → กรอกอาการ), My Appointments (ปุ่มยกเลิกจะซ่อนเมื่อเหลือน้อยกว่า 2 ชม. และมี Pop-up ยืนยัน), Live Queue, Treatment Notes, Notifications
  - **Vet:** Daily Schedule (Date Picker), Case Detail และประวัติ, Treatment Note Editor พร้อม Version History, Reschedule Request
  - **Staff:** Schedule Board (กรองตามแพทย์), ปุ่มเปลี่ยนสถานะ, Reschedule/Swap/Transfer, Shift Management, Reschedule Approvals, Audit Log Viewer, Create Staff/Vet
- **สเปกสำคัญ:**
  - ทุก query ที่ต้องเป็น real-time ตั้ง `refetchInterval: 3000`
  - ถ้า API ตอบ 409 ให้แสดง toast แล้ว refetch ทันที
  - แสดง field error จาก 422 ใต้ช่องที่ผิด
  - Route guard ตามบทบาท และออกแบบ Responsive แบบ mobile-first
- **DoD:** เปิด 2 browser ให้ STAFF เปลี่ยนสถานะ ฝั่ง OWNER ต้องเห็นการเปลี่ยนแปลงภายใน 5 วินาทีโดยไม่ต้อง reload

#### Phase 10: Observability และ Auto-Recovery (NFR-03)
- **ไฟล์ที่ต้องได้:**
  - `monitoring/prometheus/prometheus.yml` (scrape web1, web2, node-exporter, cadvisor ทุก 15 วินาที)
  - Grafana provisioning และ dashboard ที่แสดง CPU, Memory, Disk, Network, HTTP req/s, p95 latency, 5xx rate
  - Backend ใช้ `prometheus-fastapi-instrumentator`
  - service `autoheal`
- **สเปกสำคัญ:**
  - healthcheck ตั้ง `interval: 10s, timeout: 3s, retries: 3`
  - `/health/ready` ต้องเช็ก DB ด้วย
  - Docker ไม่ restart container ที่ unhealthy ให้เอง จึงต้องมี autoheal
  - Worker ต้องมี heartbeat (เช่น touch ไฟล์) เพื่อใช้ทำ healthcheck
- **DoD:** `docker kill web1` แล้ว Nginx ต้องส่งต่อไป web2 โดยผู้ใช้ไม่เห็น 5xx และ web1 ต้องกลับมาภายใน 60 วินาที ทำซ้ำกับ worker และ postgres แล้ววัดเวลาบันทึกไว้ใน `docs/runbook.md`

#### Phase 11: Jenkins CI/CD และ Security
- **Jenkinsfile:**
  1. **Checkout:** ดึงโค้ด
  2. **Build & Verify:** ruff, mypy, `gitleaks detect` (ถ้าเจอ secret ให้ fail), pytest พร้อม test DB, `npm ci && npm run build && npm test`, `docker compose build`
  3. **Deploy:** `docker compose up -d --remove-orphans` (migrate รันอัตโนมัติ)
  4. **Post-Deployment Verification:** วนเช็ก `/api/v1/health/ready` ผ่าน Nginx สูงสุด 60 วินาที, smoke test (login และ availability), เช็กว่า target ใน Prometheus เป็น `up == 1` ทั้งหมด ถ้าไม่ผ่านให้ fail และแจ้ง rollback
- **Security:** ตั้ง pre-commit gitleaks, เก็บ `.env` ไว้ใน Jenkins Credentials, ห้าม hardcode secret, ตั้ง CORS ให้รับเฉพาะ origin ของตัวเอง, ทำ rate limit ที่ Nginx สำหรับ `/auth/login`
- **DoD:** pipeline ผ่านครบ 4 stage และถ้าลองใส่ secret ปลอมใน commit ต้องทำให้ pipeline fail

#### Phase 12: Verification Suite และ UAT
- **Test ที่ต้องมี:**

| Test | วิธีทดสอบ | ผลที่คาดหวัง |
|---|---|---|
| Concurrency Locking | ยิง 20 Request พร้อมกันผ่าน Nginx | 201 ×1 และ 409 ×19 |
| RBAC Boundary | matrix ทุก endpoint × 3 บทบาท × ข้ามเจ้าของ | เป็น 403 ตามที่กำหนดทุกช่อง |
| Worker Failure | หยุด worker แล้วสร้าง event แล้วเปิดใหม่ | ส่งครบ ไม่หาย ไม่ซ้ำ ภายใน 2 นาที |
| Auto-Recovery | kill container ทีละตัว | กลับมาภายใน 60 วินาที |
| Real-time | Playwright เปิด 2 context | UI อัปเดตภายใน 5 วินาที |
| Password/Secret | query DB และรัน gitleaks | เป็น hash ทั้งหมดและไม่พบ secret |

- **DoD:** ได้ Traceability Report ที่แสดงว่า US-1 ถึง US-17 แต่ละข้อผ่าน test ข้อใด

---

### 7. Traceability Matrix (ย่อ)

| Requirement | Phase | Test หลัก |
|---|---|---|
| FR-01–03, US-7, 16, 17 | 3 | test_auth, test_rbac_matrix |
| FR-04, US-2, 14 | 4 | test_availability, test_shifts |
| FR-05–08, US-1, 3, 4 | 5 | test_double_booking, test_cancel_window |
| FR-09, 14, US-6, 12, 13, 15 | 6 | test_state_machine, test_swap_transfer |
| FR-10–13, US-8–11 | 7 | test_vet_ownership, test_note_versions |
| NFR-01 | 6, 9 | e2e_realtime |
| NFR-02, 04, US-5 | 8 | test_worker_recovery |
| NFR-03 | 10 | recovery script |
| NFR-10 | 5–7 | test_audit_written |

---

### 8. ชุดคำสั่งสำหรับ DeepSeek

**8.1 Global Context:** วางไว้ต้นทุก session

```text
คุณคือ Senior Backend/Full-stack Engineer กำลังพัฒนา "PetCare System"
Stack: Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic v2,
PostgreSQL 16, React 18 + Vite + TS + TanStack Query + Tailwind, Docker Compose,
Nginx (round-robin → web1/web2:8000), Prometheus, Grafana, Jenkins.

กฎบังคับ:
1. ส่งไฟล์ "ฉบับเต็ม" พร้อม path ทุกไฟล์ ห้ามละโค้ดด้วย "..." หรือ "เหมือนเดิม"
2. ห้ามเปลี่ยน DB schema / API contract / error codes ที่ให้ไว้ ถ้าจำเป็นต้องเปลี่ยนให้ถามก่อน
3. Backend ต้อง stateless; ป้องกัน race ด้วย DB constraint + transaction เสมอ
4. ทุกการเปลี่ยนสถานะ appointment: เขียน audit_logs + outbox_events ใน transaction เดียวกัน
5. Error format: {"error":{"code","message","details"}}; 401/403/404/409/422 ตามสัญญา
6. Secret อ่านจาก env เท่านั้น; type hints ครบ; เขียน pytest คู่กับทุก service
7. ปิดท้ายด้วย: (a) คำสั่งรัน/ทดสอบ (b) รายการ DoD ที่ทำแล้ว (c) สมมติฐานที่ตั้งเพิ่ม

[แนบ: ADR ข้อ 0, Schema ข้อ 3, Business Rules ข้อ 4, API Contract ข้อ 5]
```

**8.2 Template คำสั่งแต่ละเฟส:**

```text
## งาน: Phase {N} — {ชื่อเฟส}
สถานะปัจจุบัน: Phase 1..{N-1} เสร็จแล้ว (แนบ file tree ปัจจุบัน + ไฟล์ที่เกี่ยวข้อง)
เป้าหมาย: {จากแผน}
ไฟล์ที่ต้องสร้าง/แก้: {รายการ}
สเปกบังคับ: {bullet จากแผน}
Definition of Done: {รายการ}
ขั้นตอน: 1) เขียน test ก่อน 2) implement 3) แสดงคำสั่งรันที่ทำให้ test ผ่าน
```

**8.3 เคล็ดลับเมื่อใช้งาน DeepSeek:**
- แนบไฟล์จริงจากเฟสก่อนทุกครั้ง อย่าให้มันเดาจากความจำ เพราะมักเขียน import หรือชื่อฟังก์ชันไม่ตรงกับของเดิม
- Phase 5, 6 และ 8 มีความเสี่ยงสูง ให้สั่งรีวิว Transaction boundary แยกอีกรอบ เช่น "ชี้จุดที่อาจเกิด race condition หรือ deadlock ในโค้ดนี้"
- ถ้าเฟสไหนใหญ่ (โดยเฉพาะ Phase 9) ให้แบ่งย่อยตาม portal เป็น 9A Owner, 9B Vet และ 9C Staff

---

### 9. ความเสี่ยงและวิธีรับมือ

| ความเสี่ยง | วิธีรับมือ |
|---|---|
| AI Coder ข้าม DB constraint แล้วเช็กสล็อตว่างด้วยโค้ดอย่างเดียว | ให้ Concurrency Test ใน Phase 5 เป็นเงื่อนไขบังคับก่อนผ่านเฟส |
| สองตัว instance รัน migration พร้อมกัน | ใช้ service `migrate` แยกเป็น one-shot |
| Docker ไม่ restart container ที่ unhealthy | ใช้ autoheal ร่วมกับ healthcheck |
| ถ้าเครื่อง (node) ล่มทั้งเครื่อง ระบบจะไม่ฟื้นเอง (ข้อจำกัดที่เอกสารระบุไว้) | บันทึกไว้ใน runbook และเสนอเป็น Swarm/K8s ใน Phase ถัดไป |
| แจ้งเตือนมีแค่ In-App | ออกแบบ worker ให้เพิ่มช่องทางได้ (`channel` adapter) รองรับ Email/LINE ในอนาคต |
| Polling ทำให้โหลด DB สูงขึ้น | ใช้ `?since=` + ETag/304 และมี index ที่ `updated_at` |

---

ถ้าจะเริ่มเลย ผมเขียน Prompt ฉบับเต็มของ Phase 1 ที่ใส่ Global Context ครบแล้วให้ได้ คัดลอกไปวางใน DeepSeek ได้ทันที หรือถ้าอยากได้ Masterplan นี้เป็นไฟล์ไว้แชร์ทีม บอกได้ว่าต้องการ PDF หรือ Word