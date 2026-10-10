"""
NetworkX-based delay propagation simulator.

Aircraft rotation model:
  Flight[i] departs ICN → arrives dest → turns around → returns ICN → turns around
  → departs ICN as flight[i+1] (same aircraft_registration, same day).

Propagation rule:
  buffer(i→i+1) = scheduled_dep[i+1] - (scheduled_dep[i] + 2*block[i] + 2*min_turn)
  propagated_delay[i+1] = max(0, initial_delay[i] - buffer(i→i+1))

Three OCC recovery scenarios are generated automatically; a human manager
must approve before any action is executed.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import networkx as nx
import pandas as pd

from argos.domain.fleet import compatible_types, min_turn_minutes
from argos.domain.rotation import aircraft_rotation_span

# Rotation edge constraints
_MAX_ROTATION_GAP_HOURS = 14  # max gap to still consider two flights a rotation pair
_MIN_ROTATION_GAP_MIN = 60  # below this, schedule is a data artifact (same-time conflict)
_MAX_PROPAGATED_DELAY = 300  # cap per hop — beyond this the flight is operationally cancelled


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class FlightNode:
    flight_id: str
    flight_number: str
    route_id: str
    aircraft_registration: str
    aircraft_type: str
    origin_iata: str
    dest_iata: str
    scheduled_dep_utc: datetime
    scheduled_arr_utc: datetime
    block_time_minutes: int
    pax_boarded: int
    status: str
    dep_delay_minutes: int = 0

    @property
    def actual_dep_utc(self) -> datetime:
        return self.scheduled_dep_utc + timedelta(minutes=self.dep_delay_minutes)

    @property
    def actual_arr_dest_utc(self) -> datetime:
        """Estimated actual arrival at destination (outbound leg)."""
        return self.actual_dep_utc + timedelta(minutes=self.block_time_minutes)

    @property
    def earliest_return_dep_utc(self) -> datetime:
        """Earliest the aircraft can depart the destination back to ICN."""
        turn = min_turn_minutes(self.aircraft_type)
        return self.actual_arr_dest_utc + timedelta(minutes=turn)

    @property
    def earliest_icn_ready_utc(self) -> datetime:
        """Earliest this aircraft is ready for the next ICN departure."""
        span = aircraft_rotation_span(self.block_time_minutes, min_turn_minutes(self.aircraft_type))
        return self.actual_dep_utc + timedelta(minutes=span)


@dataclass
class PropagationResult:
    trigger_flight_id: str
    initial_delay_minutes: int
    cascade_chain: list[str]  # flight_ids in propagation order
    affected_nodes: list[FlightNode]  # flights with dep_delay > 0 after propagation
    total_delay_minutes: int
    total_pax_impacted: int

    @property
    def cascade_depth(self) -> int:
        return len(self.cascade_chain)


@dataclass
class RecoveryScenario:
    scenario_id: int  # 1, 2, or 3
    name: str
    description: str
    action_required: str
    feasibility: str  # "HIGH" | "MEDIUM" | "LOW"
    residual: PropagationResult  # impact AFTER applying this scenario
    cost_index: float  # relative cost (0.0 = free, 1.0 = most expensive)
    requires_approval: bool = True  # always True — human-in-the-loop


# ── Propagator ────────────────────────────────────────────────────────────────


class DelayPropagator:
    """Builds aircraft rotation DAGs and propagates delays through them."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_flights(self, dep_date: date) -> pd.DataFrame:
        """Load all non-cancelled flights departing on dep_date from DuckDB."""
        day_start = datetime(dep_date.year, dep_date.month, dep_date.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        con = duckdb.connect(str(self.db_path), read_only=True)
        try:
            df = con.execute(
                """
                SELECT
                    flight_id, flight_number, route_id,
                    aircraft_registration, aircraft_type,
                    origin_iata, dest_iata,
                    scheduled_dep_utc, scheduled_arr_utc,
                    block_time_minutes,
                    COALESCE(pax_boarded, 0) AS pax_boarded,
                    status
                FROM flights
                WHERE scheduled_dep_utc >= ?
                  AND scheduled_dep_utc <  ?
                  AND status != 'CNX'
                ORDER BY aircraft_registration, scheduled_dep_utc
            """,
                [day_start, day_end],
            ).df()
        finally:
            con.close()

        df["scheduled_dep_utc"] = pd.to_datetime(df["scheduled_dep_utc"], utc=True)
        df["scheduled_arr_utc"] = pd.to_datetime(df["scheduled_arr_utc"], utc=True)
        return df

    def load_fleet_registrations(self, dep_date: date) -> dict[str, list[str]]:
        """Return all aircraft registrations in fleet, grouped by type.

        Used to find spare aircraft not scheduled on dep_date.
        """
        con = duckdb.connect(str(self.db_path), read_only=True)
        try:
            df = con.execute(
                "SELECT registration, aircraft_type FROM aircraft ORDER BY registration"
            ).df()
        finally:
            con.close()
        result: dict[str, list[str]] = {}
        for _, row in df.iterrows():
            result.setdefault(row["aircraft_type"], []).append(row["registration"])
        return result

    # ── Graph construction ────────────────────────────────────────────────────

    def build_rotation_graph(self, flights_df: pd.DataFrame) -> nx.DiGraph:
        """Build directed rotation graph from same-day flights.

        Nodes: flight_id  (attributes: FlightNode)
        Edges: aircraft rotation dependency — flight[i] → flight[i+1] same reg
               attribute 'buffer_minutes': schedule slack available
        """
        G = nx.DiGraph()

        for _, row in flights_df.iterrows():
            node = FlightNode(
                flight_id=row["flight_id"],
                flight_number=row["flight_number"],
                route_id=row["route_id"],
                aircraft_registration=row["aircraft_registration"],
                aircraft_type=row["aircraft_type"],
                origin_iata=row["origin_iata"],
                dest_iata=row["dest_iata"],
                scheduled_dep_utc=row["scheduled_dep_utc"].to_pydatetime(),
                scheduled_arr_utc=row["scheduled_arr_utc"].to_pydatetime(),
                block_time_minutes=int(row["block_time_minutes"]),
                pax_boarded=int(row["pax_boarded"]),
                status=row["status"],
            )
            G.add_node(row["flight_id"], data=node)

        # Add rotation edges within each aircraft's sequence
        by_reg = flights_df.groupby("aircraft_registration")
        for _, group in by_reg:
            group = group.sort_values("scheduled_dep_utc")
            ids = list(group["flight_id"])
            for i in range(len(ids) - 1):
                u_node: FlightNode = G.nodes[ids[i]]["data"]
                v_node: FlightNode = G.nodes[ids[i + 1]]["data"]

                # Minimum time needed between the two ICN departures
                min_elapsed_min = aircraft_rotation_span(
                    u_node.block_time_minutes, min_turn_minutes(u_node.aircraft_type)
                )
                gap_min = (v_node.scheduled_dep_utc - u_node.scheduled_dep_utc).total_seconds() / 60

                # Skip implausible schedule artifacts (same aircraft < 60 min apart)
                if gap_min < _MIN_ROTATION_GAP_MIN:
                    continue
                # Skip if gap exceeds maximum rotation window
                if gap_min > _MAX_ROTATION_GAP_HOURS * 60:
                    continue

                buffer_min = gap_min - min_elapsed_min
                G.add_edge(
                    ids[i],
                    ids[i + 1],
                    buffer_minutes=buffer_min,
                    min_elapsed_minutes=min_elapsed_min,
                )

        return G

    # ── Propagation ───────────────────────────────────────────────────────────

    def propagate(
        self,
        G: nx.DiGraph,
        trigger_flight_id: str,
        initial_delay_minutes: int,
    ) -> PropagationResult:
        """Propagate delay from trigger flight through all downstream rotations.

        Returns a PropagationResult with a deep-copied graph (originals unchanged).
        """
        G_copy = copy.deepcopy(G)

        if trigger_flight_id not in G_copy:
            raise ValueError(f"Flight {trigger_flight_id!r} not in graph")

        # Set initial delay on trigger
        G_copy.nodes[trigger_flight_id]["data"].dep_delay_minutes = initial_delay_minutes

        cascade_chain = [trigger_flight_id]
        affected: list[FlightNode] = []

        if initial_delay_minutes > 0:
            affected.append(G_copy.nodes[trigger_flight_id]["data"])

        # Topological propagation through downstream nodes
        try:
            topo_order = list(nx.topological_sort(G_copy))
        except nx.NetworkXUnfeasible:
            topo_order = list(G_copy.nodes)

        trigger_seen = False
        for node_id in topo_order:
            if node_id == trigger_flight_id:
                trigger_seen = True
                continue
            if not trigger_seen:
                continue

            node: FlightNode = G_copy.nodes[node_id]["data"]
            max_incoming_delay = 0

            for pred_id in G_copy.predecessors(node_id):
                pred: FlightNode = G_copy.nodes[pred_id]["data"]
                edge = G_copy.edges[pred_id, node_id]
                buffer = edge["buffer_minutes"]
                propagated = max(0.0, pred.dep_delay_minutes - buffer)
                max_incoming_delay = max(max_incoming_delay, propagated)

            if max_incoming_delay > 0:
                node.dep_delay_minutes = min(round(max_incoming_delay), _MAX_PROPAGATED_DELAY)
                if node_id not in cascade_chain:
                    cascade_chain.append(node_id)
                affected.append(node)

        total_delay = sum(n.dep_delay_minutes for n in affected)
        total_pax = sum(n.pax_boarded for n in affected if n.dep_delay_minutes > 0)

        return PropagationResult(
            trigger_flight_id=trigger_flight_id,
            initial_delay_minutes=initial_delay_minutes,
            cascade_chain=cascade_chain,
            affected_nodes=affected,
            total_delay_minutes=total_delay,
            total_pax_impacted=total_pax,
        )

    # ── Recovery scenario generation ─────────────────────────────────────────

    def generate_scenarios(
        self,
        G: nx.DiGraph,
        trigger_flight_id: str,
        initial_delay_minutes: int,
        dep_date: date,
    ) -> list[RecoveryScenario]:
        """Generate 3 OCC recovery scenarios. Human approval required for each."""
        scenarios: list[RecoveryScenario] = []

        # ── Scenario 1: Accept & Absorb ───────────────────────────────────────
        s1_result = self.propagate(G, trigger_flight_id, initial_delay_minutes)
        scenarios.append(
            RecoveryScenario(
                scenario_id=1,
                name="Accept & Absorb",
                description=(
                    f"Accept {initial_delay_minutes} min delay on "
                    f"{G.nodes[trigger_flight_id]['data'].flight_number}. "
                    "No operational changes. Delay propagates through rotation chain."
                ),
                action_required="No action. Monitor cascade and update passengers.",
                feasibility="HIGH",
                residual=s1_result,
                cost_index=0.2,
            )
        )

        # ── Scenario 2: Aircraft Substitution ─────────────────────────────────
        trigger_node: FlightNode = G.nodes[trigger_flight_id]["data"]
        spare_reg = self._find_spare_aircraft(trigger_node.aircraft_type, dep_date)

        if spare_reg:
            G_swap = copy.deepcopy(G)
            # Break all outgoing rotation edges from trigger — downstream flights
            # are now operated by the spare (arrive fresh, no inherited delay)
            downstream = list(nx.descendants(G_swap, trigger_flight_id))
            for ds_id in downstream:
                G_swap.nodes[ds_id]["data"].dep_delay_minutes = 0

            # Trigger flight still has its original delay
            s2_result = self.propagate(G_swap, trigger_flight_id, initial_delay_minutes)
            # But downstream is broken — zero cascade
            s2_result.cascade_chain = [trigger_flight_id]
            s2_result.affected_nodes = [G_swap.nodes[trigger_flight_id]["data"]]
            s2_result.total_pax_impacted = trigger_node.pax_boarded

            scenarios.append(
                RecoveryScenario(
                    scenario_id=2,
                    name="Aircraft Substitution",
                    description=(
                        f"Assign spare {trigger_node.aircraft_type} ({spare_reg}) to downstream "
                        f"rotation. Breaks cascade after {trigger_node.flight_number}."
                    ),
                    action_required=(
                        f"Position {spare_reg} to ICN. Re-assign {len(downstream)} downstream "
                        "flight(s) to spare. Notify maintenance of original aircraft swap."
                    ),
                    feasibility="MEDIUM",
                    residual=s2_result,
                    cost_index=0.6,
                )
            )
        else:
            # No spare available — report infeasibility
            scenarios.append(
                RecoveryScenario(
                    scenario_id=2,
                    name="Aircraft Substitution (N/A)",
                    description="No spare aircraft of compatible type available on this date.",
                    action_required="Escalate to fleet control for cross-fleet swap options.",
                    feasibility="LOW",
                    residual=s1_result,
                    cost_index=1.0,
                )
            )

        # ── Scenario 3: Cancel Least-Critical Downstream Leg ─────────────────
        s1_chain = s1_result.cascade_chain
        if len(s1_chain) > 1:
            # Find the downstream flight with fewest PAX to cancel
            downstream_nodes = [G.nodes[fid]["data"] for fid in s1_chain[1:] if fid in G.nodes]
            cancel_node = min(downstream_nodes, key=lambda n: n.pax_boarded)

            G_cancel = copy.deepcopy(G)
            # Remove all nodes downstream of (and including) cancel_node
            to_remove = list(nx.descendants(G_cancel, cancel_node.flight_id))
            to_remove.append(cancel_node.flight_id)
            G_cancel.remove_nodes_from(to_remove)

            s3_result = self.propagate(G_cancel, trigger_flight_id, initial_delay_minutes)

            scenarios.append(
                RecoveryScenario(
                    scenario_id=3,
                    name="Cancel Least-Loaded Leg",
                    description=(
                        f"Cancel {cancel_node.flight_number} ({cancel_node.route_id}, "
                        f"{cancel_node.pax_boarded} PAX) to prevent further cascade. "
                        f"Protects {len(downstream_nodes) - 1} downstream flight(s)."
                    ),
                    action_required=(
                        f"Issue cancellation for {cancel_node.flight_number}. "
                        "Rebook affected passengers. Notify downstream stations."
                    ),
                    feasibility="MEDIUM",
                    residual=s3_result,
                    cost_index=0.8,
                )
            )
        else:
            # Single-flight cascade — cancellation not needed
            s3_clone = copy.deepcopy(s1_result)
            scenarios.append(
                RecoveryScenario(
                    scenario_id=3,
                    name="No Further Action (Single Leg)",
                    description=(
                        "Trigger flight has no downstream rotation on this date. No cascade."
                    ),
                    action_required="None. Monitor flight and update ETA.",
                    feasibility="HIGH",
                    residual=s3_clone,
                    cost_index=0.0,
                )
            )

        return scenarios

    def _find_spare_aircraft(self, aircraft_type: str, dep_date: date) -> str | None:
        """Return spare aircraft registration not scheduled on dep_date.

        Checks exact type first, then compatible types (with a note).
        """
        fleet_by_type = self.load_fleet_registrations(dep_date)

        day_start = datetime(dep_date.year, dep_date.month, dep_date.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        con = duckdb.connect(str(self.db_path), read_only=True)
        try:
            busy = set(
                con.execute(
                    """
                    SELECT DISTINCT aircraft_registration
                    FROM flights
                    WHERE scheduled_dep_utc >= ? AND scheduled_dep_utc < ?
                      AND status != 'CNX'
                """,
                    [day_start, day_end],
                )
                .df()["aircraft_registration"]
                .tolist()
            )
        finally:
            con.close()

        # Check exact type first, then compatible types
        check_types = compatible_types(aircraft_type)
        for t in check_types:
            for reg in fleet_by_type.get(t, []):
                if reg not in busy:
                    return reg
        return None
