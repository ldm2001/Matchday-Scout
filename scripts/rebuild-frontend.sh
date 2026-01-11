#!/bin/bash

# 프론트엔드 재빌드 스크립트 (캐시 완전 클리어)

set -e

echo "=========================================="
echo "프론트엔드 재빌드 (캐시 클리어)"
echo "=========================================="

cd ~/Matchday-Scout/frontend

echo ""
echo "[1/5] 빌드 캐시 삭제 중..."
rm -rf .next
rm -rf node_modules/.cache
rm -rf .turbo 2>/dev/null || true
echo "✓ 캐시 삭제 완료"

echo ""
echo "[2/5] 환경 변수 확인..."
if [ -f ".env.local" ]; then
    echo "⚠ .env.local 파일 발견:"
    cat .env.local | grep NEXT_PUBLIC_API_URL || echo "  NEXT_PUBLIC_API_URL 없음"
    echo ""
    echo "프로덕션에서는 .env.local의 NEXT_PUBLIC_API_URL이 무시됩니다."
    echo "코드에서 브라우저 환경에서는 항상 상대 경로를 사용합니다."
else
    echo "✓ .env.local 파일 없음"
fi

echo ""
echo "[3/5] 의존성 확인..."
npm install --prefer-offline --no-audit

echo ""
echo "[4/5] 프로덕션 빌드 실행..."
NODE_ENV=production npm run build

echo ""
echo "[5/5] 빌드 확인..."
if [ -d ".next" ]; then
    echo "✓ 빌드 성공: .next 디렉토리 생성됨"
    ls -la .next | head -5
else
    echo "✗ 빌드 실패: .next 디렉토리가 없습니다"
    exit 1
fi

echo ""
echo "=========================================="
echo "빌드 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "  cd ~/Matchday-Scout"
echo "  ./restart.sh"
echo ""

