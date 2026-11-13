# PetCare — Minimal application (devtools)

คู่มือเริ่มแอปโดยใช้ `devtools` และ Docker Compose เท่านั้น **ไม่ต้องตั้ง Jenkins, GitHub webhook หรือ ngrok**. หากมี Docker Engine และ Compose บนเครื่องพัฒนาอยู่แล้ว สามารถรันคำสั่ง Compose จาก repository โดยตรงได้เช่นกัน

> `devtools` ใช้ Docker-in-Docker และต้องเริ่มด้วย `--privileged` ซึ่งให้สิทธิ์สูงแก่ container ใช้เฉพาะเครื่องที่เชื่อถือได้ อย่าเปิด Docker daemon ออกสู่อินเทอร์เน็ต

## สิ่งที่ต้องมี

- Docker Engine/Desktop และ Docker Compose v2 (หรือ `devtools` image ที่มี Docker และ Compose)
- พอร์ตว่าง 80, 3000 และ 9090 สำหรับ Nginx, Grafana และ Prometheus
- Repository นี้ในโฟลเดอร์ที่ใช้งาน

## 1. เริ่ม devtools

ถ้ายังไม่มี `devtools` container ให้รันบน host:

```bash
docker run -dit --name devtools --privileged -p 80:80 -p 3000:3000 -p 9090:9090 --tmpfs /run --restart unless-stopped tuchsanai/devtools:2569_1
```

เปิด shell ภายใน `devtools`:

```bash
docker exec -it --user root devtools bash
```

จากนั้นรันคำสั่งต่อไปนี้ **ภายใน shell ของ devtools**:

```bash
docker info
docker compose version
```

หาก source code ยังไม่ได้อยู่ใน container ให้ clone repository ภายใน shell:

```bash
git clone https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git /root/Pet-Clinic-Booking-and-Appointment-System
cd /root/Pet-Clinic-Booking-and-Appointment-System
```

ถ้า image ไม่มี `bash` ให้ใช้ `sh`. อีกทางหนึ่งคือ mount source directory ของเครื่องเข้า `devtools` ตอนสร้าง container แล้วทำงานจาก directory ที่ mount

## 2. ตั้งค่าและเริ่มแอป

จาก repository root สร้าง `.env` จากตัวอย่างและเปลี่ยน secrets:

```bash
cp .env.example .env
```

ตั้งค่าอย่างน้อย `POSTGRES_PASSWORD`, `JWT_SECRET` และ `GRAFANA_ADMIN_PASSWORD` ใน `.env` ก่อนใช้งานจริง ห้าม commit ไฟล์นี้ จากนั้น build และเริ่ม services:

```bash
docker compose up -d --build
docker compose ps
```

Compose จะเริ่ม PostgreSQL, รัน migration (`alembic upgrade head`) และเริ่ม backend สอง instances, worker, Nginx, Prometheus และ Grafana. ตรวจสถานะ:

```bash
docker compose logs --tail=100
curl -fsS http://localhost/api/v1/health/ready
```

| URL | บริการ |
|---|---|
| `http://localhost` | เว็บแอปและ API ผ่าน Nginx |
| `http://localhost/api/v1/health/live` | Backend liveness |
| `http://localhost/api/v1/health/ready` | Backend readiness และฐานข้อมูล |
| `http://localhost:3000` | Grafana (ค่าเริ่มต้น user `admin`; ใช้รหัสผ่านจาก `.env`) |
| `http://localhost:9090` | Prometheus |

เมื่อ Compose ทำงานใน Docker-in-Docker ที่อยู่ภายใน `devtools`, ports ที่ publish โดย Compose ชั้นในอาจไม่ถูกส่งต่อถึง host ตามที่คาด หากเปิด URL จาก host ไม่ได้ ให้ตรวจ Docker network/port forwarding ของ Docker daemon ที่ใช้ หรือรัน Compose โดยตรงจาก Docker Engine ของ host

## Seed ข้อมูลตัวอย่าง (ไม่บังคับ)

การเริ่มแอปและ migration **ไม่ต้องใช้ seed**. หากต้องการบัญชีและข้อมูล demo ให้รันจาก directory ของ repository:

```bash
docker compose run --rm web1 python -m scripts.seed
```

สคริปต์สร้างผู้ใช้ เจ้าของสัตว์เลี้ยง สัตว์เลี้ยง และกะตรวจ และสามารถรันซ้ำได้โดยไม่สร้างข้อมูลเหล่านี้ซ้ำ บัญชีตัวอย่าง:

| บทบาท | อีเมล |
|---|---|
| OWNER | `owner1@petcare.local` |
| VET | `vet1@petcare.local` |
| STAFF | `staff@petcare.local` |

รหัสผ่าน demo ของทุกบัญชีคือ `Petcare123!` ใช้เพื่อทดลองเท่านั้น; ห้ามใช้กับ production

## หยุดแอป

หยุด services แต่เก็บข้อมูลฐานข้อมูลและรูปภาพใน named volumes:

```bash
docker compose down
```

เริ่มใหม่ด้วย `docker compose up -d`. คำสั่ง `docker compose down -v` จะลบ volumes รวมถึงข้อมูล PostgreSQL และรูปภาพ ใช้เฉพาะเมื่อต้องการล้างข้อมูลทั้งหมด

## เอกสารเพิ่มเติม

- ระบบ CI/CD ด้วย devtools, Jenkins และ ngrok: [README-CICD.md](README-CICD.md)
- แนวทางทดสอบและ runbook: [docs/runbook.md](docs/runbook.md)
- คู่มือใช้งานและแก้ปัญหา: [docs/project-usage-guide-th.md](docs/project-usage-guide-th.md)
