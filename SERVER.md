# Ubuntu 2022 서버 배포 가이드

이 문서는 Matchday Scout 애플리케이션을 Ubuntu 22.04 서버에 배포하는 방법을 설명합니다.

## 목차
1. [시스템 요구사항](#시스템-요구사항)
2. [정적 IP 설정](#정적-ip-설정)
3. [필수 소프트웨어 설치](#필수-소프트웨어-설치)
4. [애플리케이션 배포](#애플리케이션-배포)
5. [HTTPS 설정](#https-설정)
6. [서비스 관리](#서비스-관리)
7. [방화벽 설정](#방화벽-설정)

---

## 시스템 요구사항

- Ubuntu 22.04 LTS
- 최소 2GB RAM
- 최소 10GB 디스크 공간
- Python 3.10 이상
- Node.js 18 이상
- Nginx

---

## 정적 IP 설정

### 1. 현재 네트워크 정보 확인

```bash
ip addr show
# 또는
ifconfig
```

현재 IP 주소, 서브넷 마스크, 게이트웨이를 확인합니다.

### 2. Netplan 설정 파일 수정

Ubuntu 22.04는 Netplan을 사용합니다.

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

다음과 같이 설정합니다 (예시):

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:  # 네트워크 인터페이스 이름 (ip addr show로 확인)
      dhcp4: no
      addresses:
        - 192.168.1.100/24  # 원하는 정적 IP 주소/서브넷 마스크
      routes:
        - to: default
          via: 192.168.1.1  # 게이트웨이 주소
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

### 3. 설정 적용

```bash
sudo netplan apply
```

### 4. 연결 확인

```bash
ip addr show
ping -c 3 8.8.8.8
```

---

## 필수 소프트웨어 설치

### 1. 시스템 업데이트

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Python 및 pip 설치

```bash
sudo apt install -y python3 python3-pip python3-venv
```

### 3. Node.js 설치 (NodeSource 저장소 사용)

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

버전 확인:
```bash
node --version
npm --version
```

### 4. Nginx 설치

```bash
sudo apt install -y nginx
```

### 5. 방화벽 설정

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

---

## 애플리케이션 배포

### 1. 프로젝트 디렉토리로 이동

```bash
cd ~/Matchday-Scout
```

### 2. 프로젝트 파일 업로드 (필요한 경우)

이미 파일이 있다면 이 단계를 건너뛰세요.

로컬에서 서버로 파일을 전송합니다 (SCP 사용 예시):

```bash
# 로컬 컴퓨터에서 실행
scp -r /path/to/Matchday-Scout/* ubuntu@server-ip:~/Matchday-Scout/
```

또는 Git을 사용하는 경우:

```bash
cd ~
git clone <repository-url> Matchday-Scout
cd Matchday-Scout
```

### 3. 백엔드 설정

```bash
cd ~/Matchday-Scout/backend

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 4. 프론트엔드 빌드 (중요!)

**반드시 빌드를 실행해야 합니다.** 빌드하지 않으면 프론트엔드 서비스가 시작되지 않습니다.

```bash
cd ~/Matchday-Scout/frontend

# 의존성 설치
npm install

# 프로덕션 빌드 (필수!)
npm run build

# 빌드 확인
ls -la .next
```

빌드가 완료되면 `.next` 디렉토리가 생성됩니다. 이 디렉토리가 없으면 `npm start`가 실패합니다.

### 5. Systemd 서비스 파일 생성

#### 백엔드 서비스

```bash
sudo nano /etc/systemd/system/matchday-backend.service
```

다음 내용 추가:

```ini
[Unit]
Description=Matchday Scout Backend API
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Matchday-Scout/backend
Environment="PATH=/home/ubuntu/Matchday-Scout/backend/venv/bin"
ExecStart=/home/ubuntu/Matchday-Scout/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 프론트엔드 서비스

```bash
sudo nano /etc/systemd/system/matchday-frontend.service
```

다음 내용 추가:

```ini
[Unit]
Description=Matchday Scout Frontend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Matchday-Scout/frontend
Environment="NODE_ENV=production"
Environment="PATH=/home/ubuntu/.nvm/versions/node/v24.1.0/bin:/usr/bin:/usr/local/bin:/home/ubuntu/.local/bin"
ExecStart=/home/ubuntu/.nvm/versions/node/v24.1.0/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 6. 서비스 활성화 및 시작

```bash
# 서비스 파일 리로드
sudo systemctl daemon-reload

# 서비스 활성화 (부팅 시 자동 시작)
sudo systemctl enable matchday-backend
sudo systemctl enable matchday-frontend

# 서비스 시작
sudo systemctl start matchday-backend
sudo systemctl start matchday-frontend

# 상태 확인
sudo systemctl status matchday-backend
sudo systemctl status matchday-frontend
```

---

## HTTPS 설정

### 프로덕션 환경 SSL 인증서 선택

**도메인이 있는 경우**: Let's Encrypt 무료 SSL 인증서 사용 (권장)
**도메인이 없는 경우 (IP 주소만)**: 자체 서명 인증서 사용 (브라우저 경고 발생)

> **중요**: Let's Encrypt는 도메인 이름이 필요합니다. IP 주소만으로는 사용할 수 없습니다.

---

### 옵션 1: Let's Encrypt 사용 (도메인이 있는 경우 - 권장)

현재 도메인: **mscout.xyz**

#### 1. 도메인 DNS 설정 (먼저 완료 필요)

도메인 등록 업체(예: Namecheap, GoDaddy, Cloudflare 등)에서 DNS 설정:

**A 레코드 추가:**
- 호스트: `@` 또는 `mscout.xyz` 또는 빈 값
- 값/포인트: `43.201.164.55`
- TTL: 3600 (또는 기본값)

**www 서브도메인 (선택사항):**
- 호스트: `www`
- 값/포인트: `43.201.164.55`
- TTL: 3600

**DNS 전파 확인:**

```bash
# 방법 1: nslookup
nslookup mscout.xyz
# 43.201.164.55가 나와야 함

# 방법 2: dig (더 자세한 정보)
dig mscout.xyz +short
# 43.201.164.55가 나와야 함

# 방법 3: 온라인 도구 사용
# https://dnschecker.org 에서 mscout.xyz 확인
```

**DNS 전파 시간:**
- 보통 몇 분~몇 시간 소요
- 최대 24-48시간까지 걸릴 수 있음
- 전파가 완료되기 전까지 Let's Encrypt 인증서 발급 불가

**NXDOMAIN 오류 해결:**

`nslookup mscout.xyz`에서 `NXDOMAIN` 오류가 나오면:

1. **도메인 등록 확인:**
   - 도메인이 실제로 등록되어 있는지 확인
   - 도메인 등록 업체에서 도메인 상태 확인

2. **DNS 설정 확인:**
   - 도메인 등록 업체의 DNS 관리 페이지에서 A 레코드가 올바르게 설정되었는지 확인
   - 호스트: `@` 또는 `mscout.xyz`
   - 값: `43.201.164.55`

3. **DNS 서버 확인:**
   ```bash
   # 도메인의 네임서버 확인
   dig NS mscout.xyz
   
   # 특정 네임서버에서 직접 확인
   dig @ns1.example.com mscout.xyz
   ```

4. **전파 대기:**
   - DNS 설정 후 전파를 기다림
   - 온라인 DNS 체커(https://dnschecker.org)로 전세계 전파 상태 확인

**DNS 전파 완료 확인 후 진행:**
DNS가 전파되어 `nslookup mscout.xyz`에서 `43.201.164.55`가 나올 때까지 기다린 후 Let's Encrypt 인증서 발급을 진행하세요.

#### 2. Certbot 설치

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

#### 3. Nginx 설정 파일 수정 (도메인 사용)

기존 설정을 도메인으로 변경:

```bash
sudo nano /etc/nginx/sites-available/matchday-scout
```

`server_name _;`를 `server_name mscout.xyz www.mscout.xyz;`로 변경:

```nginx
# HTTP를 HTTPS로 리다이렉트
server {
    listen 80;
    server_name mscout.xyz www.mscout.xyz;
    return 301 https://$host$request_uri;
}

# HTTPS 서버
server {
    listen 443 ssl http2;
    server_name mscout.xyz www.mscout.xyz;
    
    # SSL 인증서는 Certbot이 자동으로 설정함
    # ssl_certificate /etc/nginx/ssl/matchday-scout.crt;
    # ssl_certificate_key /etc/nginx/ssl/matchday-scout.key;
    
    # ... 나머지 설정
}
```

설정 테스트 및 재시작:
```bash
sudo nginx -t
sudo systemctl restart nginx
```

#### 4. SSL 인증서 발급

```bash
# mscout.xyz 도메인으로 인증서 발급
sudo certbot --nginx -d mscout.xyz -d www.mscout.xyz

# Certbot이 자동으로:
# - SSL 인증서 발급
# - Nginx 설정 자동 업데이트
# - 자동 갱신 설정
```

인증서 발급 중 Certbot이 물어보는 질문:
- Email 주소 입력 (선택사항)
- Terms of Service 동의: `Y`
- 이메일 공유 동의: `Y` 또는 `N`

#### 5. 인증서 자동 갱신 확인

```bash
# 갱신 테스트
sudo certbot renew --dry-run

# 자동 갱신은 systemd timer로 설정됨
sudo systemctl status certbot.timer

# 자동 갱신 활성화 확인
sudo systemctl enable certbot.timer
```

#### 6. 접속 확인

```bash
# HTTPS 접속 테스트 (경고 없이 작동해야 함)
curl -I https://mscout.xyz
curl -I https://www.mscout.xyz
```

브라우저에서 `https://mscout.xyz` 접속 시 경고 없이 접속됩니다.

---

### 옵션 2: 자체 서명 인증서 (IP 주소만 있는 경우)

도메인이 없고 IP 주소만 있는 경우:

```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/matchday-scout.key \
  -out /etc/nginx/ssl/matchday-scout.crt \
  -subj "/C=KR/ST=Seoul/L=Seoul/O=Matchday Scout/CN=localhost"
```

### 2. Nginx 설정 파일 생성

```bash
sudo nano /etc/nginx/sites-available/matchday-scout
```

다음 내용을 **정확히** 추가하세요 (두 개의 별도 server 블록):

```nginx
# HTTP를 HTTPS로 리다이렉트 (첫 번째 server 블록)
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

# HTTPS 서버 (두 번째 server 블록)
server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate /etc/nginx/ssl/matchday-scout.crt;
    ssl_certificate_key /etc/nginx/ssl/matchday-scout.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 프론트엔드 프록시
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 백엔드 API 프록시
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 백엔드 문서 프록시
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Nginx 설정 활성화

#### 기존 설정 확인 및 비활성화

먼저 현재 활성화된 설정을 확인합니다:

```bash
# 활성화된 설정 파일 확인
ls -la /etc/nginx/sites-enabled/

# 현재 어떤 설정이 사용 중인지 확인
sudo nginx -T | grep "server_name\|listen"
```

기존 설정을 비활성화합니다:

```bash
# 기본 설정이 있다면 비활성화
sudo rm -f /etc/nginx/sites-enabled/default

# 다른 기존 설정이 있다면 확인 후 비활성화
# 예: mamat.kr 같은 기존 설정이 있는 경우
sudo rm -f /etc/nginx/sites-enabled/mamat.kr

# 또는 모든 기존 설정 확인 후 선택적으로 비활성화
ls -la /etc/nginx/sites-enabled/
# 필요한 설정만 남기고 나머지는 삭제
```

> **주의**: `sites-enabled` 경로를 정확히 입력하세요. `sites-enable` (오타)가 아닙니다!

#### 새 설정 활성화

```bash
# 새 설정 활성화
sudo ln -sf /etc/nginx/sites-available/matchday-scout /etc/nginx/sites-enabled/matchday-scout

# 활성화된 설정 확인
ls -la /etc/nginx/sites-enabled/

# 설정 파일 문법 확인
sudo nginx -t
```

오류가 없으면:

```bash
# Nginx 재시작
sudo systemctl restart nginx

# 상태 확인
sudo systemctl status nginx
```

#### 설정이 적용되지 않는 경우

```bash
# Nginx 설정 다시 로드
sudo systemctl reload nginx

# 또는 강제 재시작
sudo systemctl restart nginx

# 현재 사용 중인 설정 확인
sudo nginx -T | head -50
```

### 4. HTTPS 설정 확인 및 수정

HTTPS가 작동하지 않는 경우 단계별로 확인하세요:

#### 1단계: SSL 인증서 확인

```bash
# SSL 인증서 파일 확인
sudo ls -la /etc/nginx/ssl/

# 인증서가 없다면 생성
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/matchday-scout.key \
  -out /etc/nginx/ssl/matchday-scout.crt \
  -subj "/C=KR/ST=Seoul/L=Seoul/O=Matchday Scout/CN=localhost"

# 인증서 권한 확인
sudo chmod 600 /etc/nginx/ssl/matchday-scout.key
sudo chmod 644 /etc/nginx/ssl/matchday-scout.crt
```

#### 2단계: Nginx 설정 확인

```bash
# 현재 설정 확인
sudo cat /etc/nginx/sites-available/matchday-scout

# 설정 파일 수정
sudo nano /etc/nginx/sites-available/matchday-scout
```

#### 3단계: 포트 80, 443 리스닝 확인

```bash
# 포트 80, 443이 리스닝 중인지 확인
sudo ss -tlnp | grep -E ':(80|443)'
# 또는
sudo netstat -tlnp | grep -E ':(80|443)'
```

포트가 리스닝되지 않으면:
1. Nginx가 실행되지 않았을 수 있음
2. Nginx 설정에 오류가 있을 수 있음
3. Lightsail 방화벽에서 포트가 닫혀있을 수 있음

```bash
# Nginx 상태 확인
sudo systemctl status nginx

# Nginx가 실행되지 않았다면 시작
sudo systemctl start nginx

# Nginx 설정 테스트
sudo nginx -t
```

#### 포트 80이 리스닝되지 않는 경우 (Connection refused)

HTTPS는 작동하지만 HTTP(포트 80)가 작동하지 않는 경우:

```bash
# 1. 포트 80 사용 확인
sudo ss -tlnp | grep :80
sudo lsof -i :80

# 2. Nginx 설정에서 listen 80 확인
sudo cat /etc/nginx/sites-available/matchday-scout | grep "listen 80"

# 3. Nginx 설정 파일에 HTTP server 블록이 있는지 확인
sudo cat /etc/nginx/sites-available/matchday-scout

# 4. HTTP server 블록이 없다면 추가 필요
# 첫 번째 server 블록이 있어야 함:
# server {
#     listen 80;
#     server_name _;
#     return 301 https://$host$request_uri;
# }

# 5. Nginx 재시작
sudo systemctl restart nginx

# 6. 포트 확인
sudo ss -tlnp | grep :80
```

**참고**: HTTPS가 작동한다면 서비스 자체는 정상입니다. HTTP 리다이렉트만 설정하면 됩니다.

#### HTTP가 HTTPS로 리다이렉트되지 않는 경우

HTTP로 접속했는데 HTTPS로 자동 리다이렉트가 안 되는 경우:

```bash
# 1. HTTP server 블록이 제대로 있는지 확인
sudo cat /etc/nginx/sites-available/matchday-scout | head -10

# 2. HTTP 리다이렉트 테스트
curl -I http://43.201.164.55
# 301 Moved Permanently와 Location: https://... 가 나와야 함

# 3. Nginx 설정 테스트
sudo nginx -t

# 4. Nginx 재시작 (강제)
sudo systemctl stop nginx
sudo systemctl start nginx

# 5. Nginx 에러 로그 확인
sudo tail -50 /var/log/nginx/error.log

# 6. 활성화된 설정 확인
ls -la /etc/nginx/sites-enabled/
# matchday-scout만 있어야 함

# 7. 설정 파일이 활성화되어 있는지 확인
sudo cat /etc/nginx/sites-enabled/matchday-scout | head -10
```

**확인 사항:**
- HTTP server 블록이 파일 맨 위에 있어야 함
- `return 301 https://$host$request_uri;`가 정확히 있어야 함
- Nginx가 재시작되었는지 확인
- 브라우저 캐시를 지우고 다시 시도

#### 4단계: Lightsail 방화벽 확인 (중요!)

Lightsail 콘솔에서:
1. 인스턴스 선택
2. **Networking** 탭 클릭
3. **Firewall** 섹션 확인
4. **HTTPS (443)** 포트가 열려있는지 확인
5. 없다면 추가하고 **Save** 클릭

#### 5단계: Nginx 설정 테스트 및 재시작

```bash
# 설정 파일 문법 확인
sudo nginx -t

# 오류가 없다면 재시작
sudo systemctl restart nginx

# Nginx 상태 확인
sudo systemctl status nginx

# Nginx 에러 로그 확인
sudo tail -50 /var/log/nginx/error.log
```

#### 6단계: IP 주소로 HTTPS 접속 테스트

```bash
# 서버 IP 주소로 HTTPS 접속 테스트
curl -k https://43.201.164.55

# 또는 로컬에서 테스트
curl -k https://localhost
# -k 옵션은 자체 서명 인증서 경고를 무시합니다
```

#### 7단계: IP 주소 접속 확인

현재 설정(`server_name _;`)은 IP 주소 접속을 허용합니다.

**접속 방법:**
- HTTP: `http://43.201.164.55` → 자동으로 HTTPS로 리다이렉트
- HTTPS: `https://43.201.164.55`

**브라우저에서 접속 시:**
1. 자체 서명 인증서 경고가 표시됩니다 (정상)
2. "고급" 또는 "Advanced" 클릭
3. "계속 진행" 또는 "Proceed to 43.201.164.55" 클릭

**확인 사항:**
```bash
# 1. 포트 80, 443 리스닝 확인
sudo ss -tlnp | grep -E ':(80|443)'

# 2. Nginx 설정에서 server_name 확인
sudo cat /etc/nginx/sites-available/matchday-scout | grep server_name

# 3. 실제 IP 주소로 접속 테스트
curl -I http://43.201.164.55
# 301 리다이렉트가 나와야 함

curl -k -I https://43.201.164.55
# 200 OK가 나와야 함
```

**올바른 설정 구조** (반드시 두 개의 별도 server 블록):

```nginx
# 첫 번째 server 블록: HTTP를 HTTPS로 리다이렉트
# server_name _; 는 모든 호스트명과 IP 주소를 허용합니다
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

# 두 번째 server 블록: HTTPS 서버
# IP 주소(43.201.164.55)로 접속 가능합니다
server {
    listen 443 ssl http2;
    server_name _;  # _ 는 모든 호스트명과 IP 주소를 허용

    ssl_certificate /etc/nginx/ssl/matchday-scout.crt;
    ssl_certificate_key /etc/nginx/ssl/matchday-scout.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # 프론트엔드 프록시
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 백엔드 API 프록시
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 백엔드 문서 프록시
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**잘못된 설정 예시** (이렇게 하면 안 됨):
- ❌ `listen 80`과 `listen 443`이 같은 server 블록에 있음
- ❌ `ssl_certificate`가 중복되어 있음
- ❌ server 블록이 제대로 닫히지 않음

```bash
# 3. SSL 인증서 확인 및 생성 (없다면)
sudo ls -la /etc/nginx/ssl/
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/matchday-scout.key \
  -out /etc/nginx/ssl/matchday-scout.crt \
  -subj "/C=KR/ST=Seoul/L=Seoul/O=Matchday Scout/CN=localhost"

# 4. Nginx 설정 테스트
sudo nginx -t

# 5. Nginx 재시작
sudo systemctl restart nginx

# 6. 포트 확인
sudo ss -tlnp | grep -E ':(80|443)'
```

### 5. 브라우저에서 접속

#### 자체 서명 인증서 경고 (정상)

자체 서명 인증서를 사용하므로 브라우저에서 다음과 같은 경고가 표시됩니다:

**Chrome/Edge 경고 메시지:**
```
연결이 비공개로 설정되어 있지 않습니다.
공격자가 43.201.164.55에서 사용자의 정보를 도용하려고 시도할 수 있습니다.
net::ERR_CERT_AUTHORITY_INVALID
이 서버가 43.201.164.55임을 입증할 수 없으며 컴퓨터의 운영체제에서 신뢰하는 보안 인증서가 아닙니다.
```

**이것은 정상입니다!** 자체 서명 인증서를 사용하기 때문에 나타나는 경고입니다.

#### 접속 방법

1. **경고 화면에서:**
   - "고급" 또는 "Advanced" 버튼 클릭
   - "43.201.164.55(안전하지 않음)으로 이동" 또는 "Proceed to 43.201.164.55 (unsafe)" 클릭

2. **또는 직접 입력:**
   - 주소창에 `thisisunsafe` 입력 (Chrome에서만 작동)
   - 또는 `https://43.201.164.55` 입력 후 경고 무시

3. **시크릿 모드에서 테스트:**
   - 시크릿 모드로 접속하면 경고가 표시되지만 접속은 가능합니다

#### 프로덕션 환경 권장사항

**도메인이 있는 경우:**
- **Let's Encrypt** 무료 SSL 인증서 사용 (위의 "옵션 1: Let's Encrypt 사용" 참고)
- 자동 갱신, 브라우저 경고 없음, 완전 무료

**도메인이 없는 경우 (IP 주소만):**
- 자체 서명 인증서 사용 (현재 설정)
- 브라우저 경고 발생 (정상)
- 또는 상용 IP 주소 SSL 인증서 구매 (비용 발생)

**프로덕션 환경 권장:**
도메인을 구매하여 Let's Encrypt를 사용하는 것을 강력히 권장합니다. 도메인 비용은 연간 약 $10-15 정도입니다.

---

## 서비스 관리

> **중요**: systemd 서비스로 실행되므로 터미널을 닫아도 서비스는 계속 실행됩니다. 또한 `systemctl enable`로 활성화하면 서버 재부팅 후에도 자동으로 시작됩니다.

### 스크립트 사용

프로젝트 루트 디렉토리에 제공된 스크립트를 사용할 수 있습니다:

```bash
# 스크립트에 실행 권한 부여 (최초 1회만)
chmod +x restart.sh stop.sh

# 서비스 재시작
./restart.sh

# 서비스 중지
./stop.sh
```

### 수동 관리

```bash
# 백엔드 재시작
sudo systemctl restart matchday-backend

# 프론트엔드 재시작
sudo systemctl restart matchday-frontend

# Nginx 재시작
sudo systemctl restart nginx

# 서비스 중지
sudo systemctl stop matchday-backend
sudo systemctl stop matchday-frontend

# 서비스 시작
sudo systemctl start matchday-backend
sudo systemctl start matchday-frontend

# 로그 확인
sudo journalctl -u matchday-backend -f
sudo journalctl -u matchday-frontend -f
```

---

## 방화벽 설정

UFW 방화벽이 활성화되어 있는지 확인:

```bash
sudo ufw status
```

필요한 포트가 열려있는지 확인:

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
```

---

## 문제 해결

### 502 Bad Gateway 오류 해결

502 오류는 Nginx가 백엔드나 프론트엔드 서비스에 연결할 수 없을 때 발생합니다.

#### 1. 서비스 실행 상태 확인

```bash
# 모든 서비스 상태 확인
sudo systemctl status matchday-backend
sudo systemctl status matchday-frontend
sudo systemctl status nginx

# 서비스가 실행 중인지 확인
sudo systemctl is-active matchday-backend
sudo systemctl is-active matchday-frontend
```

#### 2. 서비스가 실행되지 않은 경우 시작

```bash
# 서비스 시작
sudo systemctl start matchday-backend
sudo systemctl start matchday-frontend

# 또는 재시작 스크립트 사용
cd ~/Matchday-Scout
./restart.sh
```

#### 3. 포트 리스닝 확인

```bash
# 백엔드 포트 (8000) 확인
sudo ss -tlnp | grep 8000
# 또는
sudo netstat -tlnp | grep 8000

# 프론트엔드 포트 (3000) 확인
sudo ss -tlnp | grep 3000
# 또는
sudo netstat -tlnp | grep 3000
```

포트가 리스닝되지 않으면 서비스가 제대로 시작되지 않은 것입니다.

#### 4. 서비스 로그 확인

```bash
# 백엔드 로그 확인
sudo journalctl -u matchday-backend -n 50 --no-pager

# 프론트엔드 로그 확인
sudo journalctl -u matchday-frontend -n 50 --no-pager

# Nginx 에러 로그 확인
sudo tail -50 /var/log/nginx/error.log
```

#### 5. 로컬에서 직접 테스트

```bash
# 백엔드 직접 접속 테스트
curl http://localhost:8000/health

# 프론트엔드 직접 접속 테스트
curl http://localhost:3000
```

#### 6. Nginx 설정 확인

Nginx 설정에서 프록시 대상이 올바른지 확인:

```bash
# Nginx 설정 확인
sudo cat /etc/nginx/sites-available/matchday-scout | grep proxy_pass
```

다음과 같이 설정되어 있어야 합니다:
- 프론트엔드: `proxy_pass http://127.0.0.1:3000;`
- 백엔드: `proxy_pass http://127.0.0.1:8000;`

#### 7. 빠른 해결 방법

```bash
cd ~/Matchday-Scout

# 모든 서비스 재시작
./restart.sh

# 또는 수동으로
sudo systemctl restart matchday-backend
sudo systemctl restart matchday-frontend
sudo systemctl restart nginx

# 상태 확인
sudo systemctl status matchday-backend matchday-frontend nginx
```

#### 8. 포트가 리스닝되지 않는 경우 (가장 흔한 문제)

포트 3000이 리스닝되지 않으면 프론트엔드가 제대로 시작되지 않은 것입니다.

**단계별 해결:**

1. **프론트엔드 로그 확인** (가장 먼저):
```bash
sudo journalctl -u matchday-frontend -n 100 --no-pager
```

2. **프론트엔드 빌드 확인 및 실행** (가장 중요!):

에러 메시지: `Could not find a production build in the '.next' directory`

```bash
cd ~/Matchday-Scout/frontend

# 빌드 확인
ls -la .next

# 빌드가 없다면 반드시 빌드 실행
npm run build

# 빌드 완료 확인 (BUILD_ID 파일이 있어야 함)
ls -la .next/BUILD_ID

# 빌드 완료 후 서비스 재시작
sudo systemctl restart matchday-frontend

# 포트 확인
sleep 5
sudo ss -tlnp | grep 3000
```

**빌드가 완료되어야만 `npm start`가 정상 작동합니다.**

3. **수동으로 실행 테스트**:
```bash
cd ~/Matchday-Scout/frontend
npm start
```

수동 실행이 안 되면:
- 의존성 재설치: `npm install`
- 빌드 재실행: `npm run build`
- 로그 확인: 오류 메시지 확인

4. **서비스 재시작**:
```bash
sudo systemctl restart matchday-frontend
sleep 5
sudo ss -tlnp | grep 3000
```

5. **여전히 안 되면 서비스 파일의 PATH 확인**:
```bash
sudo cat /etc/systemd/system/matchday-frontend.service
```

nvm 경로가 올바른지 확인하고, 필요시 수정 후:
```bash
sudo systemctl daemon-reload
sudo systemctl restart matchday-frontend
```

### 백엔드가 시작되지 않는 경우

1. 로그 확인:
```bash
sudo journalctl -u matchday-backend -n 50
```

2. 가상환경 및 의존성 확인:
```bash
cd ~/Matchday-Scout/backend
source venv/bin/activate
python -c "import fastapi; print('OK')"
```

3. 포트 사용 확인:
```bash
sudo netstat -tlnp | grep 8000
```

### 프론트엔드가 시작되지 않는 경우

#### exit-code 203/EXEC 오류 해결

이 오류는 npm을 찾을 수 없거나 실행 권한 문제일 때 발생합니다.

1. **npm 경로 확인**:
```bash
# npm 위치 확인
which npm
# 또는
whereis npm

# npm 실행 테스트
npm --version
```

2. **서비스 파일 수정** (npm 경로가 다른 경우):

```bash
sudo nano /etc/systemd/system/matchday-frontend.service
```

**nvm을 사용하는 경우** (npm이 `/home/ubuntu/.nvm/versions/node/v24.1.0/bin/npm`인 경우):
```ini
[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Matchday-Scout/frontend
Environment="NODE_ENV=production"
Environment="PATH=/home/ubuntu/.nvm/versions/node/v24.1.0/bin:/usr/bin:/usr/local/bin:/home/ubuntu/.local/bin"
ExecStart=/home/ubuntu/.nvm/versions/node/v24.1.0/bin/npm start
Restart=always
RestartSec=10
```

**일반 npm 설치인 경우**:
```ini
[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Matchday-Scout/frontend
Environment="NODE_ENV=production"
Environment="PATH=/usr/bin:/usr/local/bin:/home/ubuntu/.local/bin"
ExecStart=/usr/bin/npm start
# 또는 npm의 실제 경로 사용 (which npm 결과 사용)
# ExecStart=/usr/local/bin/npm start
Restart=always
RestartSec=10
```

> **참고**: `which npm` 명령어로 확인한 경로를 `ExecStart`에 사용하고, PATH에도 해당 디렉토리를 추가하세요.

3. **서비스 파일 확인 및 수정**:

먼저 현재 서비스 파일 내용을 확인:
```bash
sudo cat /etc/systemd/system/matchday-frontend.service
```

**중요**: `ExecStart`는 하나만 있어야 합니다. 여러 개가 있다면 하나만 남기고 나머지는 삭제하세요.

올바른 서비스 파일 예시 (nvm 사용 시):
```ini
[Unit]
Description=Matchday Scout Frontend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Matchday-Scout/frontend
Environment="NODE_ENV=production"
Environment="PATH=/home/ubuntu/.nvm/versions/node/v24.1.0/bin:/usr/bin:/usr/local/bin:/home/ubuntu/.local/bin"
ExecStart=/home/ubuntu/.nvm/versions/node/v24.1.0/bin/npm start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

4. **서비스 파일 리로드 및 재시작**:
```bash
sudo systemctl daemon-reload
sudo systemctl restart matchday-frontend
sudo systemctl status matchday-frontend
```

서비스가 정상적으로 실행되면 다음과 같이 표시됩니다:
```
Active: active (running)
Main PID: [숫자] (node .../npm start)
```

5. **접속 확인**:
```bash
# 로컬에서 프론트엔드 테스트
curl http://localhost:3000

# 백엔드 테스트
curl http://localhost:8000/health

# 브라우저에서 접속
# https://서버-IP주소
```

4. **로그 확인**:
```bash
sudo journalctl -u matchday-frontend -n 50 --no-pager
```

5. **빌드 확인**:
```bash
cd ~/Matchday-Scout/frontend
ls -la .next

# 빌드가 없다면 다시 빌드
npm run build
```

6. **포트 사용 확인**:
```bash
sudo netstat -tlnp | grep 3000
# 또는
sudo ss -tlnp | grep 3000
```

7. **수동으로 실행 테스트**:
```bash
cd ~/Matchday-Scout/frontend
npm start
```

수동 실행이 되면 서비스 파일의 경로나 환경변수 문제입니다.

### Nginx 오류 및 기존 설정 문제

1. **현재 활성화된 설정 확인**:
```bash
# 활성화된 설정 파일 목록
ls -la /etc/nginx/sites-enabled/

# 실제 사용 중인 설정 확인
sudo nginx -T | grep -A 10 "server {"
```

2. **기존 설정 비활성화 및 새 설정 적용**:
```bash
# 모든 활성화된 설정 확인
ls -la /etc/nginx/sites-enabled/

# 기존 설정 비활성화 (필요한 경우)
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/mamat.kr
# 또는 다른 기존 설정 파일명

# 새 설정 활성화
sudo ln -sf /etc/nginx/sites-available/matchday-scout /etc/nginx/sites-enabled/matchday-scout

# 활성화된 설정 확인 (matchday-scout만 남아야 함)
ls -la /etc/nginx/sites-enabled/

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

> **주의**: 경로는 `/etc/nginx/sites-enabled/`입니다. `sites-enable` (오타)가 아닙니다!
```

3. **설정 파일 문법 확인**:
```bash
sudo nginx -t
```

4. **Nginx 로그 확인**:
```bash
# 에러 로그
sudo tail -50 /var/log/nginx/error.log

# 접근 로그
sudo tail -50 /var/log/nginx/access.log
```

5. **포트 충돌 확인**:
```bash
# 80, 443 포트를 사용하는 프로세스 확인
sudo lsof -i :80
sudo lsof -i :443
# 또는
sudo ss -tlnp | grep -E ':(80|443)'
```

### 권한 문제

프로젝트 디렉토리 권한 확인 및 수정:

```bash
sudo chown -R ubuntu:ubuntu ~/Matchday-Scout
chmod -R 755 ~/Matchday-Scout
```

---

## 업데이트 방법

### 1. 코드 업데이트

```bash
cd ~/Matchday-Scout
# Git을 사용하는 경우
git pull

# 또는 파일을 다시 업로드
```

### 2. 백엔드 업데이트

```bash
cd ~/Matchday-Scout/backend
source venv/bin/activate
pip install -r requirements.txt --upgrade
```

### 3. 프론트엔드 업데이트

```bash
cd ~/Matchday-Scout/frontend
npm install
npm run build
```

### 4. 서비스 재시작

```bash
./restart.sh
```

---

## 보안 권장사항

1. **SSH 키 인증 사용**: 비밀번호 인증 대신 SSH 키 사용
2. **정기 업데이트**: `sudo apt update && sudo apt upgrade` 정기 실행
3. **방화벽 관리**: 불필요한 포트는 열지 않기
4. **로그 모니터링**: 정기적으로 로그 확인
5. **백업**: 정기적으로 데이터 및 설정 파일 백업

---

## 접속 정보

현재 서버 IP 주소: **43.201.164.55**

- **프론트엔드**: `https://43.201.164.55` 또는 `http://43.201.164.55` (자동 HTTPS 리다이렉트)
- **백엔드 API**: `https://43.201.164.55/api`
- **API 문서**: `https://43.201.164.55/docs`
- **ReDoc**: `https://43.201.164.55/redoc`

### IP 주소 접속 확인

서버에서 다음 명령어로 확인하세요:

```bash
# HTTP 접속 테스트 (301 리다이렉트 확인)
curl -I http://43.201.164.55

# HTTPS 접속 테스트
curl -k -I https://43.201.164.55

# 프론트엔드 직접 확인
curl -k https://43.201.164.55

# 백엔드 API 확인
curl -k https://43.201.164.55/api/health
```

**중요**: 
- `server_name _;` 설정은 모든 호스트명과 IP 주소를 허용하므로 IP 주소로 접속 가능합니다
- 자체 서명 인증서이므로 브라우저에서 경고가 표시됩니다 (정상)
- 경고 화면에서 "고급" → "43.201.164.55(안전하지 않음)으로 이동" 클릭하면 접속됩니다
- 또는 주소창에 `thisisunsafe` 입력 (Chrome에서만 작동)

---

## 참고사항

### SSL 인증서

- **자체 서명 인증서**: IP 주소만 있는 경우 사용. 브라우저 경고 발생 (정상)
- **Let's Encrypt**: 도메인이 있는 경우 사용 권장. 무료, 자동 갱신, 브라우저 경고 없음
- **상용 인증서**: IP 주소용으로도 구매 가능하지만 비용 발생

### 도메인 설정 (mscout.xyz)

현재 도메인: **mscout.xyz**

**설정 단계:**
1. ✅ 도메인 구매 완료: mscout.xyz
2. DNS A 레코드 설정: `mscout.xyz` → `43.201.164.55`
3. DNS 전파 대기 (보통 몇 분~몇 시간)
4. Let's Encrypt로 SSL 인증서 발급 (위의 "옵션 1: Let's Encrypt 사용" 참고)
5. Nginx 설정의 `server_name`을 `mscout.xyz www.mscout.xyz`로 변경

**DNS 설정 확인:**
```bash
nslookup mscout.xyz
# 43.201.164.55가 나와야 함
```

### 프로덕션 환경 권장사항

프로덕션 환경에서는 도메인을 구매하여 Let's Encrypt를 사용하는 것을 강력히 권장합니다:
- 브라우저 경고 없음
- 사용자 신뢰도 향상
- 완전 무료 (도메인 비용만)
- 자동 갱신

