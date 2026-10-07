# CLAUDE.md

ARGOS (Airline Route & Ground Operations System): 인천 허브 항공사(대한항공 모델)의 AI 운항통제센터(OCC) 포트폴리오 프로젝트.

핵심 흐름: **지연 입력 → 전파 시뮬레이션 → 회복 시나리오 3개 → 자원 최적화 → OCC 관리자 승인**

이 파일은 지도다. 자세한 내용은 링크된 문서 한 곳에만 있다.

## 작업 시작 전

1. [`docs/exec-plans/active/`](docs/exec-plans/active/) 에 지금 작업과 관련된 계획이 있는지 본다. 있으면 그 단계와 완료 조건을 따른다.
2. 건드릴 모듈의 [아키텍처 문서](docs/architecture/overview.md) 와 관련 [ADR](docs/decisions/) 을 읽는다.
3. 모르는 약어는 [용어집](docs/glossary.md), 코딩 규칙은 [컨벤션](docs/conventions.md) 에서 찾는다.

## 완료 조건

```bash
python scripts/verify.py          # ruff check → ruff format --check → mypy → pytest. 하나라도 실패하면 exit 1
python scripts/verify.py --fast   # @pytest.mark.slow 제외
python scripts/check_doc_links.py # 문서를 고쳤다면: CLAUDE.md, docs/ 상대 링크 검사
```

이 명령이 통과하기 전에는 "완료"라고 하지 않는다. 테스트는 `data/db/` 를 읽지 않는다 (fixture DB, [conventions](docs/conventions.md)).

## 사람이 결정하는 영역: 수정하지 말고 제안만

| 영역 | 이유 | 문서 |
|---|---|---|
| `src/argos/domain/far117.py` 규정 값 | 안전 규정. 골든 테스트로 고정됨. Table B 는 검증 대기 | [ADR 0002](docs/decisions/0002-fdp-hard-constraint.md) |
| `src/argos/data_gen/routes.py` 60개 노선 정의 | 합성 데이터와 모델 전체의 전제 | [data_gen](docs/architecture/data_gen.md) |
| 승인 게이트 구조 (`agents/occ_graph.py` `human_gate`) | Agents propose; humans decide | [ADR 0004](docs/decisions/0004-all-approvals-via-human-gate.md) |
| `design/` 디자인 자산 | 명시적 요청이 있을 때만 수정 | [ADR 0006](docs/decisions/0006-design-assets-in-design-dir.md) |
| prediction 을 OCC 흐름에 연결 | 보류 결정 | [ADR 0005](docs/decisions/0005-prediction-not-wired.md) |

변경이 필요해 보이면 근거(규정 조항, 진단 항목 번호)와 함께 제안하고 멈춘다.

## 구조

| 경로 | 책임 | 문서 |
|---|---|---|
| `src/argos/domain/` | 규정·성능 계산의 단일 기준 출처. I/O 없음 | [domain](docs/architecture/domain.md) |
| `src/argos/data_gen/` | 합성 데이터 생성·검증, 노선 정의, DDL | [data_gen](docs/architecture/data_gen.md) |
| `src/argos/simulation/` | 지연 전파, 회복 시나리오 3개 | [simulation](docs/architecture/simulation.md) |
| `src/argos/optimization/` | CP-SAT 기체·승무원 재배정 | [optimization](docs/architecture/optimization.md) |
| `src/argos/agents/` | LangGraph OCC 그래프, 승인 게이트 | [agents](docs/architecture/agents.md) |
| `src/argos/uav/` | UAM 공역·ACROSS 시뮬레이션 (OCC 와 독립) | [uav](docs/architecture/uav.md) |
| `src/argos/ui/dashboard.py` | Streamlit 대시보드 | [ui](docs/architecture/ui.md) |
| `src/argos/prediction/` | LightGBM 지연 예측 (런타임 미연결) | [ADR 0005](docs/decisions/0005-prediction-not-wired.md) |
| `scripts/` | typer CLI 진입점, `verify.py` | 아래 명령 |
| `design/` | 디자인 시스템 자산 | [design/README.md](design/README.md) |
| `docs/harness/` | 에이전트 작업 환경 진단 (항목 번호 C·V·D 의 출처) | [00-diagnosis](docs/harness/00-diagnosis.md) |

의존 방향과 레이어 규칙: [overview](docs/architecture/overview.md)

## 환경

```bash
python -m venv venv && venv\Scripts\activate   # Python 3.12
pip install -e ".[dev]"                         # scripts 는 editable 설치로 argos 를 import
cp .env.example .env                            # ANTHROPIC_API_KEY (run_occ 실제 실행에만 필요)
```

## 자주 쓰는 명령

**DB 를 쓰는 스크립트는 --yes 없이 먼저 실행해 확인할 것.** `setup_db.py`, `generate_data.py`, `train_model.py` 는 `--yes` 가 없으면 바꿀 내용만 출력하고 종료한다. `generate_data.py --yes` 는 기존 `flights` 를 기간과 무관하게 전부 지운다.

```bash
python scripts/setup_db.py --yes
python scripts/generate_data.py --yes [--start 2024-01-01 --end 2024-01-31] [--routes ICN-NRT ...]
python scripts/validate_data.py [--strict]
python scripts/train_model.py --yes             # models/delay_predictor.lgb 덮어씀
python scripts/run_occ.py --auto --dry-run      # LLM 노드 생략. --dry-run 없으면 Anthropic API 호출 (비용)
streamlit run src/argos/ui/dashboard.py
```

## 전역 불변식

- 모든 timestamp 는 UTC 로 저장한다. KST 는 표시와 규정 판정에만 쓴다.
- FAR 117 안전 제약은 완화하지 않는다. 풀리지 않으면 미배정으로 드러낸다.
- 회복 조치 확정은 사람 승인(`human_gate`) 뒤에만 한다.
- 도메인 상수는 `domain/` 에만 정의한다 ([ADR 0001](docs/decisions/0001-domain-single-source.md)).
- LLM 호출 규칙은 [conventions](docs/conventions.md) 에 있다.
