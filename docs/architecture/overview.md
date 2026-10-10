# 아키텍처 개요

단일 Python 패키지 `argos` ([`src/argos/`](../../src/argos/)) 와, 이를 호출하는 CLI ([`scripts/`](../../scripts/)) 로 구성된다. 저장소는 DuckDB 파일 하나(`data/db/argos.duckdb`, gitignore) 다.

핵심 흐름: **지연 입력 → 전파 시뮬레이션 → 회복 시나리오 3개 → 자원 최적화 → OCC 관리자 승인**
지연 입력 단계는 사람이 트리거 편과 지연 분을 직접 넣는다. 예측 모델은 연결하지 않는다 ([ADR 0005](../decisions/0005-prediction-not-wired.md)).

## 현재 의존 방향 (실제 import 기준, 2026-10-07)

함수 안에서 하는 지연 import 도 포함한다. 진단 [1.2](../harness/00-diagnosis.md) 그래프에 `cli_guard` 를 더한 것이다.

```
ui.dashboard ──► simulation.propagation, config
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

scripts/* ──► 각 모듈, cli_guard, config   (editable 설치로 import, sys.path 조작 없음)
```

순환 import 는 없다.

## 레이어 규칙 (목표)

| 레이어 | 모듈 | import 해도 되는 대상 | 하지 말 것 |
|---|---|---|---|
| 0 도메인 | [domain](domain.md) | domain 내부만 | I/O, LLM, 다른 argos 모듈 import |
| 1 데이터 | [data_gen](data_gen.md), `prediction`, `config` | domain, config | agents·ui import |
| 1 계산 | [simulation](simulation.md), [optimization](optimization.md) | domain | 서로 상수 복사 ([ADR 0001](../decisions/0001-domain-single-source.md)) |
| 1 독립 | [uav](uav.md) | uav 내부 | OCC 쪽 모듈 import |
| 2 오케스트레이션 | [agents](agents.md) | 레이어 0·1, config | 승인 없는 확정 경로 ([ADR 0004](../decisions/0004-all-approvals-via-human-gate.md)) |
| 3 진입점 | [ui](ui.md), `scripts/` | 모든 레이어 | 승인 로직을 agents 밖에서 따로 구현 |

추가 규칙:

- DuckDB 를 직접 import 하는 것은 레이어 1 데이터(`data_gen`, `prediction`), 레이어 3, `cli_guard` 만 된다. domain·계산·오케스트레이션의 I/O 는 부채다 (D8, 아래).
- Claude 호출(`anthropic`, `langchain_anthropic`)은 `agents.occ_graph` 에서만 한다 ([conventions](../conventions.md) LLM 호출).
- `cli_guard` 는 `scripts/` 전용이다. `argos` 패키지 안에서 import 하지 않는다.

## 경계 강제 (import-linter)

위 규칙은 [`pyproject.toml`](../../pyproject.toml) 의 `[tool.importlinter]` contracts 로 강제한다. `python scripts/verify.py` 의 `import contracts` 단계(`lint-imports`)가 검사하고, CI 도 같은 명령을 돈다. 함수 안의 지연 import 도 잡는다.

| contract id | 강제하는 규칙 |
|---|---|
| `layers` | `ui → agents → {simulation, optimization, data_gen, prediction, uav} → config → domain`. 위에서 아래로만 import. 중괄호 안 모듈끼리는 서로 import 하지 않는다 |
| `compute-domain-only` | simulation, optimization 은 config 도 import 하지 않는다 |
| `uav-standalone` | uav 는 config, domain 도 import 하지 않는다 |
| `cli-guard-entry-only` | 패키지 안에서 `cli_guard` import 금지 |
| `no-db-io-in-compute` | domain, simulation, optimization, agents → `duckdb` 금지 |
| `llm-via-occ-graph` | `agents.occ_graph` 밖에서 `anthropic`, `langchain_anthropic` import 금지 |

- **baseline**: 현재 위반은 contract 의 `ignore_imports` 에 진단 항목 번호와 함께 적었다. 지금은 `no-db-io-in-compute` 의 3줄(D8)뿐이다.
- baseline 은 늘리지 않는다. 위반을 고치면 해당 줄을 지운다. 지우지 않으면 import-linter 가 "일치하지 않는 ignore" 로 실패시킨다.
- `scripts/` 는 패키지 밖이라 검사 대상이 아니다.

## 레이어 공통 부채

- **계산과 I/O 가 섞임 (D8)**: 계산 클래스 안에서 DuckDB 를 직접 읽는다. `DelayPropagator.load_flights`, `_find_spare_aircraft`, `AircraftAssigner.load_from_db`, `agents.tools.run_crew_optimisation` 이 그렇다.
- **DB 경로 결정 방식이 여러 가지 (D3)**: 규칙은 [conventions](../conventions.md) 에 있다.
- **로깅·결과 타입이 섞임 (D9, D10)**: 규칙은 [conventions](../conventions.md) 에 있다.

## 전역 제약

- 모든 timestamp 는 UTC 로 저장한다.
- FAR 117 안전 제약은 완화하지 않는다 ([ADR 0002](../decisions/0002-fdp-hard-constraint.md)).
- 회복 조치 확정에는 사람의 승인이 필요하다 ([ADR 0004](../decisions/0004-all-approvals-via-human-gate.md)).
