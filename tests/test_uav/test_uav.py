"""Unit tests for UAM/AAM ACROSS integration modules."""

from datetime import datetime, timedelta, timezone

import pytest

from argos.uav.models import (
    ApprovalStatus,
    ConflictType,
    FlightRules,
    GeoPoint,
    UAMFlightPlan,
    UAMVehicle,
    VehicleClass,
    Vertiport,
    Waypoint4D,
)
from argos.uav.network import (
    VERTIPORTS,
    build_uam_network,
    estimate_flight_time_min,
    find_route,
    route_distance_nm,
    all_routes_from,
)
from argos.uav.airspace import (
    ICN_CENTRE,
    ICN_CTR_RADIUS_NM,
    UAM_MAX_ALT_ICN_FT,
    assess_conflicts,
    check_ctr_altitude,
    check_curfew,
    check_ils_corridor,
)
from argos.uav.across_client import ACROSSClient

# ── Fixtures ──────────────────────────────────────────────────────────────────

UTC = timezone.utc
BASE_TIME = datetime(2024, 6, 15, 2, 0, 0, tzinfo=UTC)  # 11:00 KST (daytime)

DEMO_VEHICLE = UAMVehicle(
    vehicle_id="KE-AAM-001",
    call_sign="KAM001",
    vehicle_class=VehicleClass.EVTOL,
    manufacturer="Joby Aviation",
    model="S4",
    max_alt_ft=3000,
    cruise_speed_kts=150,
    range_nm=100,
    max_payload_kg=450,
    pax_capacity=4,
    registration="KR-00001",
)


def _plan(
    plan_id: str,
    origin_id: str = "SBR",
    dest_id: str = "YDP",
    alt_ft: float = 800.0,
    dep_hour_utc: int = 2,
) -> UAMFlightPlan:
    """Build a simple 2-waypoint flight plan."""
    origin_vp = VERTIPORTS[origin_id]
    dest_vp = VERTIPORTS[dest_id]
    etd = datetime(2024, 6, 15, dep_hour_utc, 0, tzinfo=UTC)
    eta = etd + timedelta(minutes=20)
    return UAMFlightPlan(
        plan_id=plan_id,
        vehicle_id="KE-AAM-001",
        origin_id=origin_id,
        dest_id=dest_id,
        flight_rules=FlightRules.VFRC,
        etd_utc=etd,
        eta_utc=eta,
        cruise_alt_ft=alt_ft,
        trajectory=[
            Waypoint4D(GeoPoint(origin_vp.position.lat, origin_vp.position.lon, alt_ft), etd),
            Waypoint4D(GeoPoint(dest_vp.position.lat, dest_vp.position.lon, alt_ft), eta),
        ],
        pax_count=2,
    )


# ── GeoPoint tests ────────────────────────────────────────────────────────────


def test_geopoint_distance_same_point():
    p = GeoPoint(37.4691, 126.4505)
    assert p.distance_nm(p) == pytest.approx(0.0, abs=1e-6)


def test_geopoint_distance_icn_to_gmp():
    icn = GeoPoint(37.4691, 126.4505)
    gmp = GeoPoint(37.5583, 126.7906)
    dist = icn.distance_nm(gmp)
    assert 17.0 < dist < 22.0  # ~19 NM ICN→GMP


def test_geopoint_distance_symmetry():
    a = GeoPoint(37.4691, 126.4505)
    b = GeoPoint(37.5219, 126.9244)
    assert a.distance_nm(b) == pytest.approx(b.distance_nm(a), rel=1e-6)


# ── Network tests ─────────────────────────────────────────────────────────────


def test_network_builds():
    G = build_uam_network()
    assert len(G.nodes) == len(VERTIPORTS)
    assert G.number_of_edges() > 0


def test_all_vertiports_in_network():
    G = build_uam_network()
    for vid in VERTIPORTS:
        assert vid in G.nodes


def test_find_route_direct():
    G = build_uam_network()
    path = find_route(G, "SBR", "YDP")
    assert path is not None
    assert path[0] == "SBR"
    assert path[-1] == "YDP"


def test_find_route_multi_hop():
    G = build_uam_network()
    # SBR→YDP→GMP (no direct SBR→GMP edge)
    path = find_route(G, "SBR", "GMP")
    assert path is not None
    assert path[0] == "SBR"
    assert path[-1] == "GMP"
    assert len(path) >= 2


def test_find_route_nonexistent_node():
    G = build_uam_network()
    path = find_route(G, "NOWHERE", "YDP")
    assert path is None


def test_route_distance_positive():
    G = build_uam_network()
    path = find_route(G, "ICN-T1", "ICN-T2")
    assert path is not None
    dist = route_distance_nm(G, path)
    assert dist > 0


def test_estimate_flight_time_positive():
    G = build_uam_network()
    path = find_route(G, "SBR", "YDP")
    assert path is not None
    t = estimate_flight_time_min(G, path, DEMO_VEHICLE)
    assert t > 0


def test_all_routes_from_returns_dict():
    G = build_uam_network()
    routes = all_routes_from(G, "YDP")
    assert isinstance(routes, dict)
    assert len(routes) > 0
    assert "YDP" not in routes  # no self-route


# ── Airspace / conflict tests ─────────────────────────────────────────────────


def test_ctr_altitude_ok_outside_ctr():
    plan = _plan("P1", "SBR", "YDP", alt_ft=800)
    # SBR and YDP are outside ICN CTR — no altitude violation expected
    conflicts = check_ctr_altitude(plan)
    assert conflicts == []


def test_ctr_altitude_violation_inside_ctr():
    """A waypoint inside ICN CTR above 1000 ft triggers a conflict."""
    # Put a waypoint near ICN centre (inside CTR) but at 1500 ft
    plan = UAMFlightPlan(
        plan_id="P-VIOLATION",
        vehicle_id="KE-AAM-001",
        origin_id="ICN-T1",
        dest_id="ICN-T2",
        flight_rules=FlightRules.VFRC,
        etd_utc=BASE_TIME,
        eta_utc=BASE_TIME + timedelta(minutes=5),
        cruise_alt_ft=1500,  # over the 1000 ft limit inside CTR
        trajectory=[
            Waypoint4D(
                GeoPoint(ICN_CENTRE.lat, ICN_CENTRE.lon, 1500),  # inside CTR
                BASE_TIME,
            ),
        ],
    )
    conflicts = check_ctr_altitude(plan)
    assert len(conflicts) >= 1
    assert any(c.conflict_type == ConflictType.AIRSPACE for c in conflicts)


def test_curfew_daytime_ok():
    # BASE_TIME is 02:00 UTC = 11:00 KST — well within allowed hours
    plan = _plan("P1", dep_hour_utc=2)
    conflicts = check_curfew(plan)
    assert conflicts == []


def test_curfew_night_violation():
    # 15:00 UTC = 00:00 KST next day — inside curfew (23:00–06:00 KST)
    plan = _plan("P-CURFEW", dep_hour_utc=15)
    conflicts = check_curfew(plan)
    assert len(conflicts) >= 1
    assert conflicts[0].conflict_type == ConflictType.CURFEW


def test_assess_conflicts_clean_plan():
    plan = _plan("P-CLEAN", "SBR", "YDP", alt_ft=800, dep_hour_utc=2)
    conflicts = assess_conflicts(plan)
    # SBR→YDP at 800 ft daytime should have no conflicts
    assert conflicts == []


def test_assess_conflicts_catches_curfew():
    plan = _plan("P-NIGHT", dep_hour_utc=15)  # midnight KST
    conflicts = assess_conflicts(plan)
    curfew_hits = [c for c in conflicts if c.conflict_type == ConflictType.CURFEW]
    assert len(curfew_hits) >= 1


# ── ACROSS client tests ───────────────────────────────────────────────────────


def test_submit_clean_plan_approved():
    client = ACROSSClient()
    plan = _plan("PLAN-001", "SBR", "YDP", alt_ft=800, dep_hour_utc=2)
    response = client.submit_plan(plan)

    assert response.approved
    assert response.plan_id == "PLAN-001"
    assert response.conflicts == []


def test_submit_curfew_plan_denied():
    client = ACROSSClient()
    plan = _plan("PLAN-NIGHT", dep_hour_utc=15)  # midnight KST
    response = client.submit_plan(plan)

    assert response.denied
    assert any(c.conflict_type == ConflictType.CURFEW for c in response.conflicts)


def test_submit_high_alt_ctr_plan_denied():
    """Plan with waypoint over altitude limit inside CTR is denied."""
    client = ACROSSClient()
    plan = UAMFlightPlan(
        plan_id="PLAN-HIGHALT",
        vehicle_id="KE-AAM-001",
        origin_id="ICN-T1",
        dest_id="ICN-T2",
        flight_rules=FlightRules.VFRC,
        etd_utc=BASE_TIME,
        eta_utc=BASE_TIME + timedelta(minutes=5),
        cruise_alt_ft=1500,
        trajectory=[
            Waypoint4D(GeoPoint(ICN_CENTRE.lat, ICN_CENTRE.lon, 1500), BASE_TIME),
        ],
    )
    response = client.submit_plan(plan)
    assert response.denied


def test_get_status_after_submit():
    client = ACROSSClient()
    plan = _plan("PLAN-002")
    client.submit_plan(plan)
    status = client.get_status("PLAN-002")

    assert status is not None
    assert status.plan_id == "PLAN-002"


def test_cancel_plan():
    client = ACROSSClient()
    plan = _plan("PLAN-003")
    client.submit_plan(plan)
    response = client.cancel_plan("PLAN-003", reason="Test cancellation")

    assert response.status == ApprovalStatus.CANCELLED
    assert "PLAN-003" not in [p.plan_id for p in client.list_active_plans()]


def test_list_active_plans():
    client = ACROSSClient()
    plan1 = _plan("P1")
    plan2 = _plan("P2", origin_id="YDP", dest_id="GMP")
    client.submit_plan(plan1)
    client.submit_plan(plan2)

    active = client.list_active_plans()
    ids = [p.plan_id for p in active]
    assert "P1" in ids
    assert "P2" in ids


def test_suggest_uam_alternative_connected():
    client = ACROSSClient()
    etd = datetime(2024, 6, 15, 3, 0, tzinfo=UTC)  # 12:00 KST
    result = client.suggest_uam_alternative(
        delayed_flight_number="KE001",
        delayed_pax=10,
        origin_vertiport_id="SBR",
        dest_vertiport_id="YDP",
        etd_utc=etd,
    )

    assert result is not None
    plan, response = result
    assert plan.origin_id == "SBR"
    assert plan.dest_id == "YDP"
    assert plan.pax_count <= 4  # eVTOL capacity cap
    assert response.plan_id == plan.plan_id


def test_suggest_uam_alternative_no_route():
    client = ACROSSClient()
    etd = datetime(2024, 6, 15, 3, 0, tzinfo=UTC)
    result = client.suggest_uam_alternative(
        delayed_flight_number="KE001",
        delayed_pax=10,
        origin_vertiport_id="NOWHERE",
        dest_vertiport_id="ALSO-NOWHERE",
        etd_utc=etd,
    )
    assert result is None
