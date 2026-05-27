# ARGOS — Airline Route & Ground Operations System

**AI 기반 인천 허브 항공사 운항통제센터(OCC) 의사결정 지원 시스템**  
항공사 포트폴리오 프로젝트 · Python 3.12 · 테스트 80개 통과

---

## 개요

ARGOS는 인천국제공항(ICN/RKSI)을 허브로 하는 항공사의 운항통제센터(OCC) 핵심 워크플로우를 구현합니다.

```
지연 감지  →  전파 시뮬레이션  →  회복 시나리오 3개 자동 생성  →  OCC 관리자 최종 승인
```

고전적 OR 기법(ILP/CP-SAT), ML 예측(LightGBM), 그래프 알고리즘(NetworkX), LangGraph 멀티 에이전트(Claude Sonnet)를 하나의 OCC 의사결정 지원 도구로 통합했습니다. **회복 조치는 반드시 인간의 명시적 승인 후에만 실행됩니다.**

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| 데이터 저장소 | DuckDB (단일 파일 분석 DB) |
| ML 예측 | LightGBM (이진 지연 분류기) |
| 지연 전파 | NetworkX DAG |
| 기재 재배정 | OR-Tools CP-SAT |
| 승무원 스케줄링 | OR-Tools CP-SAT + FAR 117 |
| 멀티 에이전트 OCC | LangGraph + Claude Sonnet (`claude-sonnet-4-6`) |
| UAM/UTM 연동 | ACROSS API 시뮬레이션 (국토교통부 UTM) |
| 대시보드 | Streamlit + Plotly |

---

## 프로젝트 구조

```
ARGOS/
├── src/argos/
│   ├── config.py                   # 설정 (pydantic-settings, .env)
│   ├── data_gen/
│   │   ├── generator.py            # 합성 운항 데이터 생성기
│   │   ├── routes.py               # ICN 기반 60개 노선 정의
│   │   ├── schemas.py              # Pydantic 모델 + DuckDB DDL
│   │   └── validator.py            # 데이터 품질 검증
│   ├── domain/
│   │   ├── block_time.py           # 항공기 성능 테이블 + CI 보정
│   │   ├── far117.py               # FAR 117 비행 근무 시간 제한 (하드 컨스트레인트)
│   │   ├── mct.py                  # ICN T1/T2 최소 연결 시간 매트릭스
│   │   └── cost_index.py           # DOC 최소화 CI 그리드 서치
│   ├── prediction/
│   │   ├── features.py             # 피처 엔지니어링 (시간, 요일, 기상 등)
│   │   └── model.py                # LightGBM 지연 예측기 (P(지연 ≥ 15분))
│   ├── simulation/
│   │   └── propagation.py          # NetworkX 기재 회전 DAG + 시나리오 3개 생성
│   ├── optimization/
│   │   ├── aircraft.py             # CP-SAT 기재 재배정 ILP
│   │   └── crew.py                 # CP-SAT 승무원 로스터 (기장/부기장, FAR 117)
│   ├── agents/
│   │   ├── state.py                # OCCState TypedDict
│   │   ├── tools.py                # 도메인 모듈을 감싸는 LangChain 도구
│   │   └── occ_graph.py            # LangGraph StateGraph (7개 노드, Human-in-the-loop)
│   ├── uav/
│   │   ├── models.py               # UAMVehicle, Vertiport, FlightPlan4D, ACROSSResponse
│   │   ├── network.py              # ICN 허브 버티포트 네트워크 (NetworkX)
│   │   ├── airspace.py             # ICN CTR / ILS 충돌 감지
│   │   └── across_client.py        # ACROSS UTM 클라이언트 (시뮬레이션 모드)
│   └── ui/
│       └── dashboard.py            # Streamlit OCC 대시보드 (2개 탭)
├── scripts/
│   ├── setup_db.py                 # DuckDB 스키마 초기화
│   ├── generate_data.py            # 3년치 합성 데이터셋 생성
│   ├── validate_data.py            # 데이터 품질 검증
│   ├── train_model.py              # LightGBM 예측 모델 학습
│   ├── simulate_delay.py           # CLI에서 지연 전파 실행
│   └── run_occ.py                  # LangGraph OCC 에이전트 실행 (dry-run 또는 전체)
├── tests/
│   ├── test_data_gen/              # 7개 테스트
│   ├── test_optimization/          # 39개 테스트 (기재 + 승무원)
│   ├── test_agents/                # 9개 테스트
│   └── test_uav/                   # 25개 테스트
├── notebooks/
│   └── 01_eda.ipynb                # 탐색적 데이터 분석 노트북
└── data/
    └── db/
        └── argos.duckdb            # 항공편 161,868건 · 항공기 58대 · 노선 60개
```

---

## 빠른 시작

```bash
# 1. 환경 생성
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# 2. API 키 설정
cp .env.example .env
# → ANTHROPIC_API_KEY=sk-ant-... 추가

# 3. DB 초기화 및 데이터 생성
python scripts/setup_db.py
python scripts/generate_data.py          # 3년치 전체 데이터셋 (~2분)
# python scripts/generate_data.py --start 2024-01-01 --end 2024-06-30  # 빠른 실행

# 4. 데이터 품질 검증
python scripts/validate_data.py

# 5. 지연 예측 모델 학습
python scripts/train_model.py

# 6. 테스트 실행
pytest                                   # 80개 테스트, 약 10초

# 7. 대시보드 실행
streamlit run src/argos/ui/dashboard.py
```

---

## 핵심 모듈

### 지연 전파 시뮬레이터 (`simulation/propagation.py`)

당일 스케줄에서 기재 회전 방향 그래프(DAG)를 구성하고, 동일 기재의 후속 편에 출발 지연이 연쇄 전파되는 과정을 시뮬레이션합니다.

```python
from argos.simulation.propagation import DelayPropagator

propagator = DelayPropagator(db_path=Path("data/db/argos.duckdb"))
flights_df = propagator.load_flights(date(2024, 6, 15))
G = propagator.build_rotation_graph(flights_df)

result = propagator.propagate(G, trigger_flight_id, initial_delay_minutes=120)
print(f"연쇄: {result.cascade_depth}편, 영향 여객 {result.total_pax_impacted}명")

scenarios = propagator.generate_scenarios(G, trigger_flight_id, 120, dep_date)
# → RecoveryScenario 3개: 수용(Accept) / 기재 교체(Swap) / 결항(Cancel)
```

### 기재 재배정 최적화 (`optimization/aircraft.py`)

CP-SAT ILP로 혼란 발생 편에 기종 호환성과 시간 중복 없는 조건(왕복 운항 범위) 하에서 커버 여객 수를 최대화하는 기재를 배정합니다.

```python
from argos.optimization.aircraft import AircraftAssigner

assigner, tasks, resources = AircraftAssigner.load_from_db(
    db_path=Path("data/db/argos.duckdb"),
    op_date=date(2024, 6, 15),
    disrupted_flight_ids=[...],
)
result = assigner.solve(tasks, resources, op_day=date(2024, 6, 15))
print(result.summary())
```

### 승무원 스케줄링 (`optimization/crew.py`)

CP-SAT으로 혼란 발생 편에 기장/부기장 쌍을 배정합니다. FAR 117 §117.65(a) 일일 비행 시간 제한을 강제하며, 사후 검증에서 `far117.is_fdp_legal()`을 호출해 FDP 구간 합법성을 확인합니다.

```python
from argos.optimization.crew import CrewAssigner

crew_pool = CrewAssigner.generate_crew(op_day=date(2024, 6, 15))
assigner = CrewAssigner()
result = assigner.solve(legs, crew_pool, op_day=date(2024, 6, 15))
print(result.summary())
# FAR 117 위반 사항은 result.far117_violations에 표시
```

### LangGraph OCC 에이전트 (`agents/occ_graph.py`)

7개 노드로 구성된 StateGraph입니다. `human_gate` 노드는 `interrupt()`를 사용해 조치가 기록되기 전 OCC 관리자 승인을 위해 반드시 일시 정지합니다.

```
시뮬레이션 → 분석 → 최적화 → OCC 브리핑 → 승인 대기 ──► 실행
                                                      └──► 중단
```

```python
from argos.agents.occ_graph import run_until_approval, resume_after_approval

state, graph = run_until_approval(
    db_path="data/db/argos.duckdb",
    op_date="2024-06-15",
    trigger_flight_id="<uuid>",
    initial_delay_minutes=120,
)
print(state["scenario_briefing"])          # Claude가 작성한 OCC 브리핑

final = resume_after_approval(graph, approved_scenario_id=2, approval_notes="승인")
print(final["execution_summary"])
```

**CLI (dry-run, API 키 불필요):**
```bash
python scripts/run_occ.py --auto --delay 120 --date 2024-06-15 --dry-run
```

**전체 실행 (`ANTHROPIC_API_KEY` 필요):**
```bash
python scripts/run_occ.py --auto --delay 120 --date 2024-06-15
```

### UAM / ACROSS (`uav/`)

ICN 허브 UAM 네트워크(버티포트 7개, 항로 14개)를 모델링하고, eVTOL 비행 계획 승인을 위한 한국 ACROSS UTM 시스템을 시뮬레이션합니다.

```python
from argos.uav.across_client import ACROSSClient

client = ACROSSClient()                    # 시뮬레이션 모드
plan, response = client.suggest_uam_alternative(
    delayed_flight_number="KE001",
    delayed_pax=10,
    origin_vertiport_id="SBR",            # 송도
    dest_vertiport_id="YDP",              # 여의도
    etd_utc=datetime(2024, 6, 15, 3, 0, tzinfo=timezone.utc),
)
print(response.approved, response.message)
```

충돌 감지 항목: ICN CTR 고도 제한(AGL 1,000ft 이하), ILS 진입 복행 구역 보호, 야간 소음 운항 통제(23:00–06:00 KST), UAM 간 분리 기준(최소 0.3NM).

---

## OCC 대시보드

```bash
streamlit run src/argos/ui/dashboard.py
```

**탭 1 — OCC 운항 현황**
- KPI 카드: 총 운항편, 지연 편수, 결항 편수, 영향 여객 수
- 지연 하이라이트 표시 Plotly 노선 지도
- 색상 코드 상태별 출발 스케줄 테이블
- 지연 시뮬레이션: 연쇄 전파 경로, 승인 버튼이 있는 회복 시나리오 3개 카드
- 출발 지연 시간 히스토그램

**탭 2 — UAM / ACROSS**
- CTR 회피 색상 코딩 버티포트 네트워크 지도 (OpenStreetMap)
- 실시간 충돌 감지가 포함된 ACROSS 비행 계획 제출
- 버티포트 등록 테이블

---

## 주요 도메인 상수

| 상수 | 값 | 출처 |
|------|-----|------|
| 허브 | ICN (RKSI), UTC+9 | 대한항공 네트워크 |
| 운용 기종 | B737-800, A321neo, B777-300ER, B787-9, B747-8i | KE 기단 |
| 협동체 최소 지상 시간 | 45분 | ICN 지상 운영 |
| 광동체 최소 지상 시간 | 60분 | ICN 지상 운영 |
| FAR 117 최대 비행 시간 | 하루 8시간 | 14 CFR §117.65(a) |
| FAR 117 최소 휴식 | 10시간 | 14 CFR §117.25 |
| ICN CTR 반경 | 5NM | 한국 AIP |
| UAM 고도 상한 (CTR 내) | AGL 1,000ft | 국토교통부 UAM 가이드라인 |
| UAM 간 분리 기준 | 0.3NM | ACROSS 초안 표준 |

---

## 데이터셋

| 테이블 | 행 수 | 설명 |
|--------|-------|------|
| `flights` | 161,868 | 3년치 합성 스케줄 (2022–2024), 60개 노선 |
| `routes` | 60 | 6개 권역 ICN 기반 노선 |
| `aircraft` | 58 | KE 스타일 기재 등록부 (HL7xxx / HL8xxx / HL80xx) |
| `route_aircraft` | — | 노선별 기종 배정 |
| `weather_events` | — | 지연과 연결된 합성 기상 구간 |
| `delay_codes_ref` | 99 | IATA AHM 730 지연 코드 참조 테이블 |

`scripts/generate_data.py`로 생성 — 순수 Python, API 호출 없음.

---

## 환경 변수

```env
ANTHROPIC_API_KEY=sk-ant-...              # LangGraph OCC 에이전트 실행에 필요
CLAUDE_MODEL=claude-sonnet-4-6            # 기본 추론 모델
CLAUDE_HAIKU_MODEL=claude-haiku-4-5-20251001  # 대량 추론용
DUCKDB_PATH=data/db/argos.duckdb
DATA_START_DATE=2022-01-01
DATA_END_DATE=2024-12-31
RANDOM_SEED=42
```

---

## 테스트

```
tests/
├── test_data_gen/test_validator.py       7개   데이터 품질 검증
├── test_optimization/test_aircraft.py   18개   CP-SAT 기재 배정
├── test_optimization/test_crew.py       21개   CP-SAT 승무원 스케줄링
├── test_agents/test_tools.py             9개   LangGraph 도구 + 그래프 구조
└── test_uav/test_uav.py                 25개   UAM 네트워크, 공역, ACROSS
                                         ────
                                         80개   약 10초
```

```bash
pytest                     # 전체 테스트
pytest tests/test_uav/     # 단일 모듈
pytest -v --tb=short       # 상세 출력
```

---

## 안전 원칙

- **FAR 117은 하드 컨스트레인트입니다.** `far117.max_fdp_hours()`가 근무 시간 제한의 단일 기준입니다. 어떤 코드 경로도 이 제한을 완화하지 않습니다.
- **Human-in-the-loop은 필수입니다.** LangGraph `human_gate` 노드는 회복 조치가 기록되기 전 반드시 일시 정지합니다. 에이전트는 제안하고, OCC 관리자가 결정합니다.
- **시뮬레이션 전용입니다.** 실제 항공사 시스템과 연결되지 않습니다. 모든 데이터는 합성 데이터입니다.