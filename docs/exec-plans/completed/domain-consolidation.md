# domain 단일 기준 출처로 통합

- 근거: [ADR 0001](../../decisions/0001-domain-single-source.md), 진단 [D2, C4, C5](../../harness/00-diagnosis.md)
- 상태: **완료** (2026-10-10, phase3/boundaries). 1~5단계 결정 모두 반영. 남은 것은 ±15% 밖 블록타임 2쌍의 값 수정 여부(사람 판단, 4단계)뿐

## 목표

턴타임, 기체 분류, 기종 호환, rotation footprint, 블록타임, MCT 를 `domain/` 에서 한 번만 정의하고, 다른 모듈은 이를 import 한다. 이 단계에서는 동작(수치 결과)을 바꾸지 않는다.

## 영향 파일

- `src/argos/domain/`: 새 모듈 `fleet.py`, `rotation.py`
- `src/argos/optimization/aircraft.py`: `_WIDE_BODY`, `_MIN_TURN_*`, `_min_turn`, `_TYPE_COMPAT`, footprint
- `src/argos/optimization/crew.py`: `_WIDE_BODY`, `_MIN_TURN_*`, `_min_turn`, `_crew_footprint`
- `src/argos/simulation/propagation.py`: `_WIDE_BODY`, `_MIN_TURN_*`, `_min_turn`, `DelayPropagator._TYPE_COMPAT`, footprint
- `src/argos/data_gen/routes.py`: 블록타임 출처. 마지막 단계에서 별도로 다룬다

## 단계

1. 고정부터 한다. 지금의 턴타임 값, 기종 호환표, footprint 계산 결과를 세 모듈 각각에서 고정하는 테스트를 추가한다.
2. `domain` 에 턴타임, 광동체 집합, 기종 호환표를 정의하고 세 모듈이 import 하게 바꾼다. 로컬 사본은 지운다.
3. footprint 를 domain 함수로 옮긴다. aircraft/propagation 공식과 crew 공식은 **이름을 달리해 둘 다** 둔다. 둘을 합칠지는 사람이 결정한다.
4. `routes.py` 블록타임과 `domain.block_time.calculate_block_time()` 의 차이를 측정해 표로 보고한다. 교체 여부는 사람이 결정한다. `routes.py` 는 사람이 결정하는 영역이다.
5. `domain/mct.py` 를 런타임에 연결할지 결정해 달라고 보고한다.

## 완료 조건

- `grep -rn "_MIN_TURN_\|_WIDE_BODY\|_TYPE_COMPAT" src/argos` 결과가 `domain/` 안에서만 나온다.
- 1단계에서 만든 고정 테스트를 포함해 `python scripts/verify.py` 가 통과한다.
- 수치 결과(전파, 배정)가 변경 전과 같다.

## 위험

- crew footprint 의 `1·turn` 이 의도인지 버그인지 모른다. 합치면 crew 배정 결과가 바뀐다.
- 블록타임을 바꾸면 합성 데이터와 학습된 예측 모델이 모두 달라진다.

## 진행 기록

### 1단계 (완료)

[`tests/test_domain/test_consolidation_parity.py`](../../../tests/test_domain/test_consolidation_parity.py). 통합 전(main `0c33942`) 출력을 숫자로 고정했다.

- 턴타임: 5개 기종 + 미등록 기종(`A380-800`, `""` → 45분) × block 60/125/600
- footprint: propagation `earliest_icn_ready_utc`·그래프 edge `min_elapsed_minutes`, aircraft 솔버 경계(footprint 정각이면 둘 다 배정, 1분 앞이면 하나), crew `_crew_footprint`·`_validate_far117` release
- 기종 호환: aircraft 는 솔버 배정 결과(6×6), propagation 은 `_find_spare_aircraft` 탐색 순서
- fixture DB(2024-06-15, seed 42): edge 62개, 노드 146개 전파 결과, 시나리오 75개(25 트리거 × 3)의 digest
- 변이 확인: 협동체 턴 45→46 이면 27건, B747-8i 호환 순서를 바꾸면 1건 실패

### 2단계 (완료)

[`domain/fleet.py`](../../../src/argos/domain/fleet.py): `WIDE_BODY_TYPES`, `MIN_TURN_NARROW_MINUTES`/`MIN_TURN_WIDE_MINUTES`, `TYPE_SUBSTITUTES`, `is_wide_body`, `min_turn_minutes`, `compatible_types`.

- 세 모듈의 사본 삭제. 완료 조건 grep(`_MIN_TURN_\|_WIDE_BODY\|_TYPE_COMPAT`)은 `src/argos` 에서 0건이다.
- 미등록 기종 → 45분 동작은 그대로 두고 docstring 에 적었다 ([conventions](../../conventions.md) domain 함수의 입력 검증).
- 비교 테스트 123건이 기대값 변경 없이 통과했다.

### 3단계: footprint (완료)

**결정 (2026-10-10, 사람)**: 둘 다 맞다. 서로 다른 개념이라 통일하지 않고 이름을 나눠 domain 에 둔다.

[`domain/rotation.py`](../../../src/argos/domain/rotation.py):

| 함수 | 공식 | 사용처 |
|---|---|---|
| `icn_block_in_offset` | `2·block + turn` | 공통 기준. crew `_validate_far117` release 계산 |
| `aircraft_rotation_span` | 블록인 + turn | aircraft no-overlap, propagation edge `min_elapsed`·`earliest_icn_ready_utc` |
| `crew_duty_span` | 60 + 블록인 + 30 | crew no-overlap |
| `crew_fdp_span` | 60 + 블록인 | **정의만**. [fdp-hard-constraint](../active/fdp-hard-constraint.md) 에서 사용. 현재 crew 는 duty span 을 FDP 로 쓴다 (그 계획에 메모) |

- `CREW_CHECK_IN_MINUTES`(60), `CREW_POST_FLIGHT_MINUTES`(30)도 crew 에서 domain 으로 옮겼다.
- 음수 block/turn 은 `ValueError` 다 (새 함수의 정의역 검증. 기존 호출자는 음수를 넘기지 않는다).
- 비교 테스트는 crew footprint 를 솔버 배정 경계로 확인하도록 바꾼 뒤(`ce999a3`, 변이 확인 10건 실패) 통합했고, 기대값 변경 없이 통과했다.

아래는 결정 전 보고한 비교다.

| 모듈 | 공식 | 구간 | narrow, block 125 | wide, block 125 |
|---|---|---|---|---|
| aircraft (`solve` no-overlap) | `2·block + 2·turn` | `[dep, dep + 340)` | 340 | 370 |
| propagation (edge `min_elapsed`, `earliest_icn_ready_utc`) | `2·block + 2·turn` | 다음 ICN 출발까지 | 340 | 370 |
| crew (`_crew_footprint`) | `60 + 2·block + 1·turn + 30` | `[dep − 60, dep + 2·block + turn + 30)` | 385 | 400 |
| crew (`_validate_far117` release) | `dep + 2·block + 1·turn + 30` | FDP 종료 | dep+325 | dep+340 |

같은 승무원이 연속 두 편을 맡으려면 출발 간격이 `2·block + turn + 90` 이상이어야 한다. 기체는 `2·block + 2·turn` 이다. 그래서 출발 간격이 최소인 기체 rotation(협동체 `2·block + 90`, 광동체 `2·block + 120`)을 같은 승무원이 이어 탈 수 없다. 차이는 협동체 45분, 광동체 30분이다.

판단 재료 (결정은 하지 않았다):

- 왕복을 따라가면 ICN 블록인 시각은 `dep + 2·block + 1·turn` 이다(목적지 턴 1회). 기체의 두 번째 turn 은 ICN 에서 다음 출발 전 지상 시간이다.
- 이렇게 읽으면 crew 의 `1·turn` 은 같은 블록인 시각에 check-in·post-flight 를 더한 것이다. 두 공식이 서로 다른 자원을 모델링한 것일 수 있다.
- 반대로 crew 도 ICN 턴을 포함해야 한다고 보면 crew footprint 가 turn 만큼 길어진다. 그러면 crew 배정 결과와 FDP 판정이 바뀐다.
- crew FDP 종료 시점(블록인 + 30분) 문제는 [01-retro](../../harness/01-retro.md) 3절 #3, [retro-01-followups](../active/retro-01-followups.md) R2 와 같은 결정이다.


### 4단계: 블록타임 (완료)

**결정 (2026-10-10, 사람)**: `routes.py` 를 기준 출처로 유지한다. `calculate_block_time()` 은 `routes.py` 에 없는 노선용 추정기다 ([domain.md](../../architecture/domain.md), [ADR 0001](../../decisions/0001-domain-single-source.md) 갱신).

- [`test_block_time_vs_routes.py`](../../../tests/test_domain/test_block_time_vs_routes.py): 상대 차이 `(추정 − routes) / routes` 가 ±15% 를 넘으면 `BlockTimeDivergenceWarning` 으로 목록만 낸다. 실패시키지 않는다.
- 2026-10-10 기준 99쌍 중 2쌍이 벗어난다. 값 수정은 사람 결정 대기 (routes.py 는 사람 결정 영역):

| 노선 | 기종 | routes.py | 추정 | 차이 |
|---|---|---|---|---|
| ICN-ALA | B787-9 | 368 | 311 | −15.5% |
| ICN-MNL | B777-300ER | 285 | 241 | −15.4% |

아래는 결정 전 측정(분 단위 차이)이다.

`routes.py` 의 99개 (노선, 기종) 블록타임과 `calculate_block_time(distance_nm, type)` (CI 70, 바람 0) 를 비교했다. 차이는 `계산값 − routes.py` 다.

| 묶음 | 쌍 | 평균 | 최소 | 최대 |
|---|---|---|---|---|
| 전체 | 99 | −6.7 | −63 | +100 |
| 북미 | 12 | +79.4 | +44 | +100 |
| 동남아 | 15 | −53.7 | −63 | −42 |
| CIS | 2 | −52.5 | −57 | −48 |
| 일본 | 20 | −10.8 | −22 | +1 |
| 중국 | 22 | −16.7 | −32 | +3 |
| 유럽 | 11 | +5.5 | +1 | +13 |

- |차이| ≤ 10분은 30쌍, > 30분은 34쌍이다.
- 극단값: ICN-ATL B777-300ER `740` vs `840` (+100), ICN-SIN B777-300ER `450` vs `387` (−63).
- 북미가 크게 양수인 것은 `calculate_block_time` 에 바람이 없기 때문으로 보인다 (동향 제트기류 순풍). routes.py 값이 실제 시간표에 더 가깝다는 근거는 확인하지 않았다.
- 교체하면 합성 데이터, 학습된 예측 모델, 이 계획 1단계의 fixture digest 가 모두 바뀐다. `routes.py` 는 사람 결정 영역이다.

### 5단계: MCT (완료)

**결정 (2026-10-10, 사람)**: 런타임에 연결하지 않는다. MCT(승객·승무원 환승)와 turn(기체 지상 준비)은 다른 개념이다 ([glossary](../../glossary.md), [domain.md](../../architecture/domain.md)). 승객 환승 지연을 모델링할 때 쓴다 → [passenger-connection-delay](../active/passenger-connection-delay.md) (미래 항목).

결정 전 보고:


`domain/mct.py` 는 승객 연결 최소 시간(국제↔국제 60분 등)이다. 기체 턴타임(`fleet.min_turn_minutes`)과 다른 개념이라 이번 통합에서 합치지 않았다. 런타임 호출자는 여전히 없다. 연결 승객 영향(환승 실패)을 전파·시나리오에 넣을지 결정이 필요했다.

### 범위 밖에서 발견한 것

- `crew._RATING_GROUPS` 도 NARROW/WIDE 분류다. 미등록 기종을 자격 없음으로 처리하므로 그대로 둔다 (사람 결정, [domain.md](../../architecture/domain.md) 알려진 부채에 기록).
- 합성 데이터 편명 중복 → [bug-backlog](../active/bug-backlog.md) B7.
