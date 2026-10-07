"""
UAM vertiport network for the ICN hub region.

Network covers: ICN공항 ↔ 김포 ↔ 여의도 ↔ 송도 ↔ 수원 corridor.
All edges represent approved UAM corridors with altitude bands and
separation requirements from ICN CTR (Class C airspace 5 NM radius).
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from argos.uav.models import GeoPoint, UAMVehicle, Vertiport

# ── Vertiport registry ────────────────────────────────────────────────────────

VERTIPORTS: dict[str, Vertiport] = {
    "ICN-T1": Vertiport(
        vertiport_id="ICN-T1",
        name_ko="인천공항 T1 버티포트",
        name_en="ICN Terminal 1 Vertiport",
        position=GeoPoint(37.4549, 126.4402),
        icao_code="RKSI",
        pad_count=4,
        charging_slots=8,
    ),
    "ICN-T2": Vertiport(
        vertiport_id="ICN-T2",
        name_ko="인천공항 T2 버티포트",
        name_en="ICN Terminal 2 Vertiport",
        position=GeoPoint(37.4463, 126.4508),
        icao_code="RKSI",
        pad_count=4,
        charging_slots=8,
    ),
    "GMP": Vertiport(
        vertiport_id="GMP",
        name_ko="김포공항 버티포트",
        name_en="Gimpo Airport Vertiport",
        position=GeoPoint(37.5583, 126.7906),
        icao_code="RKSS",
        pad_count=6,
        charging_slots=12,
    ),
    "YDP": Vertiport(
        vertiport_id="YDP",
        name_ko="여의도 버티포트",
        name_en="Yeouido Vertiport",
        position=GeoPoint(37.5219, 126.9244),
        icao_code=None,
        pad_count=8,
        charging_slots=16,
    ),
    "SBR": Vertiport(
        vertiport_id="SBR",
        name_ko="송도 버티포트",
        name_en="Songdo Vertiport",
        position=GeoPoint(37.3920, 126.6476),
        icao_code=None,
        pad_count=4,
        charging_slots=8,
    ),
    "SWN": Vertiport(
        vertiport_id="SWN",
        name_ko="수원 버티포트",
        name_en="Suwon Vertiport",
        position=GeoPoint(37.2387, 127.0065),
        icao_code=None,
        pad_count=4,
        charging_slots=6,
    ),
    "BDC": Vertiport(
        vertiport_id="BDC",
        name_ko="판교 버티포트",
        name_en="Pangyo (Bundang) Vertiport",
        position=GeoPoint(37.3943, 127.1110),
        icao_code=None,
        pad_count=4,
        charging_slots=6,
    ),
}


# ── Corridor edge attributes ───────────────────────────────────────────────────


@dataclass(frozen=True)
class CorridorEdge:
    """Attributes of a UAM approved corridor segment."""

    origin_id: str
    dest_id: str
    distance_nm: float
    cruise_alt_ft: float  # published cruise altitude AGL
    min_alt_ft: float  # minimum en-route altitude
    max_alt_ft: float  # maximum en-route altitude
    speed_limit_kts: float  # max corridor speed
    avoids_icn_ctr: bool  # True if corridor stays outside ICN CTR (5 NM)
    notes: str = ""


# ── Network builder ────────────────────────────────────────────────────────────


def build_uam_network() -> nx.DiGraph:
    """Return directed graph of UAM corridors.

    Nodes: vertiport_id (str), attributes: Vertiport object
    Edges: corridor with CorridorEdge attributes + 'weight' = distance_nm
    """
    G = nx.DiGraph()

    for vid, vp in VERTIPORTS.items():
        G.add_node(vid, vertiport=vp)

    # Published corridor definitions
    # (symmetric routes get both directions)
    corridors: list[CorridorEdge] = [
        # ICN T1 ↔ ICN T2 (airport internal shuttle)
        CorridorEdge("ICN-T1", "ICN-T2", 0.8, 500, 300, 800, 60, True),
        CorridorEdge("ICN-T2", "ICN-T1", 0.8, 500, 300, 800, 60, True),
        # ICN ↔ 송도 (coast route, avoids CTR)
        CorridorEdge(
            "ICN-T2", "SBR", 8.6, 800, 500, 1200, 80, True, "Coast corridor; avoids ICN ILS"
        ),
        CorridorEdge("SBR", "ICN-T2", 8.6, 800, 500, 1200, 80, True),
        # 송도 ↔ 여의도 (Han River corridor)
        CorridorEdge("SBR", "YDP", 20.5, 1000, 600, 1500, 90, True, "Han River UAM highway"),
        CorridorEdge("YDP", "SBR", 20.5, 1000, 600, 1500, 90, True),
        # 여의도 ↔ 김포 (West Seoul)
        CorridorEdge("YDP", "GMP", 9.3, 800, 500, 1200, 80, True),
        CorridorEdge("GMP", "YDP", 9.3, 800, 500, 1200, 80, True),
        # 김포 ↔ ICN (direct, low altitude — crosses CTR boundary)
        CorridorEdge(
            "GMP",
            "ICN-T1",
            18.4,
            600,
            400,
            1000,
            70,
            False,
            "Crosses ICN CTR boundary; requires ATC coordination",
        ),
        CorridorEdge("ICN-T1", "GMP", 18.4, 600, 400, 1000, 70, False),
        # 여의도 ↔ 수원 (south corridor)
        CorridorEdge("YDP", "SWN", 18.2, 1000, 600, 1500, 90, True),
        CorridorEdge("SWN", "YDP", 18.2, 1000, 600, 1500, 90, True),
        # 수원 ↔ 판교
        CorridorEdge("SWN", "BDC", 12.0, 1000, 600, 1500, 90, True),
        CorridorEdge("BDC", "SWN", 12.0, 1000, 600, 1500, 90, True),
        # 여의도 ↔ 판교
        CorridorEdge("YDP", "BDC", 11.8, 1000, 600, 1500, 90, True),
        CorridorEdge("BDC", "YDP", 11.8, 1000, 600, 1500, 90, True),
    ]

    for c in corridors:
        G.add_edge(
            c.origin_id,
            c.dest_id,
            corridor=c,
            weight=c.distance_nm,
        )

    return G


# ── Route planner ─────────────────────────────────────────────────────────────


def find_route(
    G: nx.DiGraph,
    origin_id: str,
    dest_id: str,
    prefer_ctr_avoidance: bool = True,
) -> list[str] | None:
    """Return shortest vertiport sequence (by distance) or None if no path.

    Args:
        G: UAM network graph
        origin_id: departure vertiport ID
        dest_id: arrival vertiport ID
        prefer_ctr_avoidance: if True, add penalty to edges crossing ICN CTR
    """
    if origin_id not in G or dest_id not in G:
        return None

    if prefer_ctr_avoidance:
        # Create temp graph with CTR-crossing edges penalised
        H = G.copy()
        for u, v, data in H.edges(data=True):
            corridor: CorridorEdge = data["corridor"]
            if not corridor.avoids_icn_ctr:
                H[u][v]["weight"] = data["weight"] * 3.0  # heavy penalty
    else:
        H = G

    try:
        path = nx.shortest_path(H, origin_id, dest_id, weight="weight")
        return path
    except nx.NetworkXNoPath:
        return None


def route_distance_nm(G: nx.DiGraph, path: list[str]) -> float:
    """Sum of edge distances along a vertiport path."""
    total = 0.0
    for i in range(len(path) - 1):
        total += G[path[i]][path[i + 1]]["weight"]
    return total


def estimate_flight_time_min(
    G: nx.DiGraph,
    path: list[str],
    vehicle: UAMVehicle,
) -> float:
    """Estimate flight time in minutes for a path given vehicle cruise speed."""
    dist_nm = route_distance_nm(G, path)
    # Apply 80% speed efficiency for ATC compliance, turns, altitude changes
    eff_speed = vehicle.cruise_speed_kts * 0.80
    return (dist_nm / eff_speed) * 60 if eff_speed > 0 else 0.0


def all_routes_from(G: nx.DiGraph, origin_id: str) -> dict[str, list[str]]:
    """Return shortest path to every reachable vertiport from origin."""
    if origin_id not in G:
        return {}
    paths = nx.single_source_shortest_path(G, origin_id, cutoff=5)
    return {dest: path for dest, path in paths.items() if dest != origin_id}
