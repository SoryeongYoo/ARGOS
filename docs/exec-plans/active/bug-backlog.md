# 버그 백로그 (Phase 1 발견분)

harness/verify 작업(2026-10) 중 발견했지만, 동작이 바뀌는 수정이라 고치지 않은 것들이다. 각 항목에 "현재 동작을 고정하는 테스트가 있는지"를 함께 적었다.

## 공통 규칙

- **목표**: 각 항목을 버그인지 의도인지 판정하고, 버그면 고친다.
- **완료 조건**: 항목마다 재현 테스트를 먼저 쓰고 → 수정 → `python scripts/verify.py` 통과. far117 값과 관련된 항목은 사람의 승인이 필요하다.
- **위험**: 표시된 항목은 골든 테스트와 충돌한다. 기대값을 바꾸는 근거를 PR 에 적는다.

---

## B1. `max_fdp_hours(num_segments=0)` 이 6구간 값을 반환

- 상태: **해결** (2026-10-08). `num_segments < 1` 이면 `ValueError`. 테스트 `test_max_fdp_hours_rejects_fewer_than_one_segment`. 회고: [01-retro](../../harness/01-retro.md)
- 위치: [`src/argos/domain/far117.py`](../../../src/argos/domain/far117.py) `max_fdp_hours`
- 현상:
  - `seg_idx = min(num_segments, 6) - 1` 이라 0 이면 인덱스가 -1 이 된다.
  - 파이썬 음수 인덱스로 마지막 열(6구간) 값을 조용히 반환한다.
  - 음수 입력은 `-1`~`-5` 가 조용히 다른 열 값을 반환하고 (`-1`→5구간, `-5`→1구간), `-6` 이하는 `IndexError` 다.
- 고정 테스트: 없음. 골든 테스트는 1~6구간과 6 초과 클램프만 고정한다.
- 권장 동작: `num_segments < 1` 이면 `ValueError`. FDP 에는 최소 1구간이 있어야 하므로, 조용히 값을 반환하는 것보다 안전하다.
- 단계:
  1. 호출 지점을 확인한다. `crew.py` `_validate_far117` 은 `num_segs = 2 * len(flight_list)` 를 넘기므로 0 이 들어가지 않는다. 그래서 현재 런타임 영향은 없다. `augmented_required` 는 src 에서 호출하는 곳이 없다. `is_fdp_legal` 과 `augmented_required` 는 `max_fdp_hours` 를 거치므로 같은 검증을 물려받는다.
  2. [`tests/test_domain/test_far117.py`](../../../tests/test_domain/test_far117.py) 에 0, -1 입력이 `ValueError` 를 내는 테스트를 추가한다. 기존 골든 테스트(표 값과 1~6구간, 클램프)는 건드리지 않는다.
  3. `max_fdp_hours` 맨 앞에 입력 검증을 넣는다. 표와 상수는 수정하지 않는다.
  4. `python scripts/verify.py`
- 사람 결정: 불필요. 입력 검증일 뿐 규정 값은 바뀌지 않는다. [ADR 0002](../../decisions/0002-fdp-hard-constraint.md) 의 "검증 대기"는 표 값에만 적용된다.

## B2. `run_crew_optimisation` 의 `midnight_utc` 미사용

- 위치: [`src/argos/agents/tools.py`](../../../src/argos/agents/tools.py) `run_crew_optimisation`
- 현상: `midnight_utc` 를 계산만 하고 쓰지 않는다 (F841 `noqa`). SQL 은 `flight_id IN (...)` 로만 조회하므로 날짜 필터가 없다.
- 판단 필요: 날짜 필터를 넣으려다 빠진 것인지, 단순 잔재인지. `disrupted_flight_ids` 가 이미 해당 날짜 편이므로 결과는 같을 가능성이 높다. TODO(확인 필요)
- 단계: 의도를 확인하고, 잔재면 삭제한다. 같은 함수의 `.format` SQL(D6)도 함께 바인딩으로 바꾼다.

## B3. ILS 회랑을 원형으로 판정

- 위치: [`src/argos/uav/airspace.py`](../../../src/argos/uav/airspace.py) `check_ils_corridor`
- 현상:
  - `_ILS_CORRIDORS` 의 `hdg`(접근 방향)와 `width_nm`(회랑 폭)을 쓰지 않는다 (B007 `noqa`).
  - 활주로 끝에서의 거리만 보므로 회랑이 원형으로 판정된다.
  - 그래서 회랑 옆쪽은 과잉 경고, 회랑 끝 바깥쪽은 놓칠 수 있다.
- 고정 테스트: 없음. `tests/test_uav/test_uav.py` 에는 `assess_conflicts` 의 정상 계획과 야간 금지 테스트만 있다.
- 단계: 접근 방향 기준 좌표계에서 종·횡 거리로 판정하도록 바꾼다. 경계값 테스트를 먼저 쓴다.

## B4. 증원 승무원 FDP 를 "기본 + 2h" 로 계산

- 위치: [`src/argos/domain/far117.py`](../../../src/argos/domain/far117.py) `max_fdp_hours(augmented=True)`, `required_rest_hours`
- 현상:
  - 증원 승무원 한도를 Table B + `MAX_FDP_EXTENSION`(2h) 로 계산한다.
  - 규정상 증원 승무원은 별도 표(Table C, 휴식 시설 등급별)로 정하고, 2h 는 예기치 못한 상황의 연장 한도로 알고 있다. 원문 대조 전이라 TODO(확인 필요).
  - `required_rest_hours(augmented=True)` 의 8h 와 `prior_fdp × 0.9` 공식도 근거 조항을 찾지 못했다.
- 고정 테스트: **있음.** [`test_far117.py`](../../../tests/test_domain/test_far117.py) `test_max_fdp_hours_augmented_adds_extension`, `test_required_rest_hours`
- 사람 결정: **필요.** 규정 값이므로 [fdp-hard-constraint](fdp-hard-constraint.md) 0단계에서 함께 판정한다.

## B5. Table B 값이 원문과 다를 가능성

- 위치: `far117._APPENDIX_B`
- 현상: 예를 들어 07–11시 1구간이 13.5h 다. 원문 Table B 에는 7구간 이상 열도 있는 것으로 안다. TODO(확인 필요)
- 고정 테스트: **있음** (`test_appendix_b_table_is_unchanged`).
- 사람 결정: **필요.** [ADR 0002](../../decisions/0002-fdp-hard-constraint.md) 의 검증 대기 항목이다.

## B6. `crew.py` 의 `_MIN_REST_MIN` 미사용

- 위치: [`src/argos/optimization/crew.py`](../../../src/argos/optimization/crew.py)
- 현상: `_MIN_REST_MIN = 600` 이 정의만 되어 있다. 연속 duty 사이의 휴식을 모델도 사후 검증도 확인하지 않는다.
- 단계: [fdp-hard-constraint](fdp-hard-constraint.md) 4단계에서 처리한다.

## B7. 합성 데이터에서 같은 기체가 겹치는 rotation 을 동시에 운항

- 상태: **해결** (2026-10-10). [ADR 0007](../../decisions/0007-fleet-sized-for-overlap-free-tails.md). 회고: [02-retro](../../harness/02-retro.md)
- 우선순위: 높음 (2026-10-10 지정). 같은 기체가 같은 시각에 두 노선을 나는 것은 물리적으로 불가능하다. 전파 그래프·기체 배정·승무원 배정의 입력이 오염된다.
- 발견: 2026-10-10, domain-consolidation 1단계 fixture digest 작성 중. `KE0005` 가 ICN-ORD 와 ICN-HNL 에 같은 `HL7705`, 같은 시각(01:20 UTC)으로 있었다.
- 원인 (측정 결과, 처음 생각보다 넓었다):
  - 기체를 편마다 `rng.choice` 로 골라 겹침을 확인하지 않았다. fixture 하루치에서 146편 중 127편(87%)이 같은 기체의 rotation 과 겹쳤다. 로컬 3년치 DB 에서는 129,836편이다.
  - 겹침 때문에 전파 그래프 edge 62개 중 53개의 buffer 가 음수였다. 0분 지연 트리거 146개 중 145개가 연쇄 지연을 만들었다.
  - 편명은 `지역 base + 기종순번·2 + n%2` 라 같은 지역·기종 노선끼리 겹쳤다. fixture 하루 146편이 편명 33개를 썼다. 로컬 DB 에서 (날짜, 편명) 중복은 20,827쌍이다. `_fn_counter` 가 클래스 변수라 인스턴스끼리 공유되기도 했다.
  - 기단이 모자라 겹침 없는 배정이 불가능했다 (B777 필요 65대, 보유 15대).
- 수정: 기체를 출발 순서대로 best fit 배정, 기단 58 → 150대, 편명을 (노선, slot) 별 고유 번호로, validator 에 두 검사를 오류로 추가. RNG 스트림을 보존해 다른 컬럼은 행 단위로 같다.
- 고정 테스트: [`test_generator_schedule.py`](../../../tests/test_data_gen/test_generator_schedule.py), [`test_fixture_propagation.py`](../../../tests/test_simulation/test_fixture_propagation.py) (0분 지연이 연쇄 지연을 만들지 않음), [`test_validator.py`](../../../tests/test_data_gen/test_validator.py) 의 겹침·편명 테스트
- 남은 것: 로컬 DB 재생성(사람이 실행), 기단 현실화 [fleet-realism](fleet-realism.md), B8

## B8. 지연 전파가 음수 buffer 를 "지연 생성"으로 처리

- 발견: 2026-10-10, B7 조사 중
- 위치: [`simulation/propagation.py`](../../../src/argos/simulation/propagation.py) `propagate`
- 현상:
  - 전파량이 `max(0, 앞 편 지연 − buffer)` 다. buffer 가 음수면 앞 편 지연이 0 이어도 다음 편이 지연된다.
  - 트리거 이후 위상 순서의 모든 노드를 돈다. 트리거의 후손이 아닌 노드도 음수 buffer edge 가 있으면 지연된다.
- 현재 영향: 없음. B7 수정 후 생성 데이터에는 음수 buffer 가 없고, validator 가 겹침을 오류로 막는다. 회귀 테스트가 fixture 에서 0분 지연 연쇄를 막는다.
- 판단 필요: 데이터가 깨끗하다는 전제에 기대지 않고 propagate 가 후손만 돌고 음수 buffer 를 0 으로 볼지. 바꾸면 그래프 의미가 달라지므로 사람이 정한다. TODO(확인 필요)
