# 회고 01 후속 항목

- 근거: [01-retro](../../harness/01-retro.md) 5절 개선 제안
- 상태: 미착수 (항목별)

phase3/boundaries 작업(경계 강제, domain 통합)에서 다루지 않은 제안이다. 반영한 것은 아래 "반영됨" 에 적었다.

## 반영됨 (phase3/boundaries)

- conventions 에 "domain 함수의 입력 검증" 절과 경계값 테스트 체크리스트 추가 (회고 2-4, 2-1)
- 계획 결과에 실제 출력 값 기록: [domain-consolidation](domain-consolidation.md) 결과 절 (회고 3-1)
- 낡은 문서 내용 갱신: overview(경계 강제), domain.md(D2) (회고 4-5)

## 남은 항목

| # | 대상 | 할 일 | 회고 항목 | 사람 결정 |
|---|---|---|---|---|
| R1 | 문서 | exec-plan 템플릿(`docs/exec-plans/TEMPLATE.md`)을 만든다. `상태:` 줄(미착수/진행 중/차단됨/해결)과 "시작 전 `git status` 로 부분 수정이 워킹트리에 있는지 확인" 단계를 넣는다 | 2-5 | 불필요 |
| R2 | 문서 | glossary Segment 에 "`crew.py` 는 FlightLeg(왕복) 1개를 2구간으로 계산" 을 적는다. FDP 종료 시점(블록인 vs `_POST_FLIGHT_MIN` 포함)은 규정 조항 근거로 정한 뒤 glossary 와 `crew.py` 중 하나를 맞춘다. [fdp-hard-constraint](fdp-hard-constraint.md) 0단계에서 함께 판정 | 3-3, 3-4 | **필요** |
| R3 | 테스트 | `test_is_fdp_legal_rejects_zero_segments`, `test_augmented_required_rejects_zero_segments` 추가 | 4-2 | 불필요 |
| R4 | 테스트 | `test_crew.py` 에 `DutyPeriod` 구간 수(=2×편 수)와 FDP 계산을 고정하는 테스트 추가 | 4-3, 3-4 | 불필요 |
| R5 | 절차 | 버그 수정 PR 에서 "새 테스트를 수정 전 코드로 돌려 실패 확인" 절차를 conventions 에 적는다. 보조 스크립트(`git stash` 후 해당 테스트만 실행)는 선택 | 4-1 | 불필요 |
| R6 | lint | `check_doc_links.py` 에 해결된 bug-backlog 식별자가 다른 문서에 남아 있으면 경고. 비용 대비 효과가 낮아 R1 뒤로 미룬다 | 4-5, 3-2 | 불필요 |
