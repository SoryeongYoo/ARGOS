# simulation

[`src/argos/simulation/propagation.py`](../../src/argos/simulation/propagation.py)

## 책임

한 편의 지연이 같은 기체의 다음 rotation 으로 어떻게 번지는지 계산하고, 회복 시나리오 3개를 만든다. 시나리오는 LLM 이 아니라 결정적 코드가 만든다. LLM 은 이를 설명만 한다 (진단 D5).

## 공개 인터페이스

- `DelayPropagator(db_path)`: `load_flights`, `build_rotation_graph`(NetworkX DAG), `propagate`, `generate_scenarios`
- 결과 타입: `FlightNode`, `PropagationResult`, `RecoveryScenario` (dataclass)
- `RecoveryScenario.cost_index` 는 운항 CI 가 아닌 0~1 상대 비용이다. → [ADR 0003](../decisions/0003-rename-relative-cost.md)

## 핵심 가정

- ICN 출발 왕복. 정의는 [conventions](../conventions.md) 에 있다.
- 한 홉당 전파 지연 상한은 300분(`_MAX_PROPAGATED_DELAY`)이다. 이를 넘으면 운항상 결항으로 본다.

## 의존해도 되는 대상

domain 만 된다. 현재는 argos 내부 import 가 없고, 필요한 상수를 로컬에 복사해 쓴다.

## 알려진 부채

- **D2**: 해소. 턴타임·기종 호환은 [`domain/fleet.py`](../../src/argos/domain/fleet.py) 를 쓴다.
- **C5**: footprint `2·block + 2·turn` 가 코드에 박혀 있다.
- **D8**: 계산 클래스가 DuckDB 를 직접 읽는다.
- **C3**: `cost_index` 이름 충돌.
