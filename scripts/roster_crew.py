"""
OCC crew roster optimizer demo.

Usage:
    python scripts/roster_crew.py                        # auto date, synthetic crew
    python scripts/roster_crew.py --date 2023-07-15
    python scripts/roster_crew.py --date 2023-07-15 --narrow 20 --wide 15
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from argos.config import get_settings
from argos.optimization.crew import CrewAssigner, FlightLeg

app = typer.Typer(help="ARGOS CP-SAT crew roster optimizer")
console = Console()


def _load_legs(db_path: Path, op_date: date) -> list[FlightLeg]:
    day_start = datetime(op_date.year, op_date.month, op_date.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute(
            """
            SELECT flight_id, flight_number, aircraft_type,
                   origin_iata, dest_iata,
                   scheduled_dep_utc, block_time_minutes,
                   COALESCE(pax_boarded, 0) AS pax_boarded
            FROM flights
            WHERE scheduled_dep_utc >= ?
              AND scheduled_dep_utc <  ?
              AND status != 'CNX'
            ORDER BY scheduled_dep_utc
        """,
            [day_start, day_end],
        ).df()
    finally:
        con.close()

    df["scheduled_dep_utc"] = pd.to_datetime(df["scheduled_dep_utc"], utc=True)

    return [
        FlightLeg(
            flight_id=str(row["flight_id"]),
            flight_number=str(row["flight_number"]),
            aircraft_type=str(row["aircraft_type"]),
            origin_iata=str(row["origin_iata"]),
            dest_iata=str(row["dest_iata"]),
            scheduled_dep_utc=row["scheduled_dep_utc"].to_pydatetime(),
            block_time_minutes=int(row["block_time_minutes"]),
            pax_boarded=int(row["pax_boarded"]),
        )
        for _, row in df.iterrows()
    ]


@app.command()
def roster(
    dep_date: str | None = typer.Option(
        None, "--date", "-d", help="Operating date YYYY-MM-DD (default: 2023-07-15)"
    ),
    n_narrow: int = typer.Option(16, "--narrow", help="Narrow-body crew pairs (CAPT+FO each)"),
    n_wide: int = typer.Option(12, "--wide", help="Wide-body crew pairs (CAPT+FO each)"),
    time_limit: float = typer.Option(
        30.0, "--time-limit", help="CP-SAT solver time limit in seconds"
    ),
) -> None:
    settings = get_settings()
    db_path = Path(settings.duckdb_path)

    if not db_path.exists():
        console.print(f"[red]DuckDB not found: {db_path}. Run generate_data.py first.")
        raise typer.Exit(1)

    op_date = date.fromisoformat(dep_date) if dep_date else date(2023, 7, 15)

    console.print(f"Loading flights for [cyan]{op_date}[/]...")
    legs = _load_legs(db_path, op_date)

    crew = CrewAssigner.generate_crew(
        n_capt_narrow=n_narrow,
        n_fo_narrow=n_narrow,
        n_capt_wide=n_wide,
        n_fo_wide=n_wide,
        op_day=op_date,
    )

    n_narrow_legs = sum(1 for leg in legs if leg.aircraft_type in {"B737-800", "A321neo"})
    n_wide_legs = sum(1 for leg in legs if leg.aircraft_type not in {"B737-800", "A321neo"})
    console.print(
        f"[green]{len(legs)}[/] legs  "
        f"([dim]narrow: {n_narrow_legs}, wide: {n_wide_legs}[/])  |  "
        f"[green]{len(crew)}[/] crew  "
        f"([dim]narrow: {n_narrow * 2}, wide: {n_wide * 2}[/])"
    )

    console.rule("[bold]Solving CP-SAT crew roster")
    assigner = CrewAssigner()
    result = assigner.solve(legs, crew, op_date, time_limit_seconds=time_limit)

    # ── Status banner ─────────────────────────────────────────────────────────
    status_color = {"OPTIMAL": "green", "FEASIBLE": "yellow"}.get(result.status, "red")
    console.print(
        f"\n[bold {status_color}]{result.status}[/]  "
        f"solved in [cyan]{result.solve_time_seconds:.2f}s[/]  |  "
        f"[bold]{len(result.fully_crewed)}/{len(legs)}[/] flights fully crewed  "
        f"(position fill [bold]{result.coverage_rate:.1%}[/])"
    )

    # ── Fully crewed flights ───────────────────────────────────────────────────
    if result.fully_crewed:
        leg_map = {leg.flight_id: leg for leg in legs}
        t = Table(
            title=f"Crew Assignments ({len(result.fully_crewed)} fully crewed)",
            show_header=True,
            header_style="bold",
            expand=False,
        )
        t.add_column("Flight", style="cyan")
        t.add_column("Route")
        t.add_column("Type", style="dim")
        t.add_column("CAPT")
        t.add_column("FO")
        t.add_column("PAX", justify="right")
        t.add_column("Dep UTC")

        shown = sorted(
            result.fully_crewed,
            key=lambda fid: leg_map[fid].scheduled_dep_utc,
        )
        for fid in shown:
            leg = leg_map[fid]
            t.add_row(
                leg.flight_number,
                f"{leg.origin_iata}-{leg.dest_iata}",
                leg.aircraft_type,
                result.captain_assignments[fid],
                result.fo_assignments[fid],
                str(leg.pax_boarded),
                leg.scheduled_dep_utc.strftime("%H:%M"),
            )
        console.print(t)

    # ── Gaps ──────────────────────────────────────────────────────────────────
    all_gaps = set(result.unassigned_captain) | set(result.unassigned_fo)
    if all_gaps:
        leg_map = {leg.flight_id: leg for leg in legs}
        g = Table(
            title=f"[red]Crew Gaps ({len(all_gaps)} flights)[/]",
            show_header=True,
            header_style="bold red",
        )
        g.add_column("Flight", style="cyan")
        g.add_column("Route")
        g.add_column("CAPT missing?", justify="center")
        g.add_column("FO missing?", justify="center")
        g.add_column("PAX", justify="right")
        for fid in sorted(all_gaps, key=lambda f: leg_map[f].scheduled_dep_utc):
            leg = leg_map[fid]
            no_c = "[red]YES[/]" if fid in result.unassigned_captain else ""
            no_f = "[red]YES[/]" if fid in result.unassigned_fo else ""
            g.add_row(
                leg.flight_number,
                f"{leg.origin_iata}-{leg.dest_iata}",
                no_c,
                no_f,
                str(leg.pax_boarded),
            )
        console.print(g)

    # ── FAR 117 duty summary ───────────────────────────────────────────────────
    if result.duty_periods:
        d = Table(
            title="FAR 117 Duty Periods",
            show_header=True,
            header_style="bold",
            expand=False,
        )
        d.add_column("Crew ID")
        d.add_column("Legs", justify="right")
        d.add_column("FDP (h:mm)", justify="right")
        d.add_column("Max (h)", justify="right")
        d.add_column("Legal", justify="center")

        violations = 0
        for dp in sorted(result.duty_periods, key=lambda x: x.crew_id):
            fdp_str = f"{dp.fdp_minutes // 60}:{dp.fdp_minutes % 60:02d}"
            legal_str = "[green]OK[/]" if dp.far117_legal else "[red]VIOL[/]"
            if not dp.far117_legal:
                violations += 1
            d.add_row(
                dp.crew_id,
                str(len(dp.flight_ids)),
                fdp_str,
                f"{dp.far117_max_hours:.1f}",
                legal_str,
            )
        console.print(d)

    # ── Summary panel ─────────────────────────────────────────────────────────
    far_status = (
        "[green]PASS[/]"
        if not result.far117_violations
        else f"[red]{len(result.far117_violations)} VIOLATION(S)[/]"
    )
    console.print(
        Panel(
            f"Fully crewed    : [bold]{len(result.fully_crewed)}/{len(legs)}[/] flights\n"
            f"Position fill   : [bold]{result.coverage_rate:.1%}[/]\n"
            f"CAPT gaps       : {len(result.unassigned_captain)} flight(s)\n"
            f"FO gaps         : {len(result.unassigned_fo)} flight(s)\n"
            f"FAR 117 check   : {far_status}\n"
            f"Solver status   : [{status_color}]{result.status}[/]\n"
            f"[dim]Human OCC approval required before execution.[/dim]",
            title="Summary",
            expand=False,
        )
    )


if __name__ == "__main__":
    app()
