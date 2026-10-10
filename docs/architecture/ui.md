# ui

[`src/argos/ui/dashboard.py`](../../src/argos/ui/dashboard.py)

## 책임

Streamlit OCC 대시보드다. 탭은 두 개다.

- 운항 관제: 날짜·트리거 선택 → 전파 시뮬레이션 → 시나리오 카드
- UAM/ACROSS

실행: `streamlit run src/argos/ui/dashboard.py`. Docker 이미지의 기본 CMD 도 이것이다.

DB 경로는 `get_settings().duckdb_path` 를 쓴다 (기본값은 CWD 기준 `data/db/argos.duckdb`, `DUCKDB_PATH` 로 바꿀 수 있다).

## 테스트

[`tests/test_ui/test_dashboard.py`](../../tests/test_ui/test_dashboard.py): Streamlit AppTest 스모크 테스트. fixture DB 로 첫 렌더링, OCC 탭 시뮬레이션·승인 버튼, UAM 탭 ACROSS 제출을 실행한다. 예외와 deprecated 경고(Python 경고, Streamlit deprecation 안내)는 실패로 처리한다.

디자인 시스템(토큰, 폰트, 목업, UI 문구 규칙)은 이 모듈이 아니라 [`design/`](../../design/) 에 있다. design/ 은 명시적 요청이 있을 때만 수정한다 ([ADR 0006](../decisions/0006-design-assets-in-design-dir.md)).

## 공개 인터페이스

없음. Streamlit 진입점(`dashboard.py`)만 있고, 다른 모듈이 import 하는 대상이 아니다.

## 의존해도 되는 대상

모든 레이어. 다만 회복 시나리오 승인은 agents 의 `human_gate` 를 거쳐야 한다 ([ADR 0004](../decisions/0004-all-approvals-via-human-gate.md)).

## 알려진 부채

- **D1**: 현재는 `simulation.propagation.DelayPropagator` 를 직접 호출하고, "승인" 버튼은 `st.success` 토스트만 띄운다. → [dashboard-human-gate](../exec-plans/active/dashboard-human-gate.md)
- **C6**: [`design/README.md`](../../design/README.md) 의 문구 규칙(이모지 금지 등)을 지키지 않는다.
- **C9**: `KST = timezone(timedelta(hours=9))` 를 로컬에 정의한다.
