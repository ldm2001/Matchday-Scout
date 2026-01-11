#!/bin/bash

# Matchday Scout Nginx HTTPS 설정 스크립트
# 이 스크립트는 Let's Encrypt SSL 인증서를 사용하여 HTTPS를 설정합니다.

set -e  # 오류 발생 시 스크립트 중단

echo "=========================================="
echo "Matchday Scout Nginx HTTPS 설정 시작"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 도메인 설정
DOMAIN="mscout.xyz"
WWW_DOMAIN="www.mscout.xyz"

# 1. DNS 전파 확인
echo -e "\n${YELLOW}[1/6] DNS 전파 확인${NC}"
echo "도메인 $DOMAIN의 DNS 설정을 확인합니다..."

DNS_IP=$(dig +short $DOMAIN | tail -n1)
EXPECTED_IP="43.201.164.55"

if [ "$DNS_IP" = "$EXPECTED_IP" ]; then
    echo -e "${GREEN}✓ DNS 전파 완료: $DOMAIN → $DNS_IP${NC}"
else
    echo -e "${RED}✗ DNS 전파 미완료${NC}"
    echo "   현재 IP: $DNS_IP"
    echo "   예상 IP: $EXPECTED_IP"
    echo ""
    echo "다음 단계를 확인하세요:"
    echo "1. 도메인 등록 업체에서 A 레코드 설정 확인"
    echo "2. DNS 전파 대기 (보통 몇 분~몇 시간 소요)"
    echo "3. 온라인 DNS 체커(https://dnschecker.org)로 전파 상태 확인"
    echo ""
    read -p "DNS 전파가 완료되지 않았습니다. 계속 진행하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "설정을 중단합니다."
        exit 1
    fi
fi

# 2. Certbot 설치 확인 및 설치
echo -e "\n${YELLOW}[2/6] Certbot 설치 확인${NC}"
if command -v certbot &> /dev/null; then
    echo -e "${GREEN}✓ Certbot이 이미 설치되어 있습니다.${NC}"
else
    echo "Certbot을 설치합니다..."
    sudo apt update
    sudo apt install -y certbot python3-certbot-nginx
    echo -e "${GREEN}✓ Certbot 설치 완료${NC}"
fi

# 3. Nginx 설정 파일 복사
echo -e "\n${YELLOW}[3/6] Nginx 설정 파일 설정${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NGINX_CONFIG="$PROJECT_ROOT/nginx/matchday-scout.conf"

if [ ! -f "$NGINX_CONFIG" ]; then
    echo -e "${RED}✗ Nginx 설정 파일을 찾을 수 없습니다: $NGINX_CONFIG${NC}"
    exit 1
fi

echo "Nginx 설정 파일을 복사합니다..."
sudo cp "$NGINX_CONFIG" /etc/nginx/sites-available/matchday-scout

# 기존 설정 비활성화
echo "기존 설정을 비활성화합니다..."
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/matchday-scout

# 새 설정 활성화
echo "새 설정을 활성화합니다..."
sudo ln -sf /etc/nginx/sites-available/matchday-scout /etc/nginx/sites-enabled/matchday-scout

# Nginx 설정 테스트
echo "Nginx 설정을 테스트합니다..."
if sudo nginx -t; then
    echo -e "${GREEN}✓ Nginx 설정 파일 문법 확인 완료${NC}"
else
    echo -e "${RED}✗ Nginx 설정 파일에 오류가 있습니다.${NC}"
    exit 1
fi

# 4. Nginx 재시작
echo -e "\n${YELLOW}[4/6] Nginx 재시작${NC}"
sudo systemctl restart nginx
echo -e "${GREEN}✓ Nginx 재시작 완료${NC}"

# 5. SSL 인증서 발급
echo -e "\n${YELLOW}[5/6] Let's Encrypt SSL 인증서 발급${NC}"
echo "도메인: $DOMAIN, $WWW_DOMAIN"
echo ""
echo "Certbot이 다음을 수행합니다:"
echo "- SSL 인증서 발급"
echo "- Nginx 설정 자동 업데이트"
echo "- 자동 갱신 설정"
echo ""

# Certbot 실행
sudo certbot --nginx -d $DOMAIN -d $WWW_DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
    echo -e "${RED}✗ SSL 인증서 발급 실패${NC}"
    echo ""
    echo "가능한 원인:"
    echo "1. DNS 전파가 완료되지 않음"
    echo "2. 포트 80이 차단되어 있음 (방화벽 확인 필요)"
    echo "3. 도메인이 올바르게 설정되지 않음"
    echo ""
    echo "수동으로 다시 시도하려면:"
    echo "  sudo certbot --nginx -d $DOMAIN -d $WWW_DOMAIN"
    exit 1
}

echo -e "${GREEN}✓ SSL 인증서 발급 완료${NC}"

# 6. 자동 갱신 확인
echo -e "\n${YELLOW}[6/6] 자동 갱신 설정 확인${NC}"
sudo systemctl enable certbot.timer
sudo systemctl status certbot.timer --no-pager || true

# 갱신 테스트
echo "인증서 갱신을 테스트합니다..."
sudo certbot renew --dry-run
echo -e "${GREEN}✓ 자동 갱신 설정 완료${NC}"

# 완료 메시지
echo ""
echo "=========================================="
echo -e "${GREEN}HTTPS 설정이 완료되었습니다!${NC}"
echo "=========================================="
echo ""
echo "접속 URL:"
echo "  - https://$DOMAIN"
echo "  - https://$WWW_DOMAIN"
echo ""
echo "다음 명령어로 상태를 확인할 수 있습니다:"
echo "  sudo systemctl status nginx"
echo "  sudo certbot certificates"
echo "  curl -I https://$DOMAIN"
echo ""

