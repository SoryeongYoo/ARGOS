"""
UAM/AAM ACROSS integration demo.

Demonstrates:
  1. UAM vertiport network overview (ICN-hub corridor map)
  2. Route planning between vertiports
  3. ACROSS flight plan submission & conflict detection
  4. OCC integration: suggest UAM alternative for delayed flight passengers

Usage:
    python scripts/uam_demo.py
    python scripts/uam_demo.py --origin SBR --dest GMP
    python scripts/uam_demo.py --scenario occ   # OCC passenger alternative
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from argos.uav.models import (
    ApprovalStatus,
    FlightRules,
    GeoPoint,
    UAMFlightPlan,
    UAMVehicle,
    VehicleClass,
    Waypoint4D,
)
from argos.uav.network import (
    VERTIPORTS,
    build_uam_network,
    estimate_flight_time_min,
    find_route,
    route_distance_nm,
    all_routes_from,
)
from argos.uav.across_client import ACROSSClient

app = typer.Typer(help="ARGOS UAM/AAM ACROSS integration demo")
console = Console()
UTC = timezone.utc

DEMO_VEHICLE = UAMVehicle(
    vehicle_id="KE-AAM-001",
    call_sign="KAM001",
    vehicle_class=VehicleClass.EVTOL,
    manufacturer="Joby Aviation",
    model="S4",
    max_alt_ft=3000,
    cruise_speed_kts=150,
    range_nm=100,
    max_payload_kg=450,
    pax_capacity=4,
    registration="KR-00001",
)


def _status_color(status: ApprovalStatus) -> str:
    return {
        ApprovalStatus.APPROVED: "green",
        ApprovalStatus.DENIED: "red",
        ApprovalStatus.CANCELLED: "yellow",
        ApprovalStatus.PENDING: "cyan",
        ApprovalStatus.ACTIVE: "blue",
        ApprovalStatus.COMPLETED: "dim",
    }.get(status, "white")


def _show_network(G) -> None:
    console.rule("[bold]UAM Vertiport Network - ICN Hub Region")

    vt = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    vt.add_column("ID", style="cyan")
    vt.add_column("Name (EN)")
    vt.add_column("Lat", justify="right")
    vt.add_column("Lon", justify="right")
    vt.add_column("Pads", justify="right")
    vt.add_column("Charging", justify="right")
    vt.add_column("ICAO", style="dim")

    for vid, vp in VERTIPORTS.items():
        vt.add_row(
            vid,
            vp.name_en,
            f"{vp.position.lat:.4f}",
            f"{vp.position.lon:.4f}",
            str(vp.pad_count),
            str(vp.charging_slots),
            vp.icao_code or "-",
        )
    console.print(vt)

    et = Table(
        title=f"Corridors ({G.number_of_edges()} edges)",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
    )
    et.add_column("Origin", style="cyan")
    et.add_column("Dest", style="cyan")
    et.add_column("Dist (NM)", justify="right")
    et.add_column("Cruise ft", justify="right")
    et.add_column("Speed kts", justify="right")
    et.add_column("CTR-free", justify="center")

    for u, v, data in sorted(G.edges(data=True), key=lambda e: e[0]):
        c = data["corridor"]
        free = "[green]Yes[/]" if c.avoids_icn_ctr else "[yellow]No[/]"
        et.add_row(
            u,
            v,
            f"{c.distance_nm:.1f}",
            str(int(c.cruise_alt_ft)),
            str(int(c.speed_limit_kts)),
            free,
        )
    console.print(et)


def _show_route(G, origin_id: str, dest_id: str) -> None:
    console.rule(f"[bold]Route Planning: {origin_id} -> {dest_id}")

    path = find_route(G, origin_id, dest_id, prefer_ctr_avoidance=True)
    if path is None:
        console.print(f"[red]No route found from {origin_id} to {dest_id}.")
        return

    dist = route_distance_nm(G, path)
    ft = estimate_flight_time_min(G, path, DEMO_VEHICLE)

    console.print(
        f"Path     : [cyan]{' -> '.join(path)}[/]\n"
        f"Distance : [bold]{dist:.1f} NM[/]\n"
        f"Est. time: [bold]{ft:.0f} min[/] ({DEMO_VEHICLE.model} "
        f"@ {DEMO_VEHICLE.cruise_speed_kts} kts, 80% eff)"
    )

    # Show each hop
    ht = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    ht.add_column("Hop")
    ht.add_column("Segment")
    ht.add_column("Dist (NM)", justify="right")
    ht.add_column("Cruise ft", justify="right")
    ht.add_column("CTR-free", justify="center")
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        c = G[u][v]["corridor"]
        free = "[green]Yes[/]" if c.avoids_icn_ctr else "[yellow]No[/]"
        ht.add_row(
            str(i + 1), f"{u} -> {v}", f"{c.distance_nm:.1f}", str(int(c.cruise_alt_ft)), free
        )
    console.print(ht)


def _submit_plans(client: ACROSSClient, G) -> None:
    console.rule("[bold]ACROSS Flight Plan Submission")

    etd_day = datetime(2024, 6, 15, 3, 0, tzinfo=UTC)  # 12:00 KST

    test_cases = [
        ("PLAN-OK", "SBR", "YDP", 800, 3, "Normal daytime SBR->YDP"),
        ("PLAN-CURFEW", "SBR", "YDP", 800, 15, "Midnight KST curfew violation"),
        ("PLAN-CTR", "ICN-T1", "ICN-T2", 1500, 3, "High altitude inside ICN CTR"),
        ("PLAN-MULTI", "ICN-T2", "YDP", 800, 4, "Multi-hop ICN-T2->SBR->YDP"),
    ]

    rt = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    rt.add_column("Plan ID", style="cyan")
    rt.add_column("Route")
    rt.add_column("Alt ft", justify="right")
    rt.add_column("Dep (UTC)")
    rt.add_column("Status", justify="center")
    rt.add_column("Conflicts", justify="right")
    rt.add_column("Note", style="dim")

    for pid, origin, dest, alt_ft, dep_hour, note in test_cases:
        etd = datetime(2024, 6, 15, dep_hour, 0, tzinfo=UTC)
        eta = etd + timedelta(minutes=20)

        origin_vp = VERTIPORTS[origin]
        dest_vp = VERTIPORTS[dest]

        plan = UAMFlightPlan(
            plan_id=pid,
            vehicle_id=DEMO_VEHICLE.vehicle_id,
            origin_id=origin,
            dest_id=dest,
            flight_rules=FlightRules.VFRC,
            etd_utc=etd,
            eta_utc=eta,
            cruise_alt_ft=float(alt_ft),
            trajectory=[
                Waypoint4D(GeoPoint(origin_vp.position.lat, origin_vp.position.lon, alt_ft), etd),
                Waypoint4D(GeoPoint(dest_vp.position.lat, dest_vp.position.lon, alt_ft), eta),
            ],
            pax_count=2,
        )
        resp = client.submit_plan(plan)
        sc = _status_color(resp.status)
        rt.add_row(
            pid,
            f"{origin} -> {dest}",
            str(alt_ft),
            etd.strftime("%H:%M"),
            f"[{sc}]{resp.status.value}[/]",
            str(len(resp.conflicts)),
            note,
        )

    console.print(rt)

    # Show conflict details for denied plans
    for pid in ["PLAN-CURFEW", "PLAN-CTR"]:
        resp = client.get_status(pid)
        if resp and resp.conflicts:
            console.print(f"\n[yellow]Conflict details for {pid}:[/]")
            for c in resp.conflicts:
                console.print(f"  [{c.conflict_type.value}] {c.description}")


def _occ_scenario(client: ACROSSClient, G) -> None:
    console.rule("[bold]OCC Integration: UAM Alternative for Delayed Passengers")

    console.print(
        "Scenario: KE0701 ICN->NRT delayed 90 min. "
        "8 passengers have a critical connection at Gimpo.\n"
        "OCC checks if UAM shuttle (SBR -> GMP) can serve as alternative.\n"
    )

    etd = datetime(2024, 6, 15, 3, 30, tzinfo=UTC)  # 12:30 KST
    result = client.suggest_uam_alternative(
        delayed_flight_number="KE0701",
        delayed_pax=8,
        origin_vertiport_id="SBR",
        dest_vertiport_id="GMP",
        etd_utc=etd,
    )

    if result is None:
        console.print("[red]No UAM connection available for this route.")
        return

    plan, resp = result
    sc = _status_color(resp.status)
    flight_min = (plan.eta_utc - plan.etd_utc).total_seconds() / 60

    console.print(
        Panel(
            f"Plan ID    : {plan.plan_id}\n"
            f"Route      : {plan.origin_id} -> {plan.dest_id}\n"
            f"Departure  : {plan.etd_utc.strftime('%H:%M UTC')} "
            f"({plan.etd_utc.hour + 9:02d}:{plan.etd_utc.minute:02d} KST)\n"
            f"ETA        : {plan.eta_utc.strftime('%H:%M UTC')}\n"
            f"Flight time: {flight_min:.0f} min\n"
            f"PAX slots  : {plan.pax_count} (capped at eVTOL capacity)\n"
            f"Status     : [{sc}]{resp.status.value}[/]\n"
            + (f"Message    : {resp.message}" if resp.message else ""),
            title="UAM Alternative Flight Plan",
            border_style=sc,
            expand=False,
        )
    )

    if resp.approved:
        console.print(
            "[green]UAM alternative approved.[/] OCC may offer seats to time-critical passengers."
        )
    else:
        console.print(
            f"[red]UAM alternative denied.[/] Conflicts: "
            + ", ".join(c.conflict_type.value for c in resp.conflicts)
        )


@app.command()
def demo(
    origin: Optional[str] = typer.Option(
        None, "--origin", "-o", help="Origin vertiport ID for route demo"
    ),
    dest: Optional[str] = typer.Option(None, "--dest", "-d", help="Destination vertiport ID"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Scenario to run: 'occ'"),
) -> None:
    G = build_uam_network()
    client = ACROSSClient(mode="simulation")

    _show_network(G)

    o = origin or "SBR"
    d = dest or "GMP"
    _show_route(G, o, d)

    _submit_plans(client, G)

    if scenario == "occ" or scenario is None:
        _occ_scenario(client, G)


if __name__ == "__main__":
    app()
