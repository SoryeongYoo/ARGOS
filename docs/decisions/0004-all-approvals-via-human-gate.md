# 0004. 모든 승인 경로는 LangGraph human_gate 를 거친다

- 상태: 승인됨 (2026-10-07). 대시보드는 아직 따르지 않음
- 관련 진단: [D1](../harness/00-diagnosis.md)

## 맥락

회복 시나리오를 승인하는 경로가 두 개다 (D1).

| 경로 | 승인 방식 |
|---|---|
| CLI [`scripts/run_occ.py`](../../scripts/run_occ.py) | [`agents/occ_graph.py`](../../src/argos/agents/occ_graph.py) 의 `human_gate` 노드. LangGraph `interrupt()` 로 그래프를 멈추고, `resume_after_approval()` 로 재개한다 |
| 대시보드 [`ui/dashboard.py`](../../src/argos/ui/dashboard.py) | "시나리오 N 승인" 버튼이 `st.success` 토스트만 띄운다. 그래프를 거치지 않는다 |

"Agents propose; humans decide" 규칙이 코드 구조로 강제되지 않는다. 그래서 새 실행 경로를 만들 때 승인 게이트를 빠뜨려도 막을 장치가 없다.

`build_occ_graph()` 는 `interrupt_before=["human_gate"]` 와 노드 안의 `interrupt()` 를 둘 다 사용한다. 이중 게이트가 의도된 것인지는 TODO(확인 필요).

## 결정

1. 회복 조치를 "승인됨/확정됨"으로 기록하는 모든 경로는 `human_gate` 를 거친다. 대시보드도 포함한다.
2. 승인 없이 결과를 확정하는 경로를 새로 만드는 것은 금지한다. 에이전트가 이 구조를 바꿔야 한다고 판단하면, 코드를 고치지 말고 제안만 한다.
3. 범위: OCC 회복 시나리오 승인. 대시보드 UAM 탭의 "ACROSS 에 제출" 결과(`response.approved`)는 외부 당국(ACROSS 시뮬레이터)의 판정이라 이 ADR 대상이 아니다.

## 결과

- 영향 파일: `ui/dashboard.py`, `agents/occ_graph.py`, `scripts/run_occ.py`
- 대시보드는 그래프 상태(checkpointer, thread_id)를 세션 사이에 유지해야 한다.

## 후속 작업

- [dashboard-human-gate](../exec-plans/active/dashboard-human-gate.md)
