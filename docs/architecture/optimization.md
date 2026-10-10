# optimization

[`src/argos/optimization/`](../../src/argos/optimization/)

## 책임

OR-Tools CP-SAT 으로 자원을 재배정한다.

- [`aircraft.py`](../../src/argos/optimization/aircraft.py): 지연·결항으로 영향받은 편에 대체 기체를 배정한다. 목표는 커버한 승객 수(`pax_boarded × priority`) 최대화이고, 기종 대체에는 패널티를 준다.
- [`crew.py`](../../src/argos/optimization/crew.py): 기장·부기장을 배정한다. 승무원 풀은 합성으로 만들고, crew DB 는 없다.

## 공개 인터페이스

- `AircraftAssigner.solve(tasks, aircraft, op_day, time_limit_seconds=30.0)` → `AssignmentResult`. DB 로더는 `AircraftAssigner.load_from_db(...)` 다.
- `CrewAssigner.solve(legs, crew, op_day, time_limit_seconds=30.0)` → `CrewAssignmentResult`. 승무원 풀은 `CrewAssigner.generate_crew(...)` 로 만든다.
- 결과의 `status` 는 `OPTIMAL`/`FEASIBLE`/`INFEASIBLE`/`UNKNOWN` 중 하나다.

## 경계와 제약

- **안전 제약은 완화하지 않는다.** 풀리지 않으면 미배정 편으로 드러나야 한다.
- 현재 FAR 117 관련 hard constraint 는 일일 비행시간 480분 하나다. FDP 는 사후 검증(`far117_violations`)만 한다. → [ADR 0002](../decisions/0002-fdp-hard-constraint.md)
- 실제 운항 규모에서 crew CP-SAT 은 30초 시간 제한을 다 쓰고 FEASIBLE 로 끝난다. 2024-06-15, cascade 54편으로 측정했다. 테스트는 `agents.tools` 의 `*_SOLVER_TIME_LIMIT_S` 를 monkeypatch 로 1초로 낮춘다.
- `ortools>=9.11,<9.12` 로 고정되어 있다. 9.12 이상은 Windows 에서 `CpSolver.Solve` 가 비정상 종료한다.

## 의존해도 되는 대상

domain 만 된다. 현재 `crew` 는 `domain.far117` 을 import 하고, `aircraft` 는 argos 내부 import 가 없다.

## 알려진 부채

- **D2, C5**: 해소. 턴타임·기종 호환은 [`domain/fleet.py`](../../src/argos/domain/fleet.py), 구간은 [`domain/rotation.py`](../../src/argos/domain/rotation.py) 를 쓴다. aircraft 는 `aircraft_rotation_span`(`2·block + 2·turn`), crew 는 `crew_duty_span`(`60 + 2·block + turn + 30`). 서로 다른 개념이다 ([domain-consolidation](../exec-plans/completed/domain-consolidation.md)).
- crew 의 FDP 판정은 duty span(마무리 30분 포함)을 쓴다. FAR 117 FDP 는 `crew_fdp_span` 이다. → [fdp-hard-constraint](../exec-plans/active/fdp-hard-constraint.md)
- **C2**: `_MAX_FLIGHT_TIME_MIN` 이 far117 상수를 쓰지 않는다. `_MIN_REST_MIN` 은 정의만 있고 쓰이지 않는다.
- **D8**: `AircraftAssigner.load_from_db` 가 계산 클래스 안에서 I/O 를 한다.
- `crew.py` 의 B007 `noqa`(`cm` 미사용 루프 변수)
