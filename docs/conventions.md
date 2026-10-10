# 코드 컨벤션

새 코드가 따라야 할 규칙이다. "현재 상태"는 규칙과 어긋나는 기존 코드이고, 고칠 대상이다. 새 코드에서 그 방식을 따라 하면 안 된다.

## 시간

- **저장과 계산은 UTC**, KST(UTC+9)는 화면 표시와 규정 판정(현지 시각 기준)에만 쓴다. DB 의 timestamp 컬럼은 모두 UTC 다.
- 규정 판정에 쓰는 "현지 시각"은 승무원 기지(ICN) 기준 KST 다. 예: FAR 117 보고 시각, UAM 야간 금지 시간대.
- 변환 함수의 단일 위치: TODO(확인 필요). 아직 정해지지 않았다.
- 현재 상태 (진단 C9): 변환 방식이 세 가지다.
  - [`ui/dashboard.py`](../src/argos/ui/dashboard.py): `KST = timezone(timedelta(hours=9))`
  - [`optimization/crew.py`](../src/argos/optimization/crew.py): `+ timedelta(hours=_KST_OFFSET)`
  - [`uav/airspace.py`](../src/argos/uav/airspace.py): `(hour + KST_OFFSET_H) % 24`
- 개발 venv 에는 `pytz` 가 없다. 그래서 DuckDB `TIMESTAMPTZ` 를 `.fetchall()` 로 읽으면 예외가 난다. `.df()` 로 읽는다.

## DB 경로

- **`get_settings().duckdb_path` 만 쓴다.** `.env` 와 `DUCKDB_PATH` 환경변수가 반영된다. 하위 함수에는 경로를 인자나 state 로 넘긴다.
- 테스트는 `data/db` 를 쓰지 않고 [`tests/conftest.py`](../tests/conftest.py) 의 `fixture_db_path` 를 쓴다.
- 현재 상태 (진단 D3): 규칙과 다른 방식이 남아 있다.
  - [`scripts/run_occ.py`](../scripts/run_occ.py): CWD 기준 `data/db/argos.duckdb` 하드코딩
- DB 를 쓰는 스크립트는 `--yes` 없이 먼저 실행해 바꿀 내용을 확인한다 ([`cli_guard.py`](../src/argos/cli_guard.py)).

## SQL

- **파라미터 바인딩(`?`)만 쓴다.** 값을 `.format`, f-string, `%` 로 SQL 문자열에 넣지 않는다.
- 예외: DuckDB replacement scan(`INSERT INTO t SELECT * FROM some_df`)은 변수 이름이 SQL 안에 들어가는 방식이라 허용한다. 이때 ruff 가 F841 을 오탐하므로 `# noqa: F841` 에 사유를 적는다.
- 현재 상태:
  - [`agents/tools.py`](../src/argos/agents/tools.py) `run_crew_optimisation`: `IN ({})` 를 `.format` 으로 조립 (D6)
  - [`data_gen/validator.py`](../src/argos/data_gen/validator.py): 클래스 상수를 f-string 으로 넣음
  - [`cli_guard.py`](../src/argos/cli_guard.py): `SHOW TABLES` 결과의 테이블 이름을 f-string 으로 넣음

## 로깅과 출력

- 라이브러리 코드(`src/argos/`)는 `logging.getLogger(__name__)` 을 쓴다. `print` 는 쓰지 않는다.
- 사람이 보는 콘솔 출력은 진입점(`scripts/`, `cli_guard`)에서 `rich.Console` 로 한다.
- 현재 상태 (진단 D9): `print` 가 generator, validator, aircraft, crew 에 남아 있다. 설정의 `LOG_LEVEL` 은 어디서도 읽지 않는다.

## 결과 타입

| 용도 | 타입 | 예 |
|---|---|---|
| 계산 결과, 내부 값 객체 | `dataclass` | `PropagationResult`, `AssignmentResult`, `GeoPoint` |
| 외부 입력·DB 레코드처럼 검증이 필요한 경계 | Pydantic `BaseModel` | `schemas.Flight`, `RouteParams`, `config.Settings` |
| LangGraph state | `TypedDict` | `agents.state.OCCState` |

- tool 이 반환하는 값은 JSON 직렬화 가능한 dict 다. 현재는 dataclass 를 손으로 변환한다 (D10).
- enum 은 `(str, Enum)` 을 유지한다. `StrEnum` 으로 바꾸면 `str()` 결과가 바뀐다 (UP042 `noqa`).

## LLM 호출

- 모든 Claude 호출은 [`agents/occ_graph.py`](../src/argos/agents/occ_graph.py) 의 `_make_llm()` 하나로 한다. 이 함수는 `langchain_anthropic.ChatAnthropic(api_key=settings.anthropic_api_key)` 를 쓴다. 키를 하드코딩하지 않는다.
- 구조화된 출력은 자유 텍스트 JSON 파싱이 아니라 tool use 로 받는다.
- 기본 모델: 복잡한 추론에는 `claude-sonnet-4-6`, 대량·저비용 작업에는 `claude-haiku-4-5-20251001`.
- 현재 상태 (진단 D4): 모델명이 `_make_llm` 에 하드코딩되어 있다. `settings.claude_model` 과 `claude_haiku_model` 은 쓰이지 않는다.
- 테스트는 `_make_llm` 을 mock 으로 바꾼다. 실제 API 를 호출하는 테스트를 추가하지 않는다 (비용).

## domain 함수의 입력 검증

[`domain/`](../src/argos/domain/) 함수는 규정·성능 값의 기준 출처라, 이상한 입력에 조용히 엉뚱한 값을 돌려주면 세 모듈이 같이 틀린다 ([01-retro](harness/01-retro.md) 5절).

- **정의역 밖 입력은 `ValueError`** 로 거부한다. 메시지에 인자 이름과 받은 값을 넣는다. 예: `max_fdp_hours(num_segments=0)` → `ValueError("num_segments must be >= 1, got 0")`.
- **대체 동작을 두는 경우는 docstring 에 적는다.** 클램프(예: 6구간 초과는 6구간 값), 기본값 대체(예: `fleet.min_turn_minutes` 는 미등록 기종을 협동체 45분으로 처리)처럼 예외 대신 값을 돌려주면, 어떤 입력이 어떤 값이 되는지 docstring 에 쓴다.
- 기존 동작을 옮기는 리팩터링에서는 대체 동작을 `ValueError` 로 바꾸지 않는다. 바꾸려면 호출 지점을 확인한 별도 작업으로 한다.
- 인덱스 계산(`min(x, N) - 1` 등)에는 음수 인덱스 위험이 있다. ruff 로는 잡히지 않는다.

**경계값 테스트 체크리스트** (domain 함수를 추가하거나 바꿀 때):

- 정상 범위 양 끝 (예: 1구간, 6구간)
- 0, 음수
- 상한 + 1 (클램프 확인)
- 미등록 키 (기종 이름, 공항 코드)
- 반환한 컬렉션을 호출자가 바꿔도 domain 테이블이 바뀌지 않는지

## ICN 출발 왕복 가정

- 모든 rotation 은 **ICN 출발 → 목적지 → ICN 복귀** 왕복으로 본다. 목적지에서 다른 곳으로 이어지는 편(W 패턴)은 없다.
- 한 편의 "footprint"(기체나 승무원이 묶이는 시간)는 이 가정에서 나온다. 공식은 [ADR 0001](decisions/0001-domain-single-source.md) 에 있다. 턴타임은 [`domain/fleet.py`](../src/argos/domain/fleet.py) 의 `min_turn_minutes` 하나만 쓴다. footprint 공식은 아직 aircraft·propagation(`2·block + 2·turn`)과 crew(`checkin + 2·block + 1·turn + post`)가 다르다 (C5, D2). 어느 쪽을 기준으로 할지 사람 결정 대기다.
- 이 가정을 깨는 노선이나 기능을 추가하려면 footprint 를 쓰는 세 모듈을 함께 바꿔야 한다.

## 정적 검사

- 완료 조건: `python scripts/verify.py` 통과 (ruff check, ruff format, mypy strict, import contracts, 문서 상대 링크, pytest).
- `# noqa` 는 동작을 바꿔야 고칠 수 있는 경우에만 달고, 이유를 적는다.
- mypy 는 [`pyproject.toml`](../pyproject.toml) 의 `[[tool.mypy.overrides]]` 에 있는 baseline 모듈만 예외다. 모듈을 고치면 override 를 지운다.
- 포맷만 바꾼 커밋은 [`.git-blame-ignore-revs`](../.git-blame-ignore-revs) 에 등록한다.

## 의존성

- 설치는 `pip install -e ".[dev]" -c constraints.txt`. [`constraints.txt`](../constraints.txt) 는 CI(ubuntu-latest, Python 3.12) 에서 verify 가 통과한 버전이다.
- 의존성 업그레이드는 `constraints.txt` 갱신 PR 로만 한다. CI 통과 확인 후 머지한다.
- 고정하지 않으면 CI 가 코드 변경 없이 깨진다: mypy 2.1 → 2.4 에서 ortools stub 해석이 달라져 실패한 적이 있다 (PR #4).

## CI

[`.github/workflows/verify.yml`](../.github/workflows/verify.yml) 의 두 job 이 병렬로 돈다. 둘 다 통과해야 완료다.

| job | 검증하는 것 | 검증하지 않는 것 |
|---|---|---|
| `verify` | `scripts/verify.py` 전체: ruff, mypy, 문서 링크, pytest. 대시보드 스크립트는 AppTest 스모크 테스트([`tests/test_ui/`](../tests/test_ui/))로 실행된다 | Docker 이미지, 실제 서버 기동 |
| `docker` | `docker compose build`, setup 프로필로 DB 생성(`SETUP_START_DATE`=`SETUP_END_DATE`=2024-06-15 하루치), `up -d` 후 `/_stcore/health` 200 | 대시보드 스크립트 실행. health 는 서버만 확인하고, 스크립트는 브라우저 세션이 붙어야 돈다 |

- 대시보드 화면 코드의 오류는 `verify` 의 AppTest 가 잡는다. `docker` job 이 초록이어도 화면이 정상이라는 뜻은 아니다.
- `ANTHROPIC_API_KEY` 는 두 job 모두 주지 않는다. 테스트가 키를 요구하면 버그다.
