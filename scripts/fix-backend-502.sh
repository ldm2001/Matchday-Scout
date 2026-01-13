#!/bin/bash

# 백엔드 502 오류 전용 진단 및 해결 스크립트

echo "=========================================="
echo "백엔드 502 오류 진단 및 해결"
echo "=========================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ERRORS=0
FIXES=0

# 1. 백엔드 서비스 상태 확인
echo -e "\n${BLUE}[1] 백엔드 서비스 상태 확인${NC}"
echo "----------------------------------------"

if systemctl is-active --quiet matchday-backend; then
    echo -e "${GREEN}✓ 백엔드 서비스: 실행 중${NC}"
    systemctl status matchday-backend --no-pager -l | head -3
else
    echo -e "${RED}✗ 백엔드 서비스: 중지됨${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → 백엔드 서비스 시작 시도...${NC}"
    sudo systemctl start matchday-backend
    sleep 3
    if systemctl is-active --quiet matchday-backend; then
        echo -e "${GREEN}  ✓ 백엔드 서비스 시작 성공${NC}"
        FIXES=$((FIXES + 1))
    else
        echo -e "${RED}  ✗ 백엔드 서비스 시작 실패${NC}"
    fi
fi

# 2. 포트 8000 리스닝 확인
echo -e "\n${BLUE}[2] 포트 8000 리스닝 확인${NC}"
echo "----------------------------------------"

if ss -tlnp 2>/dev/null | grep -q ':8000 '; then
    echo -e "${GREEN}✓ 포트 8000: 리스닝 중${NC}"
    ss -tlnp | grep ':8000 '
else
    echo -e "${RED}✗ 포트 8000: 리스닝 안 함${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 3. 백엔드 로그 확인
echo -e "\n${BLUE}[3] 백엔드 최근 로그 확인${NC}"
echo "----------------------------------------"
echo "최근 20줄:"
sudo journalctl -u matchday-backend -n 20 --no-pager 2>/dev/null || echo "로그 확인 불가"

# 4. 백엔드 직접 연결 테스트
echo -e "\n${BLUE}[4] 백엔드 직접 연결 테스트${NC}"
echo "----------------------------------------"
echo -n "localhost:8000/health: "
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200\|404"; then
    echo -e "${GREEN}✓ 연결 가능${NC}"
    curl -s http://localhost:8000/health 2>/dev/null | head -1 || echo ""
else
    echo -e "${RED}✗ 연결 불가${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 5. 가상환경 및 Python 확인
echo -e "\n${BLUE}[5] 가상환경 및 Python 확인${NC}"
echo "----------------------------------------"

BACKEND_DIR="$HOME/Matchday-Scout/backend"
if [ -d "$BACKEND_DIR" ]; then
    echo "백엔드 디렉토리: $BACKEND_DIR"
    
    # 가상환경 확인
    if [ -d "$BACKEND_DIR/venv" ]; then
        echo -e "${GREEN}✓ 가상환경 존재${NC}"
        
        # Python 경로 확인
        VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
        if [ -f "$VENV_PYTHON" ]; then
            echo -e "${GREEN}✓ Python 실행 파일 존재${NC}"
            echo "  경로: $VENV_PYTHON"
            
            # Python 버전 확인
            PYTHON_VERSION=$($VENV_PYTHON --version 2>&1)
            echo "  버전: $PYTHON_VERSION"
            
            # FastAPI 확인
            if $VENV_PYTHON -c "import fastapi" 2>/dev/null; then
                echo -e "${GREEN}✓ FastAPI 설치됨${NC}"
            else
                echo -e "${RED}✗ FastAPI 미설치${NC}"
                ERRORS=$((ERRORS + 1))
                echo -e "${YELLOW}  → FastAPI 설치 필요:${NC}"
                echo -e "${BLUE}    cd $BACKEND_DIR${NC}"
                echo -e "${BLUE}    source venv/bin/activate${NC}"
                echo -e "${BLUE}    pip install -r requirements.txt${NC}"
            fi
            
            # uvicorn 확인
            if $VENV_PYTHON -c "import uvicorn" 2>/dev/null; then
                echo -e "${GREEN}✓ uvicorn 설치됨${NC}"
            else
                echo -e "${RED}✗ uvicorn 미설치${NC}"
                ERRORS=$((ERRORS + 1))
            fi
        else
            echo -e "${RED}✗ Python 실행 파일 없음${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}✗ 가상환경 없음${NC}"
        ERRORS=$((ERRORS + 1))
        echo -e "${YELLOW}  → 가상환경 생성 필요:${NC}"
        echo -e "${BLUE}    cd $BACKEND_DIR${NC}"
        echo -e "${BLUE}    python3 -m venv venv${NC}"
        echo -e "${BLUE}    source venv/bin/activate${NC}"
        echo -e "${BLUE}    pip install -r requirements.txt${NC}"
    fi
else
    echo -e "${RED}✗ 백엔드 디렉토리 없음: $BACKEND_DIR${NC}"
    ERRORS=$((ERRORS + 1))
fi

# 6. 서비스 파일 확인
echo -e "\n${BLUE}[6] 서비스 파일 확인${NC}"
echo "----------------------------------------"

if [ -f "/etc/systemd/system/matchday-backend.service" ]; then
    echo -e "${GREEN}✓ 서비스 파일 존재${NC}"
    echo "서비스 파일 내용:"
    sudo cat /etc/systemd/system/matchday-backend.service | head -15
else
    echo -e "${RED}✗ 서비스 파일 없음${NC}"
    ERRORS=$((ERRORS + 1))
    echo -e "${YELLOW}  → 서비스 파일 생성 필요 (SERVER.md 참고)${NC}"
fi

# 7. 요약 및 해결 방법
echo ""
echo "=========================================="
echo "진단 결과"
echo "=========================================="

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ 모든 검사 통과! 백엔드가 정상 작동 중입니다.${NC}"
    echo ""
    echo "백엔드 상태:"
    echo "  - 서비스: $(systemctl is-active matchday-backend 2>/dev/null || echo 'unknown')"
    echo "  - 포트 8000: $(ss -tlnp 2>/dev/null | grep -q ':8000 ' && echo '리스닝' || echo '리스닝 안 함')"
    echo ""
    echo "브라우저에서 /api 경로를 다시 시도해보세요."
else
    echo -e "${YELLOW}⚠ ${ERRORS}개의 문제가 발견되었습니다.${NC}"
    if [ $FIXES -gt 0 ]; then
        echo -e "${GREEN}  → ${FIXES}개의 문제가 자동으로 해결되었습니다.${NC}"
    fi
    echo ""
    echo "추가 해결 방법:"
    echo ""
    echo "1. 백엔드 서비스 재시작:"
    echo -e "   ${BLUE}sudo systemctl restart matchday-backend${NC}"
    echo ""
    echo "2. 상세 로그 확인:"
    echo -e "   ${BLUE}sudo journalctl -u matchday-backend -n 50 --no-pager${NC}"
    echo ""
    echo "3. 가상환경 재설정 (필요한 경우):"
    echo -e "   ${BLUE}cd ~/Matchday-Scout/backend${NC}"
    echo -e "   ${BLUE}source venv/bin/activate${NC}"
    echo -e "   ${BLUE}pip install --upgrade pip setuptools wheel${NC}"
    echo -e "   ${BLUE}pip install -r requirements.txt${NC}"
    echo ""
    echo "4. 수동으로 백엔드 실행 테스트:"
    echo -e "   ${BLUE}cd ~/Matchday-Scout/backend${NC}"
    echo -e "   ${BLUE}source venv/bin/activate${NC}"
    echo -e "   ${BLUE}uvicorn main:app --host 127.0.0.1 --port 8000${NC}"
    echo ""
    echo "5. 서비스 파일 확인 및 수정:"
    echo -e "   ${BLUE}sudo cat /etc/systemd/system/matchday-backend.service${NC}"
    echo -e "   ${BLUE}sudo systemctl daemon-reload${NC}"
    echo -e "   ${BLUE}sudo systemctl restart matchday-backend${NC}"
fi

echo ""
echo "=========================================="

