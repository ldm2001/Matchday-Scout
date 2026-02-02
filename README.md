# K리그-서울시립대 공개 AI 경진대회 Track2 아이디어 개발 부문 장려상 수상작

> K리그 이벤트 데이터 기반 AI 전술 분석 플랫폼
> Matchday Scout
> **경기 전, 승부는 이미 시작된다**

<img width="1728" height="961" alt="메인 화면 썸네일" src="https://github.com/user-attachments/assets/89b7d5d6-b6fb-405f-adec-bb519653a55f" />
https://youtu.be/jrm1NChYSYc

## 프로젝트 개요

Matchday Scout는 **579,307건의 K리그 이벤트 데이터**를 분석하여 상대팀의 전술적 약점을 파악하고, AI 기반 경기 시뮬레이션을 제공하는 전술 분석 플랫폼입니다.

**K리그-서울시립대 공개 AI 경진대회** 프로젝트로, 감독과 분석관이 경기 전 상대팀을 연구하고 최적의 전술을 수립할 수 있도록 지원합니다.

### 분석 데이터 규모
- **12개 팀** K리그 1 전 팀 데이터
- **198경기** 2024 시즌 전체 경기
- **446명** 선수 개인별 통계
- **579,307건** 이벤트 데이터 (패스, 슈팅, 태클 등)

---

## 핵심 기능

### 1. 공격 패턴 분석
상대팀의 득점 루트를 Phase 단위로 분해하고, **DTW(Dynamic Time Warping) 알고리즘**으로 유사한 공격 패턴을 클러스터링합니다.

**구현 기술**:
- Phase 분할: 10초 이상 공격 중단 시 새로운 Phase로 분리
- DTW 거리 기반 클러스터링 (scikit-learn DBSCAN)
- 슈팅 전환율, 평균 패스 수, 공격 지속 시간 등 지표 제공
- 실시간 피치 리플레이 시각화 (2D 애니메이션)

**주요 지표**:
- 슈팅 전환율: 해당 패턴에서 슈팅까지 연결된 비율
- 발생 빈도: 최근 N경기 내 반복 횟수
- 평균 패스/시간: 패턴의 복잡도 지표

### 2. 세트피스 인텔리전스
코너킥과 프리킥의 루틴을 분석하여 **키커-타겟-존-스윙 패턴**을 추출하고 수비 대응 전략을 제안합니다.

**구현 기술**:
- 코너킥/프리킥 이벤트 시퀀스 추출
- 타겟존 분류 (near_post, far_post, central, penalty_spot)
- 스윙 타입 분류 (inswing/outswing)
- 슈팅 전환율 기반 위험도 평가

**수비 제안 예시**:
- "먼 포스트 집중 마킹 필요 - 70% 타겟률"
- "인스윙 킥 패턴 반복 - 니어포스트 수비 강화"

### 3. 빌드업 허브 탐지
**NetworkX 그래프 이론**을 활용해 팀의 빌드업 핵심 선수를 탐지하고, 해당 선수 압박 시 팀 공격력 저하 효과를 예측합니다.

**구현 기술**:
- 패스 네트워크 그래프 생성 (선수 = 노드, 패스 = 엣지)
- PageRank 알고리즘으로 허브 점수 계산
- Betweenness Centrality로 중개 역할 평가
- 허브 차단 시뮬레이션 (압박 효과 예측)

**분석 결과**:
- 허브 선수 TOP 3 (허브 점수, 패스 수신/전달 통계)
- 3D 패스 네트워크 시각화 (Three.js)
- 압박 타겟 우선순위 제안

### 4. AI 프리매치 시뮬레이션
**VAEP(Valuing Actions by Estimating Probabilities)** 모델과 **Poisson 분포 기반 득점 예측**으로 경기 결과를 시뮬레이션하고, 전술 조합별 승률을 제공합니다.

**구현 기술**:
- VAEP 모델: 각 액션의 득점/실점 확률 변화 계산
- Poisson 모델: 팀별 득점 기댓값 기반 승/무/패 확률 계산
- ThreadPoolExecutor 병렬 시뮬레이션
- 전술 시나리오별 승률 변화 분석

**시뮬레이션 결과**:
- 기본 승부 예측 (승/무/패 확률)
- 전술 적용 후 예측 (최적 전술 조합)
- 승률 개선도 (전술 효과 정량화)
- 핵심 전술 제안 TOP 3 (우선순위, 근거, 기대효과)

### 5. 경기 영상 분석 (비디오 인텔리전스)
**YOLOv8 객체 탐지 모델**로 경기 영상에서 선수 포지셔닝과 전술적 패턴을 자동 추출합니다.

**구현 기술**:
- YOLOv8 선수/공 탐지
- 옵티컬 플로우 기반 움직임 추적
- 포메이션 자동 인식
- 압박 강도/공간 점유율 계산

**분석 항목**:
- 수비 라인 높이 변화
- 선수 간 거리 (컴팩트함 지표)
- 압박 시작 지점 분포
- 공간 점유율 히트맵

### 6. 팀 AI 종합 분석
경기 데이터를 종합하여 팀의 **강점/약점**을 자동 분석하고, 전술적 인사이트를 제공합니다.

**분석 항목**:
- 종합 점수 (0-100점)
- 강점 분석 (득점력, 빌드업, 세트피스)
- 약점 분석 (수비 취약점, 압박 대응력)
- 전술적 인사이트 (개선 제안)

### 7. VAEP 선수 공헌도 평가
**VAEP(Valuing Actions by Estimating Probabilities)** 방법론으로 선수별 공격/수비 기여도를 정량화합니다.

**구현 기술**:
- SPADL(Soccer Action Description Language) 표준 적용
- XGBoost 모델로 액션별 득점/실점 확률 예측
- 선수별 VAEP 점수 집계 (공격 VAEP + 수비 VAEP)

**제공 지표**:
- 전체 공헌도 TOP 5
- 공격 기여도 TOP 5
- 수비 기여도 TOP 5

---

## 기술 아키텍처

### 시스템 구성
```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 16)                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │  Dashboard  │  │ Pitch 2D/3D  │  │  Video Player  │ │
│  └─────────────┘  └──────────────┘  └────────────────┘ │
└───────────────────────────┬─────────────────────────────┘
                            │ REST API
┌───────────────────────────┴─────────────────────────────┐
│                  Backend (FastAPI)                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Routers (teams, patterns, setpieces, network,   │  │
│  │           simulation, video)                      │  │
│  └────────────────────┬─────────────────────────────┘  │
│  ┌────────────────────┴─────────────────────────────┐  │
│  │  Services                                         │  │
│  │  ├─ analyzers/ (pattern, network, setpiece)      │  │
│  │  ├─ vaep/ (model, calc, summary)                 │  │
│  │  ├─ sim/ (match, tactic, rules)                  │  │
│  │  ├─ video/ (pipe, flow, model, store)            │  │
│  │  └─ core/ (data, spadl, spec)                    │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────┐
│              Data Layer (CSV + LRU Cache)                │
│  - 579,307 events (SPADL format)                         │
│  - 198 matches metadata                                  │
│  - 12 teams, 446 players                                 │
└──────────────────────────────────────────────────────────┘
```

### 백엔드 기술 스택
| 카테고리 | 기술 | 용도 |
|---------|------|------|
| **웹 프레임워크** | FastAPI | REST API 서버, 자동 문서화 |
| **데이터 처리** | pandas, numpy | 대용량 이벤트 데이터 처리 |
| **머신러닝** | scikit-learn, XGBoost | 패턴 클러스터링, VAEP 모델 |
| **그래프 분석** | NetworkX | 패스 네트워크, 중심성 분석 |
| **컴퓨터 비전** | YOLOv8, OpenCV | 영상 분석, 선수 탐지 |
| **통계** | scipy, statsmodels | Poisson 모델, 확률 계산 |
| **캐싱** | functools.lru_cache | 반복 분석 결과 캐싱 |
| **병렬 처리** | ThreadPoolExecutor | 시뮬레이션 병렬 실행 |

### 프론트엔드 기술 스택
| 카테고리 | 기술 | 용도 |
|---------|------|------|
| **프레임워크** | Next.js 16 (App Router) | React 19 기반 SSR/CSR |
| **언어** | TypeScript | 타입 안전성 확보 |
| **스타일링** | Tailwind CSS 4, CSS Module | 반응형 디자인 |
| **3D 시각화** | Three.js, @react-three/fiber | 3D 피치, 패스 네트워크 |
| **상태 관리** | React Hooks | useState, useCallback, useRef |
| **API 통신** | Fetch API (with retry) | REST API 클라이언트 |

---

## 주요 알고리즘

### 1. VAEP (Valuing Actions by Estimating Probabilities)
**논문**: Decroos et al., "Actions Speak Louder than Goals" (KDD'19)

```python
# 각 액션의 가치 = 득점 확률 변화 - 실점 확률 변화
VAEP = P(score | action) - P(score | before)
     - (P(concede | action) - P(concede | before))
```

**구현**:
- XGBoost 분류 모델 (득점/실점 확률 예측)
- 10개 액션 단위로 득점 가능성 평가
- 선수별 VAEP 누적 점수 계산

### 2. DTW (Dynamic Time Warping) 패턴 클러스터링
시퀀스 길이가 다른 공격 패턴을 비교하기 위해 DTW 거리를 사용합니다.

```python
# Phase 시퀀스 비교
def dtw_distance(seq_a, seq_b):
    n, m = len(seq_a), len(seq_b)
    dtw_matrix = np.full((n+1, m+1), np.inf)
    dtw_matrix[0, 0] = 0

    for i in range(1, n+1):
        for j in range(1, m+1):
            cost = euclidean_distance(seq_a[i-1], seq_b[j-1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i-1, j],    # insertion
                dtw_matrix[i, j-1],    # deletion
                dtw_matrix[i-1, j-1]   # match
            )
    return dtw_matrix[n, m]
```

### 3. PageRank 허브 탐지
Google의 PageRank 알고리즘을 패스 네트워크에 적용합니다.

```python
# NetworkX PageRank
hub_scores = nx.pagerank(
    pass_network,
    alpha=0.85,  # damping factor
    weight='passes'
)
```

### 4. Poisson 득점 예측
팀별 득점 기댓값을 Poisson 분포로 모델링합니다.

```python
from scipy.stats import poisson

# 팀 A가 x골 넣을 확률
P(goals_A = x) = (λ_A^x * e^(-λ_A)) / x!

# λ_A = 팀 A 공격력 * 팀 B 수비력
λ_A = attack_strength_A * defense_weakness_B
```

## 실행 방법

### 빠른 시작

**터미널 1 - 백엔드**:
```bash
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**터미널 2 - 프론트엔드**:
```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

접속: `http://localhost:3000`


1. **백엔드 디렉토리로 이동**:
```bash
cd backend
```

2. **환경변수 설정**:
```bash
cp .env.example .env
```

3. **Python 가상환경 생성 (선택사항)**:
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

4. **의존성 설치**:
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

5. **서버 실행**:
```bash
uvicorn main:app --reload --port 8000
```

**API 문서**: `http://localhost:8000/docs`

</details>

<details>
<summary><strong>프론트엔드 설치 및 실행</strong></summary>

1. **프론트엔드 디렉토리로 이동**:
```bash
cd frontend
```

2. **환경변수 설정 (선택사항)**:
```bash
cp .env.example .env.local
```

3. **의존성 설치**:
```bash
npm install
```

4. **개발 서버 실행**:
```bash
npm run dev
```

**접속**: `http://localhost:3000`

## 성능 최적화

### 백엔드 캐싱 전략
```python
@lru_cache(maxsize=128)
def get_team_patterns(team_id: int, n_games: int):
    # 반복 요청 시 캐시에서 반환
    pass
```

- LRU 캐시로 분석 결과 재사용
- 파일 변경 감지로 캐시 무효화
- 최대 128개 결과 메모리 캐싱

### 프론트엔드 최적화
- Next.js 이미지 최적화 (`next/image`)
- 순차적 API 로딩 (사용자 경험 우선)
- 시뮬레이션 결과 클라이언트 캐싱
- React.memo로 불필요한 리렌더링 방지

### 병렬 처리
```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(simulate_match) for _ in range(1000)]
    results = [f.result() for f in futures]
```

---

## 참고 문헌

1. **VAEP**: Decroos, T., et al. (2019). "Actions Speak Louder than Goals: Valuing Player Actions in Soccer." In Proceedings of KDD'19.
2. **SPADL**: Decroos, T., et al. (2019). "SPADL: A Soccer Player Action Description Language."
3. **DTW**: Sakoe, H., & Chiba, S. (1978). "Dynamic programming algorithm optimization for spoken word recognition."
4. **PageRank**: Page, L., et al. (1999). "The PageRank Citation Ranking: Bringing Order to the Web."
