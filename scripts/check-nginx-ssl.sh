#!/bin/bash

# Nginx SSL 설정 확인 스크립트

echo "=========================================="
echo "Nginx SSL 설정 확인"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DOMAIN="mscout.xyz"

echo -e "\n${YELLOW}[1] 활성화된 Nginx 설정 파일 확인${NC}"
echo "----------------------------------------"
if [ -f "/etc/nginx/sites-enabled/matchday-scout" ]; then
    echo -e "${GREEN}✓ 설정 파일 존재: /etc/nginx/sites-enabled/matchday-scout${NC}"
    echo ""
    echo "SSL 인증서 설정:"
    sudo grep -E "ssl_certificate|ssl_certificate_key" /etc/nginx/sites-enabled/matchday-scout || echo -e "${RED}✗ SSL 인증서 경로를 찾을 수 없습니다${NC}"
else
    echo -e "${RED}✗ 설정 파일을 찾을 수 없습니다${NC}"
    echo "활성화된 설정 파일 목록:"
    ls -la /etc/nginx/sites-enabled/
fi

echo -e "\n${YELLOW}[2] Let's Encrypt 인증서 확인${NC}"
echo "----------------------------------------"
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    echo -e "${GREEN}✓ 인증서 파일 존재${NC}"
    echo "인증서 경로: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
    echo ""
    echo "인증서 정보:"
    sudo openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -subject -dates
else
    echo -e "${RED}✗ 인증서 파일을 찾을 수 없습니다${NC}"
fi

echo -e "\n${YELLOW}[3] Nginx 설정 테스트${NC}"
echo "----------------------------------------"
if sudo nginx -t 2>&1; then
    echo -e "${GREEN}✓ Nginx 설정 파일 문법 정상${NC}"
else
    echo -e "${RED}✗ Nginx 설정 파일에 오류가 있습니다${NC}"
fi

echo -e "\n${YELLOW}[4] HTTPS 연결 테스트${NC}"
echo "----------------------------------------"
echo "HTTPS 응답 헤더:"
curl -I https://$DOMAIN 2>&1 | head -10

echo -e "\n${YELLOW}[5] SSL 인증서 유효성 확인${NC}"
echo "----------------------------------------"
echo | openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -dates -subject -issuer 2>/dev/null || echo -e "${RED}✗ SSL 연결 실패${NC}"

echo -e "\n${YELLOW}[6] Certbot 인증서 목록${NC}"
echo "----------------------------------------"
sudo certbot certificates 2>/dev/null | grep -A 10 "$DOMAIN" || echo "인증서 정보를 찾을 수 없습니다"

echo ""
echo "=========================================="
echo "확인 완료"
echo "=========================================="

