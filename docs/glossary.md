# 용어집

코드와 문서에 나오는 약어와 도메인 용어. "코드 위치"는 그 개념을 정의하거나 주로 쓰는 곳이다.

## 운항 통제

| 용어 | 뜻 | 코드 위치 |
|---|---|---|
| OCC | Operations Control Center. 운항통제센터. 지연·결항 대응을 결정하는 조직. ARGOS 의 사용자 | [agents](architecture/agents.md) |
| KE | 대한항공 IATA 코드. 편명 접두어 | `data_gen/generator.py` |
| ICN / RKSI | 인천국제공항 IATA / ICAO 코드. 허브이자 승무원 기지 | 전역 |
| UTC / KST | 저장·계산 시각 / 표시용 한국 표준시 (UTC+9) | [conventions](conventions.md) |
| Rotation | 한 기체가 ICN 을 출발해 목적지를 거쳐 ICN 으로 돌아오는 왕복 | [conventions](conventions.md) |
| Cascade (전파) | 앞 편의 지연이 같은 기체의 다음 편으로 번지는 것 | `simulation/propagation.py` |
| ICN 블록인 시각 | 왕복에서 ICN 으로 돌아와 블록인하는 시각. 출발 + `2·block + turn`(목적지 턴 1회). 아래 구간들의 공통 기준 | `domain.rotation.icn_block_in_offset` |
| Footprint (span) | 한 편 배정으로 자원이 묶이는 시간. 기체와 승무원은 개념이 달라 공식도 다르다: 기체는 `aircraft_rotation_span`, 승무원은 `crew_duty_span` | [`domain/rotation.py`](../src/argos/domain/rotation.py) |
| Aircraft rotation span | 출발부터 다음 ICN 출발 가능 시각까지 = 블록인 + ICN 턴 = `2·block + 2·turn` | `domain.rotation.aircraft_rotation_span` |
| Turn time (턴타임) | **기체**가 도착 후 다음 출발까지 필요한 최소 지상 준비 시간. 협동체 45분, 광동체 60분. MCT 와 다르다 | `domain.fleet.min_turn_minutes` |
| Block time | 출발 블록아웃부터 도착 블록인까지의 시간. 지상 이동(taxi) 포함. 기준 출처는 `routes.py`, `calculate_block_time()` 은 없는 노선용 추정기 | `data_gen/routes.py`, `domain/block_time.py` |
| MCT | Minimum Connection Time. **승객·승무원**이 도착 편에서 출발 편으로 갈아타는 데 필요한 최소 시간. 기체 지상 준비 시간인 turn 과 다른 개념이다. 런타임 미연결 | `domain/mct.py` |
| Wide body / Narrow body | 광동체(B777-300ER, B787-9, B747-8i) / 협동체(B737-800, A321neo) | `domain.fleet.WIDE_BODY_TYPES` |
| 기체 등록부호 | B737-800 HL74xx(54), A321neo HL82xx(10), B777-300ER HL77xx(72), B787-9 HL80xx(9), B747-8i HL75xx(5) | `data_gen/generator.py:FLEET`, [ADR 0007](decisions/0007-fleet-sized-for-overlap-free-tails.md) |
| Tail assignment (기체 배정) | 편마다 기체 등록부호를 정하는 것. 같은 기체의 rotation 은 겹치면 안 된다 | `SyntheticDataGenerator._assign_tails` |
| OTP | On-Time Performance. 출발 지연 15분 이내 비율 | `data_gen/validator.py` |
| PAX | 승객 | 전역 |
| Recovery scenario | 지연에 대한 회복안. 항상 3개를 만들고 사람이 승인한다 | `simulation/propagation.py` |
| human_gate | 사람 승인을 받을 때까지 LangGraph 를 멈추는 노드 | [ADR 0004](decisions/0004-all-approvals-via-human-gate.md) |

## 비용

| 용어 | 뜻 | 코드 위치 |
|---|---|---|
| CI (Cost Index) | 운항 비용지수. 시간 비용 ÷ 연료 비용. 0 은 연료 최소, 999 는 시간 최소 | `domain/cost_index.py` |
| relative_cost | 회복 시나리오의 상대 비용 점수(0.0 무비용 ~ 1.0 최고). CI 와 무관하다. 현재 필드 이름은 `cost_index` 이고 개명 예정 | [ADR 0003](decisions/0003-rename-relative-cost.md) |
| DOC | Direct Operating Cost. 직접 운항비 | `domain/cost_index.py` |

## 승무원 규정 (FAR 117)

| 용어 | 뜻 | 코드 위치 |
|---|---|---|
| FAR 117 | 미국 14 CFR Part 117 승무원 비행·근무 시간 제한. 국토교통부 기준이 이를 따른다고 코드 docstring 에 적혀 있다 | `domain/far117.py` |
| Duty period (근무 구간) | 출근 보고(출발 60분 전)부터 마무리 업무(블록인 + 30분) 끝까지. crew 최적화의 no-overlap 구간 | `domain.rotation.crew_duty_span` |
| FDP | Flight Duty Period. 출근 보고부터 마지막 편 블록인까지의 근무 시간. duty period 와 달리 블록인 뒤 마무리 30분을 넣지 않는다. FAR 117 한도는 이 값에 건다 | `domain.rotation.crew_fdp_span`, `far117.max_fdp_hours` |
| Duty period vs FDP | duty period = FDP + 마무리 30분. **현재 `crew.py` `_validate_far117` 은 duty period 를 FDP 로 판정한다** (30분 과대). 교체는 [fdp-hard-constraint](exec-plans/active/fdp-hard-constraint.md) 에서 | `optimization/crew.py` |
| FT | Flight Time. 비행시간 | `MAX_FT_*` |
| Table B (Appendix B) | 보고 시각과 구간 수별 FDP 한도 표. 코드 값은 원문 대조 전이라 **검증 대기** | [ADR 0002](decisions/0002-fdp-hard-constraint.md) |
| WOCL | Window of Circadian Low. 생체리듬 저점 시간대, 현지 02:00–05:59 | `far117.is_in_wocl` |
| Augmented crew | 증원 승무원. 조종사 3명 이상 | `far117.LONG_HAUL_MIN_CREW` |
| Segment (구간) | FDP 안의 비행 편 수 | `max_fdp_hours(num_segments=)` |

## 지연 코드

| 용어 | 뜻 | 코드 위치 |
|---|---|---|
| AHM 730 | IATA Airport Handling Manual 의 지연 코드 표준. 2자리 `"00"`–`"99"` | `data_gen/schemas.py:IATA_DELAY_CODES` |
| Delay responsibility | 지연 책임 주체 분류 | `schemas.DelayResponsibility` |

## UAM / 공역

| 용어 | 뜻 | 코드 위치 |
|---|---|---|
| UAM / AAM | Urban / Advanced Air Mobility. 도심항공교통 | [uav](architecture/uav.md) |
| Vertiport | UAM 이착륙장 | `uav/network.py:VERTIPORTS` |
| ACROSS | 국토교통부 UAM 교통관리 시스템. 코드에서는 시뮬레이션 클라이언트만 있다 | `uav/across_client.py` |
| CTR | Control Zone. ICN 관제권. 코드 값은 반경 5NM, 지상 ~2000ft | `uav/airspace.py` |
| TMA | Terminal Manoeuvring Area. 접근관제구역. 코드 값은 30NM | `uav/airspace.py` |
| ILS | Instrument Landing System. 계기착륙 접근 경로. UAM 진입 금지 회랑 | `uav/airspace.py:_ILS_CORRIDORS` |
| NM / ft | 해리 / 피트 | 전역 |

## 도구

| 용어 | 뜻 |
|---|---|
| CP-SAT | OR-Tools 의 제약 만족·최적화 솔버. 기체·승무원 배정에 쓴다 ([optimization](architecture/optimization.md)) |
| Replacement scan | DuckDB 가 SQL 의 테이블 이름을 같은 이름의 Python DataFrame 변수로 해석하는 기능 ([conventions](conventions.md)) |
| ADR | Architecture Decision Record. [docs/decisions/](decisions/) |
