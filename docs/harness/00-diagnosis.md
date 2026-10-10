# 00 — 에이전트 작업 환경 진단

- 작성일: 2026-10-01
- 기준 커밋: `9bc5094` (main), 워킹트리 변경은 `.claude/settings.local.json` 하나뿐
- 범위: 조사만 했습니다. 코드와 설정 파일은 수정하지 않았습니다. 이 문서 하나만 새로 만들었습니다.
- 표기:
  - **[확인]** 직접 실행했거나 파일 내용으로 확인한 사실
  - **[추측]** 근거는 있지만 확인하지 못한 판단
- 영향도는 "에이전트가 이 문제 때문에 잘못된 코드를 만들고도 알아채지 못할 가능성"을 기준으로 매겼습니다.

---

## 1. 구조 파악

### 1.1 패키지와 앱 목록 [확인]

단일 Python 패키지 `argos`(`src/argos/`, setuptools, `pyproject.toml`)와 그 주변 실행 진입점으로 이루어져 있습니다.

| 경로 | 역할 | 규모(LOC) | 테스트 |
|---|---|---|---|
| `src/argos/config.py` | `.env` 기반 설정 (pydantic-settings) | 23 | 없음 |
| `src/argos/domain/` | 순수 계산 함수: `far117`, `block_time`, `mct`, `cost_index` | 395 | **없음** (`tests/test_domain/`에 `__init__.py`만 있음) |
| `src/argos/data_gen/` | 합성 데이터 생성(`generator`), 노선 정의(`routes`), 스키마와 DDL(`schemas`), 품질 검증(`validator`) | 1,650 | `validator`만 7개 |
| `src/argos/prediction/` | LightGBM 지연 예측(`features`, `model`) | 296 | **없음** |
| `src/argos/simulation/` | NetworkX 지연 전파와 회복 시나리오 3개 생성 | 472 | 27개 |
| `src/argos/optimization/` | CP-SAT 기재 재배정(`aircraft`), 승무원 배정(`crew`) | 833 | 18개 + 21개 |
| `src/argos/agents/` | LangGraph OCC 그래프(`occ_graph`), LangChain tool 래퍼(`tools`), 상태(`state`) | 681 | 11개 (DB 필요) |
| `src/argos/uav/` | UAM/ACROSS 시뮬레이션 클라이언트, 공역 충돌 검사, 버티포트 네트워크 | 774 | 25개 |
| `src/argos/ui/dashboard.py` | Streamlit 대시보드 (OCC 탭, UAM 탭) | 520 | **없음** |
| `src/argos/ui/` (그 외) | 디자인 시스템 자산: `SKILL.md`, `README.md`, CSS 토큰, 폰트, `preview/*.html`, `ui_kits/occ_dashboard/*.jsx`(React 목업), 스크린샷 | — | — |
| `scripts/*.py` | typer CLI 진입점 10개 (`setup_db`, `generate_data`, `validate_data`, `train_model`, `simulate_delay`, `assign_aircraft`, `roster_crew`, `run_occ`, `uam_demo`, `_smoke_test`) | ~1,370 | 없음 |
| `notebooks/01_eda.ipynb` | EDA | — | 없음 |
| `Dockerfile`, `docker-compose.yml` | 대시보드 컨테이너, `setup` 프로필 | — | — |

### 1.2 의존 방향 (실제 import 기준) [확인]

`grep '^\s*(from|import) argos'` 결과를 정리했습니다. 함수 안에서 하는 지연 import도 포함했습니다.

```
ui.dashboard ──► simulation.propagation
             └─► uav.{across_client, models, network}

agents.occ_graph ──► agents.{state, tools}, config
agents.tools ──► optimization.{aircraft, crew}, simulation.propagation

optimization.crew ──► domain.far117
optimization.aircraft   (argos 내부 import 없음)
simulation.propagation  (argos 내부 import 없음)

prediction.model ──► prediction.features
data_gen.generator ──► config, data_gen.{routes, schemas}
domain.cost_index ──► domain.block_time
uav.across_client ──► uav.{airspace, models, network}

scripts/* ──► 각 모듈 (sys.path.insert로 src/를 경로에 추가)
```

이 그래프에서 확인한 사실:
- 순환 import는 없습니다. 방향은 대체로 `ui/agents → simulation/optimization → domain` 순서입니다.
- **`prediction`을 런타임에서 쓰는 곳이 없습니다.** `DelayPredictor`는 `scripts/train_model.py`만 사용합니다. `agents`와 `ui`는 예측 모델을 로드하지 않습니다. 그래서 핵심 흐름의 첫 단계인 "지연 감지"는 실제로는 사람이 트리거 항공편과 지연 분을 직접 입력하는 방식입니다.
- **`domain` 4개 모듈 중 실제로 쓰이는 것은 `far117` 하나입니다.** 그것도 `crew.py`에서만 씁니다.
  - `block_time`, `mct`, `cost_index`는 `scripts/_smoke_test.py` 외에는 어디서도 import하지 않습니다.
  - 블록타임은 `data_gen/routes.py`에 하드코딩된 `block_times` dict를 씁니다.
  - 턴타임은 각 모듈의 로컬 상수(`_MIN_TURN_*`)를 씁니다.
- **`ui.dashboard`는 `agents`를 거치지 않습니다.** `DelayPropagator`를 직접 호출하고, 승인 버튼은 `st.success` 토스트만 띄웁니다(`dashboard.py:329`). LangGraph `human_gate`는 `scripts/run_occ.py` 경로에서만 동작합니다.

### 1.3 빌드, 테스트, 린트, 타입체크 (직접 실행) [확인]

실행 환경은 `venv/Scripts/python.exe`이고 **Python 3.12.10**입니다. `pyproject`의 `requires-python`은 `>=3.11`이고 Dockerfile은 `python:3.11-slim`을 씁니다. 실행할 때 캐시 파일은 만들지 않도록 했습니다(`-p no:cacheprovider`, `--no-cache`).

| 항목 | 명령 | 결과 | 비고 |
|---|---|---|---|
| 설치/빌드 | `pip install -e ".[dev]"` | 이미 설치되어 있음 (`argos 0.1.0` editable) | 재설치는 하지 않음 |
| 콘솔 엔트리포인트 | `argos-generate --help` | ❌ **실패** `ModuleNotFoundError: No module named 'argos.scripts'` | `pyproject.toml`의 `[project.scripts]`가 존재하지 않는 `argos.scripts.*`를 가리킴. `argos-setup-db`도 같은 원인 |
| 테스트 | `pytest -q` | ✅ **109 passed**, 2 warnings, **75초** | README에는 "80개 테스트, 약 10초"라고 적혀 있음. warning은 protobuf DeprecationWarning |
| 도메인 스모크 | `python scripts/_smoke_test.py` | ✅ 통과 | pytest에 포함되지 않은 단독 스크립트 |
| 린트 | `ruff check src tests` | ❌ **134 errors** (74개 자동 수정 가능) | UP017 32, F401 26, E501 25, I001 13, E402 9, F841 8, E741 7, UP042 7, B007 4 등 |
| 린트 (scripts) | `ruff check scripts` | ❌ 35 errors | CLAUDE.md의 lint 명령은 `scripts/`를 대상에 넣지 않음 |
| 포맷 | `ruff format --check src tests scripts` | ❌ 54개 중 46개 파일 재포맷 대상 | 포맷 규칙이 정해져 있지 않음 (1.4 참고) |
| 타입체크 | `mypy src` (strict) | ❌ **57 errors / 9 files** (31개 파일 검사) | occ_graph 20, validator 16, generator 8, prediction.model 4, agents.tools 4 등. 종류는 `type-arg` 27, `index` 15 순 |
| CI / pre-commit | — | **없음** | `.github/`, `.pre-commit-config.yaml`, Makefile 모두 없음 |
| Docker | `docker compose up` | 실행하지 않음 | — |
| 노트북 | `jupyter lab` | 실행하지 않음 | — |

### 1.4 그 밖의 환경 사실 [확인]

- `CLAUDE.md`는 `cp .env.example .env`를 안내하지만 **`.env.example` 파일이 없습니다.** `.env`에는 키 8개(`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_HAIKU_MODEL`, `DUCKDB_PATH`, `DATA_START_DATE`, `DATA_END_DATE`, `RANDOM_SEED`, `LOG_LEVEL`)가 있습니다. 값은 열어보지 않았습니다.
- 로컬 DB `data/db/argos.duckdb`(78MB)는 gitignore 대상입니다.
  - `flights` 161,868행, 기간 2022-01-01 ~ 2024-12-31(UTC)
  - 테이블 6개
- `models/delay_predictor.lgb`는 git에 커밋되어 있지만 `.dockerignore`에서는 `models/*.lgb`를 제외합니다. compose는 볼륨으로 마운트합니다.
- `streamlit_err.log`, `streamlit_out.log`가 git에 커밋되어 있습니다. `.dockerignore`에는 `*.log`가 있지만 `.gitignore`에는 없습니다.
- 개발 venv에는 `pytz`가 없습니다. 그래서 DuckDB `TIMESTAMPTZ`를 `.fetchall()`로 읽으면 예외가 납니다. 코드는 `.df()`를 써서 이 문제를 피해 가고 있습니다.
- 코드에서 `=` 정렬용 공백 패딩을 넓게 씁니다(예: `occ_graph.py`의 dict, `_MIN_TURN_WIDE   = 60`). 그런데 `ruff format`을 적용하면 이 정렬이 사라집니다.

---

## 2. 에이전트 관점의 장애물

> 각 항목: **영향도** · 근거 경로 · [확인]/[추측]. 섹션 안에서 영향도 순으로 정렬했습니다.

### 2.1 컨텍스트 부족: 코드만 봐서는 알 수 없는 규칙, 암묵적 컨벤션, 도메인 용어

| # | 영향도 | 내용 | 근거 |
|---|---|---|---|
| C1 | **상** | **CLAUDE.md가 실제 코드와 어긋납니다.** 에이전트는 CLAUDE.md를 가장 먼저 신뢰하므로 잘못된 전제로 작업하게 됩니다. [확인]<br>① "generator가 Claude API, prompt caching, tool use로 노선 파라미터를 생성한다"고 적혀 있지만, 실제 `generator.py` 상단 docstring은 "pure Python, no API calls"입니다. `_REGION_PROFILES` 규칙 기반이고 `anthropic` import도 없습니다. 메모리 기록상 2026-05-20에 변경되었습니다.<br>② 스프린트 표에서 Week 4–10이 미완료로 표시되어 있지만 모두 구현되어 있습니다.<br>③ `.env.example`이 없습니다.<br>④ "All Claude API calls go through `anthropic.Anthropic(...)`"이라고 하지만, 유일한 LLM 호출은 `langchain_anthropic.ChatAnthropic`입니다. | `CLAUDE.md`, `src/argos/data_gen/generator.py:1-9`, `src/argos/agents/occ_graph.py:81-90` |
| C2 | **상** | **"FAR 117은 hard constraint"라는 규칙과 구현의 실제 범위가 다릅니다.**<br>CP-SAT 모델에서 hard constraint로 거는 것은 일일 비행시간 480분 하나입니다. FDP 한도는 풀이가 끝난 뒤 `far117_violations`에 기록만 하는 사후 검증입니다. 또한 480분은 `far117.MAX_FT_CALENDAR_DAY_HOURS`를 쓰지 않고 `crew.py`에 상수로 따로 정의되어 있습니다. CLAUDE.md는 "`far117.py`가 기준이고 임의 한도를 쓰지 말 것"이라고 하므로 규칙 위반입니다. [확인]<br>에이전트가 "hard constraint"를 문자 그대로 받아들여 FDP를 솔버 제약으로 옮기는 것이 의도된 방향인지는 알 수 없습니다. | `src/argos/optimization/crew.py:14-28, 54`, `src/argos/domain/far117.py:53` |
| C3 | **상** | **`cost_index`라는 이름이 두 가지 의미로 쓰입니다.** [확인]<br>- `domain/cost_index.py`: 항공 운항의 Cost Index(CI, 연료와 시간 비용의 비율)<br>- `RecoveryScenario.cost_index`: 0.0~1.0 상대 비용 점수(0.2/0.6/1.0/0.8/0.0 하드코딩)<br>LLM 프롬프트에도 `cost index: 0.2` 형태로 들어갑니다. | `src/argos/simulation/propagation.py:106, 321-414`, `src/argos/agents/occ_graph.py:206`, `src/argos/domain/cost_index.py` |
| C4 | 중 | **도메인 상수의 기준 출처가 정해져 있지 않습니다.** [확인]<br>- 블록타임: `routes.py`의 하드코딩 값과 `domain/block_time.calculate_block_time()`이 별도로 존재하고, 후자는 쓰이지 않습니다.<br>- MCT: `domain/mct.py`는 쓰이지 않고, 각 모듈이 45분/60분 턴타임을 따로 씁니다.<br>새 코드를 쓸 때 어느 쪽을 기준으로 삼아야 하는지 알 수 없습니다. | `src/argos/data_gen/routes.py:20-21`, `src/argos/domain/block_time.py`, `src/argos/domain/mct.py` |
| C5 | 중 | **"ICN 출발 왕복" 가정이 여러 곳에 암묵적으로 깔려 있습니다.** 모든 rotation footprint를 `2·block + turn`으로 계산합니다. 이 가정을 정리한 문서는 없고 각 모듈 docstring에 흩어져 있습니다. 게다가 공식이 모듈마다 조금씩 다릅니다(D2 참고). [확인] | `src/argos/optimization/aircraft.py:21-23`, `src/argos/optimization/crew.py:30-32`, `src/argos/simulation/propagation.py:203-206` |
| C6 | 중 | **UI 문구와 디자인 규칙이 `src/argos/ui/SKILL.md`, `README.md`에만 있습니다.** 한국어 중심, 이모지 금지, 버튼 문구 8자 이내, 1·2인칭 금지 같은 규칙입니다. CLAUDE.md에서는 이 문서들을 가리키지 않습니다. 실제 `dashboard.py`도 이 규칙을 지키지 않습니다(✅ 등 이모지 4곳). 디자인 문서는 "Python 3.12"라고 적었지만 프로젝트 기준은 3.11입니다. [확인] | `src/argos/ui/SKILL.md`, `src/argos/ui/README.md:7`, `src/argos/ui/dashboard.py:329-331, 496-498` |
| C7 | 중 | **`src/argos/ui/`에 production 코드와 디자인 목업이 함께 들어 있습니다.** Streamlit(`dashboard.py`) 옆에 React JSX 목업(`ui_kits/`), 정적 HTML, 폰트, 스크린샷, 업로드 이미지가 Python 패키지 안에 있습니다. 에이전트가 "UI 수정"을 요청받았을 때 어느 쪽을 고쳐야 하는지 모호합니다. [확인]<br>[추측] `SKILL.md`는 다른 도구(디자인 툴)에서 쓰려고 만든 것으로 보입니다. `user-invocable: true` frontmatter가 있습니다. | `src/argos/ui/` 전체 |
| C8 | 하 | **도메인 약어 용어집이 없습니다.** OCC, FDP, WOCL, MCT, CI, AHM 730 지연코드, ACROSS, CTR, ILS 등의 약어가 docstring에만 흩어져 있습니다. 지연코드 표는 `schemas.py:IATA_DELAY_CODES`에 있습니다. [확인] | `src/argos/data_gen/schemas.py`, `src/argos/uav/airspace.py`, `src/argos/domain/far117.py` |
| C9 | 하 | **시간대 변환 방식이 세 가지입니다.**<br>- `timezone(timedelta(hours=9))` (dashboard)<br>- `+ timedelta(hours=_KST_OFFSET)` (crew)<br>- `(hour + KST_OFFSET_H) % 24` (uav)<br>"저장은 UTC, KST는 표시용"이라는 규칙은 메모리에만 있습니다. [확인] | `src/argos/ui/dashboard.py:41`, `src/argos/optimization/crew.py:48, 433`, `src/argos/uav/airspace.py:133` |

### 2.2 검증 불가: 테스트 없는 영역, 수동 확인이 필요한 영역

| # | 영향도 | 내용 | 근거 |
|---|---|---|---|
| V1 | **상** | **`domain/`에는 테스트가 하나도 없습니다.** CLAUDE.md가 "authority"라고 지정한 `far117.max_fdp_hours`를 포함해서입니다. 검증 수단은 pytest 밖에 있는 `_smoke_test.py`의 assert 5개뿐입니다. 에이전트가 안전 규칙 테이블을 잘못 고쳐도 `pytest`는 통과합니다. [확인] | `tests/test_domain/__init__.py`(빈 디렉터리), `scripts/_smoke_test.py` |
| V2 | **상** | **에이전트 테스트 11개는 gitignore된 로컬 DB(2024-06-15 데이터)에 의존합니다.** DB가 없으면 `skip`되므로 "통과"로 보입니다. 새 클론이나 CI에서는 OCC 그래프 E2E가 사실상 검증되지 않습니다. [확인]<br>[추측] 데이터 생성이 seed 42로 결정적이라면 재현할 수는 있습니다. 다만 3년치 생성에 README 기준 약 2분이 걸립니다. | `tests/test_agents/test_tools.py:16-24`, `.gitignore` |
| V3 | **상** | **LLM 출력은 검증하지 않습니다.**<br>- E2E 테스트는 `_make_llm`을 `MagicMock`으로 바꿔 고정 응답을 씁니다.<br>- 브리핑 품질, tool 호출 여부, "250단어 이내", "Awaiting OCC manager approval." 종결 같은 프롬프트 지시를 지키는지는 사람이 직접 봐야 합니다.<br>- `node_analyse`에서 LLM이 tool을 호출하지 않으면 `scenarios_raw = []`인 상태로 그대로 진행합니다. [확인]<br>- eval 세트나 golden output이 없습니다. | `src/argos/agents/occ_graph.py:105-144`, `tests/test_agents/test_tools.py:206-280` |
| V4 | **상** | **Streamlit 대시보드에는 테스트가 없습니다.** 과거 로그에는 `use_container_width`(2025-12-31 제거 예정), `Scattermapbox` deprecation 경고가 남아 있습니다. 현재 설치된 streamlit은 1.57.0입니다. [확인]<br>[추측] 이 API들은 현재 버전에서 이미 동작하지 않을 수 있습니다. 실행해서 확인하지는 않았습니다. | `src/argos/ui/dashboard.py`, `streamlit_err.log` |
| V5 | 중 | **`prediction/`에는 테스트가 없습니다.** 커밋된 `models/delay_predictor.lgb`가 지금 코드의 feature 목록과 맞는지 확인할 방법이 없습니다. [확인] | `src/argos/prediction/`, `models/delay_predictor.lgb` |
| V6 | 중 | **린트, 타입체크, 포맷이 모두 실패 상태입니다**(ruff 134, mypy 57, format 46파일). 에이전트가 변경한 뒤 "내 변경으로 새 오류가 생겼는지"를 구분할 기준선이 없습니다. CI와 pre-commit도 없습니다. [확인] | 1.3 표 |
| V7 | 중 | **`scripts/` 10개(typer CLI)에는 테스트가 없고, CLAUDE.md의 lint 대상에도 빠져 있습니다.** `run_occ.py`는 실제 API 키가 필요합니다(`--dry-run` 제외). [확인] | `scripts/`, `CLAUDE.md` Common commands |
| V8 | 중 | **pytest가 75초 걸립니다.** CP-SAT 솔버와 DB 테스트 때문인 것으로 보입니다. 에이전트가 짧은 주기로 반복 실행하기에는 느립니다. [확인]<br>[추측] 대부분의 시간은 `test_agents`와 `test_optimization`에서 쓰입니다. `--durations`로 측정하지는 않았습니다. | `pytest` 실행 결과 |
| V9 | 하 | **Docker 빌드와 노트북은 검증하지 않았습니다.** [확인] | `Dockerfile`, `notebooks/01_eda.ipynb` |

### 2.3 제약 없음: 경계 위반 import, 일관되지 않은 패턴

| # | 영향도 | 내용 | 근거 |
|---|---|---|---|
| D1 | **상** | **Human-in-the-loop 승인 경로가 두 개이고, 강제되는 쪽은 하나뿐입니다.** [확인]<br>- CLI(`run_occ.py`): LangGraph `interrupt` 사용<br>- 대시보드: 버튼을 누르면 토스트만 띄움<br>"Agents propose; humans decide" 규칙이 코드 구조로 보장되지 않으므로, 에이전트가 새 실행 경로를 만들 때 승인 게이트를 빠뜨려도 막을 장치가 없습니다.<br>`build_occ_graph`는 `interrupt_before=["human_gate"]`와 노드 안의 `interrupt()`를 둘 다 사용합니다. E2E 테스트는 통과하지만 이중 게이트라 의도를 읽기 어렵습니다. | `src/argos/ui/dashboard.py:329`, `src/argos/agents/occ_graph.py:269-286, 363` |
| D2 | **상** | **같은 도메인 로직이 3벌씩 복사되어 있고, 값과 공식이 조금씩 다릅니다.** [확인]<br>- `_WIDE_BODY`, `_MIN_TURN_NARROW/WIDE`, `_min_turn()`: `aircraft.py`, `crew.py`, `propagation.py`에 각각 있음<br>- `_TYPE_COMPAT`: `aircraft.py`(모듈 상수)와 `propagation.py`(클래스 속성)에 똑같이 복사됨<br>- rotation footprint 공식이 서로 다름:<br>&nbsp;&nbsp;· aircraft, propagation: `2·block + 2·turn`<br>&nbsp;&nbsp;· crew: `checkin + 2·block + 1·turn + post`<br>한 곳만 고치면 시뮬레이터와 최적화기의 결과가 어긋납니다. | `src/argos/optimization/aircraft.py:40-62`, `src/argos/optimization/crew.py:49-73`, `src/argos/simulation/propagation.py:29-35, 203-206, 420-426` |
| D3 | **상** | **DB 경로를 결정하는 방식이 4가지입니다.** [확인]<br>① `get_settings().duckdb_path` (`.env`/`DUCKDB_PATH` 반영): scripts 대부분, generator<br>② `Path(__file__)` 기준 하드코딩: `dashboard.py:40`. **compose의 `DUCKDB_PATH` 환경변수를 무시합니다.**<br>③ CWD 기준 하드코딩: `run_occ.py:30`, `tests/test_agents/test_tools.py:16`<br>④ 상태나 인자로 전달받음: agents, simulation, optimization | 좌측 경로 |
| D4 | 중 | **LLM 설정이 config를 거치지 않습니다.** [확인]<br>- `occ_graph._make_llm`이 `model="claude-sonnet-4-6"`을 하드코딩합니다. `settings.claude_model`과 `claude_haiku_model`은 어디서도 읽지 않습니다.<br>- CLAUDE.md에는 "system prompt는 prompt-cached"라고 되어 있지만, `ChatAnthropic` 호출에 `cache_control`이 없습니다. | `src/argos/agents/occ_graph.py:81-90`, `src/argos/config.py:10-11` |
| D5 | 중 | **"구조화 출력은 tool use로" 규칙이 부분적으로만 지켜집니다.** [확인]<br>- `node_analyse`: tool을 bind하지만 LLM은 tool을 "호출"할 뿐이고, 시나리오는 결정적 코드(`generate_scenarios`)가 만듭니다.<br>- `node_brief_occ`: 자유 텍스트를 생성합니다.<br>- `node_optimise`: docstring은 "Claude decides"라고 하지만 LLM을 호출하지 않습니다. | `src/argos/agents/occ_graph.py:108-184` |
| D6 | 중 | **SQL 쿼리를 문자열 포맷팅으로 조립합니다.** `flight_id IN ({})`를 `.format`으로 만듭니다. 다른 모듈은 `?` 파라미터 바인딩을 씁니다. [확인]<br>[추측] 입력이 내부 UUID라 지금 당장 위험하지는 않습니다. 하지만 에이전트가 이 패턴을 복사해 퍼뜨릴 수 있습니다. | `src/argos/agents/tools.py:165-175` vs `src/argos/simulation/propagation.py:441-448` |
| D7 | 중 | **import 경로 해결 방식이 두 가지입니다.**<br>- 패키지가 editable로 설치되어 있습니다.<br>- 그런데 모든 `scripts/*`와 `dashboard.py`가 `sys.path.insert(0, ".../src")`를 따로 합니다.<br>이 때문에 `E402`가 9건 납니다. [확인] | `scripts/*.py:6-26`, `src/argos/ui/dashboard.py:23-25` |
| D8 | 중 | **계층 경계가 정의되거나 강제되지 않습니다.** [확인]<br>- `domain`은 "No I/O"라고 문서화되어 있지만, `simulation`과 `optimization`은 계산 로직과 DuckDB I/O를 같은 클래스에 섞습니다(`DelayPropagator.load_flights`, `_find_spare_aircraft`, `AircraftAssigner`의 DB 로더).<br>- `agents.tools`도 직접 SQL을 실행합니다.<br>- import-linter 같은 경계 검사 도구가 없습니다. | `src/argos/simulation/propagation.py:125-160, 438`, `src/argos/optimization/aircraft.py:270`, `src/argos/agents/tools.py:165` |
| D9 | 하 | **로깅 방식이 섞여 있습니다.** `print`(generator, crew, aircraft, validator), `logging.getLogger`(generator, validator, model), `rich.Console`(generator)이 함께 쓰입니다. 설정의 `LOG_LEVEL`은 어디서도 읽지 않습니다. [확인] | `grep print\(|getLogger src` |
| D10 | 하 | **결과 타입을 표현하는 방식이 섞여 있습니다.** `dataclass`(대부분), Pydantic `BaseModel`(`schemas.py`), `TypedDict`(`state.py`)가 함께 쓰입니다. agents 경계에서는 dataclass를 수동으로 dict로 변환합니다. [확인] | `src/argos/agents/tools.py:53-100` |
| D11 | 하 | **`print`와 커밋된 산출물이 정리되지 않았습니다.** `streamlit_*.log`가 커밋되어 있습니다. `models/*.lgb`는 git에는 포함되어 있지만 docker 이미지에서는 빠집니다. [확인] | `.gitignore`, `.dockerignore` |

---

## 3. 영향도 상위 요약

에이전트가 잘못된 변경을 하고도 테스트가 통과할 가능성이 큰 순서입니다.

1. **C1** CLAUDE.md가 사실과 다릅니다. 에이전트가 처음 읽는 문서가 틀려 있습니다.
2. **V1, C2** FAR 117 안전 규칙에 테스트가 없고, "hard constraint"의 실제 범위가 문서와 다릅니다.
3. **D2** 턴타임, 기종 호환, footprint 로직이 3곳에 복사되어 있고 공식이 다릅니다.
4. **D1** 승인 게이트가 대시보드 경로에서는 강제되지 않습니다.
5. **V2, V3** 에이전트 E2E는 로컬 DB에 의존하고, LLM 출력은 mock으로만 검증합니다.
6. **V6** lint, type, format 기준선이 실패 상태라서 새로 생긴 오류를 구분할 수 없습니다.
7. **D3** DB 경로 결정 방식이 4가지입니다.

---

## 4. 답해주셔야 할 질문

### 기준 출처와 우선순위
1. **CLAUDE.md와 코드가 충돌하면 어느 쪽을 정답으로 볼까요?** 예: generator의 Claude API 사용 여부. CLAUDE.md를 코드에 맞게 갱신해도 될까요?
2. **FAR 117 FDP 한도를 CP-SAT의 hard constraint로 옮기는 것이 목표인가요?** 아니면 "솔버 + 사후 검증 + 인간 승인" 구조가 의도된 설계인가요?
3. **`domain/block_time`, `mct`, `cost_index`를 앞으로 실제 기준 출처로 쓸 계획인가요?** 아니면 포트폴리오 시연용 독립 모듈로 둘 건가요? 그에 따라 D2와 C4를 "통합"할지 "현 상태 유지"할지가 정해집니다.
4. **회복 시나리오의 `cost_index`(0~1 상대 비용) 필드명을 바꿔도 될까요?** 바꾸면 LLM 프롬프트와 테스트도 함께 바뀝니다.

### 범위와 경계
5. **대시보드의 "승인" 버튼도 LangGraph `human_gate`를 거치도록 바꾸는 것이 맞나요?** 아니면 대시보드는 시연용이라 지금처럼 두나요?
6. **`prediction`(LightGBM)을 OCC 흐름의 "지연 감지" 단계에 연결할 계획이 있나요?**
7. **`src/argos/ui/`의 디자인 시스템 자산(JSX 목업, HTML preview, 폰트, SKILL.md)을 에이전트가 수정해도 되는 영역인가요?** 패키지 밖(예: `design/`)으로 옮겨도 될까요?
8. **에이전트가 손대면 안 되는 영역이 있나요?** 예: `far117.py` 테이블, `routes.py` 60개 노선 정의, 커밋된 `models/*.lgb`.

### 검증 환경
9. **"통과" 기준을 무엇으로 할까요?**
   - (a) 기존 오류를 먼저 일괄 정리해 0에서 시작
   - (b) 현재 오류를 baseline으로 고정하고 새로 늘지만 않게
   - ruff format을 채택하나요? 채택하면 지금의 `=` 정렬 스타일이 사라집니다.
10. **CI(GitHub Actions)를 도입해도 될까요?** CI에서 DB 의존 테스트를 어떻게 다룰지도 정해야 합니다. 선택지는 소형 fixture DB를 커밋, 테스트 시작 시 짧은 기간 생성, 계속 skip 중 하나입니다.
11. **LLM 출력 검증은 어느 수준까지 원하시나요?** mock만 유지할지, 실제 API를 쓰는 소수 eval 세트(비용 발생)를 둘지 정해야 합니다. 에이전트가 실제 `ANTHROPIC_API_KEY`로 호출해도 되나요?
12. **대시보드 검증은 어느 수준이 필요한가요?** Streamlit `AppTest` 기반 스모크 테스트, 브라우저 스크린샷, 수동 확인 중에서 정해야 합니다.

### 환경과 버전
13. **기준 Python 버전은 3.11인가요, 3.12인가요?** 지금 venv는 3.12, Docker는 3.11, 디자인 문서는 3.12로 적혀 있습니다.
14. **`ortools<9.12` 고정(Windows 크래시 회피)은 계속 유지해야 하나요?** 에이전트의 주 실행 환경은 Windows인가요, Linux/CI인가요?
15. **`[project.scripts]`(현재 깨져 있음)와 `scripts/*.py`의 `sys.path.insert` 중 어느 방식으로 통일할까요?**
16. **커밋된 `streamlit_*.log`, `models/delay_predictor.lgb`의 의도는 무엇인가요?** 지우거나 gitignore에 추가할 대상인가요?

---

## 5. 처리 현황 (2026-10-07 갱신)

위 1~4장은 2026-10-01 시점의 기록이라 수정하지 않는다. 이후 상태만 여기에 적는다.

| 항목 | 상태 | 근거 |
|---|---|---|
| C1 | 해소 | CLAUDE.md 를 지도로 재작성 |
| C2 | 결정됨, 구현 대기 | [ADR 0002](../decisions/0002-fdp-hard-constraint.md) |
| C3 | 결정됨, 구현 대기 | [ADR 0003](../decisions/0003-rename-relative-cost.md) |
| C4, C5, D2 | 결정됨, 구현 대기 | [ADR 0001](../decisions/0001-domain-single-source.md) |
| C6, C7 | 자산 이동 완료(`design/`). dashboard 문구 규칙 불일치는 남음 | [ADR 0006](../decisions/0006-design-assets-in-design-dir.md) |
| C8 | 해소 | [glossary](../glossary.md) |
| C9, D3, D6, D9, D10 | 규칙 문서화, 코드는 그대로 | [conventions](../conventions.md) |
| V1 | 일부 해소: far117 골든 테스트, smoke 이관 | `tests/test_domain/` |
| V2 | 해소: 세션 fixture DB, skip 0 | `tests/conftest.py` |
| V5 | 결정됨, 구현 대기 | [ADR 0005](../decisions/0005-prediction-not-wired.md) |
| V6 | 해소: ruff/format/mypy baseline 0 | `scripts/verify.py` |
| V7 | 일부 해소: scripts 도 lint 대상, 상태 변경 스크립트에 `--yes` 게이트 | `src/argos/cli_guard.py` |
| V8 | 해소: pytest 72초에서 11초로 | `agents.tools.*_SOLVER_TIME_LIMIT_S` |
| D1 | 결정됨, 구현 대기 | [ADR 0004](../decisions/0004-all-approvals-via-human-gate.md) |
| D7 | 해소: `sys.path.insert` 제거, 깨진 `[project.scripts]` 삭제 | |
| D11 | 해소: `streamlit_*.log` 삭제, `*.log` gitignore | |
| D8 | 일부 해소: 경계를 import-linter 로 강제. 계산 클래스의 DuckDB I/O 3곳은 baseline 으로 남음 | [overview](../architecture/overview.md) 경계 강제 |
| V3, V4, V9, D4, D5 | 미착수 | 각 [아키텍처 문서](../architecture/overview.md) 의 알려진 부채 |
