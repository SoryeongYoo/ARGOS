# agents

[`src/argos/agents/`](../../src/argos/agents/)

## 책임

LangGraph 로 OCC 흐름을 조립하고, **사람의 승인을 강제하는 지점**을 소유한다. LLM 은 상황을 분석하고 브리핑을 작성한다. 수치(전파, 시나리오, 배정)는 결정적 코드가 만든다.

그래프: `simulate → analyse → optimise → brief_occ → human_gate → execute | abort`

## 공개 인터페이스

- [`occ_graph.py`](../../src/argos/agents/occ_graph.py)
  - `build_occ_graph(checkpointer=None)`
  - `run_until_approval(...)`: `human_gate` 에서 멈춘 상태와 graph 를 반환
  - `resume_after_approval(graph, approved_scenario_id, approval_notes, thread_id)`: `None` 이면 거절
- [`tools.py`](../../src/argos/agents/tools.py)
  - LangChain `@tool` 4개: `run_propagation`, `run_scenario_generation`, `run_aircraft_optimisation`, `run_crew_optimisation` (`OCC_TOOLS`)
  - `AIRCRAFT_SOLVER_TIME_LIMIT_S`, `CREW_SOLVER_TIME_LIMIT_S`: 기본 30초. 테스트 주입용이며 tool 인자로 노출하지 않는다
- [`state.py`](../../src/argos/agents/state.py): `OCCState` (TypedDict)

## 경계

- **승인 게이트는 `human_gate` 하나다.** 새 실행 경로도 이 게이트를 거쳐야 하고, 게이트 구조를 바꾸려면 제안만 한다 ([ADR 0004](../decisions/0004-all-approvals-via-human-gate.md)).
- `node_execute` 는 실제 운항을 바꾸지 않는다. 요약 문자열만 남기는 시뮬레이션이다.
- LLM 호출은 `_make_llm()` 하나로만 한다. `langchain_anthropic.ChatAnthropic` 을 쓴다.
- 테스트는 `_make_llm` 을 mock 으로 바꾼다. 실제 LLM 출력은 검증하지 않는다 (V3).

## 의존해도 되는 대상

simulation, optimization, domain, config.

## 알려진 부채

- **D1**: `interrupt_before=["human_gate"]` 와 노드 안 `interrupt()` 를 둘 다 써서 이중 게이트다. 의도 여부는 TODO(확인 필요).
- **D4**: 모델명 `claude-sonnet-4-6` 이 `_make_llm` 에 하드코딩되어 있다. `settings.claude_model` 은 쓰이지 않는다.
- **D5**:
  - `node_analyse` 에서 LLM 이 tool 을 호출하지 않으면 `scenarios_raw = []` 로 진행한다.
  - `node_brief_occ` 는 자유 텍스트를 만든다.
  - `node_optimise` docstring 은 "Claude decides" 라고 하지만, 실제로는 LLM 을 호출하지 않는다.
- **D6**: `run_crew_optimisation` 이 SQL `IN (...)` 을 `.format` 으로 조립한다.
- **D10**: tool 경계에서 dataclass 를 dict 로 수동 변환한다.
- `run_crew_optimisation` 의 `midnight_utc` 는 미사용이다. → [bug-backlog](../exec-plans/active/bug-backlog.md)
