#!/bin/bash

# 서비스 상태 확인 스크립트

echo "=========================================="
echo "Matchday Scout 서비스 상태 확인"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 백엔드 서비스 확인
echo -e "\n${YELLOW}[1] 백엔드 서비스 (matchday-backend)${NC}"
echo "----------------------------------------"
if systemctl is-active --quiet matchday-backend; then
    echo -e "${GREEN}✓ 실행 중${NC}"
    systemctl status matchday-backend --no-pager -l | head -5
else
    echo -e "${RED}✗ 중지됨${NC}"
fi

# 2. 프론트엔드 서비스 확인
echo -e "\n${YELLOW}[2] 프론트엔드 서비스 (matchday-frontend)${NC}"
echo "----------------------------------------"
if systemctl is-active --quiet matchday-frontend; then
    echo -e "${GREEN}✓ 실행 중${NC}"
    systemctl status matchday-frontend --no-pager -l | head -5
else
    echo -e "${RED}✗ 중지됨${NC}"
fi

# 3. Nginx 서비스 확인
echo -e "\n${YELLOW}[3] Nginx 서비스${NC}"
echo "----------------------------------------"
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ 실행 중${NC}"
    systemctl status nginx --no-pager -l | head -5
else
    echo -e "${RED}✗ 중지됨${NC}"
fi

# 4. 포트 리스닝 확인
echo -e "\n${YELLOW}[4] 포트 리스닝 상태${NC}"
echo "----------------------------------------"
echo "포트 3000 (프론트엔드):"
if ss -tlnp 2>/dev/null | grep -q ':3000 '; then
    echo -e "${GREEN}✓ 리스닝 중${NC}"
    ss -tlnp | grep ':3000 '
else
    echo -e "${RED}✗ 리스닝 안 함${NC}"
fi

echo ""
echo "포트 8000 (백엔드):"
if ss -tlnp 2>/dev/null | grep -q ':8000 '; then
    echo -e "${GREEN}✓ 리스닝 중${NC}"
    ss -tlnp | grep ':8000 '
else
    echo -e "${RED}✗ 리스닝 안 함${NC}"
fi

echo ""
echo "포트 80 (HTTP):"
if ss -tlnp 2>/dev/null | grep -q ':80 '; then
    echo -e "${GREEN}✓ 리스닝 중${NC}"
    ss -tlnp | grep ':80 '
else
    echo -e "${RED}✗ 리스닝 안 함${NC}"
fi

echo ""
echo "포트 443 (HTTPS):"
if ss -tlnp 2>/dev/null | grep -q ':443 '; then
    echo -e "${GREEN}✓ 리스닝 중${NC}"
    ss -tlnp | grep ':443 '
else
    echo -e "${RED}✗ 리스닝 안 함${NC}"
fi

# 5. 서비스 연결 테스트
echo -e "\n${YELLOW}[5] 서비스 연결 테스트${NC}"
echo "----------------------------------------"

echo "백엔드 (localhost:8000):"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200\|404"; then
    echo -e "${GREEN}✓ 연결 가능${NC}"
    curl -s http://localhost:8000/health | head -1 || echo "응답 없음"
else
    echo -e "${RED}✗ 연결 불가${NC}"
fi

echo ""
echo "프론트엔드 (localhost:3000):"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}✓ 연결 가능${NC}"
else
    echo -e "${RED}✗ 연결 불가${NC}"
fi

# 6. 최근 로그 확인
echo -e "\n${YELLOW}[6] 최근 로그 (에러 확인)${NC}"
echo "----------------------------------------"
echo "백엔드 최근 로그:"
sudo journalctl -u matchday-backend -n 3 --no-pager 2>/dev/null || echo "로그 확인 불가"

echo ""
echo "프론트엔드 최근 로그:"
sudo journalctl -u matchday-frontend -n 3 --no-pager 2>/dev/null || echo "로그 확인 불가"

# 7. 요약
echo ""
echo "=========================================="
echo "요약"
echo "=========================================="

BACKEND_ACTIVE=$(systemctl is-active matchday-backend 2>/dev/null)
FRONTEND_ACTIVE=$(systemctl is-active matchday-frontend 2>/dev/null)
NGINX_ACTIVE=$(systemctl is-active nginx 2>/dev/null)

if [ "$BACKEND_ACTIVE" = "active" ] && [ "$FRONTEND_ACTIVE" = "active" ] && [ "$NGINX_ACTIVE" = "active" ]; then
    echo -e "${GREEN}✓ 모든 서비스가 정상 실행 중입니다!${NC}"
    echo ""
    echo "접속 URL:"
    echo "  - https://mscout.xyz"
    echo "  - https://www.mscout.xyz"
else
    echo -e "${YELLOW}⚠ 일부 서비스가 중지되어 있습니다.${NC}"
    echo ""
    echo "서비스 시작:"
    echo "  cd ~/Matchday-Scout"
    echo "  ./restart.sh"
fi

echo ""

