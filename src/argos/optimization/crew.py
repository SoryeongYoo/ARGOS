"""
OR-Tools CP-SAT crew roster optimizer for OCC disruption recovery.

Scope: Flight-deck crew (CAPT + FO) on ICN-hub round-trip duties.

Formulation
-----------
Decision variables
  capt[f, c] ∈ {0,1}  crew c assigned as Captain to flight f
  fo[f, c]   ∈ {0,1}  crew c assigned as First Officer to flight f

Hard constraints
  1. Each flight: exactly 1 CAPT, exactly 1 FO (allow unassignment when infeasible)
  2. CAPT ≠ FO on same flight: capt[f,c] + fo[f,c] ≤ 1
  3. Type-rating compatibility: crew must hold rating for the aircraft type
  4. FAR 117 § 117.65(a): total block time per crew ≤ 8 h (480 min) per calendar day
  5. No-overlap per crew: round-trip footprint
         [dep - CHECK_IN, dep + 2·block + min_turn + POST_FLIGHT]
     ensures a crew cannot be double-booked

Objective: maximise weighted PAX coverage, penalise unassigned positions.

Post-solve validation
  For each crew's final duty sequence, far117.is_fdp_legal() is called and any
  violations are surfaced in CrewAssignmentResult.far117_violations.
  Safety note: FAR 117 is a hard constraint in reality; the CP-SAT model
  enforces the flight-time component.  The FDP window check is the
  post-solve gate before a human OCC manager approves the roster.

ICN-hub assumptions
  All flights depart ICN and crew returns on the same aircraft pair.
  Report time = dep_utc - 60 min converted to KST (UTC+9).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from ortools.sat.python import cp_model

from argos.domain.far117 import is_fdp_legal
from argos.domain.fleet import min_turn_minutes

# ── Constants ─────────────────────────────────────────────────────────────────

_KST_OFFSET = 9  # UTC+9
_CHECK_IN_MIN = 60  # crew reports 60 min before departure
_POST_FLIGHT_MIN = 30  # post-flight duties after block-in
_MAX_FLIGHT_TIME_MIN = 480  # FAR 117 § 117.65(a) — 8 h per calendar day
_MIN_REST_MIN = 600  # FAR 117 § 117.25 — 10 h minimum rest

# Type-rating groups: a single qualification covers all types in the group
_RATING_GROUPS: dict[str, str] = {
    "B737-800": "NARROW",
    "A321neo": "NARROW",
    "B777-300ER": "WIDE",
    "B787-9": "WIDE",
    "B747-8i": "WIDE",
}


def _crew_footprint(block_time: int, aircraft_type: str) -> int:
    """Total minutes a crew is 'occupied' by one ICN round-trip leg assignment."""
    return _CHECK_IN_MIN + 2 * block_time + min_turn_minutes(aircraft_type) + _POST_FLIGHT_MIN


def _is_rated(crew_type_rating: str, aircraft_type: str) -> bool:
    """Return True if the crew's type rating covers the required aircraft type."""
    return _RATING_GROUPS.get(crew_type_rating) == _RATING_GROUPS.get(aircraft_type)


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class FlightLeg:
    """A flight leg that needs crew assignment."""

    flight_id: str
    flight_number: str
    aircraft_type: str
    origin_iata: str
    dest_iata: str
    scheduled_dep_utc: datetime
    block_time_minutes: int
    pax_boarded: int


@dataclass
class CrewMember:
    """A crew member available for assignment."""

    crew_id: str
    name: str
    role: Literal["CAPT", "FO"]
    type_rating: str  # one of the five fleet types (used as group key)
    position_iata: str
    available_from_utc: datetime
    rest_end_utc: datetime | None = None  # earliest they can start next FDP
    fdp_used_minutes: int = 0  # FDP already consumed today
    flight_time_used_minutes: int = 0  # block time already flown today


@dataclass
class DutyPeriod:
    """Resolved duty period for one crew member after assignment."""

    crew_id: str
    flight_ids: list[str]
    report_utc: datetime
    release_utc: datetime
    total_block_minutes: int
    fdp_minutes: int
    far117_legal: bool
    far117_max_hours: float


@dataclass
class CrewAssignmentResult:
    captain_assignments: dict[str, str]  # flight_id → crew_id
    fo_assignments: dict[str, str]  # flight_id → crew_id
    unassigned_captain: list[str]  # flight_ids missing CAPT
    unassigned_fo: list[str]  # flight_ids missing FO
    duty_periods: list[DutyPeriod]
    far117_violations: list[str]  # human-readable violation messages
    solve_time_seconds: float
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "TIMEOUT"]

    @property
    def fully_crewed(self) -> list[str]:
        """Flight IDs that have both CAPT and FO assigned."""
        return [fid for fid in self.captain_assignments if fid in self.fo_assignments]

    @property
    def coverage_rate(self) -> float:
        total_positions = (
            len(self.captain_assignments)
            + len(self.unassigned_captain)
            + len(self.fo_assignments)
            + len(self.unassigned_fo)
        )
        filled = len(self.captain_assignments) + len(self.fo_assignments)
        return filled / total_positions if total_positions else 0.0

    def summary(self) -> str:
        lines = [
            f"Status  : {self.status}",
            f"Covered : {len(self.fully_crewed)} flights fully crewed "
            f"({self.coverage_rate:.1%} position fill rate)",
            f"CAPT gap: {len(self.unassigned_captain)} flights",
            f"FO gap  : {len(self.unassigned_fo)} flights",
            "FAR 117 : "
            + ("OK" if not self.far117_violations else f"{len(self.far117_violations)} violations"),
            f"Solved in {self.solve_time_seconds:.2f}s",
        ]
        for dp in self.duty_periods:
            legal = "✓" if dp.far117_legal else "✗ VIOLATION"
            lines.append(
                f"  {dp.crew_id}: {len(dp.flight_ids)} leg(s), "
                f"FDP {dp.fdp_minutes // 60}h{dp.fdp_minutes % 60:02d}m "
                f"(max {dp.far117_max_hours:.1f}h) {legal}"
            )
        if self.far117_violations:
            for v in self.far117_violations:
                lines.append(f"  [!] {v}")
        return "\n".join(lines)


# ── Optimizer ─────────────────────────────────────────────────────────────────


class CrewAssigner:
    """CP-SAT crew-to-flight assignment optimizer.

    Usage::

        assigner = CrewAssigner()
        result = assigner.solve(legs, crew_pool, op_day)
        print(result.summary())
    """

    def solve(
        self,
        legs: list[FlightLeg],
        crew: list[CrewMember],
        op_day: date,
        time_limit_seconds: float = 30.0,
    ) -> CrewAssignmentResult:
        t0 = time.perf_counter()

        if not legs:
            return CrewAssignmentResult({}, {}, [], [], [], [], 0.0, "OPTIMAL")
        if not crew:
            fids = [leg.flight_id for leg in legs]
            return CrewAssignmentResult({}, {}, fids, fids, [], [], 0.0, "INFEASIBLE")

        midnight_utc = datetime(op_day.year, op_day.month, op_day.day, tzinfo=UTC)

        def to_min(dt: datetime) -> int:
            return max(0, int((dt - midnight_utc).total_seconds() / 60))

        model = cp_model.CpModel()
        HORIZON = 30 * 60  # 30-hour window

        # ── Build feasible (leg, crew) pairs ──────────────────────────────────
        capt_vars: dict[tuple[int, int], cp_model.IntVar] = {}
        fo_vars: dict[tuple[int, int], cp_model.IntVar] = {}

        for f_idx, leg in enumerate(legs):
            dep_min = to_min(leg.scheduled_dep_utc)

            for c_idx, cm in enumerate(crew):
                # Type-rating check
                if not _is_rated(cm.type_rating, leg.aircraft_type):
                    continue

                # Availability check (rest period + position)
                ready_min = to_min(cm.available_from_utc)
                if cm.rest_end_utc:
                    ready_min = max(ready_min, to_min(cm.rest_end_utc))

                # Need to be at origin at check-in time
                checkin_min = dep_min - _CHECK_IN_MIN
                if ready_min > checkin_min:
                    continue

                key = (f_idx, c_idx)
                if cm.role == "CAPT":
                    capt_vars[key] = model.NewBoolVar(f"capt_{f_idx}_{c_idx}")
                    # Captains may also fill FO slot (downgrade) with penalty
                    fo_vars[key] = model.NewBoolVar(f"fo_capt_{f_idx}_{c_idx}")
                else:  # FO
                    fo_vars[key] = model.NewBoolVar(f"fo_{f_idx}_{c_idx}")

        # ── Each flight: at most 1 CAPT and 1 FO (allow unassignment) ─────────
        for f_idx in range(len(legs)):
            capt_pool = [capt_vars[f_idx, c] for c in range(len(crew)) if (f_idx, c) in capt_vars]
            fo_pool = [fo_vars[f_idx, c] for c in range(len(crew)) if (f_idx, c) in fo_vars]
            if capt_pool:
                model.Add(sum(capt_pool) <= 1)
            if fo_pool:
                model.Add(sum(fo_pool) <= 1)

        # ── Same crew can't be both CAPT and FO on same flight ────────────────
        for f_idx in range(len(legs)):
            for c_idx in range(len(crew)):
                if (f_idx, c_idx) in capt_vars and (f_idx, c_idx) in fo_vars:
                    model.Add(capt_vars[f_idx, c_idx] + fo_vars[f_idx, c_idx] <= 1)

        # ── FAR 117 § 117.65(a): daily flight time cap per crew ───────────────
        for c_idx, cm in enumerate(crew):
            all_assignments = []
            for f_idx, leg in enumerate(legs):
                if (f_idx, c_idx) in capt_vars:
                    all_assignments.append((capt_vars[f_idx, c_idx], leg.block_time_minutes))
                if (f_idx, c_idx) in fo_vars:
                    all_assignments.append((fo_vars[f_idx, c_idx], leg.block_time_minutes))
            if all_assignments:
                remaining = _MAX_FLIGHT_TIME_MIN - cm.flight_time_used_minutes
                model.Add(sum(var * bt for var, bt in all_assignments) <= max(0, remaining))

        # ── No-overlap per crew (round-trip footprint) ─────────────────────────
        for c_idx, cm in enumerate(crew):  # noqa: B007 — 미사용 루프 변수, 로직 검토 필요
            intervals: list[cp_model.IntervalVar] = []

            for f_idx, leg in enumerate(legs):
                dep_min = to_min(leg.scheduled_dep_utc)
                footprint = _crew_footprint(leg.block_time_minutes, leg.aircraft_type)
                start = dep_min - _CHECK_IN_MIN
                end = min(start + footprint, HORIZON)

                # Both capt and fo intervals must be tracked independently —
                # a CAPT can fill either role, so both need overlap protection.
                if (f_idx, c_idx) in capt_vars:
                    itv = model.NewOptionalIntervalVar(
                        start,
                        footprint,
                        end,
                        capt_vars[f_idx, c_idx],
                        f"itv_c_{f_idx}_{c_idx}",
                    )
                    intervals.append(itv)
                if (f_idx, c_idx) in fo_vars:
                    itv = model.NewOptionalIntervalVar(
                        start,
                        footprint,
                        end,
                        fo_vars[f_idx, c_idx],
                        f"itv_fo_{f_idx}_{c_idx}",
                    )
                    intervals.append(itv)

            if len(intervals) >= 2:
                model.AddNoOverlap(intervals)

        # ── Objective ──────────────────────────────────────────────────────────
        # Maximise PAX covered; penalise CAPT downgrade (flying as FO)
        _DOWNGRADE_PENALTY = 30  # PAX-equivalent penalty per substitution
        obj_terms = []
        for (f_idx, c_idx), var in capt_vars.items():
            leg = legs[f_idx]
            cm = crew[c_idx]
            w = leg.pax_boarded
            if cm.role == "CAPT":
                # CAPT filling FO slot: check if this is a fo_var
                pass
            obj_terms.append(var * w)

        for (f_idx, c_idx), var in fo_vars.items():
            leg = legs[f_idx]
            cm = crew[c_idx]
            w = leg.pax_boarded
            if cm.role == "CAPT":
                # Captain downgrading to FO
                w = max(0, w - _DOWNGRADE_PENALTY)
            obj_terms.append(var * w)

        if obj_terms:
            model.Maximize(sum(obj_terms))

        # ── Solve ──────────────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_seconds
        solver.parameters.num_search_workers = 4
        cp_status = solver.Solve(model)

        solve_time = time.perf_counter() - t0

        # 상태 이름(str)으로 비교한다. ortools 9.11 은 Solve() 반환을 enum 클래스
        # CpSolverStatus 로 잘못 annotate 해서, 값 비교는 환경마다 mypy 결과가 달라진다.
        _STATUS_MAP: dict[str, Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"]] = {
            "OPTIMAL": "OPTIMAL",
            "FEASIBLE": "FEASIBLE",
            "INFEASIBLE": "INFEASIBLE",
            "UNKNOWN": "UNKNOWN",
        }
        status_str: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "TIMEOUT"] = (
            _STATUS_MAP.get(solver.StatusName(cp_status), "TIMEOUT")
        )

        # ── Extract solution ───────────────────────────────────────────────────
        capt_assign: dict[str, str] = {}
        fo_assign: dict[str, str] = {}

        if status_str in ("OPTIMAL", "FEASIBLE"):
            for (f_idx, c_idx), var in capt_vars.items():
                if solver.Value(var) == 1:
                    cm = crew[c_idx]
                    if cm.role == "CAPT":
                        capt_assign[legs[f_idx].flight_id] = cm.crew_id
            for (f_idx, c_idx), var in fo_vars.items():
                if solver.Value(var) == 1:
                    fid = legs[f_idx].flight_id
                    cid = crew[c_idx].crew_id
                    if fid not in capt_assign:
                        # CAPT acting as captain was already captured above;
                        # this is either an FO or a CAPT downgrading to FO
                        fo_assign[fid] = cid
                    else:
                        fo_assign[fid] = cid

        unassigned_capt = [leg.flight_id for leg in legs if leg.flight_id not in capt_assign]
        unassigned_fo = [leg.flight_id for leg in legs if leg.flight_id not in fo_assign]

        # ── Post-solve FAR 117 FDP validation ─────────────────────────────────
        duty_periods, violations = self._validate_far117(
            legs, crew, capt_assign, fo_assign, midnight_utc
        )

        return CrewAssignmentResult(
            captain_assignments=capt_assign,
            fo_assignments=fo_assign,
            unassigned_captain=unassigned_capt,
            unassigned_fo=unassigned_fo,
            duty_periods=duty_periods,
            far117_violations=violations,
            solve_time_seconds=round(solve_time, 3),
            status=status_str,
        )

    # ── FAR 117 post-solve check ───────────────────────────────────────────────

    @staticmethod
    def _validate_far117(
        legs: list[FlightLeg],
        crew: list[CrewMember],
        capt_assign: dict[str, str],
        fo_assign: dict[str, str],
        midnight_utc: datetime,
    ) -> tuple[list[DutyPeriod], list[str]]:
        """Compute each crew member's duty period and check FAR 117 FDP limits."""
        leg_by_id = {leg.flight_id: leg for leg in legs}

        # Group assigned flights per crew member
        crew_flights: dict[str, list[FlightLeg]] = {}
        for fid, cid in {**capt_assign, **fo_assign}.items():
            crew_flights.setdefault(cid, []).append(leg_by_id[fid])

        # Sort each crew's legs by departure time
        for cid in crew_flights:
            crew_flights[cid].sort(key=lambda leg: leg.scheduled_dep_utc)

        duty_periods: list[DutyPeriod] = []
        violations: list[str] = []

        crew_by_id = {cm.crew_id: cm for cm in crew}

        for cid, flight_list in crew_flights.items():
            cm = crew_by_id.get(cid)
            if cm is None:
                continue

            first_dep = flight_list[0].scheduled_dep_utc
            last_leg = flight_list[-1]

            # Report time = departure of first leg - CHECK_IN_MIN
            report_utc = first_dep - timedelta(minutes=_CHECK_IN_MIN)

            # FDP ends when crew checks in after return from last leg
            last_arr_utc = last_leg.scheduled_dep_utc + timedelta(
                minutes=2 * last_leg.block_time_minutes + min_turn_minutes(last_leg.aircraft_type)
            )
            release_utc = last_arr_utc + timedelta(minutes=_POST_FLIGHT_MIN)

            # Convert report time to KST for FAR 117 table lookup
            report_kst = report_utc + timedelta(hours=_KST_OFFSET)
            fdp_minutes = int((release_utc - report_utc).total_seconds() / 60)
            fdp_minutes += cm.fdp_used_minutes  # add already-consumed FDP today

            total_block = sum(leg.block_time_minutes for leg in flight_list)
            num_segs = 2 * len(flight_list)  # out + back per leg

            legal, max_hours = is_fdp_legal(report_kst, fdp_minutes / 60, num_segs)

            dp = DutyPeriod(
                crew_id=cid,
                flight_ids=[leg.flight_id for leg in flight_list],
                report_utc=report_utc,
                release_utc=release_utc,
                total_block_minutes=total_block,
                fdp_minutes=fdp_minutes,
                far117_legal=legal,
                far117_max_hours=max_hours,
            )
            duty_periods.append(dp)

            if not legal:
                violations.append(
                    f"{cid}: FDP {fdp_minutes // 60}h{fdp_minutes % 60:02d}m "
                    f"exceeds max {max_hours:.1f}h "
                    f"(report {report_kst.strftime('%H:%M')} KST, {num_segs} segs)"
                )

        return duty_periods, violations

    # ── Synthetic crew generator (no DB required) ─────────────────────────────

    @staticmethod
    def generate_crew(
        n_capt_narrow: int = 10,
        n_fo_narrow: int = 10,
        n_capt_wide: int = 8,
        n_fo_wide: int = 8,
        op_day: date | None = None,
    ) -> list[CrewMember]:
        """Generate a synthetic crew pool for testing without a crew database.

        Produces ICN-based crew available from midnight on op_day.
        Two type groups: NARROW (B737-800) and WIDE (B777-300ER).
        """
        if op_day is None:
            op_day = date.today()
        midnight_utc = datetime(op_day.year, op_day.month, op_day.day, tzinfo=UTC)

        pool: list[CrewMember] = []

        configs = [
            ("CAPT", "B737-800", n_capt_narrow, "N"),
            ("FO", "B737-800", n_fo_narrow, "N"),
            ("CAPT", "B777-300ER", n_capt_wide, "W"),
            ("FO", "B777-300ER", n_fo_wide, "W"),
        ]
        for role, rating, count, prefix in configs:
            for i in range(1, count + 1):
                pool.append(
                    CrewMember(
                        crew_id=f"KE-{role[0]}{prefix}{i:03d}",
                        name=f"{role} {prefix}{i:03d}",
                        role=role,  # type: ignore[arg-type]
                        type_rating=rating,
                        position_iata="ICN",
                        available_from_utc=midnight_utc,
                    )
                )
        return pool
