# domain 단일 기준 출처로 통합

- 근거: [ADR 0001](../../decisions/0001-domain-single-source.md), 진단 [D2, C4, C5](../../harness/00-diagnosis.md)
- 상태: 진행 중 (phase3/boundaries)

## 목표

턴타임, 기체 분류, 기종 호환, rotation footprint, 블록타임, MCT 를 `domain/` 에서 한 번만 정의하고, 다른 모듈은 이를 import 한다. 이 단계에서는 동작(수치 결과)을 바꾸지 않는다.

## 영향 파일

- `src/argos/domain/`: 새 모듈 추가. 예: `turnaround.py`, `fleet.py`. 이름은 TODO(확인 필요)
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
