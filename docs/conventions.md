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

## ICN 출발 왕복 가정

- 모든 rotation 은 **ICN 출발 → 목적지 → ICN 복귀** 왕복으로 본다. 목적지에서 다른 곳으로 이어지는 편(W 패턴)은 없다.
- 한 편의 "footprint"(기체나 승무원이 묶이는 시간)는 이 가정에서 나온다. 공식은 [ADR 0001](decisions/0001-domain-single-source.md) 에 있다. 현재 aircraft·propagation 과 crew 의 공식이 다르다 (C5, D2).
- 이 가정을 깨는 노선이나 기능을 추가하려면 footprint 를 쓰는 세 모듈을 함께 바꿔야 한다.

## 정적 검사

- 완료 조건: `python scripts/verify.py` 통과 (ruff check, ruff format, mypy strict, 문서 상대 링크, pytest).
- `# noqa` 는 동작을 바꿔야 고칠 수 있는 경우에만 달고, 이유를 적는다.
- mypy 는 [`pyproject.toml`](../pyproject.toml) 의 `[[tool.mypy.overrides]]` 에 있는 baseline 모듈만 예외다. 모듈을 고치면 override 를 지운다.
- 포맷만 바꾼 커밋은 [`.git-blame-ignore-revs`](../.git-blame-ignore-revs) 에 등록한다.

## 의존성

- 설치는 `pip install -e ".[dev]" -c constraints.txt`. [`constraints.txt`](../constraints.txt) 는 CI(ubuntu-latest, Python 3.12) 에서 verify 가 통과한 버전이다.
- 의존성 업그레이드는 `constraints.txt` 갱신 PR 로만 한다. CI 통과 확인 후 머지한다.
- 고정하지 않으면 CI 가 코드 변경 없이 깨진다: mypy 2.1 → 2.4 에서 ortools stub 해석이 달라져 실패한 적이 있다 (PR #4).
