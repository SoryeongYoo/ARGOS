"""
OCC delay propagation simulator demo.

Usage:
    python scripts/simulate_delay.py                        # auto-pick worst cascade
    python scripts/simulate_delay.py --date 2023-07-15
    python scripts/simulate_delay.py --date 2023-07-15 --flight KE0700 --delay 90
"""

import sys
from pathlib import Path

from datetime import date
from typing import Optional

import networkx as nx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from argos.config import get_settings
from argos.simulation.propagation import DelayPropagator, PropagationResult, RecoveryScenario

app = typer.Typer(help="ARGOS OCC delay propagation simulator")
console = Console()


def _result_table(result: PropagationResult, title: str) -> Table:
    t = Table(title=title, show_header=True, header_style="bold", expand=False)
    t.add_column("Flight", style="cyan")
    t.add_column("Route")
    t.add_column("Aircraft", style="dim")
    t.add_column("Sched Dep (UTC)")
    t.add_column("Delay (min)", justify="right")
    t.add_column("PAX", justify="right")

    for node in result.affected_nodes:
        delay_str = f"[red]+{node.dep_delay_minutes}[/]" if node.dep_delay_minutes > 0 else "0"
        t.add_row(
            node.flight_number,
            node.route_id,
            node.aircraft_registration,
            node.scheduled_dep_utc.strftime("%H:%M"),
            delay_str,
            str(node.pax_boarded),
        )
    return t


def _scenario_panel(s: RecoveryScenario) -> Panel:
    feasibility_color = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(
        s.feasibility, "white"
    )
    r = s.residual
    body = (
        f"[italic]{s.description}[/italic]\n\n"
        f"[bold]Action:[/bold] {s.action_required}\n"
        f"[bold]Feasibility:[/bold] [{feasibility_color}]{s.feasibility}[/]\n"
        f"[bold]Relative cost:[/bold] {'*' * round(s.cost_index * 5)} ({s.cost_index:.1f})\n"
        f"[bold]Residual cascade:[/bold] {r.cascade_depth} flight(s), "
        f"[red]{r.total_delay_minutes}[/] total delay-min, "
        f"[yellow]{r.total_pax_impacted}[/] PAX impacted\n"
        f"[dim]Human approval required before execution.[/dim]"
    )
    color = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(s.feasibility, "blue")
    return Panel(
        body,
        title=f"[bold {color}]Scenario {s.scenario_id}: {s.name}[/]",
        border_style=color,
        expand=False,
    )


@app.command()
def simulate(
    dep_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Operating date YYYY-MM-DD (default: 2023-07-15)"
    ),
    flight: Optional[str] = typer.Option(
        None, "--flight", "-f", help="Trigger flight number (default: auto highest-cascade)"
    ),
    delay: int = typer.Option(90, "--delay", help="Initial delay in minutes on the trigger flight"),
) -> None:
    settings = get_settings()
    db_path = Path(settings.duckdb_path)

    if not db_path.exists():
        console.print(f"[red]DuckDB not found: {db_path}. Run generate_data.py first.")
        raise typer.Exit(1)

    op_date = date.fromisoformat(dep_date) if dep_date else date(2023, 7, 15)

    propagator = DelayPropagator(db_path)

    # Load flights and build rotation graph
    console.print(f"Loading flights for [cyan]{op_date}[/]...")
    flights_df = propagator.load_flights(op_date)

    if flights_df.empty:
        console.print(f"[red]No flights found for {op_date}. Try a different date.")
        raise typer.Exit(1)

    G = propagator.build_rotation_graph(flights_df)
    n_edges = G.number_of_edges()
    console.print(
        f"[green]{len(flights_df)}[/] flights loaded  |  "
        f"[green]{n_edges}[/] rotation edges in graph"
    )

    # Select trigger flight
    if flight:
        matches = flights_df[flights_df["flight_number"] == flight]
        if matches.empty:
            console.print(f"[red]Flight {flight!r} not found on {op_date}.")
            raise typer.Exit(1)
        trigger_id = matches.iloc[0]["flight_id"]
    else:
        # Auto-select: flight with highest downstream cascade potential
        trigger_id = _pick_best_trigger(G, flights_df)

    trigger_node = G.nodes[trigger_id]["data"]
    console.print(
        f"\nTrigger flight: [bold cyan]{trigger_node.flight_number}[/]  "
        f"({trigger_node.route_id}, {trigger_node.aircraft_registration})  "
        f"Dep {trigger_node.scheduled_dep_utc.strftime('%H:%M')} UTC  "
        f"+[red]{delay}[/] min"
    )

    # Run scenario generation
    console.rule("[bold]Delay Propagation Analysis")
    scenarios = propagator.generate_scenarios(G, trigger_id, delay, op_date)

    # Show scenario 1 detail table
    s1 = scenarios[0]
    if s1.residual.affected_nodes:
        console.print(_result_table(s1.residual, "Cascade Impact (Scenario 1: Absorb)"))

    # Show all three scenario panels
    console.rule("[bold]Recovery Scenarios")
    for s in scenarios:
        console.print(_scenario_panel(s))

    # Summary comparison table
    console.rule("[bold]Scenario Comparison")
    cmp = Table(show_header=True, header_style="bold")
    cmp.add_column("Scenario")
    cmp.add_column("Cascade Flights", justify="right")
    cmp.add_column("Total Delay (min)", justify="right")
    cmp.add_column("PAX Impacted", justify="right")
    cmp.add_column("Relative Cost")
    cmp.add_column("Feasibility")
    for s in scenarios:
        r = s.residual
        fc = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(s.feasibility, "white")
        cmp.add_row(
            f"S{s.scenario_id}: {s.name}",
            str(r.cascade_depth),
            str(r.total_delay_minutes),
            str(r.total_pax_impacted),
            "★" * round(s.cost_index * 5),
            f"[{fc}]{s.feasibility}[/]",
        )
    console.print(cmp)
    console.print("\n[bold yellow]All scenarios require OCC manager approval before execution.[/]")


def _pick_best_trigger(G, flights_df) -> str:
    """Select the flight with the most downstream rotation edges (highest cascade risk)."""
    best_id = None
    best_score = -1
    for node_id in G.nodes:
        score = len(list(nx.descendants(G, node_id)))
        if score > best_score:
            best_score = score
            best_id = node_id
    # Fallback: first flight in the day
    if best_id is None:
        best_id = flights_df.iloc[0]["flight_id"]
    return best_id


if __name__ == "__main__":
    app()
