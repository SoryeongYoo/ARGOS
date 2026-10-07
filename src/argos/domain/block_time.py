"""
Block time calculation model.

Block Time = Taxi-out + Airborne time + Taxi-in
Airborne time uses simplified performance model with wind component.
Cost Index adjusts cruise speed (and thus airborne time).
"""

from dataclasses import dataclass

# ICN taxi-out is long due to remote stands and runway distance
_ICN_TAXI_OUT_MIN = 22
_DEFAULT_TAXI_IN_MIN = 15


@dataclass(frozen=True)
class AircraftPerformance:
    aircraft_type: str
    cruise_tas_knots: float  # True airspeed at typical cruise altitude
    ci_ref: int  # Reference CI for TAS above
    ci_sensitivity: float  # knots per CI unit change
    climb_descent_distance_nm: float  # Total climb + descent distance
    climb_descent_time_min: float  # Time for climb + descent phase
    taxi_out_min: int = _ICN_TAXI_OUT_MIN
    taxi_in_min: int = _DEFAULT_TAXI_IN_MIN


_PERFORMANCE: dict[str, AircraftPerformance] = {
    "B737-800": AircraftPerformance(
        "B737-800",
        cruise_tas_knots=447,
        ci_ref=35,
        ci_sensitivity=0.18,
        climb_descent_distance_nm=300,
        climb_descent_time_min=42,
    ),
    "A321neo": AircraftPerformance(
        "A321neo",
        cruise_tas_knots=450,
        ci_ref=40,
        ci_sensitivity=0.16,
        climb_descent_distance_nm=280,
        climb_descent_time_min=40,
    ),
    "B777-300ER": AircraftPerformance(
        "B777-300ER",
        cruise_tas_knots=490,
        ci_ref=80,
        ci_sensitivity=0.25,
        climb_descent_distance_nm=380,
        climb_descent_time_min=52,
    ),
    "B787-9": AircraftPerformance(
        "B787-9",
        cruise_tas_knots=487,
        ci_ref=75,
        ci_sensitivity=0.22,
        climb_descent_distance_nm=360,
        climb_descent_time_min=50,
    ),
    "B747-8i": AircraftPerformance(
        "B747-8i",
        cruise_tas_knots=493,
        ci_ref=85,
        ci_sensitivity=0.28,
        climb_descent_distance_nm=400,
        climb_descent_time_min=55,
    ),
}


def calculate_block_time(
    distance_nm: float,
    aircraft_type: str,
    ci: int = 70,
    wind_component_knots: float = 0.0,  # positive = headwind
) -> int:
    """Return scheduled block time in minutes.

    Args:
        distance_nm: Great-circle route distance.
        aircraft_type: Must be a key in _PERFORMANCE.
        ci: Cost Index (0 = max fuel saving, 999 = max speed).
        wind_component_knots: Net wind on track; positive is a headwind.
    """
    if aircraft_type not in _PERFORMANCE:
        raise ValueError(f"Unknown aircraft type: {aircraft_type}. Known: {list(_PERFORMANCE)}")

    perf = _PERFORMANCE[aircraft_type]
    ci_delta = ci - perf.ci_ref
    adjusted_tas = perf.cruise_tas_knots + ci_delta * perf.ci_sensitivity
    effective_gs = max(adjusted_tas - wind_component_knots, 200.0)  # floor GS at 200kt

    cruise_dist = max(0.0, distance_nm - perf.climb_descent_distance_nm)
    cruise_time_min = (cruise_dist / effective_gs) * 60.0

    return round(
        perf.climb_descent_time_min + cruise_time_min + perf.taxi_out_min + perf.taxi_in_min
    )


def estimate_airborne_time(distance_nm: float, aircraft_type: str, ci: int = 70) -> int:
    """Airborne time only (excludes taxi). Useful for FDP / duty time calculations."""
    total = calculate_block_time(distance_nm, aircraft_type, ci)
    perf = _PERFORMANCE.get(aircraft_type)
    if perf is None:
        return total - 35
    return total - perf.taxi_out_min - perf.taxi_in_min


def available_aircraft_types() -> list[str]:
    return list(_PERFORMANCE.keys())
