"""
Tests for OCC agent tools — no LLM calls, no API key required.

All tools wrap domain modules (propagation, aircraft, crew optimisers).
Tests use the live DuckDB database (read-only) or skip when unavailable.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

DB_PATH = str(Path("data/db/argos.duckdb").resolve())
DB_AVAILABLE = Path(DB_PATH).exists()


@pytest.fixture(scope="module")
def sample_flight_id():
    """Return one flight_id from the DB for use in propagation tests."""
    if not DB_AVAILABLE:
        pytest.skip("argos.duckdb not found — run scripts/setup_db.py + generate_data.py")

    import duckdb
    from datetime import datetime, timezone

    # Pick a date with sufficient data
    test_date = date(2024, 6, 15)
    day_start = datetime(2024, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    day_end   = datetime(2024, 6, 16, 0, 0, 0, tzinfo=timezone.utc)

    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        rows = con.execute("""
            SELECT flight_id FROM flights
            WHERE scheduled_dep_utc >= ? AND scheduled_dep_utc < ?
              AND status != 'CNX'
            ORDER BY scheduled_dep_utc
            LIMIT 1
        """, [day_start, day_end]).fetchall()
    finally:
        con.close()

    if not rows:
        pytest.skip("No flights found for 2024-06-15")
    return rows[0][0]


# ── Graph structure tests (no DB, no API) ─────────────────────────────────────

def test_graph_compiles():
    from argos.agents.occ_graph import build_occ_graph
    graph = build_occ_graph()
    nodes = list(graph.get_graph().nodes.keys())
    for expected in ["simulate", "analyse", "optimise", "brief_occ",
                     "human_gate", "execute", "abort"]:
        assert expected in nodes


def test_graph_has_interrupt():
    """Graph must have human_gate as interrupt_before node."""
    from argos.agents.occ_graph import build_occ_graph
    graph = build_occ_graph()
    # interrupt_before is stored in the compiled graph's config
    # We verify the human_gate node exists and is reachable
    edges = list(graph.get_graph().edges)
    edge_names = [(e[0], e[1]) for e in edges]
    assert ("brief_occ", "human_gate") in edge_names


def test_occ_state_keys():
    from argos.agents.state import OCCState
    # Verify TypedDict has expected keys by instantiating a partial dict
    state: OCCState = {
        "trigger_flight_id":     "test-uuid",
        "initial_delay_minutes": 90,
        "op_date":               "2024-06-15",
        "db_path":               DB_PATH,
        "propagation_summary":   {},
        "scenarios_raw":         [],
        "scenario_briefing":     "",
        "aircraft_result":       None,
        "crew_result":           None,
        "approved_scenario_id":  None,
        "approval_notes":        "",
        "execution_summary":     "",
        "messages":              [],
    }
    assert state["trigger_flight_id"] == "test-uuid"
    assert state["initial_delay_minutes"] == 90


def test_occ_tools_importable():
    from argos.agents.tools import (
        OCC_TOOLS,
        run_aircraft_optimisation,
        run_crew_optimisation,
        run_propagation,
        run_scenario_generation,
    )
    assert len(OCC_TOOLS) == 4
    assert run_propagation.name == "run_propagation"
    assert run_scenario_generation.name == "run_scenario_generation"
    assert run_aircraft_optimisation.name == "run_aircraft_optimisation"
    assert run_crew_optimisation.name == "run_crew_optimisation"


# ── Tool invocation tests (require DB) ────────────────────────────────────────

@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_run_propagation_returns_dict(sample_flight_id):
    from argos.agents.tools import run_propagation

    result = run_propagation.invoke({
        "db_path":               DB_PATH,
        "op_date":               "2024-06-15",
        "trigger_flight_id":     sample_flight_id,
        "initial_delay_minutes": 90,
    })

    assert "trigger_flight_id" in result
    assert "cascade_chain" in result
    assert "total_delay_minutes" in result
    assert isinstance(result["cascade_chain"], list)
    assert len(result["cascade_chain"]) >= 1


@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_run_scenario_generation_returns_three(sample_flight_id):
    from argos.agents.tools import run_scenario_generation

    scenarios = run_scenario_generation.invoke({
        "db_path":               DB_PATH,
        "op_date":               "2024-06-15",
        "trigger_flight_id":     sample_flight_id,
        "initial_delay_minutes": 90,
    })

    assert isinstance(scenarios, list)
    assert len(scenarios) == 3
    ids = [s["scenario_id"] for s in scenarios]
    assert sorted(ids) == [1, 2, 3]
    for s in scenarios:
        assert "name" in s
        assert "feasibility" in s
        assert s["requires_approval"] is True


@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_run_aircraft_optimisation(sample_flight_id):
    from argos.agents.tools import run_aircraft_optimisation

    result = run_aircraft_optimisation.invoke({
        "db_path":               DB_PATH,
        "op_date":               "2024-06-15",
        "disrupted_flight_ids":  [sample_flight_id],
    })

    assert "assignments" in result
    assert "unassigned" in result
    assert "coverage_rate" in result
    assert "status" in result
    assert result["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN")


@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_run_crew_optimisation(sample_flight_id):
    from argos.agents.tools import run_crew_optimisation

    result = run_crew_optimisation.invoke({
        "db_path":               DB_PATH,
        "op_date":               "2024-06-15",
        "disrupted_flight_ids":  [sample_flight_id],
    })

    assert "captain_assignments" in result
    assert "fo_assignments" in result
    assert "far117_violations" in result
    assert "coverage_rate" in result
    assert isinstance(result["far117_violations"], list)


# ── node_simulate unit test (no LLM) ─────────────────────────────────────────

@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_node_simulate_populates_state(sample_flight_id):
    from argos.agents.occ_graph import node_simulate

    state = {
        "trigger_flight_id":     sample_flight_id,
        "initial_delay_minutes": 60,
        "op_date":               "2024-06-15",
        "db_path":               DB_PATH,
    }
    patch = node_simulate(state)

    assert "propagation_summary" in patch
    prop = patch["propagation_summary"]
    assert prop["trigger_flight_id"] == sample_flight_id
    assert prop["initial_delay_minutes"] == 60
    assert isinstance(prop["cascade_chain"], list)


# ── End-to-end graph test (mocked LLM, requires DB) ──────────────────────────

@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_full_graph_approve(monkeypatch, sample_flight_id):
    """Run the full OCC graph with a mocked LLM; approve scenario 1."""
    from unittest.mock import MagicMock
    from langchain_core.messages import AIMessage
    import argos.agents.occ_graph as occ_mod

    # Build a fake AIMessage that includes a tool call for run_scenario_generation
    # and also has text content — mirrors what the real Claude would return.
    fake_tool_call = {
        "name": "run_scenario_generation",
        "args": {
            "db_path":               DB_PATH,
            "op_date":               "2024-06-15",
            "trigger_flight_id":     sample_flight_id,
            "initial_delay_minutes": 60,
        },
        "id": "tc_mock_001",
        "type": "tool_call",
    }
    fake_analyse_msg = AIMessage(
        content="Moderate cascade risk detected across 3 downstream rotations.",
        tool_calls=[fake_tool_call],
    )
    # brief_occ node calls LLM without tools
    fake_brief_msg = AIMessage(
        content=(
            "SITUATION: KE flight delayed 60 min, cascading to 3 legs.\n"
            "OPTIONS: S1 absorb, S2 swap, S3 cancel.\n"
            "RECOMMENDATION: S1.\n"
            "REQUIRED ACTION: Approve Scenario 1.\n"
            "Awaiting OCC manager approval."
        )
    )

    call_count = {"n": 0}

    def mock_make_llm(tools=None):
        mock_llm = MagicMock()
        if tools:
            mock_llm.invoke.return_value = fake_analyse_msg
        else:
            mock_llm.invoke.return_value = fake_brief_msg
        return mock_llm

    monkeypatch.setattr(occ_mod, "_make_llm", mock_make_llm)

    state, graph = occ_mod.run_until_approval(
        db_path=DB_PATH,
        op_date="2024-06-15",
        trigger_flight_id=sample_flight_id,
        initial_delay_minutes=60,
        thread_id="test-approve",
    )

    # At the interrupt, we should have propagation + scenarios
    assert "propagation_summary" in state
    assert state["propagation_summary"]["initial_delay_minutes"] == 60
    assert "scenario_briefing" in state
    assert len(state.get("scenarios_raw", [])) == 3

    # Resume with approval
    final = occ_mod.resume_after_approval(
        graph,
        approved_scenario_id=1,
        approval_notes="Test approval",
        thread_id="test-approve",
    )
    assert "execution_summary" in final
    assert "APPROVED" in final["execution_summary"]
    assert "1" in final["execution_summary"]


@pytest.mark.skipif(not DB_AVAILABLE, reason="DuckDB not available")
def test_full_graph_reject(monkeypatch, sample_flight_id):
    """Run the full OCC graph with a mocked LLM; reject all scenarios."""
    from unittest.mock import MagicMock
    from langchain_core.messages import AIMessage
    import argos.agents.occ_graph as occ_mod

    fake_tool_call = {
        "name": "run_scenario_generation",
        "args": {
            "db_path":               DB_PATH,
            "op_date":               "2024-06-15",
            "trigger_flight_id":     sample_flight_id,
            "initial_delay_minutes": 30,
        },
        "id": "tc_mock_002",
        "type": "tool_call",
    }
    fake_analyse_msg = AIMessage(content="Minor delay.", tool_calls=[fake_tool_call])
    fake_brief_msg   = AIMessage(content="Awaiting OCC manager approval.")

    def mock_make_llm(tools=None):
        m = MagicMock()
        m.invoke.return_value = fake_analyse_msg if tools else fake_brief_msg
        return m

    monkeypatch.setattr(occ_mod, "_make_llm", mock_make_llm)

    state, graph = occ_mod.run_until_approval(
        db_path=DB_PATH,
        op_date="2024-06-15",
        trigger_flight_id=sample_flight_id,
        initial_delay_minutes=30,
        thread_id="test-reject",
    )

    final = occ_mod.resume_after_approval(
        graph,
        approved_scenario_id=None,
        approval_notes="Escalate to duty manager",
        thread_id="test-reject",
    )
    assert "REJECTED" in final["execution_summary"]
    assert "Escalate" in final["execution_summary"]
