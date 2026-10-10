# 0001. domain/ 을 도메인 상수·계산의 단일 기준 출처로 한다

- 상태: 승인됨 (2026-10-07). 구현 전
- 관련 진단: [C4, C5, D2](../harness/00-diagnosis.md)

## 맥락

같은 도메인 값과 공식이 여러 곳에 따로 정의되어 있고, 값도 서로 조금씩 다르다.

| 개념 | 기준이 되어야 할 곳 | 현재 실제로 쓰이는 곳 |
|---|---|---|
| 블록타임 | [`domain/block_time.py`](../../src/argos/domain/block_time.py) `calculate_block_time()` | [`data_gen/routes.py`](../../src/argos/data_gen/routes.py) 의 하드코딩 `block_times`. domain 함수는 테스트에서만 호출 (C4) |
| MCT | [`domain/mct.py`](../../src/argos/domain/mct.py) `get_mct()` | 어디서도 import 하지 않음 (C4) |
| 턴타임 (`_MIN_TURN_NARROW=45`, `_MIN_TURN_WIDE=60`), `_WIDE_BODY`, `_min_turn()` | 없음 | `optimization/aircraft.py`, `optimization/crew.py`, `simulation/propagation.py` 에 3벌 (D2) |
| 기종 호환표 `_TYPE_COMPAT` | 없음 | `optimization/aircraft.py`(모듈 상수), `simulation/propagation.py`(클래스 속성) 에 2벌 (D2) |
| rotation footprint | 없음 | aircraft·propagation 은 `2·block + 2·turn`, crew 는 `checkin + 2·block + 1·turn + post` (C5, D2) |

한쪽만 고치면 시뮬레이터와 최적화기의 판단이 어긋나고, 테스트는 이를 잡지 못한다.

## 결정

1. 도메인 상수와 순수 계산은 [`src/argos/domain/`](../../src/argos/domain/) 에만 둔다. 블록타임, MCT, 턴타임, 기종 호환, rotation footprint 가 대상이다.
2. 다른 모듈은 domain 을 import 해서 쓴다. 로컬 사본(`_MIN_TURN_*`, `_WIDE_BODY`, `_TYPE_COMPAT`, `_min_turn`)은 제거 대상이다.
3. domain 은 I/O(DB, 파일, 네트워크)와 LLM 호출을 하지 않는다.
4. footprint 공식 차이(aircraft 와 crew)가 의도인지는 통합 과정에서 확인한다. 확인 전에는 두 공식을 이름을 달리해 domain 에 함께 두고, 하나로 합치지 않는다.

## 결과

- 영향 파일: `optimization/aircraft.py`, `optimization/crew.py`, `simulation/propagation.py`, `data_gen/routes.py`(블록타임 출처), `domain/*`
- 새 도메인 상수를 domain 밖에 정의하는 변경은 리뷰에서 거절한다.

## 후속 작업

- [domain-consolidation](../exec-plans/completed/domain-consolidation.md) (완료 2026-10-10)

## 갱신 (2026-10-10)

결정 4 확인 결과: 두 공식은 둘 다 맞다. 기체는 다음 출발까지(ICN 턴 포함), 승무원은 근무 구간(check-in·마무리 포함)으로 다른 개념이다. [`domain/rotation.py`](../../src/argos/domain/rotation.py) 에 공통 기준 `icn_block_in_offset` 과 `aircraft_rotation_span`, `crew_duty_span`, `crew_fdp_span` 으로 나눠 정의했다.

블록타임 (위 표와 결정 1 을 바꾼다): 기준 출처는 [`data_gen/routes.py`](../../src/argos/data_gen/routes.py) 로 유지한다. `domain.block_time.calculate_block_time()` 은 `routes.py` 에 없는 노선용 추정기다. 두 값의 차이가 ±15% 를 넘으면 [`test_block_time_vs_routes.py`](../../tests/test_domain/test_block_time_vs_routes.py) 가 경고로 목록을 낸다 (실패 아님). 값 수정은 사람이 결정한다. 2026-10-10 기준 99쌍 중 2쌍이 벗어난다.

MCT (결정 1 을 바꾼다): `domain/mct.py` 는 런타임에 연결하지 않는다. MCT 는 승객·승무원 환승 시간이고 turn 은 기체 지상 준비 시간이라 다른 개념이다. 승객 환승 지연을 모델링할 때 쓴다 → [passenger-connection-delay](../exec-plans/active/passenger-connection-delay.md)
