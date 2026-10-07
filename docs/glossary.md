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
| Footprint | 한 편 배정으로 기체·승무원이 묶이는 시간. 공식은 모듈마다 다르다 | [ADR 0001](decisions/0001-domain-single-source.md) |
| Turn time (턴타임) | 도착 후 다음 출발까지의 최소 지상 시간. 협동체 45분, 광동체 60분 | `_MIN_TURN_*` (3곳 중복) |
| Block time | 출발 블록아웃부터 도착 블록인까지의 시간. 지상 이동(taxi) 포함 | `domain/block_time.py`, `data_gen/routes.py` |
| MCT | Minimum Connection Time. 환승에 필요한 최소 연결 시간 | `domain/mct.py` |
| Wide body / Narrow body | 광동체(B777-300ER, B787-9, B747-8i) / 협동체(B737-800, A321neo) | `_WIDE_BODY` |
| 기체 등록부호 | B737-800 HL74xx, A321neo HL82xx, B777-300ER HL77xx, B787-9 HL80xx, B747-8i HL75xx | `data_gen/generator.py:FLEET` |
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
| FDP | Flight Duty Period. 출근 보고부터 마지막 편 블록인까지의 근무 시간 | `far117.max_fdp_hours` |
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
