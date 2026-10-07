"""
Synthetic flight data generator — pure Python, no API calls.

Architecture:
  Phase 1 – Rule-based parameters per route (delay distributions, seasonal
             factors, weather sensitivity) using domain-encoded heuristics + NumPy.
  Phase 2 – NumPy generates actual flight records from those distributions at scale.
  Phase 3 – DuckDB stores the result.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from faker import Faker
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from argos.config import Settings
from argos.data_gen.routes import ROUTES, RouteDefinition
from argos.data_gen.schemas import (
    ALL_DDL,
    IATA_DELAY_CODES,
    RouteParams,
)

log = logging.getLogger(__name__)
console = Console()

# ── Fleet definition ──────────────────────────────────────────────────────────

FLEET: list[dict] = [
    # B737-800 (HL74xx series) — 20 frames
    *[
        {
            "registration": f"HL74{i:02d}",
            "aircraft_type": "B737-800",
            "icao_type": "B738",
            "manufacturer_serial": f"3{40000 + i}",
            "delivery_date": date(2010 + i // 4, (i % 4) * 3 + 1, 15),
            "seat_config_y": 147,
            "seat_config_c": 8,
            "seat_config_f": 0,
            "max_payload_kg": 20_000,
            "mtow_kg": 79_016,
        }
        for i in range(1, 21)
    ],
    # A321neo (HL82xx series) — 10 frames
    *[
        {
            "registration": f"HL82{i:02d}",
            "aircraft_type": "A321neo",
            "icao_type": "A321",
            "manufacturer_serial": f"1{10000 + i}",
            "delivery_date": date(2019 + i // 5, (i % 5) * 2 + 1, 20),
            "seat_config_y": 174,
            "seat_config_c": 12,
            "seat_config_f": 0,
            "max_payload_kg": 22_000,
            "mtow_kg": 97_000,
        }
        for i in range(1, 11)
    ],
    # B777-300ER (HL77xx series) — 15 frames
    *[
        {
            "registration": f"HL77{i:02d}",
            "aircraft_type": "B777-300ER",
            "icao_type": "B77W",
            "manufacturer_serial": f"4{30000 + i}",
            "delivery_date": date(2005 + i // 2, (i % 6) * 2 + 1, 10),
            "seat_config_y": 261,
            "seat_config_c": 56,
            "seat_config_f": 8,
            "max_payload_kg": 66_000,
            "mtow_kg": 352_400,
        }
        for i in range(1, 16)
    ],
    # B787-9 (HL80xx series) — 8 frames
    *[
        {
            "registration": f"HL80{i:02d}",
            "aircraft_type": "B787-9",
            "icao_type": "B789",
            "manufacturer_serial": f"6{20000 + i}",
            "delivery_date": date(2016 + i // 3, (i % 4) + 1, 5),
            "seat_config_y": 216,
            "seat_config_c": 42,
            "seat_config_f": 0,
            "max_payload_kg": 53_000,
            "mtow_kg": 254_011,
        }
        for i in range(1, 9)
    ],
    # B747-8i (HL75xx series) — 5 frames (flagship)
    *[
        {
            "registration": f"HL75{i:02d}",
            "aircraft_type": "B747-8i",
            "icao_type": "B748",
            "manufacturer_serial": f"5{10000 + i}",
            "delivery_date": date(2014 + i, 3, 20),
            "seat_config_y": 314,
            "seat_config_c": 48,
            "seat_config_f": 6,
            "max_payload_kg": 81_000,
            "mtow_kg": 447_696,
        }
        for i in range(1, 6)
    ],
]

FLEET_BY_TYPE: dict[str, list[dict]] = {}
for ac in FLEET:
    FLEET_BY_TYPE.setdefault(ac["aircraft_type"], []).append(ac)


# ── Regional delay profiles (domain knowledge, no API needed) ─────────────────
# Based on IATA industry data, Korean Air OTP statistics, and regional ATC patterns.

_REGION_PROFILES: dict[str, dict] = {
    # Japan: moderate ATC delays at NRT/HND (71-73), winter snow at CTS (63)
    "Japan": {
        "delay_prob": 0.22,
        "base_delay": 20.0,
        "dist": "lognormal",
        "param_a": 0.75,
        "param_b": 1.0,
        "wx_sens": 1.4,
        "cancel": 0.004,
        "seasonal": {"winter": 1.4, "spring": 0.9, "summer": 1.0, "autumn": 0.95},
        "codes": ["71", "93", "63", "31", "91"],
    },
    # China: highest ATC restriction rate globally (74), esp. PEK/PVG/CAN
    "China": {
        "delay_prob": 0.32,
        "base_delay": 30.0,
        "dist": "lognormal",
        "param_a": 0.90,
        "param_b": 1.0,
        "wx_sens": 1.3,
        "cancel": 0.007,
        "seasonal": {"winter": 1.2, "spring": 1.1, "summer": 1.2, "autumn": 0.9},
        "codes": ["74", "93", "71", "31", "91"],
    },
    # SE Asia: monsoon sensitivity, typhoon season Jul-Sep
    "SE Asia": {
        "delay_prob": 0.25,
        "base_delay": 25.0,
        "dist": "weibull",
        "param_a": 1.20,
        "param_b": 1.0,
        "wx_sens": 2.0,
        "cancel": 0.005,
        "seasonal": {"winter": 0.8, "spring": 1.0, "summer": 1.8, "autumn": 1.1},
        "codes": ["61", "64", "93", "71", "31"],
    },
    # North America: long-haul reactionary delays dominate
    "North America": {
        "delay_prob": 0.18,
        "base_delay": 40.0,
        "dist": "lognormal",
        "param_a": 0.80,
        "param_b": 1.0,
        "wx_sens": 1.3,
        "cancel": 0.004,
        "seasonal": {"winter": 1.3, "spring": 0.9, "summer": 1.0, "autumn": 0.95},
        "codes": ["91", "93", "94", "31", "71"],
    },
    # Europe: peak-hour ATC congestion, reactionary delays
    "Europe": {
        "delay_prob": 0.20,
        "base_delay": 35.0,
        "dist": "lognormal",
        "param_a": 0.85,
        "param_b": 1.0,
        "wx_sens": 1.4,
        "cancel": 0.003,
        "seasonal": {"winter": 1.3, "spring": 0.9, "summer": 1.1, "autumn": 0.9},
        "codes": ["91", "71", "93", "31", "94"],
    },
    "Middle East": {
        "delay_prob": 0.18,
        "base_delay": 25.0,
        "dist": "exponential",
        "param_a": 1.00,
        "param_b": 1.0,
        "wx_sens": 1.2,
        "cancel": 0.003,
        "seasonal": {"winter": 0.9, "spring": 1.0, "summer": 1.1, "autumn": 1.0},
        "codes": ["91", "71", "93", "31"],
    },
    "Oceania": {
        "delay_prob": 0.15,
        "base_delay": 40.0,
        "dist": "lognormal",
        "param_a": 0.70,
        "param_b": 1.0,
        "wx_sens": 1.3,
        "cancel": 0.003,
        "seasonal": {"winter": 0.9, "spring": 1.0, "summer": 1.0, "autumn": 1.1},
        "codes": ["91", "93", "31", "71"],
    },
    # Russia: severe winter (code 63), long-haul reactionary
    "Russia": {
        "delay_prob": 0.20,
        "base_delay": 30.0,
        "dist": "lognormal",
        "param_a": 0.80,
        "param_b": 1.0,
        "wx_sens": 1.6,
        "cancel": 0.006,
        "seasonal": {"winter": 1.5, "spring": 0.9, "summer": 0.8, "autumn": 1.0},
        "codes": ["63", "91", "71", "31"],
    },
    "CIS": {
        "delay_prob": 0.22,
        "base_delay": 30.0,
        "dist": "lognormal",
        "param_a": 0.80,
        "param_b": 1.0,
        "wx_sens": 1.5,
        "cancel": 0.006,
        "seasonal": {"winter": 1.4, "spring": 0.9, "summer": 0.9, "autumn": 1.0},
        "codes": ["63", "71", "91", "31"],
    },
    # South Asia: monsoon season (61), summer spikes
    "South Asia": {
        "delay_prob": 0.22,
        "base_delay": 25.0,
        "dist": "weibull",
        "param_a": 1.10,
        "param_b": 1.0,
        "wx_sens": 1.5,
        "cancel": 0.005,
        "seasonal": {"winter": 0.9, "spring": 1.0, "summer": 1.6, "autumn": 1.0},
        "codes": ["61", "71", "93", "31"],
    },
    "Africa": {
        "delay_prob": 0.25,
        "base_delay": 45.0,
        "dist": "lognormal",
        "param_a": 0.90,
        "param_b": 1.0,
        "wx_sens": 1.3,
        "cancel": 0.008,
        "seasonal": {"winter": 1.0, "spring": 1.0, "summer": 0.9, "autumn": 1.0},
        "codes": ["91", "71", "31", "93"],
    },
    "Mongolia": {
        "delay_prob": 0.20,
        "base_delay": 20.0,
        "dist": "lognormal",
        "param_a": 0.70,
        "param_b": 1.0,
        "wx_sens": 1.5,
        "cancel": 0.006,
        "seasonal": {"winter": 1.5, "spring": 1.0, "summer": 0.8, "autumn": 0.9},
        "codes": ["63", "71", "31", "91"],
    },
}

_DEFAULT_PROFILE: dict = {
    "delay_prob": 0.22,
    "base_delay": 25.0,
    "dist": "lognormal",
    "param_a": 0.80,
    "param_b": 1.0,
    "wx_sens": 1.5,
    "cancel": 0.005,
    "seasonal": {"winter": 1.3, "spring": 0.9, "summer": 1.1, "autumn": 0.95},
    "codes": ["91", "63", "71", "31", "93"],
}

# ── Weather event calendar ─────────────────────────────────────────────────────
# (airport, event_type, active_months, avg_events_per_month, severity_range)

_WEATHER_CALENDAR: list[tuple[str, str, list[int], float, tuple[int, int]]] = [
    ("ICN", "SNOW", [12, 1, 2], 3.0, (1, 4)),
    ("ICN", "FOG", [11, 12, 1, 2, 3], 4.0, (1, 3)),
    ("ICN", "TYPHOON", [7, 8, 9], 0.5, (2, 5)),
    ("ICN", "THUNDERSTORM", [5, 6, 7, 8, 9], 5.0, (1, 3)),
    ("NRT", "SNOW", [12, 1, 2], 2.0, (1, 3)),
    ("NRT", "THUNDERSTORM", [7, 8], 3.0, (1, 3)),
    ("PEK", "FOG", [10, 11, 12, 1, 2, 3], 5.0, (2, 4)),
    ("PVG", "THUNDERSTORM", [5, 6, 7, 8, 9], 4.0, (1, 3)),
    ("HKG", "TYPHOON", [6, 7, 8, 9, 10], 0.7, (2, 5)),
    ("SIN", "THUNDERSTORM", [3, 4, 5, 9, 10, 11, 12], 8.0, (1, 2)),
    ("CDG", "FOG", [10, 11, 12, 1, 2], 3.0, (1, 2)),
    ("LHR", "FOG", [10, 11, 12, 1], 4.0, (1, 2)),
]

_WEATHER_TEMPLATES: dict[str, list[str]] = {
    "TYPHOON": [
        "Tropical cyclone warning. All ground operations suspended pending clearance.",
        "Typhoon landfall risk. Passenger terminal on standby evacuation protocol.",
        "Severe typhoon conditions. Extended ground stop in effect.",
        "Typhoon advisory. Fuel depot closed. Departure slots cancelled.",
    ],
    "FOG": [
        "Dense radiation fog. CAT III ILS approaches only. Ground movement restricted.",
        "Low visibility procedures active. Arrival rate reduced to 60% capacity.",
        "Advection fog bank. Taxi delays expected. RVR below 400m.",
        "Freezing fog. De-icing standby units activated. Visibility deteriorating.",
    ],
    "SNOW": [
        "Heavy snowfall. Runway snow removal in progress. De-icing queue forming.",
        "Winter storm: blowing snow reducing RVR. Holding patterns activated.",
        "Freezing rain and snow mix. De-icing fluid Type IV applied.",
        "Snowfall rate 5cm/hr. Single runway ops. Ground stop for light aircraft.",
    ],
    "THUNDERSTORM": [
        "Severe convective activity. All ramp operations halted. Ground stop issued.",
        "Active CB cells on approach. 15-minute delay to all arriving traffic.",
        "Lightning within 5nm. Fuel depot closed. Ramp agents recalled to terminal.",
        "Embedded CB in cloud layer. Deviations required. SIGMET in effect.",
    ],
}


@dataclass
class GenerationResult:
    flights_count: int
    routes_count: int
    aircraft_count: int
    weather_events_count: int
    date_range: tuple[date, date]
    duckdb_path: Path


class SyntheticDataGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rng = np.random.default_rng(settings.random_seed)
        self._fake = Faker()
        self._fake.seed_instance(settings.random_seed)

    # ── Phase 1: Rule-based route parameters ─────────────────────────────────

    def generate_route_params(self, routes: list[RouteDefinition]) -> dict[str, RouteParams]:
        """Generate realistic delay parameters using rule-based domain profiles.

        Encodes ICN-hub aviation domain expertise without external API calls.
        Per-route variation is introduced via the seeded NumPy RNG (±12%).
        """
        results: dict[str, RouteParams] = {}

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            task = prog.add_task("Generating route parameters...", total=len(routes))
            for route in routes:
                results[route.route_id] = self._rule_based_params(route)
                prog.advance(task, 1)

        return results

    def _rule_based_params(self, route: RouteDefinition) -> RouteParams:
        profile = _REGION_PROFILES.get(route.region, _DEFAULT_PROFILE)
        is_long_haul = route.distance_nm > 3000
        noise = float(self.rng.uniform(0.88, 1.12))

        delay_prob = float(np.clip(profile["delay_prob"] * noise, 0.05, 0.50))
        base_delay = float(profile["base_delay"] * (1.3 if is_long_haul else 1.0) * noise)
        cancel_rate = float(np.clip(profile["cancel"] * noise, 0.001, 0.05))

        return RouteParams(
            route_id=route.route_id,
            base_delay_minutes=round(base_delay, 1),
            delay_probability=round(delay_prob, 3),
            delay_distribution=profile["dist"],
            dist_param_a=float(profile["param_a"] * self.rng.uniform(0.92, 1.08)),
            dist_param_b=float(profile["param_b"]),
            weather_sensitivity=float(profile["wx_sens"] * self.rng.uniform(0.92, 1.08)),
            seasonal_factors=profile["seasonal"],
            top_delay_codes=profile["codes"],
            cancellation_rate=round(cancel_rate, 4),
        )

    def _default_params(self, route: RouteDefinition) -> RouteParams:
        """Fallback used when rule-based generation is bypassed."""
        return self._rule_based_params(route)

    # ── Phase 2: NumPy generates flights ─────────────────────────────────────

    def generate_flights(
        self,
        routes: list[RouteDefinition],
        route_params: dict[str, RouteParams],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Generate full flight dataset algorithmically from rule-based params."""
        records: list[dict] = []
        date_range = pd.date_range(start_date, end_date, freq="D")

        # Korean Air typical departure schedule patterns (local KST = UTC+9)
        # Maps region → list of (dep_hour_local, proportion)
        dep_patterns: dict[str, list[tuple[int, float]]] = {
            "Japan": [(7, 0.25), (10, 0.25), (14, 0.25), (18, 0.25)],
            "China": [(8, 0.3), (12, 0.3), (17, 0.4)],
            "SE Asia": [(0, 0.4), (10, 0.3), (22, 0.3)],
            "North America": [(10, 0.5), (13, 0.5)],
            "Europe": [(11, 0.5), (22, 0.5)],
            "Middle East": [(8, 0.5), (23, 0.5)],
            "Oceania": [(19, 1.0)],
            "Russia": [(9, 0.5), (15, 0.5)],
            "CIS": [(10, 1.0)],
            "South Asia": [(9, 1.0)],
            "Africa": [(20, 1.0)],
            "Mongolia": [(9, 1.0)],
        }

        console.print(
            f"[cyan]Generating flights for {len(date_range)} days × {len(routes)} routes..."
        )

        for route in routes:
            params = route_params[route.route_id]
            pattern = dep_patterns.get(route.region, [(10, 1.0)])
            ac_type = route.aircraft_types[0]
            block_min = route.block_times.get(ac_type, 300)
            registrations = [a["registration"] for a in FLEET_BY_TYPE.get(ac_type, FLEET[:1])]

            for dep_date in date_range:
                # Sub-weekly routes (e.g. 4/7): skip days probabilistically
                if route.frequency_per_day < 1.0 and self.rng.random() > route.frequency_per_day:
                    continue

                for dep_hour, _proportion in pattern:
                    # scheduled times (UTC = KST - 9)
                    dep_min_offset = int(self.rng.integers(0, 60))
                    sch_dep = datetime(
                        dep_date.year,
                        dep_date.month,
                        dep_date.day,
                        (dep_hour - 9) % 24,
                        dep_min_offset,
                        tzinfo=timezone.utc,
                    )
                    sch_arr = sch_dep + timedelta(minutes=block_min)

                    # cancellation
                    if self.rng.random() < params.cancellation_rate:
                        records.append(
                            self._cancelled_flight(
                                route, sch_dep, sch_arr, ac_type, registrations, block_min
                            )
                        )
                        continue

                    # delay
                    season = self._season(dep_date.month)
                    eff_prob = params.delay_probability * params.seasonal_factors.get(season, 1.0)
                    delayed = self.rng.random() < eff_prob

                    dep_delay = 0
                    delay_code = None
                    if delayed:
                        dep_delay = max(0, int(self._sample_delay(params)))
                        if dep_delay > 0:
                            delay_code = str(self.rng.choice(params.top_delay_codes))

                    arr_delay = dep_delay  # simplified; propagation model handles cascading

                    reg = str(self.rng.choice(registrations))
                    lf = float(np.clip(self.rng.normal(0.82, 0.08), 0.40, 1.0))

                    records.append(
                        {
                            "flight_id": str(uuid.uuid4()),
                            "flight_number": self._flight_number(route),
                            "route_id": route.route_id,
                            "origin_iata": route.origin_iata,
                            "dest_iata": route.dest_iata,
                            "aircraft_registration": reg,
                            "aircraft_type": ac_type,
                            "scheduled_dep_utc": sch_dep,
                            "scheduled_arr_utc": sch_arr,
                            "actual_dep_utc": sch_dep + timedelta(minutes=dep_delay),
                            "actual_arr_utc": sch_arr + timedelta(minutes=arr_delay),
                            "block_time_minutes": block_min,
                            "distance_nm": route.distance_nm,
                            "dep_delay_minutes": dep_delay,
                            "arr_delay_minutes": arr_delay,
                            "delay_code": delay_code,
                            "delay_subcode": None,
                            "delay_responsibility": self._responsibility(delay_code),
                            "pax_boarded": self._pax(ac_type, lf),
                            "load_factor": round(lf, 3),
                            "fuel_uplift_kg": self._fuel(route.distance_nm, ac_type),
                            "cargo_kg": int(self.rng.integers(500, 8000)),
                            "status": "ARR",
                            "cancel_reason": None,
                        }
                    )

        df = pd.DataFrame(records)
        console.print(f"[green]Generated {len(df):,} flight records.")
        return df

    def _sample_delay(self, params: RouteParams) -> float:
        mu = np.log(params.base_delay_minutes)
        if params.delay_distribution == "lognormal":
            return self.rng.lognormal(mu, params.dist_param_a)
        if params.delay_distribution == "exponential":
            return self.rng.exponential(params.base_delay_minutes)
        # weibull
        return params.base_delay_minutes * self.rng.weibull(params.dist_param_a)

    @staticmethod
    def _season(month: int) -> str:
        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "spring"
        if month in (6, 7, 8):
            return "summer"
        return "autumn"

    @staticmethod
    def _responsibility(code: str | None) -> str | None:
        if code is None:
            return None
        c = int(code)
        if 60 <= c <= 69:
            return "W"
        if 70 <= c <= 79:
            return "ATC"
        if 80 <= c <= 89:
            return "AP"
        return "A"

    def _pax(self, ac_type: str, lf: float) -> int:
        caps = {
            "B737-800": 155,
            "A321neo": 186,
            "B777-300ER": 325,
            "B787-9": 258,
            "B747-8i": 368,
        }
        cap = caps.get(ac_type, 200)
        return int(cap * lf * self.rng.uniform(0.95, 1.0))

    def _fuel(self, distance_nm: int, ac_type: str) -> int:
        # rough kg/nm burn rates
        burn = {
            "B737-800": 6.5,
            "A321neo": 5.8,
            "B777-300ER": 18.0,
            "B787-9": 14.0,
            "B747-8i": 26.0,
        }
        rate = burn.get(ac_type, 10.0)
        return int(distance_nm * rate * self.rng.uniform(0.92, 1.08))

    _fn_counter: dict[str, int] = {}

    def _flight_number(self, route: RouteDefinition) -> str:
        key = route.route_id
        n = self._fn_counter.get(key, 0)
        self._fn_counter[key] = n + 1
        # Real KE flight numbers: Japan 700s, China 800s, Americas 001-099, Europe 900s, etc.
        base = {
            "Japan": 700,
            "China": 800,
            "SE Asia": 600,
            "North America": 1,
            "Europe": 900,
            "Middle East": 950,
            "Oceania": 120,
            "Russia": 920,
            "CIS": 880,
            "South Asia": 470,
            "Africa": 100,
            "Mongolia": 870,
        }.get(route.region, 500)
        num = (base + list(FLEET_BY_TYPE.keys()).index(route.aircraft_types[0]) * 2 + n % 2) % 9999
        return f"KE{num:04d}"

    def _cancelled_flight(
        self,
        route: RouteDefinition,
        sch_dep: datetime,
        sch_arr: datetime,
        ac_type: str,
        registrations: list[str],
        block_min: int,
    ) -> dict:
        reg = str(self.rng.choice(registrations))
        return {
            "flight_id": str(uuid.uuid4()),
            "flight_number": self._flight_number(route),
            "route_id": route.route_id,
            "origin_iata": route.origin_iata,
            "dest_iata": route.dest_iata,
            "aircraft_registration": reg,
            "aircraft_type": ac_type,
            "scheduled_dep_utc": sch_dep,
            "scheduled_arr_utc": sch_arr,
            "actual_dep_utc": None,
            "actual_arr_utc": None,
            "block_time_minutes": block_min,
            "distance_nm": route.distance_nm,
            "dep_delay_minutes": 0,
            "arr_delay_minutes": 0,
            "delay_code": None,
            "delay_subcode": None,
            "delay_responsibility": None,
            "pax_boarded": 0,
            "load_factor": 0.0,
            "fuel_uplift_kg": 0,
            "cargo_kg": 0,
            "status": "CNX",
            "cancel_reason": "Operational",
        }

    # ── Weather events (Faker + NumPy) ────────────────────────────────────────

    def generate_weather_events(self, start_date: date, end_date: date) -> pd.DataFrame:
        """Generate synthetic weather events using seasonal patterns and Faker descriptions."""
        records: list[dict] = []

        cur_year = start_date.year
        cur_month = start_date.month

        while True:
            cur_first = date(cur_year, cur_month, 1)
            if cur_first > end_date:
                break

            for airport, event_type, active_months, avg_per_month, sev_range in _WEATHER_CALENDAR:
                if cur_month not in active_months:
                    continue

                n_events = int(self.rng.poisson(avg_per_month))
                for _ in range(n_events):
                    day = int(self.rng.integers(1, 29))
                    try:
                        event_date = date(cur_year, cur_month, day)
                    except ValueError:
                        continue
                    if event_date < start_date or event_date > end_date:
                        continue

                    hour = int(self.rng.integers(0, 24))
                    duration_h = float(self.rng.uniform(1.0, 14.0))
                    start_dt = datetime(
                        event_date.year, event_date.month, event_date.day, hour, tzinfo=timezone.utc
                    )
                    end_dt = start_dt + timedelta(hours=duration_h)
                    severity = int(self.rng.integers(sev_range[0], sev_range[1] + 1))

                    records.append(
                        {
                            "event_id": str(uuid.uuid4()),
                            "event_type": event_type,
                            "affected_airport": airport,
                            "start_utc": start_dt,
                            "end_utc": end_dt,
                            "severity": severity,
                            "description": self._weather_description(event_type, airport, severity),
                        }
                    )

            cur_month += 1
            if cur_month > 12:
                cur_month = 1
                cur_year += 1

        df = pd.DataFrame(records)
        console.print(f"[green]Generated {len(df):,} weather events.")
        return df

    def _weather_description(self, event_type: str, airport: str, severity: int) -> str:
        templates = _WEATHER_TEMPLATES.get(event_type, [])
        if templates:
            base = str(self.rng.choice(templates))
        else:
            base = self._fake.sentence()
        return f"[{airport}] SEV{severity}: {base}"

    # ── Phase 3: Persist to DuckDB ────────────────────────────────────────────

    def save_to_duckdb(
        self,
        flights_df: pd.DataFrame,
        weather_df: pd.DataFrame | None = None,
    ) -> Path:
        db_path = Path(self.settings.duckdb_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        con = duckdb.connect(str(db_path))
        try:
            for ddl in ALL_DDL:
                con.execute(ddl)

            # Insert aircraft fleet
            fleet_df = pd.DataFrame(FLEET)
            con.execute("DELETE FROM aircraft")
            con.execute("INSERT INTO aircraft SELECT * FROM fleet_df")

            # Insert routes
            from argos.data_gen.routes import ROUTES as ALL_ROUTES

            routes_rows = [
                {
                    "route_id": r.route_id,
                    "origin_iata": r.origin_iata,
                    "origin_icao": r.origin_icao,
                    "dest_iata": r.dest_iata,
                    "dest_icao": r.dest_icao,
                    "dest_name": r.dest_name,
                    "region": r.region,
                    "distance_nm": r.distance_nm,
                    "frequency_per_day": r.frequency_per_day,
                }
                for r in ALL_ROUTES
            ]
            routes_df = pd.DataFrame(routes_rows)
            con.execute("DELETE FROM routes")
            con.execute("INSERT INTO routes SELECT * FROM routes_df")

            # Insert route_aircraft
            ra_rows = []
            for r in ALL_ROUTES:
                for priority, (ac_type, bt) in enumerate(r.block_times.items()):
                    ra_rows.append(
                        {
                            "route_id": r.route_id,
                            "aircraft_type": ac_type,
                            "block_time_min": bt,
                            "priority": priority,
                        }
                    )
            ra_df = pd.DataFrame(ra_rows)
            con.execute("DELETE FROM route_aircraft")
            con.execute("INSERT INTO route_aircraft SELECT * FROM ra_df")

            # Insert delay code reference
            codes_df = pd.DataFrame(
                [{"code": k, "description": v} for k, v in IATA_DELAY_CODES.items()]
            )
            con.execute("DELETE FROM delay_codes_ref")
            con.execute("INSERT INTO delay_codes_ref SELECT * FROM codes_df")

            # Insert flights
            con.execute("DELETE FROM flights WHERE TRUE")
            flight_cols = [
                "flight_id",
                "flight_number",
                "route_id",
                "origin_iata",
                "dest_iata",
                "aircraft_registration",
                "aircraft_type",
                "scheduled_dep_utc",
                "scheduled_arr_utc",
                "actual_dep_utc",
                "actual_arr_utc",
                "block_time_minutes",
                "distance_nm",
                "dep_delay_minutes",
                "arr_delay_minutes",
                "delay_code",
                "delay_subcode",
                "delay_responsibility",
                "pax_boarded",
                "load_factor",
                "fuel_uplift_kg",
                "cargo_kg",
                "status",
                "cancel_reason",
            ]
            insert_df = flights_df[flight_cols]
            con.execute("INSERT INTO flights SELECT * FROM insert_df")

            # Insert weather events
            if weather_df is not None and not weather_df.empty:
                con.execute("DELETE FROM weather_events WHERE TRUE")
                con.execute("INSERT INTO weather_events SELECT * FROM weather_df")

            count = con.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
            console.print(f"[green]Saved {count:,} flights to {db_path}")
        finally:
            con.close()

        return db_path

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        routes: list[RouteDefinition] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> GenerationResult:
        routes = routes or ROUTES
        start = start_date or date.fromisoformat(self.settings.data_start_date)
        end = end_date or date.fromisoformat(self.settings.data_end_date)

        console.rule("[bold cyan]ARGOS Synthetic Data Generator")
        console.print(f"Routes: {len(routes)}  |  Period: {start} → {end}")

        route_params = self.generate_route_params(routes)
        flights_df = self.generate_flights(routes, route_params, start, end)
        weather_df = self.generate_weather_events(start, end)
        db_path = self.save_to_duckdb(flights_df, weather_df)

        return GenerationResult(
            flights_count=len(flights_df),
            routes_count=len(routes),
            aircraft_count=len(FLEET),
            weather_events_count=len(weather_df),
            date_range=(start, end),
            duckdb_path=db_path,
        )
