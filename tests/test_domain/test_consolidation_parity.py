"""domain 통합 비교 테스트: 같은 입력 → 같은 출력.

docs/exec-plans 의 domain-consolidation 1단계. 턴타임, 광동체 분류, 기종 호환,
rotation footprint 가 aircraft·crew·propagation 에 따로 정의되어 있던 시점(main 0c33942)의
출력을 고정한다. 상수를 domain 으로 옮긴 뒤에도 이 파일의 기대값은 바꾸지 않는다.

- 기대값은 모듈 상수를 import 하지 않고 숫자로 적는다. 옮기는 대상과 비교하면 의미가 없다.
- 모듈의 private 이름 대신 옮긴 뒤에도 남는 동작(공개 클래스, footprint 결과)으로 검사한다.
- footprint 공식은 모듈마다 다르다 (aircraft·propagation 2·turn, crew 1·turn). 그대로 고정한다.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta

import pytest

from argos.optimization.aircraft import AircraftAssigner, AircraftResource, FlightTask
from argos.optimization.crew import CrewAssigner, CrewMember, FlightLeg
from argos.simulation.propagation import DelayPropagator, FlightNode

OP_DAY = date(2024, 6, 15)
MIDNIGHT = datetime(2024, 6, 15, tzinfo=UTC)

# 0c33942 시점의 턴타임 (분). 목록에 없는 기종은 협동체 값(45)으로 처리된다.
TURN_MIN = {
    "B737-800": 45,
    "A321neo": 45,
    "B777-300ER": 60,
    "B787-9": 60,
    "B747-8i": 60,
    "A380-800": 45,  # 미등록 기종
    "": 45,
}

# 0c33942 시점의 기종 호환 (요구 기종 → 대체 가능 기종, 순서 포함)
COMPAT = {
    "B737-800": ["B737-800", "A321neo"],
    "A321neo": ["A321neo", "B737-800"],
    "B777-300ER": ["B777-300ER", "B787-9", "B747-8i"],
    "B787-9": ["B787-9", "B777-300ER"],
    "B747-8i": ["B747-8i", "B777-300ER", "B787-9"],
    "A380-800": ["A380-800"],
}

BLOCKS = [60, 125, 600]


# ── 턴타임과 footprint ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("atype", list(TURN_MIN))
@pytest.mark.parametrize("block", BLOCKS)
def test_propagation_icn_ready_is_2block_2turn(atype: str, block: int) -> None:
    dep = MIDNIGHT.replace(hour=8)
    node = FlightNode(
        flight_id="F1",
        flight_number="KE001",
        route_id="ICN-XYZ",
        aircraft_registration="HL0001",
        aircraft_type=atype,
        origin_iata="ICN",
        dest_iata="XYZ",
        scheduled_dep_utc=dep,
        scheduled_arr_utc=dep + timedelta(minutes=block),
        block_time_minutes=block,
        pax_boarded=100,
        status="SCH",
    )
    turn = TURN_MIN[atype]
    assert node.earliest_return_dep_utc == dep + timedelta(minutes=block + turn)
    assert node.earliest_icn_ready_utc == dep + timedelta(minutes=2 * block + 2 * turn)


@pytest.mark.parametrize("atype", list(TURN_MIN))
@pytest.mark.parametrize("block", BLOCKS)
def test_propagation_edge_min_elapsed_is_2block_2turn(atype: str, block: int) -> None:
    import pandas as pd

    dep1 = MIDNIGHT.replace(hour=1)
    dep2 = dep1 + timedelta(hours=13)  # _MAX_ROTATION_GAP_HOURS(14) 안
    rows = [
        {
            "flight_id": fid,
            "flight_number": fid,
            "route_id": "ICN-XYZ",
            "aircraft_registration": "HL0001",
            "aircraft_type": atype,
            "origin_iata": "ICN",
            "dest_iata": "XYZ",
            "scheduled_dep_utc": d,
            "scheduled_arr_utc": d + timedelta(minutes=block),
            "block_time_minutes": block,
            "pax_boarded": 100,
            "status": "SCH",
        }
        for fid, d in (("F1", dep1), ("F2", dep2))
    ]
    G = DelayPropagator(db_path=None).build_rotation_graph(pd.DataFrame(rows))  # type: ignore[arg-type]
    edge = G.edges["F1", "F2"]
    expected = 2 * block + 2 * TURN_MIN[atype]
    assert edge["min_elapsed_minutes"] == expected
    assert edge["buffer_minutes"] == 13 * 60 - expected


@pytest.mark.parametrize("atype", ["B737-800", "A321neo", "B777-300ER", "B787-9", "B747-8i"])
@pytest.mark.parametrize("block", [60, 125])
def test_crew_footprint_boundary_is_checkin_2block_1turn_post(atype: str, block: int) -> None:
    """같은 CAPT 가 F2 를 맡으려면 출발 간격 ≥ 60 + 2·block + 1·turn + 30.

    정각이면 두 편 모두 CAPT 배정, 1분 앞이면 한 편만.
    """
    span = 60 + 2 * block + TURN_MIN[atype] + 30
    dep1 = MIDNIGHT.replace(hour=1)
    crew = [
        CrewMember("C1", "C1", "CAPT", atype, "ICN", MIDNIGHT),
        CrewMember("F1", "F1", "FO", atype, "ICN", MIDNIGHT),
    ]

    def legs(gap: int) -> list[FlightLeg]:
        dep2 = dep1 + timedelta(minutes=gap)
        return [
            FlightLeg("L1", "KE001", atype, "ICN", "XYZ", dep1, block, 200),
            FlightLeg("L2", "KE002", atype, "ICN", "XYZ", dep2, block, 100),
        ]

    result = CrewAssigner().solve(legs(span), crew, OP_DAY, time_limit_seconds=5)
    assert sorted(result.captain_assignments) == ["L1", "L2"]
    result = CrewAssigner().solve(legs(span - 1), crew, OP_DAY, time_limit_seconds=5)
    assert len(result.captain_assignments) == 1


@pytest.mark.parametrize("atype", ["B737-800", "A321neo", "B777-300ER", "B787-9", "B747-8i"])
def test_crew_duty_release_is_2block_1turn_post(atype: str) -> None:
    """_validate_far117 의 release = dep + 2·block + 1·turn + post(30)."""
    block = 125
    dep = MIDNIGHT.replace(hour=1)
    leg = FlightLeg("F1", "KE001", atype, "ICN", "XYZ", dep, block, 100)
    cm = CrewMember("C1", "C1", "CAPT", atype, "ICN", MIDNIGHT)
    duties, _ = CrewAssigner._validate_far117([leg], [cm], {"F1": "C1"}, {}, MIDNIGHT)
    (duty,) = duties
    assert duty.report_utc == dep - timedelta(minutes=60)
    assert duty.release_utc == dep + timedelta(minutes=2 * block + TURN_MIN[atype] + 30)


def _aircraft_task(fid: str, atype: str, dep: datetime, block: int, pax: int) -> FlightTask:
    return FlightTask(fid, fid, "ICN-XYZ", atype, "ICN", "XYZ", dep, block, pax)


@pytest.mark.parametrize("atype", ["B737-800", "A321neo", "B777-300ER", "B787-9", "B747-8i"])
@pytest.mark.parametrize("block", [60, 125])
def test_aircraft_footprint_boundary_is_2block_2turn(atype: str, block: int) -> None:
    """같은 기체에 F2 를 footprint 끝 정각에 두면 둘 다 배정, 1분 앞이면 하나만 배정."""
    dep1 = MIDNIGHT.replace(hour=1)
    footprint = 2 * block + 2 * TURN_MIN[atype]
    fleet = [AircraftResource("HL0001", atype, "ICN", MIDNIGHT)]

    at_end = [
        _aircraft_task("F1", atype, dep1, block, 200),
        _aircraft_task("F2", atype, dep1 + timedelta(minutes=footprint), block, 100),
    ]
    result = AircraftAssigner().solve(at_end, fleet, OP_DAY, time_limit_seconds=5)
    assert sorted(result.assignments) == ["F1", "F2"]

    one_early = [
        _aircraft_task("F1", atype, dep1, block, 200),
        _aircraft_task("F2", atype, dep1 + timedelta(minutes=footprint - 1), block, 100),
    ]
    result = AircraftAssigner().solve(one_early, fleet, OP_DAY, time_limit_seconds=5)
    assert sorted(result.assignments) == ["F1"]


# ── 기종 호환 ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("required", list(COMPAT))
@pytest.mark.parametrize("candidate", list(COMPAT))
def test_aircraft_solver_type_compat(required: str, candidate: str) -> None:
    """기체 하나만 있을 때 배정 여부 = candidate 가 required 의 호환 목록에 있는지."""
    task = _aircraft_task("F1", required, MIDNIGHT.replace(hour=9), 120, 200)
    fleet = [AircraftResource("HL0001", candidate, "ICN", MIDNIGHT)]
    result = AircraftAssigner().solve([task], fleet, OP_DAY, time_limit_seconds=5)
    assert ("F1" in result.assignments) == (candidate in COMPAT[required])


@pytest.mark.parametrize("required", list(COMPAT))
def test_propagation_spare_search_order(
    required: str, fixture_db_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_find_spare_aircraft 는 정확 기종 → 호환 기종 순서로 찾는다.

    비행이 없는 날짜를 써서 busy 집합을 비운다. 기종마다 기체 하나씩 두고,
    앞 순위 기체를 하나씩 지워 가며 다음 순위가 선택되는지 본다.
    """
    from pathlib import Path

    prop = DelayPropagator(Path(fixture_db_path))
    all_types = ["B737-800", "A321neo", "B777-300ER", "B787-9", "B747-8i", "A380-800"]
    fleet = {t: [f"REG-{t}"] for t in all_types}
    monkeypatch.setattr(prop, "load_fleet_registrations", lambda _d: fleet)
    empty_day = date(2030, 1, 1)

    for expected in COMPAT[required]:
        assert prop._find_spare_aircraft(required, empty_day) == f"REG-{expected}"
        del fleet[expected]
    assert prop._find_spare_aircraft(required, empty_day) is None


# ── fixture DB 전체: 전파 그래프와 시나리오 ──────────────────────────────────────

# 아래 digest 는 0c33942 시점 코드로 fixture DB(2024-06-15, seed 42)에서 계산했다.
EXPECTED_EDGES = 62
EXPECTED_NODES = 146
EXPECTED_EDGE_DIGEST = "15a93f54e52e5ce7"
EXPECTED_PROPAGATION_DIGEST = "64ca219211f169b4"
EXPECTED_SCENARIO_DIGEST = "c3d76f6b216f7ad3"


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]


def _fixture_graph(fixture_db_path: str):  # type: ignore[no-untyped-def]
    """fixture DB 그래프와, flight_id → 안정 키 함수.

    flight_id 는 uuid4 라 실행마다 바뀐다. 편명·노선·출발시각·등록번호로 비교한다.
    편명만으로는 겹친다 (KE0005 가 ICN-ORD, ICN-HNL 에 같은 기체·시각으로 있음).
    """
    from pathlib import Path

    prop = DelayPropagator(Path(fixture_db_path))
    G = prop.build_rotation_graph(prop.load_flights(OP_DAY))

    def key(fid: str) -> str:
        n: FlightNode = G.nodes[fid]["data"]
        dep = f"{n.scheduled_dep_utc:%d%H%M}"
        return f"{n.flight_number}@{n.route_id}@{dep}@{n.aircraft_registration}"

    return prop, G, key


def test_fixture_rotation_graph_unchanged(fixture_db_path: str) -> None:
    _, G, key = _fixture_graph(fixture_db_path)
    lines = sorted(
        f"{key(u)}>{key(v)}:{d['min_elapsed_minutes']}:{d['buffer_minutes']}"
        for u, v, d in G.edges(data=True)
    )
    assert len(lines) == EXPECTED_EDGES
    assert _digest(lines) == EXPECTED_EDGE_DIGEST


def test_fixture_propagation_unchanged(fixture_db_path: str) -> None:
    prop, G, key = _fixture_graph(fixture_db_path)
    lines = []
    for fid in sorted(G.nodes, key=key):
        r = prop.propagate(G, fid, 180)
        delays = ",".join(f"{key(n.flight_id)}={n.dep_delay_minutes}" for n in r.affected_nodes)
        lines.append(f"{key(fid)}|{r.total_delay_minutes}|{r.total_pax_impacted}|{delays}")
    assert len(lines) == EXPECTED_NODES
    assert _digest(lines) == EXPECTED_PROPAGATION_DIGEST


def test_fixture_scenarios_unchanged(fixture_db_path: str) -> None:
    """시나리오 2(기체 교체)가 호환 기종 spare 를 고르는 경로까지 포함한다."""
    prop, G, key = _fixture_graph(fixture_db_path)
    triggers = [fid for fid in sorted(G.nodes, key=key) if G.out_degree(fid) > 0][:25]
    lines = []
    for fid in triggers:
        for s in prop.generate_scenarios(G, fid, 150, OP_DAY):
            lines.append(
                f"{key(fid)}|{s.scenario_id}|{s.name}|{s.feasibility}|{s.action_required}|"
                f"{s.residual.total_delay_minutes}|{s.residual.total_pax_impacted}|{s.cost_index}"
            )
    assert len(lines) == 75
    assert _digest(lines) == EXPECTED_SCENARIO_DIGEST
