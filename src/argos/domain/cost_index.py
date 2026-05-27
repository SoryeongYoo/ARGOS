"""
Cost Index (CI) optimization model.

CI = DOC_time / DOC_fuel  [kg/min]
  CI=0   → maximum range cruise (minimum fuel)
  CI=999 → maximum speed cruise (minimum time)

Korean Air published CI reference values by route type:
  Short-haul (<3h): CI 30-50
  Medium-haul (3-8h): CI 60-90
  Long-haul (>8h): CI 70-100
"""


def ci_to_mach(ci: int, aircraft_type: str, altitude_fl: int = 350) -> float:
    """Approximate cruise Mach number for a given CI.

    Uses a linear interpolation between MMO (maximum operating Mach)
    and MRC (maximum range cruise Mach).
    """
    profiles = {
        #              MRC,   MMO,  ci_scale
        "B737-800":  (0.785, 0.820, 200),
        "A321neo":   (0.780, 0.820, 200),
        "B777-300ER":(0.830, 0.890, 300),
        "B787-9":    (0.845, 0.900, 300),
        "B747-8i":   (0.845, 0.900, 300),
    }
    mrc, mmo, scale = profiles.get(aircraft_type, (0.800, 0.860, 250))
    fraction = min(ci / scale, 1.0)
    return round(mrc + fraction * (mmo - mrc), 4)


def fuel_penalty_kg(
    ci: int,
    block_time_minutes: float,
    aircraft_type: str,
    reference_ci: int = 70,
) -> float:
    """Extra fuel burned vs reference CI.

    Positive = more fuel than reference (higher CI = faster = more fuel).
    Negative = fuel saving (lower CI = slower = less fuel).
    """
    fuel_rates = {
        # kg/minute burn at reference CI, and kg burned per CI unit above reference
        "B737-800":   (55.0,  0.05),
        "A321neo":    (52.0,  0.04),
        "B777-300ER": (185.0, 0.30),
        "B787-9":     (145.0, 0.22),
        "B747-8i":    (245.0, 0.40),
    }
    base_rate, ci_fuel_rate = fuel_rates.get(aircraft_type, (100.0, 0.15))
    delta_ci = ci - reference_ci
    return delta_ci * ci_fuel_rate * block_time_minutes


def time_saving_minutes(
    ci: int,
    distance_nm: float,
    aircraft_type: str,
    reference_ci: int = 70,
) -> float:
    """Minutes saved vs reference CI due to higher speed.

    Positive = time saved (higher CI = faster). Negative = slower.
    """
    from argos.domain.block_time import calculate_block_time
    ref_block = calculate_block_time(distance_nm, aircraft_type, ci=reference_ci)
    new_block = calculate_block_time(distance_nm, aircraft_type, ci=ci)
    return ref_block - new_block


def optimal_ci(
    distance_nm: float,
    aircraft_type: str,
    fuel_price_usd_per_kg: float = 0.80,
    crew_cost_usd_per_hour: float = 1200.0,
    other_time_cost_usd_per_hour: float = 300.0,
) -> int:
    """Find CI that minimises total direct operating cost for a flight.

    Uses a grid search over CI 0-999 with 10-unit step.
    """
    from argos.domain.block_time import calculate_block_time

    total_time_cost_per_min = (crew_cost_usd_per_hour + other_time_cost_usd_per_hour) / 60.0
    best_ci, best_cost = 0, float("inf")

    for ci in range(0, 1000, 10):
        block = calculate_block_time(distance_nm, aircraft_type, ci=ci)
        extra_fuel = fuel_penalty_kg(ci, block, aircraft_type)
        base_fuel = block * {"B737-800": 55, "A321neo": 52, "B777-300ER": 185, "B787-9": 145, "B747-8i": 245}.get(aircraft_type, 100)
        total_fuel = base_fuel + extra_fuel
        cost = total_fuel * fuel_price_usd_per_kg + block * total_time_cost_per_min
        if cost < best_cost:
            best_cost = cost
            best_ci = ci

    return best_ci
