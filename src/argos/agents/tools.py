"""
LangChain tools that wrap ARGOS domain modules.

These tools are called by the OCC agent nodes to:
  - run delay propagation simulation
  - generate recovery scenarios
  - optimise aircraft re-assignment
  - optimise crew re-assignment

All tools are pure-Python (no LLM calls); they bridge the LangGraph graph
to the domain/simulation/optimisation layers.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from langchain_core.tools import tool

from argos.optimization.aircraft import AircraftAssigner, AircraftResource, FlightTask
from argos.optimization.crew import CrewAssigner, FlightLeg
from argos.simulation.propagation import DelayPropagator


# ── Propagation tool ──────────────────────────────────────────────────────────


@tool
def run_propagation(
    db_path: str,
    op_date: str,
    trigger_flight_id: str,
    initial_delay_minutes: int,
) -> dict:
    """Simulate delay propagation through aircraft rotation chains.

    Args:
        db_path: Absolute path to argos.duckdb
        op_date: Operating date in ISO format (YYYY-MM-DD)
        trigger_flight_id: UUID of the flight that is delayed
        initial_delay_minutes: Departure delay in minutes

    Returns:
        dict with keys: trigger_flight_id, initial_delay_minutes,
        cascade_chain (list of flight_ids), cascade_depth,
        total_delay_minutes, total_pax_impacted
    """
    dep_date = date.fromisoformat(op_date)
    propagator = DelayPropagator(db_path=Path(db_path))
    flights_df = propagator.load_flights(dep_date)
    G = propagator.build_rotation_graph(flights_df)
    result = propagator.propagate(G, trigger_flight_id, initial_delay_minutes)

    return {
        "trigger_flight_id": result.trigger_flight_id,
        "initial_delay_minutes": result.initial_delay_minutes,
        "cascade_chain": result.cascade_chain,
        "cascade_depth": result.cascade_depth,
        "total_delay_minutes": result.total_delay_minutes,
        "total_pax_impacted": result.total_pax_impacted,
    }


@tool
def run_scenario_generation(
    db_path: str,
    op_date: str,
    trigger_flight_id: str,
    initial_delay_minutes: int,
) -> list[dict]:
    """Generate 3 OCC recovery scenarios for a delayed trigger flight.

    Returns a list of 3 scenario dicts, each with keys:
      scenario_id, name, description, action_required, feasibility,
      cost_index, cascade_depth, total_delay_minutes, total_pax_impacted,
      requires_approval (always True)
    """
    dep_date = date.fromisoformat(op_date)
    propagator = DelayPropagator(db_path=Path(db_path))
    flights_df = propagator.load_flights(dep_date)
    G = propagator.build_rotation_graph(flights_df)
    scenarios = propagator.generate_scenarios(G, trigger_flight_id, initial_delay_minutes, dep_date)

    return [
        {
            "scenario_id": s.scenario_id,
            "name": s.name,
            "description": s.description,
            "action_required": s.action_required,
            "feasibility": s.feasibility,
            "cost_index": s.cost_index,
            "cascade_depth": s.residual.cascade_depth,
            "total_delay_minutes": s.residual.total_delay_minutes,
            "total_pax_impacted": s.residual.total_pax_impacted,
            "requires_approval": s.requires_approval,
        }
        for s in scenarios
    ]


# ── Aircraft optimisation tool ────────────────────────────────────────────────


@tool
def run_aircraft_optimisation(
    db_path: str,
    op_date: str,
    disrupted_flight_ids: list[str],
) -> dict:
    """Run CP-SAT aircraft re-assignment for disrupted flights.

    Args:
        db_path: Path to argos.duckdb
        op_date: Operating date in ISO format
        disrupted_flight_ids: List of flight_ids that need new aircraft

    Returns:
        dict with keys: assignments (flight_id→registration),
        unassigned (list), coverage_rate, status, solve_time_seconds
    """
    dep_date = date.fromisoformat(op_date)
    assigner, tasks, resources = AircraftAssigner.load_from_db(
        db_path=Path(db_path),
        op_date=dep_date,
        disrupted_flight_ids=disrupted_flight_ids,
    )
    result = assigner.solve(tasks, resources, dep_date)

    return {
        "assignments": result.assignments,
        "unassigned": result.unassigned,
        "coverage_rate": round(result.coverage_rate, 3),
        "status": result.status,
        "solve_time_seconds": result.solve_time_seconds,
    }


# ── Crew optimisation tool ────────────────────────────────────────────────────


@tool
def run_crew_optimisation(
    db_path: str,
    op_date: str,
    disrupted_flight_ids: list[str],
) -> dict:
    """Run CP-SAT crew re-assignment for disrupted flights.

    Uses a synthetic crew pool sized for the KE fleet (no crew DB required).

    Args:
        db_path: Path to argos.duckdb (used to look up flight details)
        op_date: Operating date in ISO format
        disrupted_flight_ids: List of flight_ids needing crew reassignment

    Returns:
        dict with keys: captain_assignments, fo_assignments,
        unassigned_captain, unassigned_fo, fully_crewed_count,
        coverage_rate, far117_violations, status
    """
    import duckdb
    import pandas as pd

    dep_date = date.fromisoformat(op_date)
    midnight_utc = datetime(dep_date.year, dep_date.month, dep_date.day, tzinfo=timezone.utc)

    con = duckdb.connect(db_path, read_only=True)
    try:
        flt_df = con.execute(
            """
            SELECT flight_id, flight_number, aircraft_type,
                   origin_iata, dest_iata, scheduled_dep_utc, block_time_minutes,
                   COALESCE(pax_boarded, 0) AS pax_boarded
            FROM flights
            WHERE flight_id IN ({})
        """.format(",".join(f"'{fid}'" for fid in disrupted_flight_ids))
        ).df()
    finally:
        con.close()

    flt_df["scheduled_dep_utc"] = pd.to_datetime(flt_df["scheduled_dep_utc"], utc=True)
    legs = [
        FlightLeg(
            flight_id=str(r["flight_id"]),
            flight_number=str(r["flight_number"]),
            aircraft_type=str(r["aircraft_type"]),
            origin_iata=str(r["origin_iata"]),
            dest_iata=str(r["dest_iata"]),
            scheduled_dep_utc=r["scheduled_dep_utc"].to_pydatetime(),
            block_time_minutes=int(r["block_time_minutes"]),
            pax_boarded=int(r["pax_boarded"]),
        )
        for _, r in flt_df.iterrows()
    ]

    crew_pool = CrewAssigner.generate_crew(
        n_capt_narrow=12,
        n_fo_narrow=12,
        n_capt_wide=10,
        n_fo_wide=10,
        op_day=dep_date,
    )
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew_pool, dep_date)

    return {
        "captain_assignments": result.captain_assignments,
        "fo_assignments": result.fo_assignments,
        "unassigned_captain": result.unassigned_captain,
        "unassigned_fo": result.unassigned_fo,
        "fully_crewed_count": len(result.fully_crewed),
        "coverage_rate": round(result.coverage_rate, 3),
        "far117_violations": result.far117_violations,
        "status": result.status,
    }


# ── Tool registry ─────────────────────────────────────────────────────────────

OCC_TOOLS = [
    run_propagation,
    run_scenario_generation,
    run_aircraft_optimisation,
    run_crew_optimisation,
]
