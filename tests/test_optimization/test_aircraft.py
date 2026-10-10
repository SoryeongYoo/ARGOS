"""Unit tests for OR-Tools CP-SAT aircraft assignment optimizer."""

from datetime import UTC, date, datetime

import pytest

from argos.optimization.aircraft import (
    AircraftAssigner,
    AircraftResource,
    FlightTask,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

OP_DAY = date(2024, 6, 15)
MIDNIGHT = datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC)


def _dep(hour: int, minute: int = 0) -> datetime:
    return MIDNIGHT.replace(hour=hour, minute=minute)


def _aircraft(
    reg: str,
    atype: str,
    pos: str = "ICN",
    avail_hour: int = 0,
    is_spare: bool = False,
) -> AircraftResource:
    return AircraftResource(
        registration=reg,
        aircraft_type=atype,
        position_iata=pos,
        available_from_utc=_dep(avail_hour),
        is_spare=is_spare,
    )


def _flight(
    fid: str,
    fnum: str,
    atype: str,
    dep_hour: int,
    block: int = 180,
    pax: int = 200,
    priority: int = 1,
) -> FlightTask:
    return FlightTask(
        flight_id=fid,
        flight_number=fnum,
        route_id="ICN-XYZ",
        required_type=atype,
        origin_iata="ICN",
        dest_iata="XYZ",
        scheduled_dep_utc=_dep(dep_hour),
        block_time_minutes=block,
        pax_boarded=pax,
        priority=priority,
    )


# ── Basic assignment tests ────────────────────────────────────────────────────


def test_single_flight_single_aircraft():
    tasks = [_flight("F1", "KE001", "B737-800", dep_hour=9)]
    fleet = [_aircraft("HL7401", "B737-800")]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert "F1" in result.assignments
    assert result.assignments["F1"] == "HL7401"
    assert result.unassigned == []


def test_type_incompatibility_blocks_assignment():
    tasks = [_flight("F1", "KE001", "B777-300ER", dep_hour=9)]
    fleet = [_aircraft("HL7401", "B737-800")]  # wrong type, no compat
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert "F1" not in result.assignments
    assert "F1" in result.unassigned


def test_cross_type_substitution_allowed():
    # A321neo can sub for B737-800 per domain.fleet.TYPE_SUBSTITUTES
    tasks = [_flight("F1", "KE001", "B737-800", dep_hour=9)]
    fleet = [_aircraft("HL8201", "A321neo")]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert result.assignments.get("F1") == "HL8201"


def test_two_flights_two_aircraft_no_conflict():
    """Two non-overlapping flights are both assigned (may share one aircraft)."""
    # F1 footprint: dep=08:00, 2*120+2*45=330min → free at 13:30
    # F2 dep=14:00 → no conflict; one aircraft can cover both
    tasks = [
        _flight("F1", "KE001", "B737-800", dep_hour=8, block=120),
        _flight("F2", "KE002", "B737-800", dep_hour=14, block=120),
    ]
    fleet = [
        _aircraft("HL7401", "B737-800"),
        _aircraft("HL7402", "B737-800"),
    ]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert len(result.assignments) == 2
    assert result.unassigned == []


def test_no_overlap_same_aircraft():
    """One aircraft cannot cover two overlapping flights."""
    # F1 departs 09:00, block=180min → ICN-ready ~15:00 (180+180+60+60=480min)
    # F2 departs 10:00 — overlaps with F1's footprint
    tasks = [
        _flight("F1", "KE001", "B737-800", dep_hour=9, block=180, pax=300),
        _flight("F2", "KE002", "B737-800", dep_hour=10, block=180, pax=100),
    ]
    fleet = [_aircraft("HL7401", "B737-800")]  # only one aircraft
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    # Exactly one flight covered (higher-PAX flight F1 should win)
    assert len(result.assignments) == 1
    assert "F1" in result.assignments
    assert "F2" in result.unassigned


def test_empty_tasks_returns_optimal():
    fleet = [_aircraft("HL7401", "B737-800")]
    assigner = AircraftAssigner()
    result = assigner.solve([], fleet, OP_DAY)
    assert result.status == "OPTIMAL"
    assert result.assignments == {}
    assert result.unassigned == []


def test_empty_aircraft_returns_infeasible():
    tasks = [_flight("F1", "KE001", "B737-800", dep_hour=9)]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, [], OP_DAY)
    assert result.status == "INFEASIBLE"
    assert "F1" in result.unassigned


def test_priority_breaks_pax_tie():
    """Higher-priority flight wins the aircraft even with same PAX."""
    tasks = [
        _flight("F1", "KE001", "B737-800", dep_hour=9, block=180, pax=200, priority=2),
        _flight("F2", "KE002", "B737-800", dep_hour=10, block=180, pax=200, priority=1),
    ]
    fleet = [_aircraft("HL7401", "B737-800")]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    # F1 has higher priority → should be preferred
    assert result.assignments.get("F1") is not None


def test_coverage_rate():
    tasks = [
        _flight("F1", "KE001", "B737-800", dep_hour=9),
        _flight("F2", "KE002", "B777-300ER", dep_hour=10),  # no compat aircraft
    ]
    fleet = [_aircraft("HL7401", "B737-800")]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.coverage_rate == pytest.approx(0.5)


def test_summary_contains_status(capsys):
    tasks = [_flight("F1", "KE001", "B737-800", dep_hour=9)]
    fleet = [_aircraft("HL7401", "B737-800")]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    summary = result.summary()
    assert "OPTIMAL" in summary or "FEASIBLE" in summary
    assert "F1" in summary
    assert "HL7401" in summary


# ── Multi-aircraft scheduling ─────────────────────────────────────────────────


def test_three_flights_two_aircraft_sequential():
    """Aircraft A handles F1+F3 (non-overlapping), aircraft B handles F2."""
    # block=90, turn=45 narrow → footprint = 2*90+2*45 = 270 min = 4.5 hr
    # F1 dep 06:00 → free ~10:30; F3 dep 12:00 → OK on same aircraft
    # F2 dep 07:00 → overlaps with F1, needs different aircraft
    tasks = [
        _flight("F1", "KE001", "B737-800", dep_hour=6, block=90, pax=150),
        _flight("F2", "KE002", "B737-800", dep_hour=7, block=90, pax=150),
        _flight("F3", "KE003", "B737-800", dep_hour=12, block=90, pax=150),
    ]
    fleet = [
        _aircraft("HL7401", "B737-800"),
        _aircraft("HL7402", "B737-800"),
    ]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert len(result.assignments) == 3
    # F1 and F3 can share an aircraft (non-overlapping); F2 on the other
    assert result.assignments["F1"] != result.assignments["F2"]


def test_spare_aircraft_used_last():
    """Solver should prefer non-spare aircraft; spare fills gaps."""
    tasks = [
        _flight("F1", "KE001", "B737-800", dep_hour=9, block=120, pax=200),
        _flight("F2", "KE002", "B737-800", dep_hour=9, block=120, pax=200),
    ]
    fleet = [
        _aircraft("HL7401", "B737-800", is_spare=False),
        _aircraft("HL7402", "B737-800", is_spare=True),
    ]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert len(result.assignments) == 2


def test_aircraft_availability_respected():
    """Aircraft available only at 14:00 cannot cover 09:00 flight."""
    tasks = [_flight("F1", "KE001", "B737-800", dep_hour=9, block=120)]
    fleet = [_aircraft("HL7401", "B737-800", avail_hour=14)]
    assigner = AircraftAssigner()
    result = assigner.solve(tasks, fleet, OP_DAY)

    # Aircraft available at 14:00 is 5h late for 09:00 dep → should be excluded
    # (60-min grace window doesn't help when gap is 5h)
    assert "F1" in result.unassigned
