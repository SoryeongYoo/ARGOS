# 아키텍처 개요

단일 Python 패키지 `argos` ([`src/argos/`](../../src/argos/)) 와, 이를 호출하는 CLI ([`scripts/`](../../scripts/)) 로 구성된다. 저장소는 DuckDB 파일 하나(`data/db/argos.duckdb`, gitignore) 다.

핵심 흐름: **지연 입력 → 전파 시뮬레이션 → 회복 시나리오 3개 → 자원 최적화 → OCC 관리자 승인**
지연 입력 단계는 사람이 트리거 편과 지연 분을 직접 넣는다. 예측 모델은 연결하지 않는다 ([ADR 0005](../decisions/0005-prediction-not-wired.md)).

## 현재 의존 방향 (실제 import 기준, 2026-10-07)

함수 안에서 하는 지연 import 도 포함한다. 진단 [1.2](../harness/00-diagnosis.md) 그래프에 `cli_guard` 를 더한 것이다.

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

이 규칙을 도구로 강제하지는 않는다. import-linter 같은 검사가 없다 (진단 D8).

## 레이어 공통 부채

- **계산과 I/O 가 섞임 (D8)**: 계산 클래스 안에서 DuckDB 를 직접 읽는다. `DelayPropagator.load_flights`, `_find_spare_aircraft`, `AircraftAssigner.load_from_db`, `agents.tools.run_crew_optimisation` 이 그렇다.
- **DB 경로 결정 방식이 여러 가지 (D3)**: 규칙은 [conventions](../conventions.md) 에 있다.
- **로깅·결과 타입이 섞임 (D9, D10)**: 규칙은 [conventions](../conventions.md) 에 있다.

## 전역 제약

- 모든 timestamp 는 UTC 로 저장한다.
- FAR 117 안전 제약은 완화하지 않는다 ([ADR 0002](../decisions/0002-fdp-hard-constraint.md)).
- 회복 조치 확정에는 사람의 승인이 필요하다 ([ADR 0004](../decisions/0004-all-approvals-via-human-gate.md)).
