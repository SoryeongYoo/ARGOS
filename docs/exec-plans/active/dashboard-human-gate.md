# 대시보드 승인을 human_gate 경유로

- 근거: [ADR 0004](../../decisions/0004-all-approvals-via-human-gate.md), 진단 [D1](../../harness/00-diagnosis.md)
- 상태: 대기. 승인 게이트 구조는 사람이 결정하는 영역이므로 설계안을 먼저 승인받는다

## 목표

대시보드의 "시나리오 N 승인" 버튼이 `run_until_approval()` 과 `resume_after_approval()` 을 거쳐 LangGraph `human_gate` 를 통과하게 한다. 그래프를 거치지 않고 "승인됨"을 표시하는 경로를 없앤다.

## 영향 파일

- `src/argos/ui/dashboard.py`: 운항 관제 탭의 시뮬레이션·승인 흐름
- `src/argos/agents/occ_graph.py`: 필요하면 LLM 없이 도는 모드 추가. TODO(확인 필요), 대시보드가 API 키 없이 동작해야 하는지 결정 필요
- 새 테스트: Streamlit `AppTest` 또는 대시보드 로직을 분리한 함수 테스트

## 단계

1. **설계 제안**: 다음을 정리해 사람의 승인을 받는다.
   - checkpointer 와 `thread_id` 를 Streamlit `session_state` 에 어떻게 둘지
   - API 키가 없을 때 LLM 노드를 어떻게 처리할지
   - 이중 interrupt(`interrupt_before` 와 `interrupt()`)를 정리할지
2. 대시보드 시뮬레이션 버튼이 `run_until_approval()` 을 호출하고, 반환된 state 의 `scenarios_raw` 와 `scenario_briefing` 을 표시하게 한다.
3. 승인·거절 버튼이 `resume_after_approval()` 을 호출하고, `execution_summary` 를 표시하게 한다.
4. `DelayPropagator` 를 직접 호출하던 승인 경로를 지운다. 순수 시각화 용도는 남겨도 된다.
5. 승인 버튼을 누르면 그래프의 `execute` 노드에 도달하는지 확인하는 테스트를 추가한다.

## 완료 조건

- `dashboard.py` 에서 `st.success` 로 회복 시나리오 승인을 표시하는 코드가 그래프 결과 없이 실행되지 않는다.
- 승인과 거절이 각각 `[APPROVED]`, `[REJECTED]` `execution_summary` 로 이어지는 테스트가 있다.
- `python scripts/verify.py` 가 통과한다.

## 위험

- 대시보드 응답 시간이 길어진다. crew CP-SAT 이 실제 운항에서 30초를 다 쓰고, 여기에 LLM 호출이 더해진다.
- 대시보드는 테스트가 없다 (V4). 회귀를 사람이 직접 확인해야 할 수 있다.
