"""Unit tests for NetworkX delay propagation simulator."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import networkx as nx
import pandas as pd
import pytest

from argos.domain.fleet import min_turn_minutes
from argos.domain.rotation import aircraft_rotation_span
from argos.simulation.propagation import (
    _MAX_PROPAGATED_DELAY,
    DelayPropagator,
    FlightNode,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

BASE_DATE = date(2024, 6, 15)
MIDNIGHT = datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC)


def _dt(hour: int, minute: int = 0) -> datetime:
    return MIDNIGHT.replace(hour=hour, minute=minute)


def _node(
    flight_id: str,
    flight_number: str,
    reg: str,
    aircraft_type: str,
    dep_hour: int,
    block_minutes: int = 180,
    pax: int = 200,
    origin: str = "ICN",
    dest: str = "NRT",
) -> FlightNode:
    dep = _dt(dep_hour)
    arr = dep + timedelta(minutes=block_minutes)
    return FlightNode(
        flight_id=flight_id,
        flight_number=flight_number,
        route_id=f"{origin}-{dest}",
        aircraft_registration=reg,
        aircraft_type=aircraft_type,
        origin_iata=origin,
        dest_iata=dest,
        scheduled_dep_utc=dep,
        scheduled_arr_utc=arr,
        block_time_minutes=block_minutes,
        pax_boarded=pax,
        status="SCH",
    )


def _build_graph(*nodes: FlightNode) -> nx.DiGraph:
    """Build a linear rotation chain from the given ordered nodes."""
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n.flight_id, data=n)
    for i in range(len(nodes) - 1):
        u = nodes[i]
        v = nodes[i + 1]
        min_elapsed = aircraft_rotation_span(
            u.block_time_minutes, min_turn_minutes(u.aircraft_type)
        )
        gap = (v.scheduled_dep_utc - u.scheduled_dep_utc).total_seconds() / 60
        buffer = gap - min_elapsed
        G.add_edge(u.flight_id, v.flight_id, buffer_minutes=buffer, min_elapsed_minutes=min_elapsed)
    return G


# ── FlightNode properties ─────────────────────────────────────────────────────


def test_flight_node_no_delay_properties():
    n = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=9, block_minutes=120)
    assert n.dep_delay_minutes == 0
    assert n.actual_dep_utc == _dt(9)
    assert n.actual_arr_dest_utc == _dt(11)


def test_flight_node_with_delay():
    n = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=9, block_minutes=120)
    n.dep_delay_minutes = 30
    assert n.actual_dep_utc == _dt(9) + timedelta(minutes=30)
    assert n.actual_arr_dest_utc == _dt(9) + timedelta(minutes=30 + 120)


def test_earliest_icn_ready_narrow():
    # dep=09:00, block=120, turn=45 → dest arr=11:00 → dest dep>=11:45
    #   → ICN arr>=13:45 → ready>=14:30
    n = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=9, block_minutes=120)
    expected = _dt(9) + timedelta(minutes=120 + 45 + 120 + 45)
    assert n.earliest_icn_ready_utc == expected


def test_earliest_icn_ready_wide():
    n = _node("F1", "KE001", "HL7701", "B777-300ER", dep_hour=9, block_minutes=240)
    expected = _dt(9) + timedelta(minutes=240 + 60 + 240 + 60)
    assert n.earliest_icn_ready_utc == expected


# ── build_rotation_graph ──────────────────────────────────────────────────────


def test_build_graph_single_flight():
    df = pd.DataFrame(
        [
            {
                "flight_id": "F1",
                "flight_number": "KE701",
                "route_id": "ICN-NRT",
                "aircraft_registration": "HL7401",
                "aircraft_type": "B737-800",
                "origin_iata": "ICN",
                "dest_iata": "NRT",
                "scheduled_dep_utc": pd.Timestamp(_dt(9)),
                "scheduled_arr_utc": pd.Timestamp(_dt(11)),
                "block_time_minutes": 120,
                "pax_boarded": 150,
                "status": "SCH",
            }
        ]
    )
    propagator = DelayPropagator.__new__(DelayPropagator)
    G = propagator.build_rotation_graph(df)
    assert G.number_of_nodes() == 1
    assert G.number_of_edges() == 0


def test_build_graph_rotation_edge_created():
    # Two flights same aircraft: F1 dep=06:00 block=120, F2 dep=14:00
    # min_elapsed = 2*120 + 2*45 = 330 min; gap = 8h = 480 min → buffer = 150
    df = pd.DataFrame(
        [
            {
                "flight_id": "F1",
                "flight_number": "KE701",
                "route_id": "ICN-NRT",
                "aircraft_registration": "HL7401",
                "aircraft_type": "B737-800",
                "origin_iata": "ICN",
                "dest_iata": "NRT",
                "scheduled_dep_utc": pd.Timestamp(_dt(6)),
                "scheduled_arr_utc": pd.Timestamp(_dt(8)),
                "block_time_minutes": 120,
                "pax_boarded": 150,
                "status": "SCH",
            },
            {
                "flight_id": "F2",
                "flight_number": "KE702",
                "route_id": "ICN-NRT",
                "aircraft_registration": "HL7401",
                "aircraft_type": "B737-800",
                "origin_iata": "ICN",
                "dest_iata": "NRT",
                "scheduled_dep_utc": pd.Timestamp(_dt(14)),
                "scheduled_arr_utc": pd.Timestamp(_dt(16)),
                "block_time_minutes": 120,
                "pax_boarded": 150,
                "status": "SCH",
            },
        ]
    )
    propagator = DelayPropagator.__new__(DelayPropagator)
    G = propagator.build_rotation_graph(df)
    assert G.number_of_edges() == 1
    edge = G.edges["F1", "F2"]
    assert edge["buffer_minutes"] == pytest.approx(150.0)


def test_build_graph_different_aircraft_no_edge():
    df = pd.DataFrame(
        [
            {
                "flight_id": "F1",
                "flight_number": "KE701",
                "route_id": "ICN-NRT",
                "aircraft_registration": "HL7401",
                "aircraft_type": "B737-800",
                "origin_iata": "ICN",
                "dest_iata": "NRT",
                "scheduled_dep_utc": pd.Timestamp(_dt(6)),
                "scheduled_arr_utc": pd.Timestamp(_dt(8)),
                "block_time_minutes": 120,
                "pax_boarded": 150,
                "status": "SCH",
            },
            {
                "flight_id": "F2",
                "flight_number": "KE001",
                "route_id": "ICN-JFK",
                "aircraft_registration": "HL7701",  # different aircraft
                "aircraft_type": "B777-300ER",
                "origin_iata": "ICN",
                "dest_iata": "JFK",
                "scheduled_dep_utc": pd.Timestamp(_dt(14)),
                "scheduled_arr_utc": pd.Timestamp(_dt(14) + timedelta(hours=10)),
                "block_time_minutes": 600,
                "pax_boarded": 300,
                "status": "SCH",
            },
        ]
    )
    propagator = DelayPropagator.__new__(DelayPropagator)
    G = propagator.build_rotation_graph(df)
    assert G.number_of_edges() == 0


def test_build_graph_too_large_gap_excluded():
    # Gap > 14 hours should not create a rotation edge
    df = pd.DataFrame(
        [
            {
                "flight_id": "F1",
                "flight_number": "KE701",
                "route_id": "ICN-NRT",
                "aircraft_registration": "HL7401",
                "aircraft_type": "B737-800",
                "origin_iata": "ICN",
                "dest_iata": "NRT",
                "scheduled_dep_utc": pd.Timestamp(_dt(0)),
                "scheduled_arr_utc": pd.Timestamp(_dt(2)),
                "block_time_minutes": 120,
                "pax_boarded": 150,
                "status": "SCH",
            },
            {
                "flight_id": "F2",
                "flight_number": "KE702",
                "route_id": "ICN-NRT",
                "aircraft_registration": "HL7401",
                "aircraft_type": "B737-800",
                "origin_iata": "ICN",
                "dest_iata": "NRT",
                "scheduled_dep_utc": pd.Timestamp(_dt(0) + timedelta(hours=15)),
                "scheduled_arr_utc": pd.Timestamp(_dt(0) + timedelta(hours=17)),
                "block_time_minutes": 120,
                "pax_boarded": 150,
                "status": "SCH",
            },
        ]
    )
    propagator = DelayPropagator.__new__(DelayPropagator)
    G = propagator.build_rotation_graph(df)
    assert G.number_of_edges() == 0


# ── propagate ─────────────────────────────────────────────────────────────────


def test_propagate_no_cascade_when_buffer_absorbs():
    # F1 dep=06:00, block=120, narrow turn=45 → min_elapsed=330
    # F2 dep=14:00 → gap=480 → buffer=150 min
    # delay=90 < buffer → no propagation to F2
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=150)
    G = _build_graph(n1, n2)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 90)

    assert result.trigger_flight_id == "F1"
    assert result.initial_delay_minutes == 90
    assert result.cascade_chain == ["F1"]
    assert result.cascade_depth == 1
    assert (
        len([n for n in result.affected_nodes if n.dep_delay_minutes > 0 and n.flight_id != "F1"])
        == 0
    )


def test_propagate_cascades_when_delay_exceeds_buffer():
    # F1 dep=06:00, block=120, narrow → min_elapsed=330, F2 dep=11:30 → gap=330 → buffer=0
    # delay=60 > buffer=0 → propagates 60 min
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=11, block_minutes=120, pax=100)
    # manually set buffer to 0 by building graph directly
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 60)

    assert "F2" in result.cascade_chain
    f2_node = next(n for n in result.affected_nodes if n.flight_id == "F2")
    assert f2_node.dep_delay_minutes == 60


def test_propagate_delay_reduced_by_buffer():
    # buffer=30 min, delay=90 → propagated=60
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=100)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=30, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 90)

    f2_node = next(n for n in result.affected_nodes if n.flight_id == "F2")
    assert f2_node.dep_delay_minutes == 60


def test_propagate_caps_at_max_propagated_delay():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=100)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", _MAX_PROPAGATED_DELAY + 100)

    f2_node = next(n for n in result.affected_nodes if n.flight_id == "F2")
    assert f2_node.dep_delay_minutes == _MAX_PROPAGATED_DELAY


def test_propagate_three_hop_chain():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=60, pax=100)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=10, block_minutes=60, pax=100)
    n3 = _node("F3", "KE703", "HL7401", "B737-800", dep_hour=14, block_minutes=60, pax=100)
    # buffer = 0 on both edges → full propagation
    G = nx.DiGraph()
    for n in [n1, n2, n3]:
        G.add_node(n.flight_id, data=n)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=240)
    G.add_edge("F2", "F3", buffer_minutes=0, min_elapsed_minutes=240)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 45)

    assert set(result.cascade_chain) == {"F1", "F2", "F3"}
    assert result.total_delay_minutes == 45 * 3


def test_propagate_unknown_flight_raises():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120)
    G = _build_graph(n1)
    propagator = DelayPropagator.__new__(DelayPropagator)
    with pytest.raises(ValueError, match="not in graph"):
        propagator.propagate(G, "DOES_NOT_EXIST", 60)


def test_propagate_zero_delay_no_cascade():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 0)

    assert result.cascade_depth == 1
    assert result.total_delay_minutes == 0
    assert result.total_pax_impacted == 0


def test_propagate_does_not_mutate_original_graph():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=100)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    propagator.propagate(G, "F1", 120)

    # Original nodes must be unchanged
    assert G.nodes["F1"]["data"].dep_delay_minutes == 0
    assert G.nodes["F2"]["data"].dep_delay_minutes == 0


# ── generate_scenarios ────────────────────────────────────────────────────────


def _make_propagator_with_no_spare(monkeypatch) -> DelayPropagator:
    propagator = DelayPropagator.__new__(DelayPropagator)
    monkeypatch.setattr(propagator, "_find_spare_aircraft", lambda *a, **kw: None)
    return propagator


def _make_propagator_with_spare(monkeypatch, spare_reg: str = "HL7402") -> DelayPropagator:
    propagator = DelayPropagator.__new__(DelayPropagator)
    monkeypatch.setattr(propagator, "_find_spare_aircraft", lambda *a, **kw: spare_reg)
    return propagator


def test_generate_scenarios_returns_three(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=100)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = _make_propagator_with_spare(monkeypatch)
    scenarios = propagator.generate_scenarios(G, "F1", 90, BASE_DATE)

    assert len(scenarios) == 3
    assert scenarios[0].scenario_id == 1
    assert scenarios[1].scenario_id == 2
    assert scenarios[2].scenario_id == 3


def test_scenario1_is_accept_absorb(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    G = _build_graph(n1)
    propagator = _make_propagator_with_no_spare(monkeypatch)
    scenarios = propagator.generate_scenarios(G, "F1", 60, BASE_DATE)
    assert scenarios[0].name == "Accept & Absorb"
    assert scenarios[0].feasibility == "HIGH"
    assert scenarios[0].requires_approval is True


def test_scenario2_substitution_when_spare_available(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=100)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = _make_propagator_with_spare(monkeypatch, "HL7402")
    scenarios = propagator.generate_scenarios(G, "F1", 90, BASE_DATE)

    s2 = scenarios[1]
    assert s2.name == "Aircraft Substitution"
    assert "HL7402" in s2.description
    assert s2.feasibility == "MEDIUM"
    assert s2.requires_approval is True


def test_scenario2_na_when_no_spare(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    G = _build_graph(n1)
    propagator = _make_propagator_with_no_spare(monkeypatch)
    scenarios = propagator.generate_scenarios(G, "F1", 90, BASE_DATE)

    assert scenarios[1].feasibility == "LOW"
    assert "N/A" in scenarios[1].name


def test_scenario3_cancel_least_loaded(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=90, pax=200)
    n2 = _node(
        "F2", "KE702", "HL7401", "B737-800", dep_hour=12, block_minutes=90, pax=50
    )  # fewest PAX
    n3 = _node("F3", "KE703", "HL7401", "B737-800", dep_hour=18, block_minutes=90, pax=180)
    G = nx.DiGraph()
    for n in [n1, n2, n3]:
        G.add_node(n.flight_id, data=n)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=270)
    G.add_edge("F2", "F3", buffer_minutes=0, min_elapsed_minutes=270)

    propagator = _make_propagator_with_no_spare(monkeypatch)
    scenarios = propagator.generate_scenarios(G, "F1", 60, BASE_DATE)

    s3 = scenarios[2]
    assert s3.scenario_id == 3
    # Least-loaded downstream flight (F2, 50 PAX) should be cancelled
    assert "KE702" in s3.description


def test_scenario3_no_further_action_single_leg(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    G = _build_graph(n1)
    propagator = _make_propagator_with_no_spare(monkeypatch)
    scenarios = propagator.generate_scenarios(G, "F1", 60, BASE_DATE)

    s3 = scenarios[2]
    assert "Single Leg" in s3.name
    assert s3.feasibility == "HIGH"
    assert s3.cost_index == 0.0


def test_scenarios_all_require_approval(monkeypatch):
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=100)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = _make_propagator_with_spare(monkeypatch)
    scenarios = propagator.generate_scenarios(G, "F1", 90, BASE_DATE)

    for s in scenarios:
        assert s.requires_approval is True, f"Scenario {s.scenario_id} missing human approval"


# ── PropagationResult ─────────────────────────────────────────────────────────


def test_propagation_result_cascade_depth():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 60)
    assert result.cascade_depth == len(result.cascade_chain)


def test_propagation_result_pax_count():
    n1 = _node("F1", "KE701", "HL7401", "B737-800", dep_hour=6, block_minutes=120, pax=150)
    n2 = _node("F2", "KE702", "HL7401", "B737-800", dep_hour=14, block_minutes=120, pax=200)
    G = nx.DiGraph()
    G.add_node("F1", data=n1)
    G.add_node("F2", data=n2)
    G.add_edge("F1", "F2", buffer_minutes=0, min_elapsed_minutes=330)

    propagator = DelayPropagator.__new__(DelayPropagator)
    result = propagator.propagate(G, "F1", 60)
    assert result.total_pax_impacted == 150 + 200
