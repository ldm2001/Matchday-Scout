#!/bin/bash

# Matchday Scout 서비스 재시작 스크립트

echo "========================================="
echo "Matchday Scout 서비스 재시작 중..."
echo "========================================="

# 스크립트가 실행되는 디렉토리 확인
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 백엔드 서비스 재시작
echo ""
echo "[1/3] 백엔드 서비스 재시작 중..."
sudo systemctl restart matchday-backend

if [ $? -eq 0 ]; then
    echo "✓ 백엔드 서비스 재시작 완료"
else
    echo "✗ 백엔드 서비스 재시작 실패"
    exit 1
fi

# 프론트엔드 서비스 재시작
echo ""
echo "[2/3] 프론트엔드 서비스 재시작 중..."
sudo systemctl restart matchday-frontend

if [ $? -eq 0 ]; then
    echo "✓ 프론트엔드 서비스 재시작 완료"
else
    echo "✗ 프론트엔드 서비스 재시작 실패"
    exit 1
fi

# Nginx 재시작
echo ""
echo "[3/3] Nginx 재시작 중..."
sudo systemctl restart nginx

if [ $? -eq 0 ]; then
    echo "✓ Nginx 재시작 완료"
else
    echo "✗ Nginx 재시작 실패"
    exit 1
fi

# 서비스 상태 확인
echo ""
echo "========================================="
echo "서비스 상태 확인"
echo "========================================="

echo ""
echo "백엔드 상태:"
sudo systemctl status matchday-backend --no-pager -l | head -n 5

echo ""
echo "프론트엔드 상태:"
sudo systemctl status matchday-frontend --no-pager -l | head -n 5

echo ""
echo "Nginx 상태:"
sudo systemctl status nginx --no-pager -l | head -n 5

echo ""
echo "========================================="
echo "재시작 완료!"
echo "========================================="

