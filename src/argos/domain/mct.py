"""
Minimum Connection Time (MCT) at ICN (Incheon).
Values are set by Incheon Airport Corporation and published in IATA SST.
"""

from enum import Enum


class FlightType(str, Enum):
    DOMESTIC = "D"
    INTERNATIONAL = "I"


# MCT matrix at ICN: (arriving_type, departing_type) → minutes
_ICN_MCT: dict[tuple[FlightType, FlightType], int] = {
    (FlightType.INTERNATIONAL, FlightType.INTERNATIONAL): 60,
    (FlightType.INTERNATIONAL, FlightType.DOMESTIC):      45,
    (FlightType.DOMESTIC,      FlightType.INTERNATIONAL): 60,
    (FlightType.DOMESTIC,      FlightType.DOMESTIC):      30,
}

# ICN terminal assignments (simplified — T1 vs T2)
# T2 is exclusively Korean Air and SkyTeam
_T2_AIRLINES = {"KE", "DL", "AF", "KL", "AM"}  # KE + SkyTeam partners at ICN T2
_INTER_TERMINAL_BUFFER_MIN = 30  # extra if terminals differ


def get_mct(
    arriving_type: FlightType,
    departing_type: FlightType,
    arriving_airline: str = "KE",
    departing_airline: str = "KE",
) -> int:
    """Return minimum connection time in minutes at ICN.

    Adds an inter-terminal buffer if one carrier is in T1 and the other in T2.
    """
    base = _ICN_MCT[(arriving_type, departing_type)]
    arr_t2 = arriving_airline.upper() in _T2_AIRLINES
    dep_t2 = departing_airline.upper() in _T2_AIRLINES
    if arr_t2 != dep_t2:
        base += _INTER_TERMINAL_BUFFER_MIN
    return base


def is_connection_valid(
    arriving_type: FlightType,
    departing_type: FlightType,
    connection_minutes: int,
    arriving_airline: str = "KE",
    departing_airline: str = "KE",
) -> tuple[bool, int]:
    """Check whether a connection at ICN meets MCT.

    Returns:
        (valid, mct_minutes)
    """
    mct = get_mct(arriving_type, departing_type, arriving_airline, departing_airline)
    return connection_minutes >= mct, mct


# IATA airport codes classified as domestic vs international from Korean Air's perspective
# All ARGOS routes are international
def classify_flight(dest_iata: str) -> FlightType:
    domestic_airports = {"GMP", "PUS", "CJU", "TAE", "CJJ", "KWJ", "RSU", "YNY", "WJU"}
    return FlightType.DOMESTIC if dest_iata in domestic_airports else FlightType.INTERNATIONAL
