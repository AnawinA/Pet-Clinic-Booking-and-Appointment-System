# คู่มือใช้งานโปรเจกต์ Pet Clinic และระบบ CI/CD

คู่มือนี้อธิบายการ clone โปรเจกต์ การเริ่ม Jenkins และ `devtools` การตั้งค่า SSH และ GitHub webhook ผ่าน ngrok การรันแอปด้วย Docker Compose และการแก้ปัญหาเบื้องต้น

> **คำเตือนด้านความปลอดภัย:** ตัวอย่างนี้ให้ `devtools` ทำงานแบบ `--privileged` และให้ Jenkins เชื่อมต่อ SSH ด้วย `root` ซึ่งมีสิทธิ์สูงมาก ควรใช้เฉพาะเครื่อง demo ที่เชื่อถือได้ ปิด root password login และห้ามเปิด Jenkins, Docker daemon หรือ Jupyter ที่ไม่มีการยืนยันตัวตนสู่อินเทอร์เน็ต

## ภาพรวมการทำงาน

1. Clone repository public ลงในเครื่องที่ใช้พัฒนา
2. เริ่ม Jenkins และ `devtools` ให้อยู่บน Docker network เดียวกัน
3. ติดตั้ง SSH public key ใน `devtools` และเก็บ private key เป็น Jenkins credential
4. เพิ่ม Jenkins credentials ที่ pipeline ต้องใช้ และตั้ง SSH host-key verification
5. เปิด Jenkins ให้ GitHub ติดต่อได้ด้วย ngrok และสร้าง push webhook
6. Push commit เพื่อให้ Jenkins build, test, publish images และ deploy บน `devtools`

## 1. สิ่งที่ต้องเตรียม

### เครื่องและบริการ

- Docker Engine หรือ Docker Desktop ที่ใช้งาน `docker run` และ Docker Compose ได้
- Git และ terminal ที่ใช้ Docker CLI ได้บนเครื่อง host
- บัญชี ngrok พร้อม authtoken และ HTTPS dev domain
- Jenkins ที่รับ GitHub webhook ผ่าน HTTPS URL ของ ngrok ได้
- Docker Hub account ที่มี repositories `petcare-backend` และ `petcare-nginx` พร้อม access token ที่มีสิทธิ์ push
- Jenkins agent ที่รัน pipeline ต้องมี `git`, `tar` และ OpenSSH client (`ssh`)
- `devtools` image `tuchsanai/devtools:2569_1` มี SSH server, Docker Engine, Docker Compose, Bash, tar และ curl
- Jenkins agent และ `devtools` ต้องสื่อสารกันได้ผ่าน Docker network โดยใช้ชื่อ `devtools` และ SSH port 22

Repository นี้เป็น public จึงไม่ต้องใช้ GitHub token หรือ SCM credential เพื่อให้ Jenkins checkout source ผ่าน HTTPS

### Jenkins plugins

ติดตั้ง plugins เหล่านี้จาก **Manage Jenkins → Plugins**:

| Plugin | หน้าที่ |
|---|---|
| Pipeline | รัน Jenkinsfile |
| Git | Checkout source จาก Git |
| GitHub | รองรับ trigger `githubPush()` และ GitHub webhook |
| Credentials Binding | ส่ง credentials ให้ pipeline |
| SSH Agent | ใช้ SSH private-key credential |

SSH Agent plugin ไม่ได้ติดตั้งคำสั่ง OpenSSH client (`ssh`) ให้ Jenkins agent เอง จึงต้องตรวจว่ามี executable นี้ใน agent ที่รันงาน

## 2. Clone repository

บน host เปิด terminal ในตำแหน่งที่ต้องการเก็บ source แล้ว clone repository:

```bash
git clone https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git
cd Pet-Clinic-Booking-and-Appointment-System
```

ใช้ working copy นี้สำหรับอ่านหรือแก้ไขโค้ดและรันแอปด้วยตนเอง ส่วน Jenkins จะ checkout commit จาก GitHub เองและส่ง source revision นั้นไปยัง `devtools` ทุก build

## 3. เริ่ม Jenkins และ devtools

รันคำสั่งต่อไปนี้จาก terminal บน host โดยสร้าง network เพียงครั้งเดียว:

```bash
docker network create cicd-net
docker run -dit --name devtools --privileged -p 127.0.0.1:2222:22 -p 80:80 -p 9090:9090 -p 3000:3000 --network cicd-net --tmpfs /run --restart unless-stopped tuchsanai/devtools:2569_1
docker run -d --name jenkins --network cicd-net --restart unless-stopped -p 127.0.0.1:8080:8080 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts-jdk21
docker ps
```

หากมี network `cicd-net` อยู่แล้ว ให้ข้าม `docker network create cicd-net`; หาก containers มีอยู่แล้วให้ตรวจ configuration ก่อนใช้ `docker start` เพราะการ start ไม่สามารถเปลี่ยน port mapping หรือเพิ่ม `--privileged` ให้ container เดิมได้

Image `tuchsanai/devtools:2569_1` เริ่ม Docker-in-Docker (`dockerd`) และต้องใช้ `--privileged` เพื่อให้ daemon ตั้งค่า iptables และ networking ได้ ตัวเลือกนี้ให้สิทธิ์สูงมากและเพิ่มความเสี่ยงต่อ Docker host จึงควรใช้เฉพาะสภาพแวดล้อม demo ที่เชื่อถือได้

เปิด Jenkins ที่ <http://localhost:8080> และอ่าน initial admin password:

```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

ทำตามหน้า Jenkins setup เพื่อสร้างผู้ดูแลระบบและติดตั้ง plugins ที่ระบุไว้ในหัวข้อก่อนหน้า

### การ clone source ใน devtools (ทางเลือก)

Pipeline sync source จาก Jenkins ไปยัง `/root/Pet-Clinic-Booking-and-Appointment-System` ทุก build อยู่แล้ว การ clone บน `devtools` จึงจำเป็นเฉพาะเมื่อต้องการทดลองหรือดู source ด้วยตนเอง:

```bash
docker exec -it --user root devtools sh
```

ภายใน shell ของ `devtools`:

```sh
git clone https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git /root/Pet-Clinic-Booking-and-Appointment-System
```

### พอร์ตที่ใช้

| Port | การเข้าถึงตัวอย่าง | บริการ |
|---:|---|---|
| 8080 | Host: `http://localhost:8080` | Jenkins; bind เฉพาะ host loopback |
| 2222 | Host: `localhost:2222` | SSH port 22 ของ `devtools` |
| 22 | Docker network: `devtools:22` | SSH จาก Jenkins ไป `devtools` |
| 80 | Host: `http://localhost` | แอปผ่าน Nginx เมื่อ Docker networking ส่ง port ถึง host |
| 3000 | Host: `http://localhost:3000` | Grafana เมื่อ port ถูก publish ถึง host |
| 9090 | Host: `http://localhost:9090` | Prometheus เมื่อ port ถูก publish ถึง host |
| 4040 | Host: `http://localhost:4040` | ngrok local status UI; bind เฉพาะ loopback |

การ publish port 80, 3000 หรือ 9090 ที่ container `devtools` ชั้นนอกไม่ได้รับประกันว่าจะ publish port ของ services จาก Docker daemon ซ้อนอยู่ภายใน ตรวจสอบ Docker daemon/network ที่ Compose ใช้และตั้ง port forwarding ให้ตรงกับเส้นทางจริง

## 4. ตั้งค่า SSH key สำหรับ Jenkins

สร้าง SSH key บนเครื่อง host ที่เชื่อถือได้ด้วยเครื่องมือสร้าง SSH key เลือกชนิด Ed25519 ตั้งชื่อไฟล์ `jenkins_devtools` และเก็บไว้นอก repository ในโฟลเดอร์ SSH ของผู้ใช้ ตั้ง passphrase เมื่อระบบถาม

- `jenkins_devtools` คือ private key สำหรับ Jenkins เท่านั้น ห้าม copy ไป `devtools` หรือ commit ลง Git
- `jenkins_devtools.pub` คือ public key ที่นำไปติดตั้งใน `devtools`

เปิดไฟล์ `jenkins_devtools.pub` ด้วย text editor แล้วคัดลอกทั้งบรรทัด จากนั้นเปิด shell ใน `devtools` เป็น root:

```bash
docker exec -it --user root devtools sh
```

ภายใน `devtools` สร้าง SSH directory ตั้ง permission แล้วเพิ่ม public key โดยแทน placeholder ด้วยเนื้อหาจริงทั้งบรรทัดจาก `jenkins_devtools.pub`:

```sh
install -d -m 700 /root/.ssh
printf '%s\n' 'PASTE_PUBLIC_KEY_LINE_HERE' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

หลีกเลี่ยงการเพิ่ม key ซ้ำใน `authorized_keys` และอย่าคัดลอก private key (`jenkins_devtools`) เข้า container

SSH server ของ `devtools` ต้องอนุญาต root public-key login เช่น `PermitRootLogin prohibit-password` ตามเวอร์ชัน OpenSSH และต้องไม่เปิด root password login ตรวจสอบ config ก่อน reload/restart SSH

### เพิ่ม private key ใน Jenkins

1. เปิด **Manage Jenkins → Credentials** แล้วเลือก scope ที่ job ใช้งานได้
2. เลือก **Add Credentials → SSH Username with private key**
3. ตั้ง username เป็น `root`
4. เลือก **Enter directly** แล้ววางเนื้อหาจากไฟล์ `jenkins_devtools`
5. กรอก passphrase หากตั้งไว้
6. ตั้ง Credential ID เป็น `devtools-ssh`
7. จำกัดสิทธิ์การใช้ credential ให้เฉพาะ job ที่จำเป็น

ห้ามบันทึก private key หรือ passphrase ใน Jenkinsfile, command line, repository หรือ console log

### ตรวจสอบและเพิ่ม SSH host key

Jenkinsfile ใช้ `StrictHostKeyChecking=yes` จึงต้องมี host key ที่เชื่อถือได้ของ `devtools` ใน `known_hosts` ที่ agent ผู้รัน pipeline ใช้ การเพิ่ม host key เป็นการยืนยันตัวตนของ server และแยกจาก `devtools-ssh` ซึ่งเป็น client private key ที่ใช้ยืนยันตัวตนของ Jenkins ต่อ server

จาก terminal บน host เปิด shell ภายใน Jenkins container:

```bash
docker exec -it --user jenkins jenkins sh
```

ภายใน Jenkins container ตรวจตำแหน่ง known-hosts files และหา entry ของ `devtools`:

```sh
ssh -G root@devtools | grep -i knownhostsfile
ssh-keygen -F devtools -f /var/jenkins_home/.ssh/known_hosts
ssh-keygen -F devtools -f /etc/ssh/ssh_known_hosts
exit
```

หาก `ssh-keygen -F` แสดง entry แปลว่าพบ host key ในไฟล์นั้น หากไม่พบให้ตรวจ `UserKnownHostsFile` และ `GlobalKnownHostsFile` จาก `ssh -G` แล้วตรวจ path ที่แสดง

หากยังไม่มี key ให้เปรียบเทียบ fingerprint กับค่าที่ได้จากช่องทางที่เชื่อถือได้ก่อน:

```bash
docker exec devtools ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

อย่าเชื่อถือผล `ssh-keyscan` เพียงอย่างเดียว หากไฟล์ Ed25519 ไม่มี ให้ตรวจว่ามี host key ชนิดใดอยู่ใน `/etc/ssh/` และใช้ public key ชนิดนั้นแทน

หลังยืนยัน fingerprint แล้ว แสดง public host key บน host:

```bash
docker exec devtools cat /etc/ssh/ssh_host_ed25519_key.pub
```

คัดลอก public key ทั้งบรรทัด เปิด Jenkins shell เป็น root แล้วเพิ่มบรรทัด `devtools <public-key>` ลงใน `known_hosts` โดยแทน placeholder ด้วย public key จริง:

```bash
docker exec -it --user root jenkins sh
```

ภายใน Jenkins container:

```sh
install -d -m 700 -o jenkins -g jenkins /var/jenkins_home/.ssh
printf '%s\n' 'devtools PASTE_PUBLIC_KEY_LINE_HERE' >> /var/jenkins_home/.ssh/known_hosts
chown jenkins:jenkins /var/jenkins_home/.ssh /var/jenkins_home/.ssh/known_hosts
chmod 700 /var/jenkins_home/.ssh
chmod 600 /var/jenkins_home/.ssh/known_hosts
```

ออกจาก shell แล้วตรวจ entry จาก terminal บน host:

```bash
docker exec --user jenkins jenkins ssh-keygen -F devtools -f /var/jenkins_home/.ssh/known_hosts
```

หาก Jenkins ใช้ agent แยกจาก controller ให้ติดตั้ง key ใน agent ที่รัน job แทน container `jenkins` หากสร้าง `devtools` ใหม่และ host key เปลี่ยน ให้ยืนยัน fingerprint ใหม่ ลบ entry เก่า (`ssh-keygen -R devtools -f /var/jenkins_home/.ssh/known_hosts`) แล้วเพิ่ม public key ใหม่

จาก Docker network Jenkins ต้องเชื่อม `root@devtools` ที่ port 22 ไม่ใช่ `localhost:2222`; port 2222 ใช้สำหรับเชื่อมจาก host เท่านั้น

## 5. เพิ่ม Jenkins credentials

ไปที่ **Manage Jenkins → Credentials** แล้วเพิ่ม credentials ตาม ID ที่ pipeline หรือ GitHub webhook ใช้:

| Credential ID | ประเภท | ค่าและการใช้งาน |
|---|---|---|
| `petcare-jwt-secret` | Secret text | Secret สำหรับลงนาม JWT ใน CI |
| `petcare-postgres-password` | Secret text | PostgreSQL password; ใช้เฉพาะ `A-Z`, `a-z`, ตัวเลข, `.`, `_`, `~`, `-` |
| `petcare-grafana-password` | Secret text | Grafana admin password ใน CI |
| `dockerhub` | Username with password | Docker Hub username และ access token ในช่อง password |
| `devtools-ssh` | SSH Username with private key | Username `root` และ private key สำหรับ SSH เข้า `devtools` |
| `github-webhook-secret` | Secret text | Shared secret ที่ตั้งซ้ำใน Jenkins GitHub plugin และ GitHub webhook |

`POSTGRES_PASSWORD` ถูกฝังตรงใน database URL ของ Compose จึงต้องใช้เฉพาะตัวอักษร URL-safe ตามที่ระบุ มิฉะนั้น pipeline จะหยุดพร้อม error

Repository เป็น public จึงไม่ต้องใช้ GitHub token หรือ SCM credential สำหรับ `checkout scm` ใช้ Docker Hub access token แทนรหัสผ่านบัญชี และอย่าใส่ secrets ลงใน Jenkinsfile

## 6. สร้าง Jenkins Pipeline job

1. เลือก **New Item** แล้วสร้าง job ชนิด **Pipeline**
2. ใน **Pipeline → Definition** เลือก **Pipeline script from SCM**
3. เลือก Git และกรอก repository URL `https://github.com/AnawinA/Pet-Clinic-Booking-and-Appointment-System.git`
4. กำหนด branch ที่ต้องการให้ deploy; repository สาธารณะนี้ไม่ต้องใส่ SCM credential
5. ตั้ง **Script Path** เป็น `Jenkinsfile`
6. เปิด **GitHub hook trigger for GITScm polling** หากจำเป็นตาม job type/plugin version
7. บันทึก แล้วตรวจว่า job เข้าถึง Jenkins credentials ที่ pipeline ใช้ได้
8. ตรวจว่า Jenkins agent มี `git`, `tar`, `ssh` และ host key ที่ยืนยันแล้วใน `known_hosts`

## 7. เปิด Jenkins localhost ด้วย ngrok

GitHub เข้าถึง `localhost:8080` บนเครื่องเราไม่ได้ จึงต้องเปิด HTTPS tunnel จาก ngrok ไปยัง Jenkins container ผ่าน Docker network `cicd-net`

1. สมัครหรือเข้าสู่ระบบ ngrok แล้วคัดลอก authtoken จาก dashboard และ dev domain ที่บัญชีจัดสรรให้ เก็บ authtoken เป็นความลับ
2. ใช้ไฟล์ `./ngrok/traffic-policy.yml` ใน repository:

   ตรวจให้แน่ใจว่าไฟล์มี Traffic Policy ที่อนุญาตเฉพาะ `POST /github-webhook/` และตอบ `403` สำหรับ path หรือ method อื่นก่อน request จะถึง Jenkins เป็นชั้นป้องกันเพิ่มเติม ไม่ใช่สิ่งทดแทน webhook secret หรือ Jenkins authentication

### ตั้ง NGROK_AUTHTOKEN และเริ่ม ngrok

รันคำสั่งจาก repository root และกำหนด `NGROK_DOMAIN` เป็น dev domain ของบัญชี ngrok คำสั่งจะ mount ไฟล์ policy จาก `./ngrok/traffic-policy.yml` และรับ token แบบไม่แสดงค่าที่พิมพ์หรือใส่ token ตรง ๆ ใน command history

**Windows PowerShell** :

```powershell
$NGROK_DOMAIN = Read-Host "ngrok dev domain (e.g. example.ngrok.app)"; $policyPath = (Resolve-Path .\ngrok\traffic-policy.yml).Path; $secure = Read-Host "ngrok authtoken" -AsSecureString; $env:NGROK_AUTHTOKEN = (New-Object System.Net.NetworkCredential("", $secure)).Password; docker run -d --name ngrok --network cicd-net --restart unless-stopped -p 127.0.0.1:4040:4040 -e NGROK_AUTHTOKEN --mount "type=bind,source=$policyPath,target=/etc/ngrok/traffic-policy.yml,readonly" ngrok/ngrok:latest http http://jenkins:8080 --url "https://$NGROK_DOMAIN" --traffic-policy-file /etc/ngrok/traffic-policy.yml --log stdout; Remove-Item Env:NGROK_AUTHTOKEN
```

**Linux shell (bash)**

```bash
read -r -p "ngrok dev domain (e.g. example.ngrok.app): " NGROK_DOMAIN; read -rsp "ngrok authtoken: " NGROK_AUTHTOKEN; export NGROK_AUTHTOKEN; printf '\n'; docker run -d --name ngrok --network cicd-net --restart unless-stopped -p 127.0.0.1:4040:4040 -e NGROK_AUTHTOKEN --mount "type=bind,source=$PWD/ngrok/traffic-policy.yml,target=/etc/ngrok/traffic-policy.yml,readonly" ngrok/ngrok:latest http http://jenkins:8080 --url "https://$NGROK_DOMAIN" --traffic-policy-file /etc/ngrok/traffic-policy.yml --log stdout; unset NGROK_AUTHTOKEN
```

ตัวเลือก `-e NGROK_AUTHTOKEN` ส่งค่าจาก environment ปัจจุบันเข้า container ส่วน `--mount` ใช้ path เต็มของไฟล์ policy และ mount แบบ read-only; Docker เก็บ environment ของ container ใน metadata จึงจำกัดสิทธิ์ผู้ที่เข้าถึง Docker daemon ได้

ตรวจว่า ngrok container ทำงานและไม่มี error:

```bash
docker ps --filter name=ngrok
docker logs --tail=50 ngrok
```

เปิด <http://localhost:4040> เพื่อตรวจว่า endpoint online และ Traffic Policy ทำงาน การเปิด HTTPS domain ใน browser เป็น `GET` และได้ `403` ถือว่าถูกต้องตาม policy; ใช้ GitHub webhook delivery เพื่อตรวจสอบ request จริง

คง ngrok container ให้ทำงานขณะใช้ webhook เมื่อเลิกใช้งานให้หยุด tunnel:

```bash
docker stop ngrok
```


## 8. ตั้ง GitHub push webhook และ shared secret

ก่อนสร้าง webhook ให้ตั้ง Jenkins URL ใน **Manage Jenkins → System** เป็น `https://YOUR_NGROK_DOMAIN/` เพื่อให้ URL ที่ Jenkins แสดงใช้ HTTPS domain

1. สร้าง secret แบบสุ่มที่คาดเดายากด้วย password manager หรือเครื่องมือที่เชื่อถือได้ แล้วเก็บค่าไว้เพื่อใส่ทั้งใน Jenkins และ GitHub
2. ใน **Manage Jenkins → Credentials** เพิ่ม credential ชนิด **Secret text** โดยตั้ง ID เป็น `github-webhook-secret`
3. ไปที่ **Manage Jenkins → System → GitHub → Advanced → Add shared secret** แล้วเลือก `github-webhook-secret` เป็น Shared secret โดยคงอัลกอริทึม SHA-256
4. เปิด GitHub repository → **Settings → Webhooks → Add webhook**
5. ตั้ง Payload URL เป็น `https://YOUR_NGROK_DOMAIN/github-webhook/` โดยต้องมี slash ปิดท้าย
6. ตั้ง Content type เป็น `application/json`, ใส่ secret ค่าเดียวกับ Jenkins, เปิด SSL verification และเลือก **Just the push event**
7. บันทึก webhook แล้วตรวจผลใน **Recent Deliveries**
8. ตรวจว่า Jenkins job เปิด **GitHub hook trigger for GITScm polling** หากจำเป็นตาม job type/plugin version

`githubPush()` ใน Jenkinsfile กำหนด trigger สำหรับ push แล้ว แต่ GitHub ต้องเรียกถึง ngrok และ Jenkins ได้จริง การตั้ง secret เฉพาะใน GitHub โดยไม่ตั้ง Shared secret ใน Jenkins ไม่ได้ตรวจสอบลายเซ็นที่ฝั่ง Jenkins

## 9. ขั้นตอน CI/CD เมื่อมี push

1. Jenkins checkout commit จาก GitHub และสร้าง image tag จาก 12 ตัวอักษรแรกของ commit
2. Jenkins สร้าง environment files ชั่วคราวจาก Jenkins credentials
3. Jenkins เชื่อมต่อ `devtools` ผ่าน SSH และ sync source revision ไปยัง `/root/Pet-Clinic-Booking-and-Appointment-System`
4. `devtools` build backend และ Nginx images แล้วเริ่ม PostgreSQL สำหรับตรวจสอบ
5. Pipeline รัน Ruff, mypy, Alembic migration, pytest และ Gitleaks
6. เมื่อการตรวจผ่าน Jenkins login Docker Hub ด้วย `--password-stdin` แล้ว push images
7. `devtools` pull images ที่เผยแพร่แล้วและ deploy ด้วย `docker compose up -d --no-build`
8. Pipeline seed ข้อมูลตัวอย่างและตรวจ readiness, load balancing, login/availability และ Prometheus targets
9. Pipeline ลบไฟล์ environment ชั่วคราวและ Docker Hub auth directory ส่วน runtime `.env` บน `devtools` คงอยู่ให้ Compose ใช้งาน

Jenkins build เฉพาะ backend และ Nginx เพราะ backend image ใช้ร่วมกันโดย `migrate`, `web1`, `web2` และ `worker`; Nginx image รวม static frontend assets และเป็นตัวเสิร์ฟหน้าเว็บกับ proxy API ส่วน PostgreSQL, Prometheus, Grafana และ monitoring services ใช้ prebuilt images

Docker Hub จะมี tags ต่อไปนี้ โดย `<dockerhub-user>` คือ Docker Hub username และ `<build-number>` คือ Jenkins build number:

- `<dockerhub-user>/petcare-backend:<12-character-commit>`
- `<dockerhub-user>/petcare-backend:build-<build-number>`
- `<dockerhub-user>/petcare-nginx:<12-character-commit>`
- `<dockerhub-user>/petcare-nginx:build-<build-number>`

## 10. ตรวจสอบ pipeline และใช้งานแอป

หลัง push commit ให้ตรวจ GitHub webhook **Recent Deliveries** ว่าส่งสำเร็จ จากนั้นเปิด Jenkins build → **Console Output** และตรวจ stages `Checkout`, `Connect and Sync to devtools`, `Build & Verify`, `Publish to Docker Hub`, `Deploy` และ `Post-Deployment Verification`

ตรวจ Docker Hub ว่ามี commit tag และ `build-<number>` tag สำหรับ backend และ Nginx แล้วตรวจ Compose services บน `devtools` และทดลองเปิด URL ที่ Docker networking ส่งถึง host

### รันแอปด้วยตนเองโดยไม่ผ่าน Jenkins

จาก root ของ repository สร้างสำเนา `.env.example` ชื่อ `.env` ด้วย file manager หรือเครื่องมือจัดการไฟล์ของระบบ จากนั้นตั้ง `POSTGRES_PASSWORD`, `JWT_SECRET` และ `GRAFANA_ADMIN_PASSWORD` เป็นค่าที่ไม่ซ้ำและเหมาะกับสภาพแวดล้อม ห้าม commit `.env`

สั่ง build และเริ่ม services:

```bash
docker compose up -d --build
docker compose ps
```

Compose จะรัน migration ก่อนเริ่ม backend ตรวจ endpoints ต่อไปนี้เมื่อ ports เข้าถึงจากเครื่องที่ใช้ได้:

| URL | จุดประสงค์ |
|---|---|
| `http://localhost/api/v1/health/live` | ตรวจ liveness |
| `http://localhost/api/v1/health/ready` | ตรวจ readiness และ PostgreSQL |
| `http://localhost:3000` | Grafana |
| `http://localhost:9090` | Prometheus |

seed ข้อมูลตัวอย่างด้วยคำสั่งต่อไปนี้:

```bash
docker compose run --rm web1 python -m scripts.seed
```

บัญชีตัวอย่างคือ `owner1@petcare.local`, `vet1@petcare.local` และ `staff@petcare.local` โดยใช้รหัสผ่าน `Petcare123!` เฉพาะ demo/test; เปลี่ยนหรือลบข้อมูลตัวอย่างก่อนเปิดใช้งานจริง

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

### Ports ของ Compose

Compose publish port 80 สำหรับ Nginx, 3000 สำหรับ Grafana และ 9090 สำหรับ Prometheus; PostgreSQL และ backend ไม่ได้ publish port ออกสู่ host โดยตรง

เมื่อ Compose ใช้ Docker daemon ซ้อนอยู่ใน `devtools` การ publish port ใน Compose อาจไม่ทำให้ host เข้าถึง services ได้โดยอัตโนมัติ ต้องตรวจ network และ port forwarding ของ Docker daemon ที่ใช้งานจริง

## 11. แก้ปัญหาเบื้องต้น

| อาการ | จุดตรวจสอบ |
|---|---|
| Jenkins ไม่เริ่ม build หลัง push | ตรวจ GitHub webhook Recent Deliveries, HTTPS URL, GitHub plugin, job trigger และ branch |
| ngrok endpoint offline หรือส่ง request ไม่ถึง Jenkins | ตรวจ `docker ps`, `docker logs ngrok`, authtoken, domain, network `cicd-net` และสถานะ Jenkins |
| ngrok ส่ง `403` ให้ webhook | ตรวจ path `/github-webhook/` รวม trailing slash และ method `POST` ให้ตรง Traffic Policy |
| GitHub แจ้ง webhook signature/secret ผิด | ตรวจว่า Jenkins credential, GitHub plugin Shared secret และ GitHub webhook ใช้ secret เดียวกัน |
| `Could not resolve hostname devtools` หรือ SSH timeout | ให้ Jenkins agent และ `devtools` อยู่ network เดียวกัน และตรวจ DNS/SSH port 22 |
| `Host key verification failed` | ตรวจว่า host key ที่ยืนยัน fingerprint แล้วอยู่ใน `known_hosts` ของ agent ที่รัน pipeline |
| `Permission denied (publickey)` | ตรวจ `devtools-ssh`, username `root`, passphrase, SSH server config และ permissions ของ `authorized_keys` |
| ไม่มี initial admin password | ตรวจว่า Jenkins เริ่มทำงานและ volume `jenkins_home` ถูกต้อง แล้วอ่านไฟล์ตามคำสั่งในหัวข้อเริ่ม Jenkins |
| Docker ใช้งานไม่ได้ใน `devtools` | รัน `docker exec devtools docker info`; image นี้ต้องเริ่มด้วย `--privileged` และ daemon ต้องพร้อม |
| Docker Hub push ไม่ผ่าน | ตรวจ credential `dockerhub`, token permissions และชื่อ repositories |
| Pipeline ปฏิเสธ PostgreSQL password | เปลี่ยน Jenkins credential ให้ใช้เฉพาะ URL-safe characters ตามตาราง credentials |
| Deploy แล้วเข้าแอปจาก host ไม่ได้ | ตรวจ port publishing และ Docker networking ของ daemon ที่ Compose ใช้; port ของ container ชั้นนอกอาจไม่ forward nested containers |
| Post-deployment verification ล้มเหลว | ตรวจ `docker compose ps`, logs ของ `web1`, `web2`, `worker`, `nginx`, health endpoint และ Prometheus targets |
| SSH key หายหลัง recreate `devtools` | ติดตั้ง public key ใหม่ใน `/root/.ssh/authorized_keys` และยืนยัน/อัปเดต host key ที่ Jenkins |

ตรวจ containers บน host:

```bash
docker ps
docker logs --tail=100 jenkins
docker logs --tail=100 devtools
```

ตรวจ Compose จาก shell ของ `devtools` ในฐานะ root:

```sh
cd /root/Pet-Clinic-Booking-and-Appointment-System && docker compose ps
```

หาก `POST /github-webhook/` ที่ส่งด้วย request ทั่วไปได้ HTTP `400` ซึ่งไม่มี GitHub event headers อาจแปลว่า tunnel และ route ถึง Jenkins แล้ว ให้ใช้ GitHub **Recent Deliveries** ยืนยัน webhook จริง

ดูแนวทาง recovery เพิ่มเติมใน [Runbook](runbook.md)

## 12. Checklist ก่อนใช้งานจริง

- [ ] Jenkins ใช้ authentication ที่ปลอดภัยและไม่มี anonymous access
- [ ] ngrok tunnel ชี้ไปยัง Jenkins ที่ถูกต้องและจำกัดด้วย Traffic Policy
- [ ] GitHub webhook ส่งถึง Jenkins ได้และเลือก branch ที่ถูกต้อง
- [ ] Webhook shared secret ตรงกันทั้ง Jenkins GitHub plugin และ GitHub
- [ ] Jenkins credentials มี ID ถูกต้องและจำกัด scope
- [ ] `devtools-ssh` ใช้ key เฉพาะและปิด root password login
- [ ] SSH host key ได้รับการยืนยันและเปิด `StrictHostKeyChecking`
- [ ] Docker Hub token มีสิทธิ์เท่าที่จำเป็นและ repositories ถูกต้อง
- [ ] ไม่มี secrets ใน Git, console output หรือไฟล์ที่ไม่จำเป็น
- [ ] มี backup ของข้อมูล PostgreSQL และแผน rollback ก่อน deployment
- [ ] ตรวจแล้วว่า ports และ Docker networking ทำให้บริการเข้าถึงได้ตามต้องการ

## เอกสารที่เกี่ยวข้อง

- [Runbook](runbook.md)
- [คู่มือทดสอบด้วยตนเอง](manual-testing.md)
- [แผนภาพระบบ](diagrams.md)
