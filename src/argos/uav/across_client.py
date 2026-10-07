"""
ACROSS (국토교통부 UAM 교통관리) API 클라이언트 — simulation mode.

In production, this module would call the real ACROSS REST API.
In simulation mode (default), it runs the local airspace conflict
checker and returns synthetic ACROSS-style responses.

ACROSS API reference:
  POST /v1/flight-plans          → submit plan
  GET  /v1/flight-plans/{id}     → status check
  PUT  /v1/flight-plans/{id}     → update/cancel
  GET  /v1/airspace/corridors    → corridor availability

All timestamps are UTC.  ACROSS uses KST internally for curfew checks;
the client handles the conversion transparently.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from argos.uav.airspace import assess_conflicts
from argos.uav.models import (
    ACROSSResponse,
    ApprovalStatus,
    ConflictType,
    UAMFlightPlan,
)


class ACROSSClient:
    """ACROSS UTM client.

    Args:
        mode: "simulation" (default) — local conflict check only.
              "live" — reserved for real API integration (not implemented).
        base_url: ACROSS API base URL (ignored in simulation mode).
    """

    def __init__(
        self,
        mode: Literal["simulation", "live"] = "simulation",
        base_url: str = "https://across.molit.go.kr/api",
    ) -> None:
        self.mode = mode
        self.base_url = base_url
        self._plans: dict[str, UAMFlightPlan] = {}
        self._responses: dict[str, ACROSSResponse] = {}

    # ── Plan lifecycle ────────────────────────────────────────────────────────

    def submit_plan(
        self,
        plan: UAMFlightPlan,
        active_plans: list[UAMFlightPlan] | None = None,
    ) -> ACROSSResponse:
        """Submit a UAM flight plan for approval.

        In simulation mode, runs the local conflict checker and returns
        an ACROSS-style response immediately (no async wait).
        """
        self._plans[plan.plan_id] = plan

        conflicts = assess_conflicts(plan, active_plans or list(self._plans.values()))

        # Classify severity: AIRSPACE / RUNWAY_CORR / SEPARATION → DENIED
        # CURFEW → DENIED.  WEATHER → conditional.
        hard_types = {
            ConflictType.AIRSPACE,
            ConflictType.RUNWAY_CORR,
            ConflictType.SEPARATION,
            ConflictType.CURFEW,
        }
        hard = [c for c in conflicts if c.conflict_type in hard_types]
        soft = [c for c in conflicts if c.conflict_type not in hard_types]

        if hard:
            response = ACROSSResponse(
                plan_id=plan.plan_id,
                status=ApprovalStatus.DENIED,
                approval_time_utc=datetime.now(UTC),
                conflicts=conflicts,
                message=(
                    f"Flight plan denied: {len(hard)} hard conflict(s) detected. "
                    f"See conflict details for resolution guidance."
                ),
            )
        elif soft:
            response = ACROSSResponse(
                plan_id=plan.plan_id,
                status=ApprovalStatus.APPROVED,
                approval_time_utc=datetime.now(UTC),
                conflicts=soft,
                conditions=[
                    f"Monitor {c.conflict_type.value} condition: {c.description}" for c in soft
                ],
                message="Conditionally approved. Review attached conditions.",
            )
        else:
            response = ACROSSResponse(
                plan_id=plan.plan_id,
                status=ApprovalStatus.APPROVED,
                approval_time_utc=datetime.now(UTC),
                message="Flight plan approved. No conflicts detected.",
            )

        self._responses[plan.plan_id] = response
        return response

    def get_status(self, plan_id: str) -> ACROSSResponse | None:
        """Retrieve the current approval status for a plan."""
        return self._responses.get(plan_id)

    def cancel_plan(self, plan_id: str, reason: str = "") -> ACROSSResponse:
        """Cancel an active flight plan."""
        response = ACROSSResponse(
            plan_id=plan_id,
            status=ApprovalStatus.CANCELLED,
            approval_time_utc=datetime.now(UTC),
            message=f"Cancelled by operator. Reason: {reason}" if reason else "Cancelled.",
        )
        self._responses[plan_id] = response
        if plan_id in self._plans:
            del self._plans[plan_id]
        return response

    def list_active_plans(self) -> list[UAMFlightPlan]:
        """Return all plans that are currently stored (approved or pending)."""
        return list(self._plans.values())

    # ── OCC integration helper ─────────────────────────────────────────────────

    def suggest_uam_alternative(
        self,
        delayed_flight_number: str,
        delayed_pax: int,
        origin_vertiport_id: str,
        dest_vertiport_id: str,
        etd_utc: datetime,
        vehicle_id: str = "KE-AAM-001",
    ) -> tuple[UAMFlightPlan, ACROSSResponse] | None:
        """Suggest a UAM alternative for passengers stranded by a delayed flight.

        Creates a tentative UAM flight plan and submits it to ACROSS.
        Returns (plan, response) or None if no UAM connection exists.

        This is called by the OCC agent when a cascade delay affects
        time-critical passengers (e.g., last connection of the day).
        """
        from datetime import timedelta

        from argos.uav.models import FlightRules, GeoPoint, Waypoint4D
        from argos.uav.network import (
            VERTIPORTS,
            build_uam_network,
            find_route,
        )

        G = build_uam_network()
        path = find_route(G, origin_vertiport_id, dest_vertiport_id)
        if not path or len(path) < 2:
            return None

        # Build a simple two-waypoint trajectory (direct, no intermediate stops)
        origin_vp = VERTIPORTS.get(origin_vertiport_id)
        dest_vp = VERTIPORTS.get(dest_vertiport_id)
        if not origin_vp or not dest_vp:
            return None

        # Rough ETA: assume 120 knot cruise, 80% efficiency
        dist_nm = origin_vp.position.distance_nm(dest_vp.position)
        flight_min = (dist_nm / (120 * 0.8)) * 60
        eta_utc = etd_utc + timedelta(minutes=flight_min)

        cruise_alt = 800.0  # standard UAM cruise inside metro corridor
        plan = UAMFlightPlan(
            plan_id=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            vehicle_id=vehicle_id,
            origin_id=origin_vertiport_id,
            dest_id=dest_vertiport_id,
            flight_rules=FlightRules.VFRC,
            etd_utc=etd_utc,
            eta_utc=eta_utc,
            cruise_alt_ft=cruise_alt,
            trajectory=[
                Waypoint4D(
                    point=GeoPoint(origin_vp.position.lat, origin_vp.position.lon, cruise_alt),
                    eta_utc=etd_utc,
                ),
                Waypoint4D(
                    point=GeoPoint(dest_vp.position.lat, dest_vp.position.lon, cruise_alt),
                    eta_utc=eta_utc,
                ),
            ],
            pax_count=min(delayed_pax, 4),  # eVTOL capacity cap
            operator="KE-AAM",
        )
        response = self.submit_plan(plan)
        return plan, response
