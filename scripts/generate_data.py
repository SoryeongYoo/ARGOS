"""
CLI entry point for synthetic data generation.

Usage:
    python scripts/generate_data.py
    python scripts/generate_data.py --start 2023-01-01 --end 2023-12-31
    python scripts/generate_data.py --routes ICN-NRT ICN-JFK --start 2024-01-01 --end 2024-03-31
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import date
from typing import Optional

import typer
from rich.console import Console

from argos.config import get_settings
from argos.data_gen.generator import SyntheticDataGenerator
from argos.data_gen.routes import ROUTE_MAP, ROUTES

app = typer.Typer(help="ARGOS synthetic flight data generator")
console = Console()


@app.command()
def generate(
    start: Optional[str] = typer.Option(None, "--start", "-s", help="Start date YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, "--end", "-e", help="End date YYYY-MM-DD"),
    routes: Optional[list[str]] = typer.Option(
        None, "--routes", "-r",
        help="Route IDs to generate (e.g. ICN-NRT ICN-JFK). Default: all 60.",
    ),
) -> None:
    settings = get_settings()

    start_date = date.fromisoformat(start) if start else None
    end_date = date.fromisoformat(end) if end else None

    selected_routes = ROUTES
    if routes:
        selected_routes = []
        for rid in routes:
            if rid not in ROUTE_MAP:
                console.print(f"[red]Unknown route: {rid}. Available: {list(ROUTE_MAP)[:5]}...")
                raise typer.Exit(1)
            selected_routes.append(ROUTE_MAP[rid])

    gen = SyntheticDataGenerator(settings)
    result = gen.run(selected_routes, start_date, end_date)

    console.rule("[bold green]Generation Complete")
    console.print(f"  Flights:        {result.flights_count:,}")
    console.print(f"  Routes:         {result.routes_count}")
    console.print(f"  Aircraft:       {result.aircraft_count}")
    console.print(f"  Weather events: {result.weather_events_count:,}")
    console.print(f"  Period:         {result.date_range[0]} → {result.date_range[1]}")
    console.print(f"  DuckDB:         {result.duckdb_path}")


if __name__ == "__main__":
    app()
