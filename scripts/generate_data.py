"""
CLI entry point for synthetic data generation.

--yes 없이 실행하면 바꿀 내용만 출력하고 종료한다.

Usage:
    python scripts/generate_data.py --yes
    python scripts/generate_data.py --start 2023-01-01 --end 2023-12-31
    python scripts/generate_data.py --routes ICN-NRT ICN-JFK --start 2024-01-01 --end 2024-03-31
"""

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from argos.cli_guard import YES_HELP, describe_db, require_yes
from argos.config import get_settings
from argos.data_gen.generator import SyntheticDataGenerator
from argos.data_gen.routes import ROUTE_MAP, ROUTES

app = typer.Typer(help="ARGOS synthetic flight data generator")
console = Console()


@app.command()
def generate(
    start: str | None = typer.Option(None, "--start", "-s", help="Start date YYYY-MM-DD"),
    end: str | None = typer.Option(None, "--end", "-e", help="End date YYYY-MM-DD"),
    routes: list[str] | None = typer.Option(
        None,
        "--routes",
        "-r",
        help="Route IDs to generate (e.g. ICN-NRT ICN-JFK). Default: all 60.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help=YES_HELP),
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

    period = f"{start_date or settings.data_start_date} ~ {end_date or settings.data_end_date}"
    require_yes(
        yes,
        [
            *describe_db(Path(settings.duckdb_path)),
            f"노선 {len(selected_routes)}개, 기간 {period}, seed {settings.random_seed} 로 생성",
            "flights 전체 삭제 후 새 데이터로 교체 (기간 밖 기존 데이터도 사라짐)",
            "aircraft, routes, route_aircraft, delay_codes_ref 전체 삭제 후 재삽입",
            "weather_events: 새 기상 이벤트가 1건 이상이면 전체 삭제 후 교체",
        ],
        console,
    )

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
