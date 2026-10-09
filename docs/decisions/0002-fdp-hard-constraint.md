# 0002. FAR 117 FDP 한도를 CP-SAT hard constraint 로 둔다

- 상태: 승인됨 (2026-10-07). 구현 전. **Table B 값은 "검증 대기"**
- 관련 진단: [C2, V1](../harness/00-diagnosis.md)

## 맥락

- [`optimization/crew.py`](../../src/argos/optimization/crew.py) 의 CP-SAT 모델에서 FAR 117 관련 hard constraint 는 일일 비행시간 480분 하나다. 이 값도 domain 상수가 아니라 `crew.py` 의 `_MAX_FLIGHT_TIME_MIN` 을 쓴다. 나머지 제약은 편당 기장·부기장 1명, 승무원별 시간 겹침 금지 같은 배정 구조 제약이다.
- `crew.py` 에 `_MIN_REST_MIN = 600` 이 정의되어 있지만, 모델에서도 사후 검증에서도 쓰지 않는다. 즉 휴식시간은 어디에서도 검사하지 않는다.
- FDP 한도는 풀이가 끝난 뒤 `_validate_far117()` 이 [`domain/far117.is_fdp_legal()`](../../src/argos/domain/far117.py) 로 확인해 `far117_violations` 에 기록만 한다. 솔버가 위반 해를 내놓을 수 있다 (C2).
- `far117._APPENDIX_B` 표 값은 규정 원문(14 CFR 117 Table B)과 대조하지 않았다. 07–11시 1구간이 13.5h 로 되어 있는 등 원문과 다를 가능성이 있다. 자세한 내용은 [bug-backlog](../exec-plans/active/bug-backlog.md) 참고.
- 2026-10 에 [`tests/test_domain/test_far117.py`](../../tests/test_domain/test_far117.py) 가 현재 값을 골든 테스트로 고정했다 (V1 일부 해소).

## 결정

1. FDP 한도는 CP-SAT 모델 안의 hard constraint 로 표현한다. 안전 제약은 완화하지 않는다.
2. 사후 검증(`far117_violations`)은 제거하지 않고, 이중 방어로 유지한다.
3. 한도 값의 출처는 `domain/far117.py` 하나다. `crew.py` 의 `_MAX_FLIGHT_TIME_MIN`, `_MIN_REST_MIN` 같은 로컬 상수는 far117 상수로 바꾼다.
4. `_APPENDIX_B` 는 규정 원문과 대조하기 전까지 **검증 대기** 상태다. 이 상태에서 표 값을 바꾸지 않는다. 값을 바꾸려면 근거 조항을 PR 에 인용하고, 사람이 승인해야 한다.

## 결과

- 영향 파일: `optimization/crew.py`, `domain/far117.py`, `tests/test_domain/test_far117.py`, `tests/test_optimization/test_crew.py`
- 예상 영향: 제약이 강해져 일부 입력에서 INFEASIBLE 이 늘어날 수 있다. 이 경우 미배정 편으로 드러나야 하며, 제약을 풀어서 해결하면 안 된다.

## 후속 작업

- [fdp-hard-constraint](../exec-plans/active/fdp-hard-constraint.md). Table B 원문 대조가 끝난 뒤 착수한다.
