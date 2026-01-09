#!/bin/bash

# Git merge 충돌 해결 스크립트

set -e

echo "=========================================="
echo "Git Merge 충돌 해결"
echo "=========================================="

cd ~/Matchday-Scout

echo ""
echo "[1] 현재 Git 상태 확인..."
git status

echo ""
echo "[2] 로컬 변경사항 확인..."
if [ -n "$(git diff --name-only)" ]; then
    echo "변경된 파일:"
    git diff --name-only
    echo ""
    read -p "로컬 변경사항을 커밋하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add -A
        git commit -m "Update server configuration files"
    fi
fi

echo ""
echo "[3] 새로 만든 파일 확인..."
if [ -n "$(git ls-files --others --exclude-standard)" ]; then
    echo "추적되지 않는 파일:"
    git ls-files --others --exclude-standard
    echo ""
    read -p "새 파일들을 Git에 추가하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git add scripts/*.sh
        git commit -m "Add server setup and utility scripts"
    fi
fi

echo ""
echo "[4] 원격 저장소에서 가져오기..."
# merge 전략 설정 (기본값: merge)
git config pull.rebase false

# 원격 변경사항 가져오기
git fetch origin

echo ""
echo "[5] 브랜치 상태 확인..."
git log --oneline --graph --all -10

echo ""
echo "[6] Merge 실행..."
read -p "원격 변경사항을 merge하시겠습니까? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    git pull origin main || git pull origin master || {
        echo "자동 merge 실패. 수동으로 해결이 필요할 수 있습니다."
        echo "충돌이 있다면 해결 후: git add . && git commit"
    }
fi

echo ""
echo "=========================================="
echo "완료!"
echo "=========================================="
echo ""
echo "현재 상태:"
git status

