# Runbook — PetCare System

> คู่มือทดสอบด้วยมนุษย์ (UAT) แบบติ๊กผ่าน/ไม่ผ่าน: [`docs/manual-testing.md`](manual-testing.md)
> ไดอะแกรมระบบ (Use Case / ER / CI-CD / Load Balancer): [`docs/diagrams.md`](diagrams.md)

## 1. สิ่งที่ต้องมี

- Docker Engine + Docker Compose v2
- พอร์ตว่าง: 80 (nginx), 3000 (Grafana), 9090 (Prometheus)
- ไฟล์ `.env` จาก `.env.example` (ห้าม commit)

```bash
cp .env.example .env
# แก้ POSTGRES_PASSWORD, JWT_SECRET, GRAFANA_ADMIN_PASSWORD
docker compose up -d --build
```

`migrate` จะรัน `alembic upgrade head` ครั้งเดียวแล้วจบ web1/web2 จะเริ่มหลัง migration สำเร็จ

### Seed ข้อมูลตัวอย่าง

```bash
docker compose run --rm web1 python -m scripts.seed
# owner1@petcare.local / vet1@petcare.local / staff@petcare.local
# password: Petcare123!
```

### สร้าง STAFF คนแรก (production)

```bash
docker compose run --rm web1 python -m scripts.create_staff \
  --email admin@clinic.local --password 'ChangeMe123!' \
  --full-name 'ผู้จัดการคลินิก' --role STAFF
```

## 2. Health และ Observability

| URL | ใช้ทำอะไร |
|---|---|
| `http://localhost/api/v1/health/live` | liveness (มี `X-Instance-Id`) |
| `http://localhost/api/v1/health/ready` | เช็กการเชื่อมต่อ PostgreSQL |
| `http://localhost:3000` | Grafana (dashboard `PetCare Overview`) |
| `http://localhost:9090` | Prometheus targets |

Healthcheck ทุก container: `interval=10s`, `timeout=3s`, `retries=3`
`autoheal` จะ restart container ที่ unhealthy (label `autoheal=true`)

## 3. การทดสอบ

### Test DB

```bash
docker compose up -d postgres
docker compose exec -T postgres psql -U petcare -d postgres -c 'CREATE DATABASE petcare_test'
```

### Backend (ruff + mypy + pytest)

```bash
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+asyncpg://petcare:petcare@postgres:5432/petcare_test \
  -e DATABASE_URL=postgresql+asyncpg://petcare:petcare@postgres:5432/petcare_test \
  web1 sh -c "ruff check app tests && mypy app && alembic upgrade head && pytest -q"
```

### Concurrency drill ผ่าน Nginx (ต้องมี token/pet/vet/slot จริง)

```bash
docker compose run --rm web1 python -m scripts.concurrency_check \
  --base-url http://nginx --token "$TOKEN" \
  --pet-id "$PET_ID" --vet-id "$VET_ID" --slot-start "2026-11-07T02:00:00Z"
# คาดหวัง: {"201": 1, "409": 19}
# ผลรันจริงผ่าน nginx: 201 = 1, 409 = 19 (20 คำขอพร้อมกัน)
```

### E2E ด้วย Playwright (UI จริง)

E2E ใช้ **test stack แยก** ไม่แตะฐานข้อมูลหรือรูปจริง:

- PostgreSQL container `postgres-e2e` / database `petcare_e2e`
- backend `web-e2e` ที่พอร์ต `8001`
- photo volume `petphotos_e2e`
- Vite test server ที่พอร์ต `5174`

```bash
cd frontend
npm install
npx playwright install chromium   # ครั้งแรกเท่านั้น
npm run test:e2e
```

สคริปต์ `scripts/e2e.sh` จะสร้าง/รีเซ็ต `petcare_e2e`, รัน migration + seed, สตาร์ท `web-e2e` แล้วจึงรัน Playwright

- เส้นทาง: OWNER จองผ่านหน้าเว็บ → STAFF เลื่อนนัดผ่านกระดาน → OWNER ยกเลิกผ่านหน้าเว็บ
- เลือกสัตวแพทย์/ช่วงเวลาว่างผ่าน API เพื่อให้รันซ้ำได้ (ไม่ hardcode สล็อต)
- ถ้าล้ม จะมี screenshot/trace ใน `frontend/test-results/` เปิดด้วย `npx playwright show-trace <trace.zip>`
- ตรวจ stack ที่ค้างได้ด้วย `docker compose -p petcare-e2e -f docker-compose.e2e.yml ps`
- ล้างเฉพาะ test stack และ test volumes ด้วย `docker compose -p petcare-e2e -f docker-compose.e2e.yml down -v` (ไม่แตะ `petcare` หรือ volume จริง)

หากต้องการยิง E2E ไปยัง stack ภายนอกโดยเจตนา ให้ใช้ `npx playwright test` พร้อม `E2E_BASE_URL` และตรวจให้แน่ใจว่าไม่ใช่ข้อมูลจริง

## 4. Recovery drills (NFR-03)

### 4.1 Backend instance ล่ม

```bash
# จำลอง process crash ภายใน container (kill -9 PID 1)
docker exec petcare-web1-1 kill -9 1
for i in $(seq 1 20); do
  curl -s -o /dev/null -w '%{http_code}\n' http://localhost/api/v1/health/ready
  sleep 1
done
docker compose ps                 # web1 ต้องกลับมา healthy เอง
```

หมายเหตุ: `docker kill petcare-web1-1` ถือเป็นการหยุดแบบ manual — Docker จะไม่ restart ตาม policy
จึงใช้ทดสอบ auto-recovery ไม่ได้ (ต้อง `docker compose up -d web1` เอง) ให้ใช้ `docker exec ... kill -9 1` แทน

nginx ตั้ง `max_fails=2 fail_timeout=10s` และ `proxy_next_upstream` จึงส่งต่อไป web2
ระหว่างที่ web1 ไม่อยู่ ผู้ใช้ไม่ควรเห็น 5xx
**ผลการวัดจริง (Docker Desktop 29.6.1, Windows, 2026-11-06):** ระหว่าง web1 ล่ม คำขอ `ready` 10/10
ยังได้ 200 ผ่าน web2 (ไม่พบ 5xx) และ web1 กลับมา healthy พร้อมรับ traffic อีกครั้งภายใน ~10 วินาที
หลัง recovery ยิง 10 คำขอ แบ่งเป็น web1 5 / web2 5

### 4.2 Worker ล่ม (NFR-02, NFR-04)

1. `docker compose stop worker`
2. จอง/เปลี่ยนสถานะ 10 ครั้งผ่าน API
3. `docker compose start worker`
4. ภายใน 2 นาที ตรวจว่าไม่หายและไม่ซ้ำ:

```sql
SELECT event_id, recipient_id, count(*)
FROM notifications
GROUP BY event_id, recipient_id
HAVING count(*) > 1;          -- ต้องได้ 0 แถว
```

Worker ใช้ `FOR UPDATE SKIP LOCKED`, `ON CONFLICT DO NOTHING` และ retry backoff
(`attempts`, `last_error`, `available_at`)

**ผลการวัดจริง (2026-11-06):** หยุด worker แล้วจอง 5 นัด → มี 11 outbox events ค้าง (booked + reminder
ที่ตั้งเวลาไว้ล่วงหน้า); เริ่ม worker แล้วเจ้าของได้รับ notification ครบ 5 รายการภายใน ~15 วินาที
และ query duplicate ได้ 0 แถว

### 4.3 PostgreSQL ล่ม

`restart: unless-stopped` + named volume `pgdata` ทำให้ container กลับมาและข้อมูลยังอยู่
`migrate` เป็น one-shot จึงไม่ทำให้ web ใหม่รัน migration ซ้ำซ้อน

**ผลการวัดจริง (2026-11-06):** `docker compose restart postgres` แล้ว `/api/v1/health/ready` = 200
และ login สำเร็จ ข้อมูลผู้ใช้/นัดหมายยังอยู่ครบ

## 5. Worker failure semantics

- อ่าน outbox ที่ `processed_at IS NULL AND available_at <= now()`
- ล็อกสูงสุด 100 แถวด้วย `FOR UPDATE SKIP LOCKED`
- สร้าง notification ต่อผู้รับแบบ idempotent
- error → `attempts += 1`, `last_error`, backoff 5s × 2^n (สูงสุด 300s)
- ครบ 10 ครั้ง → dead-letter (`processed_at` ถูกตั้ง เพื่อไม่วนไม่จบ) และ log ระดับ error
- reminder ที่นัดถูกยกเลิก/เลื่อนแล้วจะถูกข้าม (ตรวจสถานะ + slot_start)

## 6. Rollback

```bash
docker compose down                # หยุดทั้งหมด (volume ยังอยู่)
git checkout <previous-tag>
docker compose up -d --build       # migrate จะรันซ้ำแบบ idempotent
```

ถ้า migration ใหม่ต้องถอย: `docker compose run --rm web1 alembic downgrade -1`
(ระวัง: downgrade ลบข้อมูล schema ที่เพิ่งสร้าง)

## 7. ข้อจำกัดที่รู้

- Polling ทุก 3–5 วินาที แทน WebSocket/SSE (ADR-3)
- แจ้งเตือนเป็น In-App เท่านั้น (worker ออกแบบให้เพิ่ม channel adapter ได้)
- ถ้า node ทั้งเครื่องล่ม ระบบไม่ฟื้นเอง ต้องใช้ orchestrator (Swarm/K8s) ในอนาคต
- Grafana dashboard ใช้ metric มาตรฐานของ node-exporter/cadvisor; ชื่อ container ต้องขึ้นต้น
  ด้วย `petcare-` สำหรับ panel Container CPU
