"""
Pydantic models and DuckDB DDL for ARGOS flight data.
All timestamps are UTC. Delay codes follow IATA AHM 730 standard.
"""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class FlightStatus(str, Enum):
    SCHEDULED = "SCH"
    DEPARTED = "DEP"
    AIRBORNE = "AIR"
    LANDED = "LND"
    ARRIVED = "ARR"
    CANCELLED = "CNX"
    DIVERTED = "DIV"


class DelayResponsibility(str, Enum):
    AIRLINE = "A"  # Carrier responsible
    AIRPORT = "AP"  # Airport/handling responsible
    ATC = "ATC"  # Air traffic control
    WEATHER = "W"  # Weather
    OTHER = "O"


class Aircraft(BaseModel):
    registration: str  # e.g. "HL7700"
    aircraft_type: str  # e.g. "B777-300ER"
    icao_type: str  # e.g. "B77W"
    manufacturer_serial: str
    delivery_date: datetime
    seat_config_y: int  # economy seats
    seat_config_c: int  # business seats
    seat_config_f: int = 0  # first class seats


class Flight(BaseModel):
    flight_id: str  # UUID
    flight_number: str  # e.g. "KE001"
    route_id: str  # e.g. "ICN-NRT"
    origin_iata: str
    dest_iata: str
    aircraft_registration: str
    aircraft_type: str

    scheduled_dep_utc: datetime
    scheduled_arr_utc: datetime
    actual_dep_utc: datetime | None = None
    actual_arr_utc: datetime | None = None

    block_time_minutes: int  # scheduled block time
    distance_nm: int

    dep_delay_minutes: int = 0  # departure delay (negative = early)
    arr_delay_minutes: int = 0
    delay_code: str | None = None  # IATA 2-digit code "00"–"99"
    delay_subcode: str | None = None
    delay_responsibility: DelayResponsibility | None = None

    pax_boarded: int = 0
    load_factor: float = 0.0  # 0.0–1.0
    fuel_uplift_kg: int = 0
    cargo_kg: int = 0

    status: FlightStatus = FlightStatus.SCHEDULED
    cancel_reason: str | None = None


class RouteParams(BaseModel):
    """Rule-based realistic parameters per route."""

    route_id: str
    base_delay_minutes: float = Field(ge=0)
    delay_probability: float = Field(ge=0, le=1)
    delay_distribution: str = Field(pattern="^(lognormal|exponential|weibull)$")
    dist_param_a: float  # shape / scale A
    dist_param_b: float  # shape / scale B
    weather_sensitivity: float = Field(ge=1.0, le=5.0)
    seasonal_factors: dict[str, float]  # keys: winter/spring/summer/autumn
    top_delay_codes: list[str]  # primary IATA delay codes
    cancellation_rate: float = Field(ge=0, le=0.05)


# ── IATA AHM 730 delay code reference (abbreviated) ──────────────────────────

IATA_DELAY_CODES: dict[str, str] = {
    # Passenger & baggage (0x)
    "01": "Late check-in – acceptance after deadline",
    "02": "Late check-in – congestion",
    "03": "Check-in error",
    "04": "Oversales – bumping",
    "05": "Boarding – too many carry-on bags",
    "06": "Late boarding",
    "09": "Passenger/baggage reconciliation",
    # Cargo & mail (1x)
    "11": "Late delivery of freight",
    "12": "Late delivery of mail",
    "13": "Cabin crew error",
    "16": "Cargo documentation errors",
    "17": "Late acceptance of cargo",
    # Aircraft & ramp handling (2x)
    "21": "Aircraft documentation late",
    "22": "Late fueling",
    "23": "Fueling equipment fault",
    "24": "Loading equipment fault",
    "25": "Unit load device shortage",
    "26": "Late arrival of catering vehicle",
    "27": "Catering order error",
    "28": "Late loading / offloading",
    "29": "Slow boarding / cabin preparation",
    # Technical & aircraft (3x)
    "31": "Aircraft defects",
    "32": "Scheduled maintenance",
    "33": "Non-scheduled maintenance (AOG)",
    "34": "Spare parts shortage",
    "35": "Aircraft change",
    "36": "Standby aircraft shortage",
    "38": "Cabin configuration error",
    "39": "Technical stop",
    # Damage to aircraft / EDP (4x)
    "41": "Damage during flight operations",
    "42": "Damage during ground operations",
    "43": "Accident damage",
    "44": "Sabotage / bird strike",
    "46": "Removed defective parts",
    # Flight operations / crewing (5x)
    "51": "Late crew boarding or departure",
    "52": "Flight plan error",
    "55": "Crew shortage",
    "56": "Awaiting relief crew (extended duty)",
    "57": "Aviation authority requirements",
    "58": "Crew request – non-safety",
    # Weather (6x)
    "61": "Airport of departure closed – weather",
    "62": "Airport of destination closed – weather",
    "63": "De-icing aircraft",
    "64": "Awaiting improved weather",
    "65": "Aircraft damaged by hail / lightning",
    "66": "Fumes, smoke or other atmospheric conditions",
    # ATC (7x)
    "71": "ATC en-route demand",
    "72": "ATC ground delay",
    "73": "ATC departure restriction",
    "74": "Airspace restriction",
    "75": "Mandatory security",
    "76": "Military activities",
    # Airport / government (8x)
    "81": "Airport facilities",
    "82": "Airport capacity – handling",
    "83": "Airport capacity – runway",
    "84": "Airport technical equipment",
    "85": "Mandatory security",
    "87": "Immigration / customs",
    "88": "Health quarantine",
    # Reactionary / other (9x)
    "91": "Reactionary – late arrival of aircraft",
    "92": "Reactionary – late crew from another flight",
    "93": "Reactionary – connecting passengers / baggage",
    "94": "Reactionary – awaiting load from another flight",
    "95": "Industrial action – carrier",
    "96": "Industrial action – airport",
    "97": "Industrial action – ATC",
    "98": "Miscellaneous",
    "99": "Unknown",
}


# ── DuckDB DDL ────────────────────────────────────────────────────────────────

DDL_AIRCRAFT = """
CREATE TABLE IF NOT EXISTS aircraft (
    registration        VARCHAR PRIMARY KEY,
    aircraft_type       VARCHAR NOT NULL,
    icao_type           VARCHAR NOT NULL,
    manufacturer_serial VARCHAR,
    delivery_date       DATE,
    seat_config_y       INTEGER,
    seat_config_c       INTEGER,
    seat_config_f       INTEGER DEFAULT 0,
    max_payload_kg      INTEGER,
    mtow_kg             INTEGER
);
"""

DDL_ROUTES = """
CREATE TABLE IF NOT EXISTS routes (
    route_id            VARCHAR PRIMARY KEY,
    origin_iata         VARCHAR(3) NOT NULL,
    origin_icao         VARCHAR(4) NOT NULL,
    dest_iata           VARCHAR(3) NOT NULL,
    dest_icao           VARCHAR(4) NOT NULL,
    dest_name           VARCHAR,
    region              VARCHAR,
    distance_nm         INTEGER NOT NULL,
    frequency_per_day   FLOAT
);
"""

DDL_ROUTE_AIRCRAFT = """
CREATE TABLE IF NOT EXISTS route_aircraft (
    route_id        VARCHAR NOT NULL,
    aircraft_type   VARCHAR NOT NULL,
    block_time_min  INTEGER NOT NULL,
    priority        INTEGER,
    PRIMARY KEY (route_id, aircraft_type)
);
"""

DDL_FLIGHTS = """
CREATE TABLE IF NOT EXISTS flights (
    flight_id               VARCHAR PRIMARY KEY,
    flight_number           VARCHAR NOT NULL,
    route_id                VARCHAR NOT NULL,
    origin_iata             VARCHAR(3) NOT NULL,
    dest_iata               VARCHAR(3) NOT NULL,
    aircraft_registration   VARCHAR NOT NULL,
    aircraft_type           VARCHAR NOT NULL,

    scheduled_dep_utc       TIMESTAMPTZ NOT NULL,
    scheduled_arr_utc       TIMESTAMPTZ NOT NULL,
    actual_dep_utc          TIMESTAMPTZ,
    actual_arr_utc          TIMESTAMPTZ,

    block_time_minutes      INTEGER NOT NULL,
    distance_nm             INTEGER NOT NULL,

    dep_delay_minutes       INTEGER DEFAULT 0,
    arr_delay_minutes       INTEGER DEFAULT 0,
    delay_code              VARCHAR(2),
    delay_subcode           VARCHAR,
    delay_responsibility    VARCHAR(3),

    pax_boarded             INTEGER DEFAULT 0,
    load_factor             FLOAT,
    fuel_uplift_kg          INTEGER,
    cargo_kg                INTEGER,

    status                  VARCHAR(3) DEFAULT 'SCH',
    cancel_reason           VARCHAR,

    -- computed columns for ML features
    dep_hour_utc            INTEGER GENERATED ALWAYS AS (EXTRACT(HOUR FROM scheduled_dep_utc)::INTEGER),
    dep_month               INTEGER GENERATED ALWAYS AS (EXTRACT(MONTH FROM scheduled_dep_utc)::INTEGER),
    dep_dow                 INTEGER GENERATED ALWAYS AS (EXTRACT(DOW FROM scheduled_dep_utc)::INTEGER)
);
"""

DDL_WEATHER_EVENTS = """
CREATE TABLE IF NOT EXISTS weather_events (
    event_id        VARCHAR PRIMARY KEY,
    event_type      VARCHAR NOT NULL,  -- TYPHOON, FOG, SNOW, THUNDERSTORM
    affected_airport VARCHAR(3) NOT NULL,
    start_utc       TIMESTAMPTZ NOT NULL,
    end_utc         TIMESTAMPTZ NOT NULL,
    severity        INTEGER NOT NULL,  -- 1 (minor) to 5 (airport closure)
    description     VARCHAR
);
"""

DDL_DELAY_CODES_REF = """
CREATE TABLE IF NOT EXISTS delay_codes_ref (
    code        VARCHAR(2) PRIMARY KEY,
    description VARCHAR NOT NULL
);
"""

ALL_DDL = [
    DDL_AIRCRAFT,
    DDL_ROUTES,
    DDL_ROUTE_AIRCRAFT,
    DDL_FLIGHTS,
    DDL_WEATHER_EVENTS,
    DDL_DELAY_CODES_REF,
]
