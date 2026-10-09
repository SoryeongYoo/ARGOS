# 01 — 회고: bug-backlog B1 처리

- 작성일: 2026-10-08
- 기준 커밋: `573f82f` (harness/docs)
- 작업: [bug-backlog](../exec-plans/active/bug-backlog.md) B1. `max_fdp_hours(num_segments < 1)` 이면 `ValueError`
- 결과: 해결. `python scripts/verify.py` ALL PASSED (pytest 435 passed)
- 변경 파일
  - `src/argos/domain/far117.py`: `max_fdp_hours` 맨 앞에 입력 검증 추가, docstring 에 `Raises` 추가. 표와 상수는 그대로 뒀다
  - `tests/test_domain/test_far117.py`: `test_max_fdp_hours_rejects_fewer_than_one_segment` (0, -1) 추가
  - `docs/exec-plans/active/bug-backlog.md`: B1 상태를 해결로 바꾸고, 음수 입력 동작 설명을 바로잡음
  - `docs/architecture/domain.md`: 알려진 부채에서 `num_segments=0` 언급을 지움

> **주의**: 작업을 시작할 때 위 두 코드 파일에 이미 B1 수정이 커밋되지 않은 채로 들어 있었다(`git status` 의 ` M`). 이 수정은 2026-10-08 22:37 에 Phase 4 첫 세션이 에러로 중단되면서 남긴 것이다. 새로 작성하지 않고, 이 수정이 계획 단계와 맞는지 검증했다.

---

## 1. 탐색 로그

| # | 연 파일 / 실행 | 확인한 내용 |
|---|---|---|
| 1 | `docs/exec-plans/active/bug-backlog.md` | B1 의 현상, 권장 동작(`ValueError`), 4단계, 사람 결정 불필요 판단을 확인했다 |
| 2 | `git diff` (far117.py, test_far117.py) | 계획 2·3단계에 해당하는 수정이 이미 워킹트리에 있었다 |
| 3 | `src/argos/domain/far117.py` | 검증이 `seg_idx` 계산 앞에 있다. `_APPENDIX_B` 와 상수는 바뀌지 않았다 |
| 4 | `tests/test_domain/test_far117.py` | 새 테스트가 있다. 골든 테스트(표, 모든 셀, 클램프, 증원)는 그대로다 |
| 5 | `docs/decisions/0002-fdp-hard-constraint.md` | "검증 대기"는 Table B 값에만 걸린다. 입력 검증은 ADR 범위 밖이다 |
| 6 | `docs/architecture/domain.md` | 공개 인터페이스를 확인했다. 알려진 부채에 `num_segments=0` 언급이 있어 수정 후 낡은 내용이 된다 |
| 7 | `docs/conventions.md` (grep: ValueError/raise/검증) | 예외와 입력 검증 규칙이 없다. Pydantic 경계 규칙만 있다 |
| 8 | 저장소 전체 grep: `max_fdp_hours\|is_fdp_legal\|augmented_required` | src 호출 지점은 `crew.py:440` 의 `is_fdp_legal` 하나다. `augmented_required` 는 테스트에서만 쓴다. `scripts/` 에서는 호출하지 않는다 |
| 9 | `src/argos/optimization/crew.py:395-460` `_validate_far117` | `flight_list` 는 `setdefault().append()` 로 만들어져 비어 있을 수 없다. `num_segs = 2 * len(flight_list)` ≥ 2 이므로 런타임 영향은 없다 |
| 10 | `git show HEAD:src/argos/domain/far117.py` → scratchpad 에서 import | 수정 전 동작을 재현했다: `0`→11.0(6구간), `-1`→11.5(5구간), `-5`→13.5(1구간), `-6`→`IndexError` |
| 11 | `python -c` 로 수정 후 동작 확인 | `max_fdp_hours`, `is_fdp_legal`, `augmented_required` 모두 `ValueError` 를 낸다 |
| 12 | `python scripts/verify.py` | 5단계 모두 PASS |
| 13 | `docs/` grep: `구간\|왕복\|num_segs`, `docs/glossary.md`, `docs/conventions.md` §ICN 출발 왕복, `docs/harness/00-diagnosis.md` C5 | 구간 수와 FDP 정의가 문서와 코드에서 어떻게 쓰이는지 비교했다 (3절) |
| 14 | `pyproject.toml` `[tool.mypy]`, `[tool.pytest]` | far117 은 mypy strict 대상이다(baseline 예외 아님). 커버리지 설정은 없다 |

[`overview.md`](../architecture/overview.md) 는 열지 않았다. 변경이 domain 내부의 입력 검증뿐이라 의존 방향과 관계가 없다고 판단했다.

## 2. 문서에 정보가 없어서 코드에서 직접 찾은 항목

1. **음수 입력의 실제 동작.** 계획에는 "음수 입력도 마찬가지"라고만 적혀 있었다. 실제로는 `-1`~`-5` 가 서로 다른 열 값을 반환하고 `-6` 이하는 `IndexError` 를 낸다 (탐색 #10).
2. **런타임에 0 이 들어가지 않는 근거.** 계획은 결론만 적었다. 근거는 `crew.py` 가 `setdefault(cid, []).append(...)` 로만 리스트를 만든다는 점이다 (탐색 #9).
3. **`crew.py` 는 FlightLeg 하나를 2구간으로 센다** (`2 * len(flight_list)`, "out + back per leg"). 용어집은 Segment 를 "FDP 안의 비행 편 수"로만 정의한다. 하나의 `FlightLeg` 레코드가 왕복을 뜻한다는 점은 conventions 의 왕복 가정과 코드 주석을 함께 봐야 알 수 있다.
4. **domain 함수의 입력 검증·예외 규칙.** conventions 에 해당 규칙이 없다. `ValueError` 를 고른 것은 계획의 "권장 동작"을 따른 결과이고, 프로젝트 전체 규칙에서 나온 결정이 아니다.
5. **워킹트리에 이미 수정이 있었다는 사실.** 문서나 계획 어디에도 진행 상태가 적혀 있지 않았다. `git status` 로만 알 수 있었다.

## 3. 문서와 코드가 다르게 적혀 있던 항목

| # | 문서 | 코드 | 처리 |
|---|---|---|---|
| 1 | bug-backlog B1: "음수 입력도 마찬가지다" (6구간 값을 반환한다는 뜻으로 읽힘) | `-1`→5구간, `-5`→1구간, `-6` 이하 `IndexError` | 계획 문서를 고쳤다 |
| 2 | domain.md 알려진 부채: "`num_segments=0`" 의심점 | 이번 수정으로 해결됨 | 문서에서 지웠다 |
| 3 | [glossary](../glossary.md) FDP: "출근 보고부터 마지막 편 **블록인까지**". fdp-hard-constraint 3단계도 같은 정의다 | `crew.py` `_validate_far117`: `release_utc = last_arr_utc + _POST_FLIGHT_MIN`. FDP 에 블록인 뒤 시간이 포함된다 | **고치지 않았다.** B1 범위 밖이고 FDP 판정 결과가 바뀐다. 제안만 한다 (5절) |
| 4 | glossary Segment: "FDP 안의 비행 편 수" | `crew.py` 는 `FlightLeg` 1개 = 2구간 | 고치지 않았다. 용어집에 왕복 계산 방식을 적을지 제안한다 |
| 5 | `test_far117.py` 모듈 docstring: "현재 동작을 고정하는 것이 목적" | 이제 동작을 바꾼 테스트(B1)도 들어 있다 | 고치지 않았다. 해롭지 않지만, 다음 작업자가 "이 파일은 기대값을 바꾸면 안 된다"를 "테스트를 추가하면 안 된다"로 오해할 수 있다 |

## 4. verify 로 잡히지 않아서 별도로 확인한 항목

1. **새 테스트가 수정 전 코드에서 실패하는지.** verify 는 현재 트리만 검사한다. 수정이 이미 들어 있었으므로 테스트가 버그를 실제로 재현하는지는 HEAD 버전을 따로 import 해서 확인했다 (탐색 #10).
2. **검증이 상위 함수로 전파되는지.** `is_fdp_legal`, `augmented_required` 의 0/음수 입력 테스트는 없다. 직접 실행해서 확인했다 (탐색 #11).
3. **런타임 호출자가 0 을 넘기지 않는지.** `crew.py` 에는 `num_segs` 를 고정하는 테스트가 없다. 코드를 읽어서만 확인했다 (탐색 #9). `ValueError` 가 crew 최적화를 중단시킬 수 있는 경로가 없다는 것도 같은 방법으로 확인했다.
4. **표와 상수가 바뀌지 않았는지.** 골든 테스트가 잡아 주지만, 사람 결정 영역이라 diff 로도 한 번 더 확인했다.
5. **문서 내용이 낡지 않았는지.** `check_doc_links.py` 는 링크가 존재하는지만 본다. domain.md 의 `num_segments=0` 언급처럼 내용이 낡은 것은 grep 으로 찾았다.

## 5. 개선 제안

| 대상 | 제안 | 줄어드는 항목 |
|---|---|---|
| 문서 | `docs/conventions.md` 에 "domain 함수의 입력 검증" 절을 추가한다. 예: 정의역 밖 입력은 `ValueError`, 메시지에 인자 이름 포함, 클램프/랩어라운드는 docstring 에 명시 | 2-4 |
| 문서 | exec-plan 템플릿에 `상태:` 줄(미착수/진행 중/해결)과 "부분 수정이 워킹트리에 있을 수 있음" 확인 단계를 넣는다 | 2-5 |
| 문서 | glossary 의 Segment 에 "`crew.py` 는 FlightLeg(왕복) 1개를 2구간으로 계산" 을 추가한다. FDP 종료 시점(블록인 vs `_POST_FLIGHT_MIN` 포함)은 규정 조항을 근거로 사람이 정한 뒤 glossary 와 `crew.py` 중 하나를 맞춘다 (fdp-hard-constraint 계획에 0단계 항목으로 추가할 것을 제안) | 3-3, 3-4 |
| 문서 | 계획의 "현상"에 경계값을 적을 때는 실제 출력 값(예: `0→11.0`)을 같이 적는다 | 3-1 |
| 테스트 | `test_is_fdp_legal_rejects_zero_segments`, `test_augmented_required_rejects_zero_segments` 를 추가해 전파를 고정한다 | 4-2 |
| 테스트 | `tests/test_optimization/test_crew.py` 에 `DutyPeriod` 의 구간 수(=2×편 수)와 FDP 계산을 고정하는 테스트를 추가한다 | 4-3, 3-4 |
| 테스트 | 버그 수정 PR 에서는 "테스트를 수정 전 코드에 돌려 실패를 확인"하는 절차를 conventions 에 명시한다. 자동화는 `git stash` 후 해당 테스트만 실행하는 보조 스크립트로 가능하다 | 4-1 |
| lint | `check_doc_links.py` 에 "해결된 bug-backlog 항목의 식별자(예: `num_segments=0`)가 다른 문서에 남아 있으면 경고"를 넣는 방안. 비용 대비 효과는 낮으므로 문서 템플릿 개선을 먼저 권한다 | 4-5, 3-2 |
| lint | far117 표 인덱싱처럼 `min(x, N) - 1` 형태의 음수 인덱스 위험은 ruff 규칙으로 잡히지 않는다. lint 대신 domain 함수 경계값 테스트(0, 음수, 상한+1)를 conventions 의 테스트 체크리스트로 두는 편이 현실적이다 | 2-1 |
