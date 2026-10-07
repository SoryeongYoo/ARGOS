# RecoveryScenario.cost_index → relative_cost

- 근거: [ADR 0003](../../decisions/0003-rename-relative-cost.md), 진단 [C3](../../harness/00-diagnosis.md)
- 상태: 대기

## 목표

회복 시나리오의 상대 비용 필드 이름을 `relative_cost` 로 바꿔 운항 CI 와 구분한다. 값과 의미는 그대로 둔다.

## 영향 파일

시작 전에 `grep -rn "cost_index" src tests scripts` 로 다시 확인한다. `domain/cost_index.py` 는 대상이 아니다.

- `src/argos/simulation/propagation.py`: 필드 정의와 생성 5곳
- `src/argos/agents/tools.py`: 반환 dict 키, docstring
- `src/argos/agents/occ_graph.py`: LLM 프롬프트 문자열 `cost index:`
- `src/argos/ui/dashboard.py`: `Cost index:` 표시 문구
- `scripts/run_occ.py`, `scripts/simulate_delay.py`
- `tests/test_simulation/test_propagation.py`

## 단계

1. `RecoveryScenario` 필드 이름을 바꾸고 생성 지점을 모두 수정한다.
2. tool 반환 키와 LLM 프롬프트 문구를 `relative cost` 로 바꾼다.
3. 화면 문구(대시보드, CLI)를 "상대 비용" / "Relative cost" 로 바꾼다.
4. 테스트를 갱신한다.

## 완료 조건

- `grep -rn "cost_index" src scripts tests` 결과가 `domain/cost_index.py` 와 그 사용처뿐이다.
- `python scripts/verify.py` 가 통과한다.

## 위험

- LangGraph checkpointer 에 예전 키로 저장된 state 가 있으면 깨진다. 현재 `MemorySaver` 라 프로세스 수명 동안만 남으므로 영향은 작다.
- LLM 이 tool 결과의 키 이름을 근거로 설명을 만들기 때문에 브리핑 문구가 달라질 수 있다. mock 테스트로는 잡히지 않는다 (V3).
