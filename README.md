# Matchday Scout

K리그 이벤트 데이터 기반 AI 전술 분석 플랫폼

<img width="1728" height="962" alt="스크린샷 2026-01-11 오후 11 10 02" src="https://github.com/user-attachments/assets/e3d466cc-160e-40f6-9f43-ec21a3e7bbb4" />

## 프로젝트 구조

```
Matchday-Scout/
├── backend/          # FastAPI 백엔드 서버
├── frontend/         # Next.js 프론트엔드
└── open_track/       # 데이터 파일
```

## 실행 방법

### 백엔드 실행

1. 백엔드 디렉토리로 이동:
```bash
cd backend
```

2. Python 가상환경 생성 및 활성화 (선택사항):
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. 의존성 설치:
```bash
# pip 업그레이드 (권장)
python -m pip install --upgrade pip setuptools wheel

# requirements.txt 설치
pip install -r requirements.txt
```

**설치 오류 발생 시 해결 방법:**

⚠️ **Python 3.12 이상 버전 사용 시:**
- Python 3.12+는 최신 패키지 버전을 자동으로 설치합니다
- `oldest-supported-numpy` 오류가 발생하면 다음 명령어로 해결:
```bash
pip install --upgrade pip setuptools wheel
pip install numpy pandas --upgrade
pip install -r requirements.txt
```

⚠️ **Windows에서 "Failed to build pandas/numpy" 오류 발생 시:**
```bash
# 미리 빌드된 wheel 파일 사용
pip install --upgrade pip setuptools wheel
pip install numpy pandas
pip install -r requirements.txt
```

4. 서버 실행:
```bash
uvicorn main:app --reload --port 8000
```

백엔드 서버가 `http://localhost:8000`에서 실행됩니다.

### 프론트엔드 실행

1. 프론트엔드 디렉토리로 이동:
```bash
cd frontend
```

2. 의존성 설치:
```bash
npm install
```

3. 개발 서버 실행:
```bash
npm run dev
```

프론트엔드가 `http://localhost:3000`에서 실행됩니다.

## 빠른 실행 (두 터미널 사용)

### 터미널 1 - 백엔드:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 터미널 2 - 프론트엔드:
```bash
cd frontend
npm install
npm run dev
```

## API 엔드포인트

백엔드 서버가 실행되면 다음 엔드포인트를 사용할 수 있습니다:

- `http://localhost:8000/` - API 상태 확인
- `http://localhost:8000/health` - 헬스 체크
- `http://localhost:8000/docs` - Swagger API 문서
- `http://localhost:8000/redoc` - ReDoc API 문서

## 기술 스택

### 백엔드
- FastAPI
- Python 3.x
- pandas, numpy, scikit-learn
- networkx, scipy

### 프론트엔드
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- Three.js

