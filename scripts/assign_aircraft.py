"""
OCC aircraft assignment optimizer demo.

Usage:
    python scripts/assign_aircraft.py                        # full day, auto date
    python scripts/assign_aircraft.py --date 2023-07-15
    python scripts/assign_aircraft.py --date 2023-07-15 --disrupted <uuid1> <uuid2>
"""

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from argos.config import get_settings
from argos.optimization.aircraft import AircraftAssigner

app = typer.Typer(help="ARGOS CP-SAT aircraft assignment optimizer")
console = Console()


@app.command()
def assign(
    dep_date: str | None = typer.Option(
        None, "--date", "-d", help="Operating date YYYY-MM-DD (default: 2023-07-15)"
    ),
    disrupted: list[str] | None = typer.Option(
        None, "--disrupted", help="flight_ids to reassign (default: full day)"
    ),
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
    disrupted_ids = list(disrupted) if disrupted else None

    console.print(f"Loading flights and fleet for [cyan]{op_date}[/]...")

    assigner, tasks, aircraft = AircraftAssigner.load_from_db(db_path, op_date, disrupted_ids)

    n_spare = sum(1 for a in aircraft if a.is_spare)
    console.print(
        f"[green]{len(tasks)}[/] task(s)  |  "
        f"[green]{len(aircraft)}[/] aircraft  "
        f"([dim]{n_spare} spare[/])"
    )

    console.rule("[bold]Solving CP-SAT assignment")
    result = assigner.solve(tasks, aircraft, op_date, time_limit_seconds=time_limit)

    # ── Status banner ─────────────────────────────────────────────────────────
    status_color = {"OPTIMAL": "green", "FEASIBLE": "yellow"}.get(result.status, "red")
    console.print(
        f"\n[bold {status_color}]{result.status}[/]  "
        f"solved in [cyan]{result.solve_time_seconds:.2f}s[/]  |  "
        f"coverage [bold]{result.coverage_rate:.1%}[/]  "
        f"({len(result.assignments)}/{len(tasks)} flights)"
    )

    # ── Assignment table ───────────────────────────────────────────────────────
    if result.assignments:
        # Build lookup maps
        task_map = {t.flight_id: t for t in tasks}
        ac_map = {a.registration: a for a in aircraft}

        t = Table(title="Assignments", show_header=True, header_style="bold", expand=False)
        t.add_column("Flight", style="cyan")
        t.add_column("Route")
        t.add_column("Req. Type", style="dim")
        t.add_column("Assigned Reg", style="green")
        t.add_column("Actual Type")
        t.add_column("Spare?")
        t.add_column("PAX", justify="right")
        t.add_column("Dep UTC")

        for fid, reg in sorted(
            result.assignments.items(), key=lambda kv: task_map[kv[0]].scheduled_dep_utc
        ):
            task = task_map[fid]
            ac = ac_map[reg]
            sub = ac.aircraft_type != task.required_type
            type_str = f"[yellow]{ac.aircraft_type}[/]" if sub else ac.aircraft_type
            spare_str = "[yellow]Y[/]" if ac.is_spare else ""
            t.add_row(
                task.flight_number,
                task.route_id,
                task.required_type,
                reg,
                type_str,
                spare_str,
                str(task.pax_boarded),
                task.scheduled_dep_utc.strftime("%H:%M"),
            )
        console.print(t)

    # ── Unassigned table ──────────────────────────────────────────────────────
    if result.unassigned:
        task_map = {t.flight_id: t for t in tasks}
        u = Table(title="[red]Unassigned Flights[/]", show_header=True, header_style="bold red")
        u.add_column("Flight", style="cyan")
        u.add_column("Route")
        u.add_column("Req. Type")
        u.add_column("PAX", justify="right")
        u.add_column("Dep UTC")
        for fid in result.unassigned:
            task = task_map[fid]
            u.add_row(
                task.flight_number,
                task.route_id,
                task.required_type,
                str(task.pax_boarded),
                task.scheduled_dep_utc.strftime("%H:%M"),
            )
        console.print(u)

    covered_pax = sum(task_map[fid].pax_boarded for fid in result.assignments if fid in task_map)
    console.print(
        Panel(
            f"Coverage rate : [bold]{result.coverage_rate:.1%}[/]\n"
            f"Covered PAX   : [green]{covered_pax:,}[/]\n"
            f"Unassigned    : {len(result.unassigned)} flight(s)\n"
            f"Solver status : [{status_color}]{result.status}[/]",
            title="Summary",
            expand=False,
        )
    )


if __name__ == "__main__":
    app()
