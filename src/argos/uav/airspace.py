"""
ICN-hub airspace model and UAM/conventional-aircraft conflict detection.

ICN (RKSI) controlled airspace structure:
  - CTR (Control Zone): Class D, surface to 2000 ft, 5 NM radius
  - TMA (Terminal Manoeuvring Area): Class C, 2000–9500 ft, 30 NM
  - ILS corridors: Runway 15L/33R, 16R/34L — protected glide-path volumes
  - UAM altitude band: ≤ 1000 ft AGL in Seoul metro area

Separation standards (ACROSS guidelines, MOLIT 2024):
  - UAM ↔ UAM horizontal: 0.3 NM (minimum)
  - UAM ↔ conventional horizontal: 1.0 NM + vertical 500 ft
  - UAM ↔ ILS approach: must not enter 2 NM final approach corridor below 1500 ft
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from argos.uav.models import (
    ConflictDetail,
    ConflictType,
    GeoPoint,
    UAMFlightPlan,
    Waypoint4D,
)

# ── ICN airspace constants ────────────────────────────────────────────────────

ICN_CENTRE = GeoPoint(lat=37.4691, lon=126.4505)  # ARP (Aerodrome Reference Point)

ICN_CTR_RADIUS_NM   = 5.0
ICN_TMA_RADIUS_NM   = 30.0
ICN_CTR_CEILING_FT  = 2000.0
UAM_MAX_ALT_ICN_FT  = 1000.0   # UAM altitude cap inside CTR

# ILS critical areas — simplified as rectangular corridors
# Each entry: (runway_name, threshold_point, heading_deg, length_nm, width_nm)
_ILS_CORRIDORS = [
    ("15L", GeoPoint(37.4820, 126.4250), 150, 8.0, 1.0),
    ("33R", GeoPoint(37.4380, 126.4700), 330, 8.0, 1.0),
    ("16R", GeoPoint(37.4700, 126.4650), 160, 8.0, 1.0),
    ("34L", GeoPoint(37.4500, 126.4200), 340, 8.0, 1.0),
]

# Separation standards (nm)
SEP_UAM_UAM_NM         = 0.3
SEP_UAM_CONV_NM        = 1.0
SEP_UAM_CONV_VERT_FT   = 500.0
SEP_ILS_FINAL_NM       = 2.0     # keep-out from ILS final
SEP_ILS_BELOW_FT       = 1500.0  # altitude below which ILS sep applies

# Noise curfew (KST)
CURFEW_START_KST = 23
CURFEW_END_KST   = 6
KST_OFFSET_H     = 9


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _point_in_circle(
    point: GeoPoint, centre: GeoPoint, radius_nm: float
) -> bool:
    return point.distance_nm(centre) <= radius_nm


def _lateral_separation_nm(a: GeoPoint, b: GeoPoint) -> float:
    return a.distance_nm(b)


def _vertical_separation_ft(a: GeoPoint, b: GeoPoint) -> float:
    return abs(a.alt_ft - b.alt_ft)


# ── Conflict detectors ────────────────────────────────────────────────────────

def check_ctr_altitude(
    plan: UAMFlightPlan,
) -> list[ConflictDetail]:
    """Check that no waypoint inside ICN CTR exceeds UAM altitude cap."""
    conflicts: list[ConflictDetail] = []
    for wp in plan.trajectory:
        if _point_in_circle(wp.point, ICN_CENTRE, ICN_CTR_RADIUS_NM):
            if wp.point.alt_ft > UAM_MAX_ALT_ICN_FT:
                conflicts.append(ConflictDetail(
                    conflict_type=ConflictType.AIRSPACE,
                    description=(
                        f"Waypoint at {wp.point.lat:.4f}/{wp.point.lon:.4f} "
                        f"is {wp.point.alt_ft:.0f} ft inside ICN CTR "
                        f"(max {UAM_MAX_ALT_ICN_FT:.0f} ft)"
                    ),
                    conflicting_entity="ICN-CTR",
                    time_window_start=wp.eta_utc,
                    time_window_end=wp.eta_utc + timedelta(seconds=30),
                ))
    return conflicts


def check_ils_corridor(
    plan: UAMFlightPlan,
) -> list[ConflictDetail]:
    """Check that the UAM plan does not penetrate any active ILS corridor."""
    conflicts: list[ConflictDetail] = []
    for rwy_name, threshold, hdg, length_nm, width_nm in _ILS_CORRIDORS:
        for wp in plan.trajectory:
            if wp.point.alt_ft >= SEP_ILS_BELOW_FT:
                continue  # above ILS protection height — no conflict
            # Simplified: check proximity to threshold along approach path
            dist_to_threshold = wp.point.distance_nm(threshold)
            if dist_to_threshold <= length_nm:
                # Check lateral offset (crude: use distance from threshold ± width)
                conflicts.append(ConflictDetail(
                    conflict_type=ConflictType.RUNWAY_CORR,
                    description=(
                        f"Waypoint {dist_to_threshold:.1f} NM from runway {rwy_name} "
                        f"threshold at {wp.point.alt_ft:.0f} ft "
                        f"(ILS protection active below {SEP_ILS_BELOW_FT:.0f} ft)"
                    ),
                    conflicting_entity=f"ILS-{rwy_name}",
                    time_window_start=wp.eta_utc,
                    time_window_end=wp.eta_utc + timedelta(minutes=2),
                ))
    return conflicts


def check_curfew(
    plan: UAMFlightPlan,
) -> list[ConflictDetail]:
    """Check noise curfew compliance (23:00–06:00 KST)."""
    conflicts: list[ConflictDetail] = []
    for wp in plan.trajectory:
        kst_hour = (wp.eta_utc.hour + KST_OFFSET_H) % 24
        if kst_hour >= CURFEW_START_KST or kst_hour < CURFEW_END_KST:
            conflicts.append(ConflictDetail(
                conflict_type=ConflictType.CURFEW,
                description=(
                    f"Operation at {kst_hour:02d}:xx KST violates noise curfew "
                    f"({CURFEW_START_KST:02d}:00-{CURFEW_END_KST:02d}:00 KST)"
                ),
                conflicting_entity="NOISE-CURFEW",
                time_window_start=wp.eta_utc,
                time_window_end=wp.eta_utc + timedelta(minutes=1),
            ))
            break  # one curfew violation is enough — don't spam
    return conflicts


def check_uam_separation(
    plan: UAMFlightPlan,
    active_plans: list[UAMFlightPlan],
    time_tolerance_sec: int = 60,
) -> list[ConflictDetail]:
    """Check horizontal separation against other active UAM flight plans.

    Two UAM flights conflict if at any time step they are within
    SEP_UAM_UAM_NM of each other laterally.
    """
    conflicts: list[ConflictDetail] = []
    plan_wps = plan.trajectory

    for other in active_plans:
        if other.plan_id == plan.plan_id:
            continue
        for wp_a in plan_wps:
            for wp_b in other.trajectory:
                dt = abs((wp_a.eta_utc - wp_b.eta_utc).total_seconds())
                if dt > time_tolerance_sec:
                    continue  # not co-temporal
                sep = _lateral_separation_nm(wp_a.point, wp_b.point)
                if sep < SEP_UAM_UAM_NM:
                    conflicts.append(ConflictDetail(
                        conflict_type=ConflictType.SEPARATION,
                        description=(
                            f"UAM separation {sep:.2f} NM < required {SEP_UAM_UAM_NM} NM "
                            f"with flight {other.plan_id}"
                        ),
                        conflicting_entity=other.plan_id,
                        time_window_start=wp_a.eta_utc,
                        time_window_end=wp_a.eta_utc + timedelta(seconds=time_tolerance_sec),
                        separation_required_nm=SEP_UAM_UAM_NM,
                        separation_actual_nm=sep,
                    ))
    return conflicts


# ── Full conflict assessment ──────────────────────────────────────────────────

def assess_conflicts(
    plan: UAMFlightPlan,
    active_plans: list[UAMFlightPlan] | None = None,
) -> list[ConflictDetail]:
    """Run all conflict checks for a UAM flight plan.

    Returns list of ConflictDetail objects. Empty list = no conflicts.
    """
    conflicts: list[ConflictDetail] = []
    conflicts.extend(check_ctr_altitude(plan))
    conflicts.extend(check_ils_corridor(plan))
    conflicts.extend(check_curfew(plan))
    if active_plans:
        conflicts.extend(check_uam_separation(plan, active_plans))
    return conflicts
