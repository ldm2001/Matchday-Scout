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

### 1. 자체 서명 인증서 생성 (도메인 없이 사용)

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

다음 내용 추가:

```nginx
# HTTP를 HTTPS로 리다이렉트
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

# HTTPS 서버
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

### 4. 브라우저에서 접속

자체 서명 인증서이므로 브라우저에서 경고가 표시됩니다. "고급" → "계속 진행"을 클릭하여 접속할 수 있습니다.

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

- **프론트엔드**: `https://서버-IP주소`
- **백엔드 API**: `https://서버-IP주소/api`
- **API 문서**: `https://서버-IP주소/docs`

---

## 참고사항

- 자체 서명 인증서는 브라우저에서 경고를 표시합니다. 프로덕션 환경에서는 Let's Encrypt와 같은 공인 인증서 사용을 권장합니다.
- 도메인이 있는 경우, Nginx 설정의 `server_name`을 도메인으로 변경하고 Let's Encrypt를 사용할 수 있습니다.

