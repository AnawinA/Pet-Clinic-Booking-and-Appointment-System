# PetCare — Full CI/CD development

คู่มือสำหรับสภาพแวดล้อมพัฒนาและ deploy ที่ใช้ **devtools, Jenkins และ ngrok** กับ GitHub webhook

> **ข้อควรระวัง:** `devtools` ต้องใช้ `--privileged` เพื่อรัน Docker-in-Docker และ Jenkins เชื่อมต่อ SSH เป็น `root` ตาม pipeline ปัจจุบัน ใช้เฉพาะเครื่อง/เครือข่ายที่เชื่อถือได้ อย่าเปิด Jenkins หรือ Docker daemon สู่สาธารณะโดยไม่มีการป้องกัน และห้าม commit secrets

## องค์ประกอบและสิ่งที่ต้องมี

- Docker Engine/Desktop, Docker Compose v2 และ Git
- Jenkins ที่มี Pipeline, Git, GitHub, Credentials Binding และ SSH Agent plugins
- Jenkins agent ที่มี `git`, `tar` และ OpenSSH client
- บัญชี ngrok พร้อม authtoken และ dev domain
- Docker Hub account/token พร้อมสิทธิ์ push ไปยัง repositories `petcare-backend` และ `petcare-nginx`
- Jenkins และ `devtools` อยู่บน Docker network เดียวกัน

## 1. เริ่ม Jenkins และ devtools

รันจาก terminal บน host:

```bash
docker network create cicd-net
docker run -dit --name devtools --privileged -p 127.0.0.1:2222:22 -p 80:80 -p 9090:9090 -p 3000:3000 --network cicd-net --tmpfs /run --restart unless-stopped tuchsanai/devtools:2569_1
docker run -d --name jenkins --network cicd-net --restart unless-stopped -p 127.0.0.1:8080:8080 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts-jdk21
```

ถ้ามี network อยู่แล้ว ให้ข้าม `docker network create`. เข้า Jenkins ที่ <http://localhost:8080> และอ่าน initial admin password:

```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

ติดตั้ง Jenkins plugins ที่ pipeline ต้องใช้ด้วยคำสั่ง:

```bash
docker exec -u root jenkins jenkins-plugin-cli --plugins "workflow-aggregator git github credentials-binding ssh-agent"
docker restart jenkins
```

คำสั่งนี้ติดตั้ง Pipeline (`workflow-aggregator`), Git, GitHub, Credentials Binding และ SSH Agent plugins แล้ว restart Jenkins. หรือจะติดตั้ง plugins เดียวกันผ่าน **Manage Jenkins → Plugins** ก็ได้

จากนั้นสร้าง Jenkins Pipeline job แบบ **Pipeline script from SCM** ชี้ไปที่ repository นี้และตั้ง Script Path เป็น `Jenkinsfile`.

## 2. ตั้งค่า Jenkins credentials และ SSH

สร้าง credentials ที่ pipeline อ้างถึง:

| Credential ID | ประเภท |
|---|---|
| `petcare-jwt-secret` | Secret text |
| `petcare-postgres-password` | Secret text ใช้ตัวอักษร `A-Z`, `a-z`, ตัวเลข, `.`, `_`, `~`, `-` |
| `petcare-grafana-password` | Secret text |
| `dockerhub` | Username with password; ใช้ Docker Hub access token เป็น password |
| `devtools-ssh` | SSH Username with private key; username `root` |
| `github-webhook-secret` | Secret text สำหรับ GitHub plugin และ webhook |

ติดตั้ง **public SSH key** ใน `/root/.ssh/authorized_keys` บน `devtools`; เก็บ **private key** เป็น Jenkins credential `devtools-ssh` เท่านั้น จากนั้นตรวจสอบ fingerprint ของ SSH host key และเพิ่ม key ที่เชื่อถือได้ลงใน `known_hosts` ของ agent ที่รัน pipeline (Jenkinsfile บังคับ `StrictHostKeyChecking=yes`). Jenkins ต้องเชื่อม `root@devtools:22` ผ่าน Docker network; `localhost:2222` ใช้เชื่อมจาก host เท่านั้น

ตั้ง GitHub plugin shared secret ให้ตรงกับ `github-webhook-secret` และตั้ง Jenkins URL เป็น HTTPS ngrok domain

## 3. เปิด ngrok และตั้ง GitHub webhook

ngrok ต้องอยู่บน `cicd-net` และ forward ไป `http://jenkins:8080`. ใช้ policy ที่ repository ให้มา ซึ่งอนุญาตเฉพาะ `POST /github-webhook/`:

```text
ngrok/traffic-policy.yml
```

เริ่ม ngrok โดยใช้ authtoken จาก environment/secret store (อย่าใส่ token ตรง ๆ ใน command history) และ mount policy แบบ read-only

**Windows PowerShell** — รันจาก repository root; กรอก dev domain และ authtoken เมื่อระบบถาม:

```powershell
$NGROK_DOMAIN = Read-Host "ngrok dev domain (e.g. example.ngrok.app)"
$policyPath = (Resolve-Path .\ngrok\traffic-policy.yml).Path
$secure = Read-Host "ngrok authtoken" -AsSecureString
$env:NGROK_AUTHTOKEN = (New-Object System.Net.NetworkCredential("", $secure)).Password
docker run -d --name ngrok --network cicd-net --restart unless-stopped -p 127.0.0.1:4040:4040 -e NGROK_AUTHTOKEN --mount "type=bind,source=$policyPath,target=/etc/ngrok/traffic-policy.yml,readonly" ngrok/ngrok:latest http http://jenkins:8080 --url "https://$NGROK_DOMAIN" --traffic-policy-file /etc/ngrok/traffic-policy.yml --log stdout
Remove-Item Env:NGROK_AUTHTOKEN
```

**Linux / macOS (Bash)** — รันจาก repository root:

```bash
read -r -p "ngrok dev domain (e.g. example.ngrok.app): " NGROK_DOMAIN
read -rsp "ngrok authtoken: " NGROK_AUTHTOKEN
export NGROK_AUTHTOKEN
printf '\n'
docker run -d --name ngrok --network cicd-net --restart unless-stopped -p 127.0.0.1:4040:4040 -e NGROK_AUTHTOKEN --mount "type=bind,source=$PWD/ngrok/traffic-policy.yml,target=/etc/ngrok/traffic-policy.yml,readonly" ngrok/ngrok:latest http http://jenkins:8080 --url "https://$NGROK_DOMAIN" --traffic-policy-file /etc/ngrok/traffic-policy.yml --log stdout
unset NGROK_AUTHTOKEN
```

ตรวจสถานะ tunnel และดู logs:

```bash
docker ps --filter name=ngrok
docker logs --tail=50 ngrok
```

หน้า ngrok local status อยู่ที่ <http://localhost:4040>. ปิด tunnel เมื่อเลิกใช้งานด้วย `docker stop ngrok`. รายละเอียดเพิ่มเติมและแนวทาง troubleshooting ดูใน [คู่มือ CI/CD ภาษาไทย](docs/project-usage-guide-th.md#7-เปิด-jenkins-localhost-ด้วย-ngrok).

ใน GitHub repository ไปที่ **Settings → Webhooks → Add webhook**:

- Payload URL: `https://<NGROK_DOMAIN>/github-webhook/` (ต้องมี `/` ปิดท้าย)
- Content type: `application/json`
- Secret: ค่าเดียวกับ Jenkins shared secret
- เปิด SSL verification และเลือก **Just the push event**

ตรวจ delivery จาก **Recent Deliveries** และตรวจ ngrok/Jenkins logs หาก webhook ไม่ทำงาน

## 4. การทำงานของ pipeline

เมื่อ push ไปยัง branch ที่กำหนดใน job, `Jenkinsfile` จะ checkout source, sync ไป `devtools`, build และตรวจ backend, รัน Ruff/mypy/Alembic/pytest/Gitleaks, push images ไป Docker Hub, deploy ด้วย Compose และตรวจสุขภาพหลัง deploy

เข้าแอปที่ `http://localhost` และตรวจ readiness ที่ `http://localhost/api/v1/health/ready`; Grafana อยู่ที่ `http://localhost:3000`, Prometheus อยู่ที่ `http://localhost:9090`. หาก Compose ทำงานผ่าน Docker-in-Docker การส่งต่อ ports ไปยัง host ขึ้นอยู่กับ Docker networking ของเครื่อง ให้ตรวจสอบเมื่อเข้า URL จาก host ไม่ได้

## ข้อมูลตัวอย่างและ seed (สำคัญ)

Compose รัน `alembic upgrade head` อัตโนมัติ แต่ **ไม่จำเป็นต้อง seed ฐานข้อมูลเพื่อเริ่มแอป**. สำหรับการ deploy ด้วยตนเอง ให้ seed เฉพาะเมื่อต้องการบัญชีและข้อมูล demo:

```bash
docker compose run --rm web1 python -m scripts.seed
```

คำสั่งนี้สร้างผู้ใช้สัตวแพทย์ เจ้าหน้าที่ เจ้าของสัตว์เลี้ยง สัตว์เลี้ยง และกะตรวจ ตัวอย่างบัญชี: `owner1@petcare.local`, `vet1@petcare.local`, `staff@petcare.local`; รหัสผ่าน demo คือ `Petcare123!`. ใช้เฉพาะข้อมูลทดสอบ และอย่าใช้รหัสผ่านนี้ใน production

**ข้อแตกต่างของ pipeline ปัจจุบัน:** Jenkins จะเรียก seed อัตโนมัติในขั้น Post-Deployment Verification ทุกครั้ง และการตรวจหลัง deploy ต้องอาศัยข้อมูล demo ดังนั้น seed เป็น optional สำหรับการรัน Compose ด้วยตนเอง แต่ยังไม่สามารถปิด seed ใน Jenkins pipeline ได้โดยไม่แก้ pipeline และขั้นตอนตรวจสอบ

## หยุดระบบและเอกสารเพิ่มเติม

- ปิด tunnel: `docker stop ngrok`
- หยุด Compose โดยเก็บข้อมูลใน volumes: `docker compose down`
- อย่าใช้ `docker compose down -v` หากต้องการเก็บฐานข้อมูล/รูปภาพ
- ขั้นตอน SSH, webhook, credentials และ troubleshooting แบบละเอียด: [คู่มือ CI/CD ภาษาไทย](docs/project-usage-guide-th.md)
- การทดสอบและ runbook: [docs/runbook.md](docs/runbook.md)
- คู่มือแอปแบบไม่ใช้ Jenkins/ngrok: [README-minimal.md](README-minimal.md)
