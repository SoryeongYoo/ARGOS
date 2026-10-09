# 0003. RecoveryScenario.cost_index 를 relative_cost 로 개명한다

- 상태: 승인됨 (2026-10-07). 구현 전
- 관련 진단: [C3](../harness/00-diagnosis.md)

## 맥락

`cost_index` 라는 이름이 서로 다른 두 개념에 쓰인다 (C3).

- 운항 Cost Index(CI): 연료비와 시간비의 비율. [`domain/cost_index.py`](../../src/argos/domain/cost_index.py) 가 다룬다.
- [`simulation/propagation.py`](../../src/argos/simulation/propagation.py) `RecoveryScenario.cost_index`: 회복 시나리오의 0.0~1.0 상대 비용 점수. 값은 0.0/0.2/0.6/0.8/1.0 으로 하드코딩되어 있다.

후자가 LLM 프롬프트에 `cost index: 0.2` 형태로 들어간다. 모델과 사람 모두 이것을 운항 CI 로 오해할 수 있다.

## 결정

`RecoveryScenario.cost_index` 를 `relative_cost` 로 바꾼다. 의미(0=무비용, 1=가장 비쌈)와 값은 그대로 둔다. 운항 CI 쪽 이름은 유지한다. 용어 정의는 [glossary](../glossary.md) 에 있다.

## 결과

- 영향 파일 (2026-10-07 grep 기준):
  - `simulation/propagation.py`: 필드 정의와 생성 5곳
  - `agents/tools.py`: dict 키, docstring
  - `agents/occ_graph.py`: LLM 프롬프트 문자열
  - `ui/dashboard.py`: 표시 문구
  - `scripts/run_occ.py`, `scripts/simulate_delay.py`
  - `tests/test_simulation/test_propagation.py`
- tool 이 반환하는 dict 의 키도 바뀐다. 이 키는 LLM 이 보는 내용이므로 프롬프트 문구도 함께 바꾼다.

## 후속 작업

- [rename-relative-cost](../exec-plans/active/rename-relative-cost.md)
