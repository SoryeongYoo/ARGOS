# FDP 한도를 CP-SAT hard constraint 로

- 근거: [ADR 0002](../../decisions/0002-fdp-hard-constraint.md), 진단 [C2, V1](../../harness/00-diagnosis.md)
- 상태: **차단됨**. FAR 117 Table B 값을 원문과 대조한 뒤 착수한다 (0단계)

## 목표

승무원 배정 솔버가 FDP 한도를 넘는 해를 내지 못하게 한다. 사후 검증(`far117_violations`)은 이중 방어로 남긴다.

## 영향 파일

- `src/argos/optimization/crew.py`: 모델 제약 추가, 로컬 한도 상수 제거
- `src/argos/domain/far117.py`: 값 변경 시에만 수정. 사람 승인 필요
- `tests/test_optimization/test_crew.py`, `tests/test_domain/test_far117.py`

## 메모: crew.py 는 duty span 을 FDP 로 쓰고 있다

- `crew._validate_far117` 의 FDP = 보고(출발 − 60분)부터 `release_utc`(ICN 블록인 + `CREW_POST_FLIGHT_MINUTES` 30분)까지다. 이것은 `domain.rotation.crew_duty_span` 구간이다.
- FAR 117 FDP 는 마지막 편 블록인에서 끝난다. 기준 함수는 `domain.rotation.crew_fdp_span` (= check-in + `icn_block_in_offset`, 마무리 제외)이다. 2026-10-10 domain-consolidation 에서 정의만 했고 사용처는 바꾸지 않았다.
- 그래서 지금 사후 검증은 FDP 를 30분 길게 잡는다 (보수적 방향). 이 계획 3단계에서 FDP 판정과 CP-SAT 제약을 `crew_fdp_span` 기준으로 바꾼다. 바꾸면 `far117_violations` 결과와 `DutyPeriod.fdp_minutes` 가 달라지므로 [비교 테스트](../../../tests/test_domain/test_consolidation_parity.py) 의 crew release 기대값을 근거와 함께 갱신해야 한다.
- glossary: [Duty period vs FDP](../../glossary.md)

## 단계

0. **사람이 할 일**: `_APPENDIX_B` 를 14 CFR 117 Table B 원문과 대조한다. 국토교통부 기준을 쓸지도 결정한다. 차이가 있으면 근거 조항과 함께 far117 수정 PR 을 따로 낸다. 증원 승무원(+2h) 처리도 같이 결정한다 ([bug-backlog](bug-backlog.md)).
1. FDP 를 넘는 배정을 솔버가 만들어 내는 입력을 테스트로 재현한다. 지금은 `far117_violations` 가 비어 있지 않게 나오는 경우다.
2. `crew.py` 의 `_MAX_FLIGHT_TIME_MIN` 을 `far117.MAX_FT_CALENDAR_DAY_HOURS` 로 바꾼다.
3. 승무원별 duty(첫 편 보고부터 마지막 편 블록인까지)를 CP-SAT 변수로 표현하고, `max_fdp_hours(보고 KST 시각, 구간 수)` 이하로 제한한다. 보고 시각에 따라 한도가 달라지므로, 이를 모델링할 방법(사전 계산한 표 제약 등)을 설계한 뒤 진행한다.
4. `_MIN_REST_MIN` 을 쓸지 지울지 결정한다. 현재는 정의만 있다.
5. 1단계 테스트에서 `far117_violations == []` 이고, 위반이 미배정 편으로 드러나는지 확인한다.

## 완료 조건

- 모든 crew 테스트 결과에서 `far117_violations == []` 다.
- FDP 를 넘는 입력에서 해당 편이 미배정으로 남는다.
- `python scripts/verify.py` 가 통과한다.

## 위험

- 모델이 커져 30초 제한 안에 FEASIBLE 해를 못 찾을 수 있다. 실제 운항에서는 이미 제한을 다 쓰고 있다.
- 표 값이 틀린 채로 hard constraint 를 걸면 잘못된 안전 기준이 솔버에 박힌다. 그래서 0단계가 먼저다.
