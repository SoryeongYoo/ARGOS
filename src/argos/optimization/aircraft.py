"""
OR-Tools CP-SAT aircraft assignment optimizer for OCC disruption recovery.

Formulation
-----------
Decision variable  x[f, a] ∈ {0,1}  aircraft a assigned to flight f.

Hard constraints
  1. Each flight covered by at most one aircraft (soft: unassignment is allowed
     so that infeasibility is never returned when the fleet is insufficient).
  2. Type compatibility: a can cover f only if a.type ∈ compatible_types(f.required_type).
  3. Aircraft availability: a.position and a.available_from are respected.
  4. No-overlap per aircraft: the "footprint" of a round-trip from ICN is
         [dep_min, dep_min + 2*block + 2*min_turn)
     AddNoOverlap ensures no two flights are active at the same time on one tail.

Objective
  Maximise  Σ x[f,a] · pax_boarded[f]   (protect most passengers first)
  tie-break: prefer exact-type matches over compatible-type substitutions.

ICN-hub assumption
  All flights depart ICN and return to ICN.  Repositioning time for an
  aircraft not currently at ICN is conservatively set to 120 min.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd
from ortools.sat.python import cp_model

# ── Domain constants ──────────────────────────────────────────────────────────

_WIDE_BODY = {"B777-300ER", "B787-9", "B747-8i"}
_MIN_TURN_NARROW = 45  # minutes
_MIN_TURN_WIDE = 60  # minutes
_REPOSITIONING_MINUTES = 120  # conservative ferry-flight estimate

_TYPE_COMPAT: dict[str, list[str]] = {
    "B737-800": ["A321neo"],
    "A321neo": ["B737-800"],
    "B777-300ER": ["B787-9", "B747-8i"],
    "B787-9": ["B777-300ER"],
    "B747-8i": ["B777-300ER", "B787-9"],
}

_SUBSTITUTION_PENALTY = 50  # PAX-equivalent cost for cross-type substitution


def _min_turn(aircraft_type: str) -> int:
    return _MIN_TURN_WIDE if aircraft_type in _WIDE_BODY else _MIN_TURN_NARROW


def _compatible_types(required_type: str) -> list[str]:
    """Return list of aircraft types that can legally cover required_type."""
    return [required_type] + _TYPE_COMPAT.get(required_type, [])


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class FlightTask:
    """A flight leg that needs an aircraft assignment."""

    flight_id: str
    flight_number: str
    route_id: str
    required_type: str  # primary required aircraft type
    origin_iata: str
    dest_iata: str
    scheduled_dep_utc: datetime
    block_time_minutes: int
    pax_boarded: int
    priority: int = 1  # 1 = normal; higher = more critical to protect


@dataclass
class AircraftResource:
    """An available aircraft tail."""

    registration: str
    aircraft_type: str
    position_iata: str  # current/last-known airport
    available_from_utc: datetime
    is_spare: bool = False  # True if not in the original day's schedule


@dataclass
class AssignmentResult:
    assignments: dict[str, str]  # flight_id → registration
    unassigned: list[str]  # flight_ids that could not be covered
    solve_time_seconds: float
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "TIMEOUT"]

    @property
    def coverage_rate(self) -> float:
        total = len(self.assignments) + len(self.unassigned)
        return len(self.assignments) / total if total else 0.0

    def summary(self) -> str:
        lines = [
            f"Status : {self.status}",
            f"Covered: {len(self.assignments)} flights  ({self.coverage_rate:.1%})",
            f"Missed : {len(self.unassigned)} flights",
            f"Solved in {self.solve_time_seconds:.2f}s",
        ]
        for fid, reg in sorted(self.assignments.items()):
            lines.append(f"  {fid} → {reg}")
        if self.unassigned:
            lines.append("  Unassigned: " + ", ".join(self.unassigned))
        return "\n".join(lines)


# ── Optimizer ─────────────────────────────────────────────────────────────────


class AircraftAssigner:
    """CP-SAT aircraft-to-flight assignment optimizer.

    Usage::

        assigner = AircraftAssigner()
        result = assigner.solve(tasks, aircraft_resources, op_day)
        print(result.summary())
    """

    def solve(
        self,
        tasks: list[FlightTask],
        aircraft: list[AircraftResource],
        op_day: date,
        time_limit_seconds: float = 30.0,
    ) -> AssignmentResult:
        """Assign aircraft to flights and return the optimal coverage plan."""
        t0 = time.perf_counter()

        if not tasks:
            return AssignmentResult({}, [], 0.0, "OPTIMAL")
        if not aircraft:
            return AssignmentResult({}, [t.flight_id for t in tasks], 0.0, "INFEASIBLE")

        midnight_utc = datetime(op_day.year, op_day.month, op_day.day, tzinfo=timezone.utc)

        def to_min(dt: datetime) -> int:
            """Convert datetime to integer minutes from midnight UTC on op_day."""
            return max(0, int((dt - midnight_utc).total_seconds() / 60))

        model = cp_model.CpModel()
        HORIZON = 30 * 60  # 30-hour window in minutes (handles red-eye delays)

        # ── Build feasible (flight, aircraft) pairs ────────────────────────────
        # x[f_idx, a_idx] = 1  ↔  aircraft a assigned to flight f
        x: dict[tuple[int, int], cp_model.IntVar] = {}

        for f_idx, task in enumerate(tasks):
            dep_min = to_min(task.scheduled_dep_utc)
            compat_types = _compatible_types(task.required_type)

            for a_idx, ac in enumerate(aircraft):
                if ac.aircraft_type not in compat_types:
                    continue

                # Earliest the aircraft is ready at the flight's origin
                ready_min = to_min(ac.available_from_utc)
                if ac.position_iata != task.origin_iata:
                    ready_min += _REPOSITIONING_MINUTES

                # 60-min flexibility window: allow slightly late aircraft (delay absorbed)
                if ready_min > dep_min + 60:
                    continue

                x[f_idx, a_idx] = model.NewBoolVar(f"x_{f_idx}_{a_idx}")

        # ── Coverage constraint: at most one aircraft per flight ───────────────
        for f_idx in range(len(tasks)):
            covered_by = [x[f_idx, a_idx] for a_idx in range(len(aircraft)) if (f_idx, a_idx) in x]
            if covered_by:
                model.Add(sum(covered_by) <= 1)

        # ── No-overlap per aircraft ────────────────────────────────────────────
        # Footprint = ICN round-trip: departure → back-at-ICN-ready-for-next
        for a_idx, ac in enumerate(aircraft):
            intervals: list[cp_model.IntervalVar] = []
            for f_idx, task in enumerate(tasks):
                if (f_idx, a_idx) not in x:
                    continue
                dep_min = to_min(task.scheduled_dep_utc)
                footprint = 2 * task.block_time_minutes + 2 * _min_turn(ac.aircraft_type)
                end_min = min(dep_min + footprint, HORIZON)
                itv = model.NewOptionalIntervalVar(
                    dep_min,
                    footprint,
                    end_min,
                    x[f_idx, a_idx],
                    f"itv_{f_idx}_{a_idx}",
                )
                intervals.append(itv)
            if len(intervals) >= 2:
                model.AddNoOverlap(intervals)

        # ── Objective: maximise covered PAX; penalise cross-type substitutions ─
        obj_terms: list[cp_model.LinearExpr] = []
        for (f_idx, a_idx), var in x.items():
            task = tasks[f_idx]
            ac = aircraft[a_idx]
            weight = task.pax_boarded * task.priority
            if ac.aircraft_type != task.required_type:
                weight = max(0, weight - _SUBSTITUTION_PENALTY)
            obj_terms.append(var * weight)

        model.Maximize(sum(obj_terms))

        # ── Solve ──────────────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = 4
        cp_status = solver.Solve(model)

        solve_time = time.perf_counter() - t0

        _STATUS_MAP = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.UNKNOWN: "UNKNOWN",
        }
        status_str: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "TIMEOUT"] = (
            _STATUS_MAP.get(cp_status, "TIMEOUT")  # type: ignore[assignment]
        )

        # ── Extract assignments ────────────────────────────────────────────────
        assignments: dict[str, str] = {}
        if cp_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for (f_idx, a_idx), var in x.items():
                if solver.Value(var) == 1:
                    assignments[tasks[f_idx].flight_id] = aircraft[a_idx].registration

        unassigned = [t.flight_id for t in tasks if t.flight_id not in assignments]

        return AssignmentResult(
            assignments=assignments,
            unassigned=unassigned,
            solve_time_seconds=round(solve_time, 3),
            status=status_str,
        )

    # ── DuckDB integration ─────────────────────────────────────────────────────

    @classmethod
    def load_from_db(
        cls,
        db_path: Path,
        op_date: date,
        disrupted_flight_ids: list[str] | None = None,
    ) -> tuple["AircraftAssigner", list[FlightTask], list[AircraftResource]]:
        """Load tasks and aircraft resources from DuckDB for the given operating date.

        Args:
            db_path: Path to argos.duckdb
            op_date: The operating date (UTC) to optimise
            disrupted_flight_ids: If provided, only these flights are treated as
                tasks needing reassignment (all others keep their original tail).
                Pass None to reassign the entire day's schedule.
        """
        day_start = datetime(op_date.year, op_date.month, op_date.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        con = duckdb.connect(str(db_path), read_only=True)
        try:
            flt_df = con.execute(
                """
                SELECT flight_id, flight_number, route_id,
                       aircraft_type, origin_iata, dest_iata,
                       scheduled_dep_utc, block_time_minutes,
                       COALESCE(pax_boarded, 0) AS pax_boarded
                FROM flights
                WHERE scheduled_dep_utc >= ?
                  AND scheduled_dep_utc <  ?
                  AND status != 'CNX'
                ORDER BY scheduled_dep_utc
            """,
                [day_start, day_end],
            ).df()

            ac_df = con.execute(
                "SELECT registration, aircraft_type FROM aircraft ORDER BY registration"
            ).df()

            busy_regs: set[str] = set(
                con.execute(
                    """
                    SELECT DISTINCT aircraft_registration
                    FROM flights
                    WHERE scheduled_dep_utc >= ?
                      AND scheduled_dep_utc <  ?
                      AND status != 'CNX'
                """,
                    [day_start, day_end],
                )
                .df()["aircraft_registration"]
                .tolist()
            )
        finally:
            con.close()

        if disrupted_flight_ids is not None:
            flt_df = flt_df[flt_df["flight_id"].isin(disrupted_flight_ids)]

        flt_df["scheduled_dep_utc"] = pd.to_datetime(flt_df["scheduled_dep_utc"], utc=True)

        tasks = [
            FlightTask(
                flight_id=str(row["flight_id"]),
                flight_number=str(row["flight_number"]),
                route_id=str(row["route_id"]),
                required_type=str(row["aircraft_type"]),
                origin_iata=str(row["origin_iata"]),
                dest_iata=str(row["dest_iata"]),
                scheduled_dep_utc=row["scheduled_dep_utc"].to_pydatetime(),
                block_time_minutes=int(row["block_time_minutes"]),
                pax_boarded=int(row["pax_boarded"]),
            )
            for _, row in flt_df.iterrows()
        ]

        resources = [
            AircraftResource(
                registration=str(row["registration"]),
                aircraft_type=str(row["aircraft_type"]),
                position_iata="ICN",
                available_from_utc=day_start,
                is_spare=(str(row["registration"]) not in busy_regs),
            )
            for _, row in ac_df.iterrows()
        ]

        return cls(), tasks, resources
