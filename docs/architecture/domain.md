# domain

[`src/argos/domain/`](../../src/argos/domain/)

## 책임

항공 운항 규정과 성능 계산의 **기준 출처**다 ([ADR 0001](../decisions/0001-domain-single-source.md)). 다른 모듈이 같은 값을 따로 정의하면 안 되는 이유는, 시뮬레이터·최적화기·데이터 생성기가 같은 세계를 가정해야 하기 때문이다.

## 공개 인터페이스

| 모듈 | 진입점 | 다루는 것 |
|---|---|---|
| [`rotation.py`](../../src/argos/domain/rotation.py) | `icn_block_in_offset`, `aircraft_rotation_span`, `crew_duty_span`, `crew_fdp_span`, `CREW_CHECK_IN_MINUTES`, `CREW_POST_FLIGHT_MINUTES` | ICN 왕복의 구간. 기체(aircraft, propagation)와 승무원(crew)은 다른 구간을 쓴다. `crew_fdp_span` 은 정의만, 사용처 없음 |
| [`fleet.py`](../../src/argos/domain/fleet.py) | `min_turn_minutes`, `compatible_types`, `is_wide_body`, `WIDE_BODY_TYPES`, `TYPE_SUBSTITUTES`, `MIN_TURN_*_MINUTES` | 광동체 분류, 지상 턴타임, 기종 호환. aircraft·crew·propagation 이 import |
| [`far117.py`](../../src/argos/domain/far117.py) | `max_fdp_hours`, `is_fdp_legal`, `required_rest_hours`, `is_in_wocl`, `check_cumulative_limits`, `augmented_required`, `MAX_FT_*` 상수 | 승무원 근무 한도 |
| [`block_time.py`](../../src/argos/domain/block_time.py) | `calculate_block_time`, `estimate_airborne_time`, `available_aircraft_types` | 블록타임 |
| [`mct.py`](../../src/argos/domain/mct.py) | `get_mct`, `is_connection_valid`, `classify_flight`, `FlightType` | ICN 최소 연결 시간 |
| [`cost_index.py`](../../src/argos/domain/cost_index.py) | `optimal_ci`, `ci_to_mach`, `fuel_penalty_kg`, `time_saving_minutes` | 운항 Cost Index |

## 의존해도 되는 대상

domain 내부만 된다 (`cost_index` → `block_time`). I/O, LLM, DuckDB 는 쓰지 않는다.

## 사람이 결정하는 영역

`far117.py` 의 규정 값은 골든 테스트([`test_far117.py`](../../tests/test_domain/test_far117.py))로 고정되어 있다. 값을 바꿀 필요가 보이면 수정하지 말고 근거 조항과 함께 제안한다. Table B 는 검증 대기 상태다 ([ADR 0002](../decisions/0002-fdp-hard-constraint.md)).

## 알려진 부채

- **C4**: `block_time`, `mct`, `cost_index` 는 런타임에서 쓰이지 않는다. 테스트에서만 호출된다.
- **D2**: 해소. 턴타임·광동체·기종 호환은 `fleet.py`, rotation 구간은 `rotation.py`. 기체 `2·turn` 과 승무원 `1·turn` 은 둘 다 맞는 서로 다른 개념이라 통일하지 않았다 (2026-10-10 결정). → [domain-consolidation](../exec-plans/completed/domain-consolidation.md)
- **`crew._RATING_GROUPS` 는 fleet 분류와 따로 둔다.** 내용(NARROW/WIDE)은 `fleet.WIDE_BODY_TYPES` 와 같지만, 미등록 기종을 **자격 없음**(`None` → 어떤 승무원도 배정 불가)으로 처리한다. `fleet` 은 미등록 기종을 협동체로 본다. 턴타임은 모르는 기종에 기본값을 줘도 되지만 승무원 자격은 안전상 기본값을 주면 안 되므로, 합치지 않는다 (2026-10-10 결정).
- **C2**: far117 은 crew 최적화의 사후 검증에서만 쓰인다. → [fdp-hard-constraint](../exec-plans/active/fdp-hard-constraint.md)
- far117 동작의 의심점(증원 +2h, Table B 값 등) → [bug-backlog](../exec-plans/active/bug-backlog.md)
