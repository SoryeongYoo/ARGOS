"""
FAR Part 117 (14 CFR Part 117) flight/duty time limitations.
Applies to Part 121 scheduled operations — Korean Air uses equivalent MOLIT (국토교통부)
regulations which mirror FAR 117 for international routes.

Key concepts:
- FDP  : Flight Duty Period — from report time until end of last flight block
- WOCL : Window of Circadian Low (0200-0559 local at crew base)
- FT   : Flight Time (airborne time only)
"""

from datetime import datetime

# ── Appendix B table: max FDP hours (unaugmented crew) ───────────────────────
# Rows = report hour (local, 0-23), Cols = number of flight segments (1-6).
# Hours exceed this → FDP violation.

_APPENDIX_B: dict[int, list[float]] = {
    #  hr   1seg  2seg  3seg  4seg  5seg  6seg
    0: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    1: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    2: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    3: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    4: [10.0, 10.0, 10.0, 10.0, 9.0, 9.0],
    5: [12.0, 12.0, 12.0, 12.0, 11.5, 11.0],
    6: [13.0, 13.0, 12.0, 12.0, 11.5, 11.0],
    7: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    8: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    9: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    10: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    11: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    12: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    13: [13.0, 13.0, 12.0, 12.0, 11.5, 11.0],
    14: [13.0, 13.0, 12.0, 12.0, 11.5, 11.0],
    15: [13.0, 12.5, 12.0, 12.0, 11.5, 11.0],
    16: [12.5, 12.0, 11.5, 11.5, 11.0, 10.0],
    17: [12.5, 12.0, 11.5, 11.5, 11.0, 10.0],
    18: [12.0, 12.0, 11.5, 11.5, 11.0, 10.0],
    19: [12.0, 12.0, 11.5, 11.5, 11.0, 10.0],
    20: [11.5, 11.5, 11.0, 11.0, 10.5, 10.0],
    21: [11.0, 11.0, 10.5, 10.5, 10.0, 9.5],
    22: [10.5, 10.5, 10.0, 10.0, 9.5, 9.0],
    23: [10.0, 10.0, 10.0, 9.5, 9.0, 9.0],
}

# Minimum rest between FDPs
_MIN_REST_HOURS = 10.0  # standard
_MIN_REST_REDUCED = 8.0  # reduced (requires compensatory rest)
_MIN_REST_AUGMENTED = 8.0  # augmented crew (≥3 pilots)

# Cumulative flight time limits
MAX_FT_CALENDAR_DAY_HOURS = 8.0
MAX_FT_28_DAY_HOURS = 100.0
MAX_FT_YEAR_HOURS = 1000.0
MAX_FDP_EXTENSION = 2.0  # max unforeseen extension to FDP (hours)

LONG_HAUL_MIN_CREW = 3  # ≥3 pilots required when FDP > 12h


def max_fdp_hours(report_hour_local: int, num_segments: int, augmented: bool = False) -> float:
    """Return maximum allowed FDP in hours.

    Args:
        report_hour_local: Hour (0-23) crew reports at origin, in crew base local time.
        num_segments: Number of flight legs in the FDP.
        augmented: True if ≥3 pilots (enables 2-hour extension allowance).

    Raises:
        ValueError: If num_segments < 1 (an FDP has at least one flight leg).
    """
    if num_segments < 1:
        raise ValueError(f"num_segments must be >= 1, got {num_segments}")
    hour = report_hour_local % 24
    seg_idx = min(num_segments, 6) - 1  # clamp to table max of 6
    base_hours = _APPENDIX_B[hour][seg_idx]
    if augmented:
        # Augmented crew with bunk rest can extend up to 2h (FAR 117.19)
        return base_hours + MAX_FDP_EXTENSION
    return base_hours


def is_fdp_legal(
    report_dt_local: datetime,
    actual_fdp_hours: float,
    num_segments: int,
    augmented: bool = False,
) -> tuple[bool, float]:
    """Check whether an FDP is within FAR 117 limits.

    Returns:
        (legal, max_allowed_hours)
    """
    limit = max_fdp_hours(report_dt_local.hour, num_segments, augmented)
    return actual_fdp_hours <= limit, limit


def required_rest_hours(prior_fdp_hours: float, augmented: bool = False) -> float:
    """Minimum rest required after an FDP (FAR 117.25)."""
    if augmented:
        return _MIN_REST_AUGMENTED
    if prior_fdp_hours > 12.0:
        # Extended FDP → longer rest
        return max(_MIN_REST_HOURS, prior_fdp_hours * 0.9)
    return _MIN_REST_HOURS


def is_in_wocl(dt_local: datetime) -> bool:
    """Return True if the datetime falls in the Window of Circadian Low (0200-0559 local)."""
    h = dt_local.hour
    return 2 <= h < 6


def check_cumulative_limits(
    flight_times_28days: list[float],
    flight_times_year: list[float],
) -> dict[str, bool | float]:
    """Check cumulative limits given lists of actual flight hours.

    Args:
        flight_times_28days: Flight hours for each of the last 28 calendar days.
        flight_times_year:   Flight hours for each of the last 365 calendar days.
    """
    total_28 = sum(flight_times_28days)
    total_year = sum(flight_times_year)
    return {
        "28_day_total": total_28,
        "28_day_limit": MAX_FT_28_DAY_HOURS,
        "28_day_legal": total_28 <= MAX_FT_28_DAY_HOURS,
        "year_total": total_year,
        "year_limit": MAX_FT_YEAR_HOURS,
        "year_legal": total_year <= MAX_FT_YEAR_HOURS,
    }


def augmented_required(fdp_hours: float, num_segments: int) -> bool:
    """Return True if a third pilot is required by FAR 117.19."""
    single_limit = max_fdp_hours(8, num_segments, augmented=False)  # daytime reference
    return fdp_hours > single_limit
