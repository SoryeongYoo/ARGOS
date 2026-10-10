# 02 — 회고: bug-backlog B7 처리

- 작성일: 2026-10-10
- 기준 커밋: `84c75ee` (main, PR #5 머지 후). 작업 브랜치 `fix/b7-aircraft-double-booking`
- 작업: [bug-backlog](../exec-plans/active/bug-backlog.md) B7. 합성 데이터에서 같은 기체가 겹치는 rotation 을 동시에 운항
- 결과: 해결. [ADR 0007](../decisions/0007-fleet-sized-for-overlap-free-tails.md). `python scripts/verify.py` ALL PASSED (pytest 593 passed)
- 변경 파일
  - `src/argos/data_gen/generator.py`: `_assign_tails`(best fit), FLEET 58 → 150대와 인도일, `_legacy_tail_draw`(RNG 보존), `_flight_number_table`, `_DEP_PATTERNS` 모듈 상수화, `_fn_counter` 제거
  - `src/argos/data_gen/validator.py`: `check_no_aircraft_rotation_overlap`, `check_no_duplicate_flight_number_per_day` (오류)
  - 테스트: `tests/test_data_gen/test_generator_schedule.py`(새로), `tests/test_simulation/test_fixture_propagation.py`(새로), `tests/test_data_gen/test_validator.py`(3건 추가), `tests/test_domain/test_consolidation_parity.py`(digest 3개 갱신)
  - 문서: ADR 0007(새로), `exec-plans/active/fleet-realism.md`(새로), bug-backlog B7 해결·B8 추가, `architecture/data_gen.md`, `glossary.md`

> **범위가 바뀐 작업이다.** B7 은 "KE0005 한 편이 두 노선에 중복"으로 등록되어 있었다. 측정해 보니 생성기 구조 문제였고(겹침 87%), 고치려면 기단 규모라는 데이터 전제를 바꿔야 했다. 그래서 두 번 멈추고 사람의 결정을 받았다 (방향 선택, FLEET 표와 영향 범위 승인).

---

## 1. 탐색 로그

| # | 연 파일 / 실행 | 확인한 내용 |
|---|---|---|
| 1 | `bug-backlog.md` B7, `git status`, PR #5 상태 | PR #5 머지됨. 워킹트리는 `.claude/settings.local.json` 만 변경 |
| 2 | `generator.py` `generate_flights`, `_flight_number`, `_cancelled_flight` | 기체 `rng.choice` 독립 선택. 편명 `base + 기종순번·2 + n%2`. `_fn_counter` 가 클래스 변수 |
| 3 | 측정: fixture 하루·7일, 같은 기체 겹침 | 하루 146편 중 127편(87%), 7일 1,027편 중 951편(93%). 같은 기체·같은 시각은 하루 1건, 7일 4건 |
| 4 | 측정: (날짜, 편명) 중복 | 하루 146편이 편명 33개. 7일 208쌍 중 130쌍이 여러 노선 |
| 5 | 측정: 기종별 최대 동시 필요 대수 (하루, 7일) | B777 51~64 vs 15대, B737 39~47 vs 20대 |
| 6 | 측정: 겹침 없는 greedy 배정 커버리지, 음수 buffer, 0분 지연 연쇄 | 대체 기종을 써도 146편 중 106편. edge 62개 중 53개 음수, 0분 트리거 146개 중 145개 연쇄 |
| 7 | **1차 멈춤** — 방향 질문 | 사람 결정: 겹침 없는 배정 + 기단 확대, 편명 같이 수정, 착수 전 보고 조건 4개 |
| 8 | 측정: 3년치(161,868편) 최대 동시 대수 | B737 49, B777 65, B787 8, B747 4 |
| 9 | `prediction/features.py`, `git ls-files models`, fixture 사용 테스트, delivery_date 공식 | feature 에 등록번호·편명 없음. `.lgb` 는 git 추적. B777 인도일 공식이 72대에서 2041년이 됨 |
| 10 | **2차 멈춤** — FLEET 표, RNG 보존안, 영향 범위 보고 | 전부 승인 + 완료 조건 4개 추가 (RNG 행 비교, edge 근거 숫자, ADR 0007, 재생성 명령) |
| 11 | 변경 전 스냅숏 (3년치 frame, fixture edge) | 비교 기준을 코드 수정 전에 저장 |
| 12 | 회귀 테스트 작성 → 실행 | 새 테스트 11건 실패 확인 후 수정 착수 |
| 13 | 구현 → RNG 비교 | 21개 컬럼 × 161,868행 동일, 기상 603건 동일 (`git stash` 로 이전 코드 실행) |
| 14 | validator 를 새 30일 DB, 로컬 3년치 DB 에 실행 | 새 DB 통과. 로컬 DB 는 겹침 129,836편, 편명 중복 20,827쌍으로 실패 |
| 15 | edge before/after 분석 | **처음 배정 정책(가장 오래 쉰 기체)에서 edge 62 → 6.** 정책을 best fit 으로 바꿔 32 |
| 16 | 사라진 비음수 edge 9개 추적 | 뒤 편이 다른 기체로 감: 4개는 새 앞 편이 14h 안, 5개는 14h 창 밖 |
| 17 | `pytest --durations`, 이전 코드로 전체 pytest | 느려진 것은 대부분 기계 부하(이전 코드도 47초). 새 테스트 추가분은 약 6초 |

## 2. 문서에 정보가 없어서 코드에서 직접 찾은 항목

1. **기체 배정 규칙.** data_gen 문서에 "같은 기체는 겹치면 안 된다"는 계약이 없었다. 생성기가 무엇을 보장하는지 알 수 없었다 (탐색 #2).
2. **RNG 호출 순서가 데이터 전체를 결정한다는 점.** seed 로 결정적이라는 말만 있었다. 호출 하나를 빼면 지연·승객·기상까지 다 바뀐다는 것은 코드를 읽어야 알 수 있었다. 이번에 data_gen 문서에 적었다.
3. **기단 규모의 근거.** FLEET 대수(20/10/15/8/5)의 출처가 어디에도 없었다. 스케줄 수요와 맞춰 본 적이 없었던 것으로 보인다.
4. **편명 규칙과 `_fn_counter` 공유.** 클래스 변수라 같은 프로세스 안에서 앞 생성 결과에 따라 편명이 달라졌다. 테스트 세션의 fixture 가 하나라 드러나지 않았다.
5. **validator 가 검사하지 않는 것.** 물리적으로 불가능한 배정, 편명 중복은 검사 대상이 아니었다. validator 는 형식·범위만 봤다.

## 3. 문서와 코드가 다르게 적혀 있던 항목

| # | 문서 | 코드 / 실제 | 처리 |
|---|---|---|---|
| 1 | bug-backlog B7(내가 쓴 것): "한 편 중복", "사람 결정 불필요할 가능성이 높다" | 겹침 87%, 기단 부족으로 사람 결정 필수 | B7 을 실제 원인으로 다시 썼다. **처음 등록할 때 측정 없이 범위를 짐작했다** |
| 2 | data_gen.md "의존해도 되는 대상: config, data_gen 내부" | import-linter 레이어상 domain 도 허용. 이번에 domain 을 import | 문서를 고쳤다 |
| 3 | `generator.py` 주석 "B737-800 — 20 frames" 등 | 스케줄 수요와 맞지 않는 대수 | 대수와 필요 대수를 주석에 적었다 |
| 4 | glossary Rotation "ICN 을 출발해 ICN 으로 돌아오는 왕복" | 생성 데이터의 같은 기체 연속 편이 물리적으로 이어지지 않았다 | 이번 수정으로 일치. Tail assignment 항목 추가 |

## 4. verify 로 잡히지 않아서 별도로 확인한 항목

1. **RNG 스트림 보존.** verify 는 현재 코드만 검사한다. 3년치 frame 을 수정 전·후로 저장해 행 단위로 비교했다 (탐색 #11, #13). 테스트로 남기지는 않았다. 3년치 생성이 35초 걸리고 이전 코드가 필요하기 때문이다.
2. **배정 정책이 시뮬레이션에 주는 영향.** 테스트는 "겹침 없음"만 본다. 처음 정책(가장 오래 쉰 기체)은 모든 테스트를 통과했지만 fixture edge 가 6개가 되어 전파 시연이 거의 의미가 없어졌다. edge 수를 직접 세 보고서야 알았다 (탐색 #15). best fit 으로 바꾼 것은 내 판단이다. ADR 0007 에 적었고, 사람이 다르게 원하면 바꿀 수 있다.
3. **validator 가 실제 오래된 DB 를 잡는지.** 단위 테스트는 작은 손 데이터만 쓴다. 로컬 3년치 DB 에 읽기 전용으로 실행해 확인했다.
4. **digest 갱신이 데이터 때문인지.** 시뮬레이션 코드 비교 테스트 109건이 그대로 통과하는지, 사라진 edge 가 왜 사라졌는지를 따로 셌다 (탐색 #15, #16). 처음 낸 사유 목록은 그래프의 14h 창을 빠뜨려 틀렸고, 다시 계산했다.
5. **pytest 시간.** verify 는 시간을 판정하지 않는다. 30초대에서 50~80초로 보였는데, 이전 코드도 같은 기계에서 47초라 대부분 기계 부하였다.

## 5. 개선 제안

| 대상 | 제안 | 줄어드는 항목 |
|---|---|---|
| 절차 | bug-backlog 에 항목을 등록할 때 "현상"을 한 사례가 아니라 측정한 범위(전체 중 몇 건)로 적는다. 측정이 없으면 "범위 미측정"이라고 쓴다 | 3-1 |
| 문서 | data_gen.md 데이터 계약에 "물리적 불변식" 절을 둔다: 기체 겹침 없음, 편명 고유, 시각 순서. 각 불변식에 대응하는 validator 검사 이름을 적는다 | 2-1, 2-5 |
| 테스트 | 생성기 변경용 "RNG 보존" 보조 스크립트를 `scripts/` 에 둔다 (기준 커밋과 현재 코드로 짧은 기간을 생성해 지정 컬럼 외 행 비교). 매 PR 테스트가 아니라 생성기 변경 시 수동 실행 | 4-1 |
| 테스트 | fixture 전파 그래프의 "모양" 지표(edge 수 하한, buffer 분포)를 느슨하게 고정한다. 예: edge ≥ 20. 배정 정책이 바뀌어 전파가 사라지는 것을 잡는다 | 4-2 |
| 코드 | B8: `propagate` 가 후손만 돌고 음수 buffer 를 0 으로 볼지 결정. 지금은 데이터가 깨끗하다는 전제에 기댄다 | 4-4 |
| 문서 | 숫자 근거를 낼 때 측정 스크립트를 scratchpad 에만 두지 말고, 재현 가능한 명령을 회고나 ADR 에 남긴다. 이번 숫자는 scratchpad 스크립트에서 나왔고 저장소에는 없다 | 4-1, 4-4 |
| 도구 | Windows Git Bash 에서 긴 heredoc 안의 `'`·백틱이 파싱 오류를 냈다(탐색 #13 직전). 긴 편집 스크립트는 파일로 쓰고 실행한다 | — |
