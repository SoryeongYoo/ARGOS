# uav

[`src/argos/uav/`](../../src/argos/uav/)

## 책임

ICN 주변 UAM(도심항공교통) 운항을 시뮬레이션한다. 다루는 것은 버티포트 네트워크, ICN 공역 충돌 검사, ACROSS 비행계획 제출이다. OCC 흐름과는 독립적이고, 대시보드 UAM 탭과 `scripts/uam_demo.py` 에서만 쓰인다.

## 공개 인터페이스

| 모듈 | 진입점 |
|---|---|
| [`models.py`](../../src/argos/uav/models.py) | `GeoPoint`, `Waypoint4D`, `UAMVehicle`, `Vertiport`, `UAMFlightPlan`, `ConflictDetail`, `ACROSSResponse` 와 enum |
| [`network.py`](../../src/argos/uav/network.py) | `VERTIPORTS`, `build_uam_network`, `find_route`, `route_distance_nm`, `estimate_flight_time_min` |
| [`airspace.py`](../../src/argos/uav/airspace.py) | `assess_conflicts` 와 개별 `check_*`(CTR 고도, ILS 회랑, 야간 금지, UAM 간 분리) |
| [`across_client.py`](../../src/argos/uav/across_client.py) | `ACROSSClient`: `submit_plan`, `get_status`, `cancel_plan`, `suggest_uam_alternative` |

## 경계

- `ACROSSClient` 는 시뮬레이션 모드뿐이다. 실제 ACROSS API 를 호출하지 않는다.
- ACROSS 의 "승인"은 외부 당국의 판정을 흉내 낸 것이다. OCC 회복 승인([ADR 0004](../decisions/0004-all-approvals-via-human-gate.md))과는 다르다.
- 분리 기준과 공역 수치의 출처는 모듈 docstring 의 "ACROSS guidelines, MOLIT 2024" 다. 원문과 대조하지 않았으므로 TODO(확인 필요).

## 의존해도 되는 대상

uav 내부만 된다. OCC 쪽 모듈을 import 하지 않는다.

## 알려진 부채

- **C9**: KST 변환을 `(hour + KST_OFFSET_H) % 24` 로 한다. → [conventions](../conventions.md)
- `check_ils_corridor` 는 회랑 방향(`hdg`)과 폭(`width_nm`)을 쓰지 않는다. 그래서 회랑이 아니라 원형으로 판정한다. → [bug-backlog](../exec-plans/active/bug-backlog.md)
