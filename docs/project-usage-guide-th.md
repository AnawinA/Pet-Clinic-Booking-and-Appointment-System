# คู่มือใช้งานโปรเจกต์ Pet Clinic และระบบ CI/CD

คู่มือนี้รวบรวมขั้นตอนตั้งแต่เตรียมเครื่อง, เริ่ม Jenkins และ `devtools`, รันแอป,
ตั้ง GitHub webhook, build และ deploy อัตโนมัติ, ตรวจสอบผล และแก้ปัญหา
สำหรับการทำงานแบบ demo ที่ใช้ Jenkins เชื่อมต่อ `devtools` ด้วย SSH

> **ขอบเขตและความปลอดภัย:** ตัวอย่างใช้ SSH เป็น `root` และ Docker daemon
> ใน `devtools` ซึ่งมีสิทธิ์สูง ให้ใช้ใน demo environment ที่แยกจากระบบจริงเท่านั้น
> ปิด root password login, ห้ามเผยแพร่ secrets และอย่าเปิด Jenkins หรือ Docker daemon
> สู่อินเทอร์เน็ตโดยไม่มีมาตรการป้องกัน

## ภาพรวมขั้นตอน

1. เตรียม Docker, Git, Jenkins, `devtools` และ Docker Hub
2. เริ่ม containers บน Docker network เดียวกัน
3. สร้าง SSH key แล้วติดตั้งเฉพาะ public key ใน `devtools`
4. เพิ่ม private key และ secrets เป็น Jenkins credentials
5. สร้าง Pipeline job และ GitHub push webhook
6. ทดสอบ build, publish, deploy และตรวจสอบการเข้าใช้งานแอป

## 1. สิ่งที่ต้องเตรียม

### เครื่องและบริการ

- Docker Engine/Desktop ที่รองรับ `docker run` และ Docker Compose
- Git และ terminal ที่ใช้ Docker CLI ได้บนเครื่อง host
- บัญชี ngrok พร้อม authtoken และ HTTPS dev domain สำหรับเปิดทางจาก GitHub ไปยัง Jenkins ที่ localhost
- Jenkins ที่รับ webhook ผ่าน URL HTTPS ของ ngrok ได้
- `devtools` image `tuchsanai/devtools:2569_1` ที่มี SSH server, Docker Engine,
  Docker Compose v2.30 ขึ้นไป, Bash, tar และ curl
- Jenkins agent ที่มี Git, tar และ OpenSSH client (`ssh`)
- Jenkins และ `devtools` ต้องสื่อสารกันได้ทาง network โดยชื่อ `devtools` และ port 22
- Docker Hub account ที่มี repositories `petcare-backend` และ `petcare-nginx`
  พร้อม access token ที่มีสิทธิ์ push

Jenkins agent ไม่จำเป็นต้องรัน Docker; คำสั่ง build/test/push/deploy ของ pipeline
จะทำงานบน `devtools`

เนื่องจาก repository เป็น public จึงไม่ต้องใช้ GitHub token หรือ SCM credential
เพื่อให้ Jenkins อ่าน repository สำหรับ `checkout scm`

## 2. Clone repository

บนเครื่อง host ให้เปิด terminal ไปยังโฟลเดอร์ที่ต้องการเก็บ source แล้ว clone
repository สาธารณะ:

```bash
git clone https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git
cd Pet-Clinic-Booking-and-Appointment-System
```

ใช้ working copy นี้สำหรับอ่าน/แก้ไขโค้ดหรือรันแอปด้วยตนเองในขั้นตอนต่อไป
Jenkins Pipeline จะ checkout commit จาก GitHub เอง และส่ง source revision นั้นไปยัง
`devtools`; ไม่จำเป็นต้อง clone ซ้ำบน `devtools` สำหรับการ deploy อัตโนมัติ

### Jenkins plugins

ติดตั้งจาก **Manage Jenkins → Plugins**:

| Plugin | หน้าที่ |
|---|---|
| Pipeline | รัน Jenkinsfile |
| Git | Checkout source |
| GitHub | รองรับ `githubPush()` และ GitHub webhook |
| Credentials Binding | ส่ง credentials ให้ pipeline |
| SSH Agent | ใช้ SSH private-key credential |

SSH Agent plugin ไม่ได้ติดตั้งคำสั่ง `ssh` ให้ Jenkins agent เอง

## 3. เริ่ม Jenkins และ devtools

รันจาก terminal บนเครื่อง host หนึ่งครั้ง หาก network มีอยู่แล้วให้ข้ามคำสั่งสร้าง network:

```bash
docker network create cicd-net
docker run -dit --name devtools --privileged -p 127.0.0.1:2222:22 -p 80:80 -p 9090:9090 -p 3000:3000 --network cicd-net --tmpfs /run --restart unless-stopped tuchsanai/devtools:2569_1
docker run -d --name jenkins --network cicd-net --restart unless-stopped -p 127.0.0.1:8080:8080 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts-jdk21
docker ps
```

image `tuchsanai/devtools:2569_1` รัน Docker-in-Docker (`dockerd`) และต้องใช้
`--privileged` เพื่อให้ daemon ตั้งค่า iptables/network ได้ ค่านี้ให้สิทธิ์สูงมาก
และเพิ่มความเสี่ยงต่อ Docker host; ใช้เฉพาะเครื่อง demo ที่เชื่อถือได้และอย่าเปิด
container นี้ให้ผู้ใช้ที่ไม่เชื่อถือ หาก containers มีอยู่แล้ว `docker start` จะไม่
เปลี่ยน privilege ของ container ที่สร้างไปแล้ว ต้อง recreate `devtools` ด้วย flag นี้
ก่อน pipeline ใช้งาน Docker ได้

ถ้า `devtools` เดิมถูกสร้างโดยไม่มี `--privileged` ให้ recreate; Docker ไม่สามารถ
เพิ่ม privilege ให้ container เดิมภายหลังได้ ตัวอย่างนี้เก็บ container เดิมไว้ชั่วคราว
และนำ volume ของ `/var/lib/docker` มาใช้ซ้ำ:

```bash
docker stop devtools
docker rename devtools devtools-old
docker run -dit --name devtools --privileged --volumes-from devtools-old -p 127.0.0.1:2222:22 -p 80:80 -p 9090:9090 -p 3000:3000 --network cicd-net --tmpfs /run --restart unless-stopped tuchsanai/devtools:2569_1
docker exec devtools docker info
```

ติดตั้ง public SSH key ใน `/root/.ssh/authorized_keys` ของ container ใหม่อีกครั้ง
เพราะไฟล์ใน root filesystem ไม่ได้ถูกย้ายตาม `--volumes-from`; Jenkins จะ sync source
กลับมาใน build ถัดไป และยืนยัน SSH host key ใหม่ผ่านช่องทางที่เชื่อถือได้ก่อนอัปเดต
`known_hosts` ของ Jenkins เพราะ SSH host keys อาจเปลี่ยนเมื่อสร้าง container ใหม่
คำสั่ง `docker info` ต้องแสดงข้อมูล `Server` โดยไม่มี error เชื่อมต่อ daemon
อย่าลบ `devtools-old` หรือ volume เดิมจนกว่าจะตรวจสอบ container ใหม่และ pipeline ผ่านแล้ว
การ bind Jenkins ที่ `127.0.0.1:8080` จำกัดการเข้าถึงผ่าน host port ไว้ในเครื่องนี้
ส่วน ngrok จะเชื่อม Jenkins ผ่าน `cicd-net` หากมี Jenkins container เก่าที่ publish
port 8080 ทุก interface การ `docker start` จะไม่เปลี่ยน port mapping; ให้ปิดช่องทาง
ภายนอกด้วย firewall หรือสร้าง container ใหม่โดยเก็บ volume `jenkins_home` ไว้

เปิด Jenkins ที่ <http://localhost:8080> และอ่าน initial admin password:

```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

ทำตามหน้า setup, สร้าง Jenkins admin และติดตั้ง plugins ตามหัวข้อก่อนหน้า
ต้องตรวจว่า SSH server ทำงานอยู่ที่ port 22 ภายใน `devtools`; คำสั่งเริ่ม SSH
ขึ้นกับการตั้งค่าของ image จึงให้ตรวจเอกสาร/การตั้งค่าของ image นี้

### การ clone source ใน devtools

เปิด shell เป็น root แล้ว clone repository ตามตัวอย่าง:

```bash
docker exec -it --user root devtools sh
```

```sh
git clone https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git /root/Pet-Clinic-Booking-and-Appointment-System
```

Pipeline จะส่ง source revision ที่ checkout จาก Jenkins ไปยัง
`/root/Pet-Clinic-Booking-and-Appointment-System` ทุก build ดังนั้นการ clone นี้
มีประโยชน์สำหรับเตรียม/ทดลองใช้งานด้วยตนเอง ไม่ใช่แหล่ง source หลักที่ pipeline deploy

### พอร์ตและการเข้าถึง

| Port | การเข้าถึงตัวอย่าง | บริการ |
|---:|---|---|
| 8080 | Host: `http://localhost:8080` | Jenkins |
| 2222 | Host: `localhost:2222` | SSH ของ `devtools` ที่ map จาก port 22 |
| 22 | Docker network: `devtools:22` | SSH ที่ Jenkins ใช้เชื่อม `devtools` |
| 80 | Host: `http://localhost` | แอปผ่าน Nginx เมื่อ Docker networking publish ถึง host |
| 3000 | Host: `http://localhost:3000` | Grafana เมื่อ publish ถึง host |
| 9090 | Host: `http://localhost:9090` | Prometheus เมื่อ publish ถึง host |

การ map port 80/3000/9090 ให้ container ชั้นนอก `devtools` **ไม่รับประกัน**
ว่าพอร์ตของ services ที่รันจาก Docker daemon ซ้อนอยู่ภายในจะเข้าถึงได้จาก host
ตรวจสอบว่า Compose ใช้ Docker daemon/network ที่ตั้งใจ และกำหนด port forwarding
สำหรับเส้นทางจริงก่อนใช้งาน

## 4. สร้าง SSH key สำหรับ Jenkins

สร้าง key บนเครื่องที่เชื่อถือได้ ไม่สร้างไว้ใน repository หรือ container ที่อาจถูกลบ
ใช้โปรแกรมสร้าง SSH key ที่เชื่อถือได้บนเครื่อง host แล้วเลือกชนิด key เป็น Ed25519
ตั้งชื่อไฟล์ `jenkins_devtools` และบันทึกไว้นอก repository ในโฟลเดอร์ SSH
ของผู้ใช้บนเครื่องนั้น ตั้ง passphrase เมื่อระบบถาม

ตั้ง passphrase เมื่อระบบถาม แล้วเก็บให้ปลอดภัย:

- `jenkins_devtools` คือ private key สำหรับ Jenkins เท่านั้น ห้าม copy ไป `devtools`
  หรือ commit ลง Git
- `jenkins_devtools.pub` คือ public key ที่นำไปติดตั้งใน `devtools`

เปิดไฟล์ public key (`jenkins_devtools.pub`) ด้วย text editor แล้วคัดลอกทั้งบรรทัด
จากนั้นเปิด shell ใน `devtools` เป็น root, สร้าง `/root/.ssh` หากยังไม่มี,
ตั้ง permission ของ directory เป็น `700`, วาง public key เป็นหนึ่งบรรทัดใหม่ท้ายไฟล์
`/root/.ssh/authorized_keys` แล้วตั้ง permission ของไฟล์เป็น `600`
ตรวจให้แน่ใจว่าไม่ได้คัดลอก private key (`jenkins_devtools`) ไปไว้ใน container

SSH server ต้องอนุญาต root public-key login (เช่น `PermitRootLogin prohibit-password`
ตามเวอร์ชัน OpenSSH) และไม่เปิด root password login ตรวจสอบ config ก่อน reload/restart SSH
เมื่อ recreate `devtools` ที่ไม่มี root home volume ต้องติดตั้ง public key ใหม่

### เพิ่ม private key ใน Jenkins

1. เปิด **Manage Jenkins → Credentials** แล้วเลือก scope ที่ job ใช้งานได้
2. เลือก **Add Credentials → SSH Username with private key**
3. ตั้ง username เป็น `root`
4. เลือก **Enter directly** แล้ววางเนื้อหาจากไฟล์ `jenkins_devtools`
5. กรอก passphrase หากตั้งไว้
6. ตั้ง Credential ID เป็น `devtools-ssh`
7. จำกัดสิทธิ์การใช้งาน credential ให้เฉพาะ job ที่จำเป็น

ห้ามบันทึก private key หรือ passphrase ใน Jenkinsfile, command line, repository
หรือ console log

### ตรวจสอบ SSH host key

Pipeline ใช้ `StrictHostKeyChecking=yes` จึงต้องติดตั้ง host key ที่ยืนยันแล้ว
ของ `devtools` ใน `known_hosts` ของ Jenkins agent ก่อน
ให้ยืนยัน fingerprint ผ่านช่องทางที่เชื่อถือได้ก่อนเพิ่ม key; อย่าเชื่อถือผล
`ssh-keyscan` เพียงอย่างเดียว และอย่าปิด host-key checking

ใน Docker network Jenkins ต้องเชื่อมไป `root@devtools` port 22 ไม่ใช่
`localhost:2222` (port 2222 ใช้สำหรับการเชื่อมจาก host เท่านั้น)

## 5. เพิ่ม Jenkins credentials

ไปที่ **Manage Jenkins → Credentials** แล้วเพิ่ม credentials ตาม ID ที่ Pipeline
และการตั้งค่า GitHub webhook ใช้:

| Credential ID | ประเภท | ค่า/การใช้งาน |
|---|---|---|
| `petcare-jwt-secret` | Secret text | secret สำหรับลงนาม JWT ใน CI |
| `petcare-postgres-password` | Secret text | รหัสผ่าน PostgreSQL; ใช้เฉพาะ `A-Z`, `a-z`, ตัวเลข, `.`, `_`, `~`, `-` |
| `petcare-grafana-password` | Secret text | รหัสผ่าน Grafana admin ใน CI |
| `dockerhub` | Username with password | Docker Hub username และ access token ในช่อง password |
| `devtools-ssh` | SSH Username with private key | `root` และ private key ที่สร้างในขั้นตอนก่อนหน้า |
| `github-webhook-secret` | Secret text | shared secret สำหรับตรวจสอบ GitHub webhook; ตั้งค่าซ้ำใน GitHub plugin และ GitHub repository |

รหัสผ่าน PostgreSQL ถูกฝังตรงใน database URL ของ Compose จึงต้องใช้ตัวอักษร
URL-safe ตามรายการด้านบน มิฉะนั้น pipeline จะหยุดพร้อม error

เนื่องจาก repository เป็น public จึงไม่ต้องใช้ GitHub token หรือ SCM credential
เพื่อให้ Jenkins อ่าน repository สำหรับ `checkout scm`

## 6. สร้าง Jenkins Pipeline job

1. เลือก **New Item** แล้วเลือกชนิด **Pipeline**
2. ใน **Pipeline → Definition** เลือก **Pipeline script from SCM**
3. เลือก Git และกรอก URL ของ public repository:
   `https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git`
4. กำหนด branch ที่ต้องการให้ deploy; repository สาธารณะนี้ไม่ต้องใส่ SCM credential
5. ตั้ง **Script Path** เป็น `Jenkinsfile`
6. เปิด **GitHub hook trigger for GITScm polling**
7. บันทึก แล้วตรวจว่า job เข้าถึง credentials ที่ Pipeline ใช้ได้
8. ตรวจว่า Jenkins agent มี `git`, `tar`, `ssh` และ `known_hosts` ที่ยืนยันแล้ว

สามารถใช้ Multibranch Pipeline ได้ แต่ต้องตั้ง branch discovery ให้เหมาะสมกับ branch
ที่อนุญาต deploy

## 7. เปิด Jenkins localhost ด้วย ngrok

GitHub เข้าถึง `localhost:8080` บนเครื่องของเราไม่ได้ จึงต้องเปิด HTTPS tunnel
จาก ngrok ไปยัง Jenkins container ผ่าน Docker network `cicd-net`

1. สมัคร/เข้าสู่ระบบ ngrok แล้วคัดลอก **authtoken** จาก dashboard
   และ dev domain ที่บัญชีจัดสรรให้ เก็บ authtoken เป็นความลับ
2. สร้างโฟลเดอร์ `ngrok` บน host นอก repository หรือเพิ่ม `ngrok/` ใน `.gitignore`
   แล้วสร้างไฟล์ `traffic-policy.yml` ภายในด้วยเนื้อหานี้:

   ```yaml
   on_http_request:
     - name: allow-github-webhook-only
       expressions:
         - "!(req.method == 'POST' && req.url.path == '/github-webhook/')"
       actions:
         - type: custom-response
           config:
             status_code: 403
             body: "Forbidden"
   ```

   Policy นี้อนุญาตเฉพาะ `POST /github-webhook/` และตอบ `403` สำหรับ path/method
   อื่นก่อน request จะถึง Jenkins เป็นชั้นป้องกันเพิ่มเติม ไม่ใช่การทดแทน webhook secret
3. ตั้ง authtoken ใน environment ของ terminal หรือ secret manager โดยไม่ใส่ค่า token
   ลงใน command history แล้วรัน ngrok container จาก host หนึ่งบรรทัด
   แทน `YOUR_NGROK_DOMAIN` ด้วย domain จาก ngrok และ
   `ABSOLUTE_PATH_TO_NGROK_DIR` ด้วย path เต็มของโฟลเดอร์ที่มี `traffic-policy.yml`:

   ```bash
   docker run -d --name ngrok --network cicd-net --restart unless-stopped -p 127.0.0.1:4040:4040 -e NGROK_AUTHTOKEN --mount type=bind,source=ABSOLUTE_PATH_TO_NGROK_DIR,target=/etc/ngrok,readonly ngrok/ngrok:latest http http://jenkins:8080 --url https://YOUR_NGROK_DOMAIN --traffic-policy-file /etc/ngrok/traffic-policy.yml --log stdout
   ```

   คำสั่งนี้อาศัย environment variable `NGROK_AUTHTOKEN` ที่ตั้งไว้ใน terminal
   และ mount policy แบบ read-only; ห้ามแทนค่าตัวแปรด้วย authtoken จริงใน command
   Docker จะเก็บ environment ของ container ไว้ใน metadata; จำกัดผู้ที่เข้าถึง Docker
   daemon ได้ Port `4040` ถูกผูกกับ loopback ของ host เพื่อให้ตรวจสถานะได้เฉพาะในเครื่อง
4. ตรวจว่า container ทำงานและไม่มี error:

   ```bash
   docker ps --filter name=ngrok
   docker logs --tail=50 ngrok
   ```

   เปิด <http://localhost:4040> เพื่อตรวจว่า endpoint online และมี Traffic Policy
   ทำงานอยู่ หาก hostname เปลี่ยนหลังเริ่ม tunnel ใหม่ ให้อัปเดต GitHub webhook URL
   ตาม domain ที่ใช้งานจริงและเลือกใช้ ngrok domain แบบคงที่ถ้าบัญชีรองรับ
   การเปิด domain เปล่าด้วย browser เป็น `GET` และได้ `403` ถือว่าถูกต้องตาม policy;
   ใช้ GitHub webhook delivery เพื่อตรวจสอบ request จริง
5. คง ngrok container ให้ทำงานขณะใช้ webhook เมื่อเลิกใช้งานให้หยุด tunnel:

   ```bash
   docker stop ngrok
   ```

> **ความปลอดภัย:** HTTPS URL นี้เปิด endpoint เข้าจากอินเทอร์เน็ต แม้ Traffic Policy
> จะกัน path อื่นก็ตาม ให้เปลี่ยนรหัสผ่าน Jenkins เริ่มต้น, เปิดใช้ Jenkins authentication,
> ตั้ง webhook shared secret ตามขั้นตอนถัดไป และอย่าเปิด Jenkins แบบ anonymous

## 8. ตั้ง GitHub push webhook และ shared secret

Jenkins ต้องรับ webhook ผ่าน ngrok domain ที่ GitHub มองเห็น ไม่ใช้ `localhost`
หรือ Docker-only address

ก่อนตั้ง webhook ให้ตั้ง Jenkins URL ใน **Manage Jenkins → System** เป็น
`https://YOUR_NGROK_DOMAIN/` เพื่อให้ลิงก์ที่ Jenkins แสดงใช้ HTTPS domain นี้

1. สร้างค่า secret แบบสุ่มที่คาดเดายากด้วย password manager หรือเครื่องมือสร้าง
   secret ที่เชื่อถือได้ แล้วบันทึกไว้อย่างปลอดภัยเพื่อนำไปใส่ทั้งใน Jenkins และ GitHub
2. ใน Jenkins ไปที่ **Manage Jenkins → Credentials** แล้วสร้าง credential:
   - Kind: **Secret text**
   - Secret: ค่า secret ที่สร้างไว้
   - ID: `github-webhook-secret`
   - Description: `GitHub webhook shared secret`
3. ไปที่ **Manage Jenkins → System → GitHub → Advanced → Add shared secret**
   เลือก credential `github-webhook-secret` เป็น Shared secret และคงอัลกอริทึม
   SHA-256 จากนั้นบันทึก การใส่ secret เฉพาะใน GitHub โดยไม่ตั้งค่านี้ใน Jenkins
   ไม่ได้ทำให้ Jenkins ตรวจสอบลายเซ็น
4. เปิด GitHub repository → **Settings → Webhooks → Add webhook**
5. ตั้ง Payload URL เป็น `https://YOUR_NGROK_DOMAIN/github-webhook/`
   โดยต้องมี `/` ปิดท้าย
6. เลือก Content type `application/json`, ใส่ secret ค่าเดียวกับ Jenkins,
   เปิด SSL verification และเลือก **Just the push event**
7. บันทึก webhook; GitHub จะส่ง ping ให้ ตรวจผลที่ **Recent Deliveries**
8. ใน Jenkins job เปิด **GitHub hook trigger for GITScm polling**
   หากจำเป็นตาม job type/plugin version

`githubPush()` ใน Jenkinsfile เปิด trigger สำหรับ push แล้ว แต่ webhook ต้องส่งถึง
Jenkins ได้จริงด้วย Public repository ทำให้ Jenkins อ่าน source ผ่าน anonymous
HTTPS checkout ได้โดยไม่ต้องใช้ GitHub token; webhook secret ใช้ตรวจลายเซ็นของ
webhook แยกจากสิทธิ์อ่าน repository

## 9. ขั้นตอนทำงานของ CI/CD

เมื่อมี push ไปยัง branch ที่ job เฝ้าดู Jenkins จะ:

1. Checkout source และหา 12 ตัวอักษรแรกของ commit เพื่อใช้เป็น image tag
2. สร้าง environment files ชั่วคราวจาก Jenkins credentials
3. SSH ไปยัง `devtools` และส่ง source ไปยัง directory ที่กำหนด
4. Build images และเริ่ม PostgreSQL สำหรับตรวจสอบ
5. รัน Ruff, mypy, Alembic migration, pytest และ Gitleaks
6. หากผ่านทั้งหมด ให้ login Docker Hub โดยใช้ `--password-stdin` และ push images
7. Pull images ที่เผยแพร่แล้วและ deploy ด้วย `docker compose up -d --no-build`
8. Seed ข้อมูลตัวอย่างและรัน post-deployment checks:
   readiness, load balancing, login/availability และ Prometheus targets
9. ลบไฟล์ environment ชั่วคราวและ Docker Hub auth directory; runtime `.env`
   บน `devtools` คงอยู่เพื่อให้ Compose ใช้งาน

ชื่อ image tags ที่คาดว่าจะเห็นใน Docker Hub:

- `<dockerhub-user>/petcare-backend:<12-character-commit>`
- `<dockerhub-user>/petcare-backend:build-<build-number>`
- `<dockerhub-user>/petcare-nginx:<12-character-commit>`
- `<dockerhub-user>/petcare-nginx:build-<build-number>`

## 10. ทดสอบการทำงานและใช้งานแอป

### ทดสอบ CI/CD

1. Push commit ไปยัง branch ที่ตั้งใน Jenkins job
2. ตรวจ GitHub webhook **Recent Deliveries** ว่าส่งสำเร็จ
3. เปิด Jenkins build → **Console Output** แล้วตรวจ stages:
   `Checkout`, `Connect and Sync to devtools`, `Build & Verify`,
   `Publish to Docker Hub`, `Deploy`, `Post-Deployment Verification`
4. ตรวจ Docker Hub ว่ามีทั้ง commit tag และ `build-<number>` tag
5. ตรวจ Compose services ที่ `devtools` และทดสอบ URL ที่เปิดจาก host ได้

### รันแอปด้วยตนเอง (โดยไม่รอ pipeline)

จาก root ของ repository บนเครื่องที่ใช้ Docker Compose:

สร้างสำเนาของ `.env.example` ชื่อ `.env` ด้วย file manager หรือเครื่องมือจัดการไฟล์
ที่ใช้อยู่ จากนั้นแก้ไข `.env` ตามคำแนะนำด้านล่าง

แก้ `.env` ให้กำหนด `POSTGRES_PASSWORD`, `JWT_SECRET` และ `GRAFANA_ADMIN_PASSWORD`
เป็นค่าไม่ซ้ำและเหมาะกับสภาพแวดล้อม ห้าม commit `.env` จากนั้นสั่ง:

```bash
docker compose up -d --build
docker compose ps
```

Compose จะรัน migration ก่อน backend พร้อมให้บริการ ตรวจ URL เหล่านี้เมื่อ port
ถูก publish ถึงเครื่องที่ใช้:

| URL | จุดประสงค์ |
|---|---|
| `http://localhost/api/v1/health/live` | ตรวจ liveness |
| `http://localhost/api/v1/health/ready` | ตรวจ readiness และ PostgreSQL |
| `http://localhost:3000` | Grafana |
| `http://localhost:9090` | Prometheus |

ข้อมูลเข้าใช้งานตัวอย่างมีให้หลัง seed:

```bash
docker compose run --rm web1 python -m scripts.seed
```

บัญชีตัวอย่าง: `owner1@petcare.local`, `vet1@petcare.local`,
`staff@petcare.local`; รหัสผ่านเริ่มต้นคือ `Petcare123!` ใช้เฉพาะ demo/test
และเปลี่ยนหรือลบข้อมูลตัวอย่างก่อนเปิดใช้งานจริง

ดูสถานะและ logs:

```bash
docker compose ps
docker compose logs --tail=100
docker compose logs --tail=100 web1 web2 worker nginx
```

หยุด services โดยเก็บ named volumes:

```bash
docker compose down
```

อย่าใช้ `docker compose down -v` เว้นแต่ตั้งใจลบข้อมูลใน volumes รวมถึงข้อมูล PostgreSQL

### พอร์ตใช้งานใน Compose

Compose กำหนด port `80` สำหรับ Nginx, `3000` สำหรับ Grafana และ `9090` สำหรับ
Prometheus ส่วน PostgreSQL และ backend ไม่ได้ publish port ออกสู่ host โดยตรง
การเข้าถึงจาก host ยังขึ้นกับ Docker daemon/network ที่ Compose ใช้
โดยเฉพาะเมื่อรัน Compose ภายใน `devtools` ที่มี Docker daemon ซ้อนอยู่

## 11. แก้ปัญหา

| อาการ | วิธีตรวจสอบ |
|---|---|
| Jenkins ไม่เริ่ม build หลัง push | ตรวจ GitHub webhook Recent Deliveries, HTTPS URL, GitHub plugin, job trigger และ branch |
| GitHub delivery ล้มเหลวหรือ ngrok endpoint offline | ตรวจ `docker ps` และ `docker logs ngrok`, authtoken, domain, network `cicd-net` และสถานะ Jenkins |
| ngrok ส่ง `403` สำหรับ webhook | ตรวจ path `/github-webhook/` และ slash ปิดท้าย รวมถึง method `POST` ให้ตรง Traffic Policy |
| GitHub webhook แจ้ง signature/secret ผิด | ตรวจว่า Jenkins credential `github-webhook-secret`, GitHub plugin Shared secret และ GitHub webhook ใช้ secret เดียวกัน |
| `Could not resolve hostname devtools` หรือ SSH timeout | ให้ Jenkins agent และ `devtools` อยู่บน network เดียวกัน; ตรวจชื่อ DNS และ SSH port 22 |
| `Host key verification failed` | ติดตั้ง host key ที่ยืนยัน fingerprint แล้วใน `known_hosts` ของ Jenkins agent |
| `Permission denied (publickey)` | ตรวจ `devtools-ssh`, username `root`, passphrase, SSH server config และ permissions `authorized_keys` |
| หา initial admin password ไม่เจอ | ตรวจว่า Jenkins เริ่มทำงานและ volume `jenkins_home` ถูกต้อง; อ่านไฟล์ด้วยคำสั่งในขั้นตอนเริ่ม Jenkins |
| Docker/Compose ใช้งานไม่ได้ใน `devtools` | ตรวจ Docker daemon, สิทธิ์ root และ Compose v2.30+ |
| Docker Hub push ไม่ผ่าน | ตรวจ ID `dockerhub`, token permissions และชื่อ repositories |
| Pipeline ปฏิเสธ PostgreSQL password | เปลี่ยน credential ให้ใช้เฉพาะ URL-safe characters ตามรายการในหัวข้อ credentials |
| Jenkins build ผ่านแต่เข้าแอปจาก host ไม่ได้ | ตรวจ port publishing และ Docker networking ของ daemon ที่ Compose ใช้; port ของ container ชั้นนอกอาจไม่ forward nested containers |
| Post-deployment verification ล้มเหลว | ตรวจ `docker compose ps` และ logs ของ `web1`, `web2`, `worker`, `nginx`; ตรวจ health endpoint และ Prometheus targets |
| SSH key หายหลัง recreate `devtools` | ติดตั้ง public key ใน `/root/.ssh/authorized_keys` ใหม่ หรือจัด persistent/provisioned storage อย่างปลอดภัย |

คำสั่งตรวจสอบ containers บน host:

```bash
docker ps
docker logs --tail=100 jenkins
docker logs --tail=100 devtools
```

เมื่อ `POST /github-webhook/` ได้ HTTP `400` จาก request ทดสอบทั่วไปที่ไม่มี
GitHub event headers อาจแปลว่า tunnel และ route ถึง Jenkins แล้ว ใช้หน้า GitHub
**Recent Deliveries** ตรวจผลจริง อย่าถือ `400` เพียงอย่างเดียวว่า webhook ทำงานครบ

คำสั่งตรวจสอบ Compose ให้รันใน shell ของ `devtools` ที่ root:

```sh
cd /root/Pet-Clinic-Booking-and-Appointment-System && docker compose ps
```

ดูรายละเอียด recovery เพิ่มเติมใน [runbook](runbook.md)

## 12. Checklist ก่อนใช้งานจริง

- [ ] ngrok tunnel ชี้ไปยัง Jenkins ที่ถูกต้อง และเปิดเฉพาะ webhook path ผ่าน Traffic Policy
- [ ] Jenkins ใช้ authentication ที่ปลอดภัยและไม่มี anonymous access
- [ ] GitHub webhook ส่งถึง Jenkins ได้ และ branch ที่ deploy ถูกต้อง
- [ ] Webhook shared secret ตั้งตรงกันทั้ง Jenkins GitHub plugin และ GitHub
- [ ] Jenkins credentials มี ID ถูกต้องและจำกัด scope
- [ ] GitHub repository ใช้ public read access โดยไม่ต้องเก็บ GitHub token ใน Jenkins
- [ ] `devtools-ssh` ใช้ key เฉพาะ; root password login ปิดอยู่
- [ ] SSH host key ได้รับการยืนยัน ไม่ได้ปิด StrictHostKeyChecking
- [ ] Docker Hub token มีสิทธิ์เท่าที่จำเป็นและ repositories ถูกต้อง
- [ ] secrets ไม่อยู่ใน Git, console output หรือไฟล์ที่ไม่จำเป็น
- [ ] มี backup ของข้อมูล PostgreSQL และแผน rollback ก่อน deployment
- [ ] ตรวจแล้วว่าพอร์ตของแอปเข้าถึงได้จาก host/network ตามต้องการ

## เอกสารที่เกี่ยวข้อง

- [Runbook](runbook.md)
- [คู่มือทดสอบด้วยตนเอง](manual-testing.md)
- [แผนภาพระบบ](diagrams.md)
