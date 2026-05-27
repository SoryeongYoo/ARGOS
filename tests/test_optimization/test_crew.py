"""Unit tests for CP-SAT crew roster optimizer."""

from datetime import date, datetime, timezone

import pytest

from argos.optimization.crew import (
    CrewAssigner,
    CrewMember,
    FlightLeg,
    _crew_footprint,
    _is_rated,
    _min_turn,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

OP_DAY  = date(2024, 6, 15)
MIDNIGHT = datetime(2024, 6, 15, 0, 0, 0, tzinfo=timezone.utc)


def _dep(hour: int, minute: int = 0) -> datetime:
    return MIDNIGHT.replace(hour=hour, minute=minute)


def _leg(
    fid: str,
    fnum: str,
    atype: str = "B737-800",
    dep_hour: int = 9,
    block: int = 180,
    pax: int = 189,
) -> FlightLeg:
    return FlightLeg(
        flight_id=fid,
        flight_number=fnum,
        aircraft_type=atype,
        origin_iata="ICN",
        dest_iata="NRT",
        scheduled_dep_utc=_dep(dep_hour),
        block_time_minutes=block,
        pax_boarded=pax,
    )


def _capt(cid: str, rating: str = "B737-800", avail_hour: int = 0) -> CrewMember:
    return CrewMember(
        crew_id=cid,
        name=cid,
        role="CAPT",
        type_rating=rating,
        position_iata="ICN",
        available_from_utc=_dep(avail_hour),
    )


def _fo(cid: str, rating: str = "B737-800", avail_hour: int = 0) -> CrewMember:
    return CrewMember(
        crew_id=cid,
        name=cid,
        role="FO",
        type_rating=rating,
        position_iata="ICN",
        available_from_utc=_dep(avail_hour),
    )


# ── Helper function tests ─────────────────────────────────────────────────────

def test_is_rated_same_type():
    assert _is_rated("B737-800", "B737-800") is True


def test_is_rated_narrow_cross():
    assert _is_rated("B737-800", "A321neo") is True
    assert _is_rated("A321neo", "B737-800") is True


def test_is_rated_narrow_wide_incompatible():
    assert _is_rated("B737-800", "B777-300ER") is False
    assert _is_rated("B777-300ER", "B737-800") is False


def test_is_rated_wide_cross():
    assert _is_rated("B777-300ER", "B787-9") is True
    assert _is_rated("B747-8i", "B787-9") is True


def test_crew_footprint_narrow():
    # check_in(60) + 2*block(360) + turn(45) + post(30) = 495
    assert _crew_footprint(180, "B737-800") == 495


def test_crew_footprint_wide():
    # 60 + 2*240 + 60 + 30 = 630
    assert _crew_footprint(240, "B777-300ER") == 630


# ── Basic assignment tests ────────────────────────────────────────────────────

def test_single_leg_gets_capt_and_fo():
    legs = [_leg("F1", "KE101")]
    crew = [_capt("C001"), _fo("F001")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert "F1" in result.captain_assignments
    assert "F1" in result.fo_assignments
    assert result.captain_assignments["F1"] != result.fo_assignments["F1"]
    assert result.unassigned_captain == []
    assert result.unassigned_fo == []


def test_type_rating_incompatibility():
    """Wide-body crew cannot be assigned to narrow-body flight."""
    legs = [_leg("F1", "KE101", atype="B737-800")]
    crew = [_capt("C001", rating="B777-300ER"), _fo("F001", rating="B777-300ER")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    assert "F1" in result.unassigned_captain
    assert "F1" in result.unassigned_fo


def test_narrow_crew_on_a321neo():
    """B737-800 rated crew can operate A321neo (same NARROW group)."""
    legs = [_leg("F1", "KE101", atype="A321neo")]
    crew = [_capt("C001", rating="B737-800"), _fo("F001", rating="B737-800")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    assert "F1" in result.captain_assignments
    assert "F1" in result.fo_assignments


def test_same_crew_not_capt_and_fo():
    """A crew member cannot be both CAPT and FO on the same flight."""
    legs = [_leg("F1", "KE101")]
    crew = [_capt("C001")]  # only one crew member available
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    # Can't fill both slots with one person
    capt = result.captain_assignments.get("F1")
    fo   = result.fo_assignments.get("F1")
    if capt and fo:
        assert capt != fo


def test_no_overlap_per_crew():
    """Crew cannot be assigned to two overlapping flights."""
    # F1 dep=09:00, block=180 → footprint ends around 15:15
    # F2 dep=10:00 overlaps
    legs = [
        _leg("F1", "KE101", dep_hour=9,  block=180, pax=300),
        _leg("F2", "KE102", dep_hour=10, block=180, pax=100),
    ]
    crew = [_capt("C001"), _fo("F001")]  # one set only
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    # Crew can only cover one flight each without overlap
    capt_f1 = result.captain_assignments.get("F1")
    capt_f2 = result.captain_assignments.get("F2")
    # If both assigned, they must be different crew
    if capt_f1 and capt_f2:
        assert capt_f1 != capt_f2


def test_empty_legs_returns_optimal():
    crew = [_capt("C001"), _fo("F001")]
    assigner = CrewAssigner()
    result = assigner.solve([], crew, OP_DAY)
    assert result.status == "OPTIMAL"
    assert result.captain_assignments == {}
    assert result.fo_assignments == {}


def test_empty_crew_returns_infeasible():
    legs = [_leg("F1", "KE101")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, [], OP_DAY)
    assert result.status == "INFEASIBLE"
    assert "F1" in result.unassigned_captain
    assert "F1" in result.unassigned_fo


def test_crew_unavailable_before_departure():
    """Crew available at 14:00 cannot cover 09:00 departure (check-in at 08:00)."""
    legs = [_leg("F1", "KE101", dep_hour=9)]
    crew = [_capt("C001", avail_hour=14), _fo("F001", avail_hour=14)]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    assert "F1" in result.unassigned_captain
    assert "F1" in result.unassigned_fo


def test_two_legs_require_separate_crew():
    """Two simultaneous legs need separate crew pairs."""
    legs = [
        _leg("F1", "KE101", dep_hour=9,  block=180),
        _leg("F2", "KE102", dep_hour=9,  block=180),
    ]
    crew = [
        _capt("C001"), _capt("C002"),
        _fo("F001"),   _fo("F002"),
    ]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    assert result.status in ("OPTIMAL", "FEASIBLE")
    assert len(result.fully_crewed) == 2
    # F1 and F2 must have different captains and different FOs
    assert result.captain_assignments["F1"] != result.captain_assignments["F2"]
    assert result.fo_assignments["F1"] != result.fo_assignments["F2"]


def test_coverage_rate():
    """Two simultaneous flights, only 1 CAPT + 1 FO → 1 fully crewed, 2 positions open."""
    legs = [
        _leg("F1", "KE101", dep_hour=9),
        _leg("F2", "KE102", dep_hour=9),  # same time → no-overlap prevents double assignment
    ]
    # C001 is CAPT, F001 is FO — each can only cover one slot due to no-overlap
    crew = [_capt("C001"), _fo("F001")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    # 2 positions filled (F1 gets CAPT + FO) out of 4 total = 50%
    assert result.coverage_rate == pytest.approx(0.5)


# ── FAR 117 tests ─────────────────────────────────────────────────────────────

def test_far117_validation_runs():
    """Post-solve FAR 117 check always produces DutyPeriod objects."""
    legs = [_leg("F1", "KE101", dep_hour=8, block=120)]
    crew = [_capt("C001"), _fo("F001")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    if result.status in ("OPTIMAL", "FEASIBLE"):
        assert len(result.duty_periods) > 0
        for dp in result.duty_periods:
            assert dp.fdp_minutes > 0
            assert dp.far117_max_hours > 0


def test_far117_legal_short_duty():
    """A single short-haul round trip (2h block, 08:00 report) is legal."""
    legs = [_leg("F1", "KE101", dep_hour=9, block=120)]
    crew = [_capt("C001"), _fo("F001")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    assert result.far117_violations == []
    for dp in result.duty_periods:
        assert dp.far117_legal is True


# ── generate_crew helper ──────────────────────────────────────────────────────

def test_generate_crew_counts():
    pool = CrewAssigner.generate_crew(
        n_capt_narrow=5, n_fo_narrow=5,
        n_capt_wide=3,   n_fo_wide=3,
        op_day=OP_DAY,
    )
    assert len(pool) == 16
    capts  = [c for c in pool if c.role == "CAPT"]
    fos    = [c for c in pool if c.role == "FO"]
    narrow = [c for c in pool if c.type_rating == "B737-800"]
    wide   = [c for c in pool if c.type_rating == "B777-300ER"]
    assert len(capts) == 8
    assert len(fos) == 8
    assert len(narrow) == 10
    assert len(wide) == 6


def test_generate_crew_ids_unique():
    pool = CrewAssigner.generate_crew(op_day=OP_DAY)
    ids = [c.crew_id for c in pool]
    assert len(ids) == len(set(ids))


def test_summary_contains_key_info():
    legs = [_leg("F1", "KE101", dep_hour=9, block=180)]
    crew = [_capt("C001"), _fo("F001")]
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, OP_DAY)

    summary = result.summary()
    assert "Status" in summary
    assert "FAR 117" in summary
