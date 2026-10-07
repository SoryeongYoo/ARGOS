"""OCC agent graph state definition."""

from __future__ import annotations

from typing import Annotated, Any
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class OCCState(TypedDict):
    """Shared state flowing through the OCC agent graph.

    All fields are optional at graph start; nodes populate them progressively.
    """

    # ── Trigger inputs ──────────────────────────────────────────────────────
    trigger_flight_id: str
    initial_delay_minutes: int
    op_date: str  # ISO format "YYYY-MM-DD"
    db_path: str  # path to argos.duckdb

    # ── Propagation ─────────────────────────────────────────────────────────
    propagation_summary: dict[str, Any]  # serialisable subset of PropagationResult

    # ── Recovery scenarios (from DelayPropagator.generate_scenarios) ────────
    scenarios_raw: list[dict[str, Any]]  # 3 serialised RecoveryScenario dicts
    scenario_briefing: str  # Claude-authored OCC briefing text

    # ── Optimiser outputs ────────────────────────────────────────────────────
    aircraft_result: dict[str, Any] | None
    crew_result: dict[str, Any] | None

    # ── Human-in-the-loop ────────────────────────────────────────────────────
    approved_scenario_id: int | None  # 1, 2, or 3
    approval_notes: str

    # ── Execution summary ────────────────────────────────────────────────────
    execution_summary: str

    # ── LLM message history (append-only) ───────────────────────────────────
    messages: Annotated[list, add_messages]
