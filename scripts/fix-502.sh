#!/bin/bash

# 502 Bad Gateway 오류 진단 및 자동 해결 스크립트

echo "=========================================="
echo "502 Bad Gateway 오류 진단 및 해결"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ERRORS=0
FIXES=0

# 1. 서비스 상태 확인
echo -e "\n${BLUE}[1] 서비스 실행 상태 확인${NC}"
echo "----------------------------------------"

# 백엔드 확인
if systemctl is-active --quiet matchday-backend; then
    echo -e "${GREEN}✓ 백엔드 서비스: 실행 중${NC}"
else
    echo -e "${RED}✗ 백엔드 서비스: 중지됨${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → 백엔드 서비스 시작 시도...${NC}"
    sudo systemctl start matchday-backend
    sleep 2
    if systemctl is-active --quiet matchday-backend; then
        echo -e "${GREEN}  ✓ 백엔드 서비스 시작 성공${NC}"
        FIXES=$((FIXES + 1))
    else
        echo -e "${RED}  ✗ 백엔드 서비스 시작 실패${NC}"
        echo -e "${YELLOW}  로그 확인: sudo journalctl -u matchday-backend -n 50${NC}"
    fi
fi

# 프론트엔드 확인
if systemctl is-active --quiet matchday-frontend; then
    echo -e "${GREEN}✓ 프론트엔드 서비스: 실행 중${NC}"
else
    echo -e "${RED}✗ 프론트엔드 서비스: 중지됨${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → 프론트엔드 서비스 시작 시도...${NC}"
    sudo systemctl start matchday-frontend
    sleep 2
    if systemctl is-active --quiet matchday-frontend; then
        echo -e "${GREEN}  ✓ 프론트엔드 서비스 시작 성공${NC}"
        FIXES=$((FIXES + 1))
    else
        echo -e "${RED}  ✗ 프론트엔드 서비스 시작 실패${NC}"
        echo -e "${YELLOW}  로그 확인: sudo journalctl -u matchday-frontend -n 50${NC}"
    fi
fi

# Nginx 확인
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx 서비스: 실행 중${NC}"
else
    echo -e "${RED}✗ Nginx 서비스: 중지됨${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → Nginx 서비스 시작 시도...${NC}"
    sudo systemctl start nginx
    sleep 1
    if systemctl is-active --quiet nginx; then
        echo -e "${GREEN}  ✓ Nginx 서비스 시작 성공${NC}"
        FIXES=$((FIXES + 1))
    else
        echo -e "${RED}  ✗ Nginx 서비스 시작 실패${NC}"
        echo -e "${YELLOW}  설정 확인: sudo nginx -t${NC}"
    fi
fi

# 2. 포트 리스닝 확인
echo -e "\n${BLUE}[2] 포트 리스닝 상태 확인${NC}"
echo "----------------------------------------"

# 포트 8000 (백엔드)
if ss -tlnp 2>/dev/null | grep -q ':8000 '; then
    echo -e "${GREEN}✓ 포트 8000 (백엔드): 리스닝 중${NC}"
else
    echo -e "${RED}✗ 포트 8000 (백엔드): 리스닝 안 함${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → 백엔드 로그 확인 중...${NC}"
    echo "  최근 에러:"
    sudo journalctl -u matchday-backend -n 5 --no-pager 2>/dev/null | tail -3 || echo "  로그 확인 불가"
fi

# 포트 3000 (프론트엔드)
if ss -tlnp 2>/dev/null | grep -q ':3000 '; then
    echo -e "${GREEN}✓ 포트 3000 (프론트엔드): 리스닝 중${NC}"
else
    echo -e "${RED}✗ 포트 3000 (프론트엔드): 리스닝 안 함${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → 프론트엔드 빌드 확인 중...${NC}"
    
    # 프론트엔드 빌드 확인
    if [ -d "$HOME/Matchday-Scout/frontend/.next" ]; then
        echo -e "${GREEN}  ✓ .next 빌드 디렉토리 존재${NC}"
        if [ -f "$HOME/Matchday-Scout/frontend/.next/BUILD_ID" ]; then
            echo -e "${GREEN}  ✓ BUILD_ID 파일 존재${NC}"
        else
            echo -e "${YELLOW}  ⚠ BUILD_ID 파일 없음 - 빌드가 완료되지 않았을 수 있음${NC}"
            echo -e "${YELLOW}  → 프론트엔드 빌드 실행 권장:${NC}"
            echo -e "${BLUE}    cd ~/Matchday-Scout/frontend && npm run build${NC}"
        fi
    else
        echo -e "${RED}  ✗ .next 빌드 디렉토리 없음${NC}"
        echo -e "${YELLOW}  → 프론트엔드 빌드가 필요합니다!${NC}"
        echo -e "${BLUE}    cd ~/Matchday-Scout/frontend${NC}"
        echo -e "${BLUE}    npm run build${NC}"
        echo -e "${BLUE}    sudo systemctl restart matchday-frontend${NC}"
    fi
    
    echo -e "${YELLOW}  → 프론트엔드 로그 확인 중...${NC}"
    echo "  최근 에러:"
    sudo journalctl -u matchday-frontend -n 5 --no-pager 2>/dev/null | tail -3 || echo "  로그 확인 불가"
fi

# 3. 서비스 연결 테스트
echo -e "\n${BLUE}[3] 서비스 연결 테스트${NC}"
echo "----------------------------------------"

# 백엔드 테스트
echo -n "백엔드 (localhost:8000): "
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200\|404"; then
    echo -e "${GREEN}✓ 연결 가능${NC}"
else
    echo -e "${RED}✗ 연결 불가${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 프론트엔드 테스트
echo -n "프론트엔드 (localhost:3000): "
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null | grep -q "200"; then
    echo -e "${GREEN}✓ 연결 가능${NC}"
else
    echo -e "${RED}✗ 연결 불가${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 4. Nginx 설정 확인
echo -e "\n${BLUE}[4] Nginx 설정 확인${NC}"
echo "----------------------------------------"

if sudo nginx -t 2>&1 | grep -q "successful"; then
    echo -e "${GREEN}✓ Nginx 설정: 정상${NC}"
else
    echo -e "${RED}✗ Nginx 설정: 오류${NC}"
    ERRORS=$((ERRORS + 1))
    echo "  오류 내용:"
    sudo nginx -t 2>&1 | grep -i error || echo "  확인 불가"
fi

# Nginx 에러 로그 확인
echo -e "\n${BLUE}[5] Nginx 에러 로그 확인${NC}"
echo "----------------------------------------"
NGINX_ERRORS=$(sudo tail -10 /var/log/nginx/error.log 2>/dev/null | grep -i "502\|connection refused\|upstream" | wc -l)
if [ "$NGINX_ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}⚠ 최근 502 관련 에러 발견: ${NGINX_ERRORS}건${NC}"
    echo "  최근 에러:"
    sudo tail -5 /var/log/nginx/error.log 2>/dev/null | grep -i "502\|connection refused\|upstream" || echo "  없음"
else
    echo -e "${GREEN}✓ 최근 502 관련 에러 없음${NC}"
fi

# 6. 요약 및 해결 방법
echo ""
echo "=========================================="
echo "진단 결과"
echo "=========================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ 모든 검사 통과! 502 오류가 해결되었을 가능성이 높습니다.${NC}"
    echo ""
    echo "서비스 상태:"
    echo "  - 백엔드: $(systemctl is-active matchday-backend 2>/dev/null || echo 'unknown')"
    echo "  - 프론트엔드: $(systemctl is-active matchday-frontend 2>/dev/null || echo 'unknown')"
    echo "  - Nginx: $(systemctl is-active nginx 2>/dev/null || echo 'unknown')"
    echo ""
    echo "브라우저에서 다시 접속해보세요."
else
    echo -e "${YELLOW}⚠ ${ERRORS}개의 문제가 발견되었습니다.${NC}"
    if [ $FIXES -gt 0 ]; then
        echo -e "${GREEN}  → ${FIXES}개의 문제가 자동으로 해결되었습니다.${NC}"
    fi
    echo ""
    echo "추가 해결 방법:"
    echo ""
    echo "1. 모든 서비스 재시작:"
    echo -e "   ${BLUE}cd ~/Matchday-Scout && ./restart.sh${NC}"
    echo ""
    echo "2. 프론트엔드 빌드 확인 (가장 흔한 원인):"
    echo -e "   ${BLUE}cd ~/Matchday-Scout/frontend${NC}"
    echo -e "   ${BLUE}ls -la .next${NC}"
    echo -e "   ${BLUE}npm run build${NC}"
    echo -e "   ${BLUE}sudo systemctl restart matchday-frontend${NC}"
    echo ""
    echo "3. 상세 로그 확인:"
    echo -e "   ${BLUE}sudo journalctl -u matchday-backend -n 50${NC}"
    echo -e "   ${BLUE}sudo journalctl -u matchday-frontend -n 50${NC}"
    echo -e "   ${BLUE}sudo tail -50 /var/log/nginx/error.log${NC}"
    echo ""
    echo "4. 포트 리스닝 확인:"
    echo -e "   ${BLUE}sudo ss -tlnp | grep -E ':(3000|8000)'${NC}"
fi

echo ""
echo "=========================================="

