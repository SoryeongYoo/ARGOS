"""
UAM/AAM domain models for ACROSS integration.

ACROSS (국토교통부 UAM 교통관리 시스템):
  Advanced Concept of Routing and Operations Support System
  Korea's UTM (UAS Traffic Management) framework for urban air mobility.

Altitude convention: all altitudes in feet AGL (above ground level).
Coordinates: WGS84 decimal degrees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# ── Enumerations ──────────────────────────────────────────────────────────────


class VehicleClass(str, Enum):  # noqa: UP042 — StrEnum 전환 시 str()/format() 결과가 바뀜
    EVTOL = "eVTOL"  # electric Vertical Take-Off and Landing
    CARGO = "CARGO"  # unmanned cargo drone
    INSPECT = "INSPECT"  # inspection UAV


class FlightRules(str, Enum):  # noqa: UP042 — StrEnum 전환 시 str()/format() 결과가 바뀜
    VFRC = "VFRC"  # Visual Flight Rules (Controlled)
    IFRC = "IFRC"  # Instrument Flight Rules (Controlled)


class ApprovalStatus(str, Enum):  # noqa: UP042 — StrEnum 전환 시 str()/format() 결과가 바뀜
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class ConflictType(str, Enum):  # noqa: UP042 — StrEnum 전환 시 str()/format() 결과가 바뀜
    SEPARATION = "SEPARATION"  # horizontal/vertical separation violation
    AIRSPACE = "AIRSPACE"  # enters restricted/controlled airspace
    RUNWAY_CORR = "RUNWAY_CORR"  # penetrates ILS/approach corridor
    CURFEW = "CURFEW"  # noise curfew violation (23:00–06:00 KST)
    WEATHER = "WEATHER"  # weather minima not met


# ── Spatial primitives ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GeoPoint:
    lat: float  # decimal degrees N
    lon: float  # decimal degrees E
    alt_ft: float = 0.0  # AGL feet

    def distance_nm(self, other: GeoPoint) -> float:
        """Haversine great-circle distance in nautical miles."""
        import math

        R_NM = 3440.065  # Earth radius in NM
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * R_NM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Waypoint4D:
    """A point in 4D space-time along a UAM trajectory."""

    point: GeoPoint
    eta_utc: datetime  # estimated time of arrival at this waypoint


# ── Fleet models ──────────────────────────────────────────────────────────────


@dataclass
class UAMVehicle:
    vehicle_id: str
    call_sign: str
    vehicle_class: VehicleClass
    manufacturer: str
    model: str
    max_alt_ft: float  # operational ceiling AGL
    cruise_speed_kts: float
    range_nm: float
    max_payload_kg: float
    pax_capacity: int  # 0 for cargo/inspection
    registration: str  # Korean CAA registration KR-XXXXX


@dataclass
class Vertiport:
    vertiport_id: str
    name_ko: str  # Korean name
    name_en: str
    position: GeoPoint
    icao_code: str | None  # if co-located with airport
    pad_count: int  # simultaneous takeoff/landing capacity
    charging_slots: int
    curfew_start_kst: int = 23  # hour; noise curfew (23:00–06:00)
    curfew_end_kst: int = 6


# ── Flight plan ───────────────────────────────────────────────────────────────


@dataclass
class UAMFlightPlan:
    plan_id: str
    vehicle_id: str
    origin_id: str  # Vertiport ID
    dest_id: str  # Vertiport ID
    flight_rules: FlightRules
    etd_utc: datetime  # estimated time of departure
    eta_utc: datetime  # estimated time of arrival
    cruise_alt_ft: float  # planned cruise altitude AGL
    trajectory: list[Waypoint4D] = field(default_factory=list)
    pax_count: int = 0
    cargo_kg: float = 0.0
    operator: str = "KE-AAM"  # Korean Air AAM division


# ── ACROSS API response models ────────────────────────────────────────────────


@dataclass
class ConflictDetail:
    conflict_type: ConflictType
    description: str
    conflicting_entity: str  # flight_id or airspace_id
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None
    separation_required_nm: float = 0.5
    separation_actual_nm: float | None = None


@dataclass
class ACROSSResponse:
    plan_id: str
    status: ApprovalStatus
    approval_time_utc: datetime | None = None
    conflicts: list[ConflictDetail] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)  # approval conditions
    message: str = ""

    @property
    def approved(self) -> bool:
        return self.status == ApprovalStatus.APPROVED

    @property
    def denied(self) -> bool:
        return self.status == ApprovalStatus.DENIED
