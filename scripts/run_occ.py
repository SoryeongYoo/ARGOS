"""
CLI: OCC 다중 에이전트 중단 복구 워크플로우 실행.

사용 예시
--------------
# 드라이런(시뮬레이션만 가능, LLM 브리핑 없음)
파이썬 스크립트/run_occ.py --flight <uuid> --delay 90 --날짜 2024-06-15 --dry-run

# 전체 실행(.env에서 ARPINTIC_API_KEY 필요)
파이썬 스크립트/run_occ.py --flight <uuid> --delay 90 --날짜 2024-06-15

# 시연을 위해 캐스케이드가 있는 첫 번째 항공편 선택
파이썬 스크립트/run_occ.py --auto --delay 120 --날짜 2024-06-15
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import typer
import duckdb

app = typer.Typer(add_completion=False)

DB_PATH = str(Path("data/db/argos.duckdb").resolve())


def _pick_cascadeable_flight(op_date: date) -> str | None:
    """Return a flight_id that has a downstream rotation on op_date."""
    day_start = datetime(op_date.year, op_date.month, op_date.day, tzinfo=timezone.utc)
    day_end = day_start.replace(hour=23, minute=59)

    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        # Find aircraft registrations with ≥2 flights on this day
        rows = con.execute(
            """
            SELECT f.flight_id, f.aircraft_registration, COUNT(*) OVER (
                PARTITION BY f.aircraft_registration
            ) AS cnt
            FROM flights f
            WHERE f.scheduled_dep_utc >= ? AND f.scheduled_dep_utc <= ?
              AND f.status != 'CNX'
            QUALIFY cnt >= 2
            ORDER BY f.scheduled_dep_utc
            LIMIT 1
        """,
            [day_start, day_end],
        ).fetchone()
    finally:
        con.close()
    return rows[0] if rows else None


@app.command()
def main(
    flight: str = typer.Option("", "--flight", "-f", help="trigger flight_id (UUID)"),
    delay: int = typer.Option(90, "--delay", "-d", help="departure delay in minutes"),
    date_str: str = typer.Option("2024-06-15", "--date", help="operating date YYYY-MM-DD"),
    auto: bool = typer.Option(False, "--auto", help="auto-pick a cascadeable flight"),
    dry_run: bool = typer.Option(False, "--dry-run", help="simulate only, skip LLM nodes"),
    approve: int = typer.Option(
        0, "--approve", help="auto-approve scenario (1/2/3); 0=interactive"
    ),
) -> None:
    """Run the ARGOS OCC disruption recovery workflow."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import IntPrompt, Prompt

    console = Console()
    op_date = date.fromisoformat(date_str)

    # Resolve flight_id
    flight_id = flight
    if auto or not flight_id:
        console.print("[yellow]Auto-selecting a cascadeable flight...[/]")
        flight_id = _pick_cascadeable_flight(op_date)
        if not flight_id:
            console.print("[red]No cascadeable flight found for this date.[/]")
            raise typer.Exit(1)
        console.print(f"[green]Selected flight_id:[/] {flight_id}")

    console.print(
        Panel(
            f"[bold]ARGOS OCC[/bold] - Disruption Recovery\n"
            f"Flight  : {flight_id}\n"
            f"Delay   : {delay} min\n"
            f"Date    : {date_str}",
            title="OCC Event",
        )
    )

    if dry_run:
        # ── Dry-run: simulation only ──────────────────────────────────────
        console.print("\n[cyan]--- DRY RUN: Propagation Simulation Only ---[/]")
        from argos.agents.tools import run_propagation, run_scenario_generation

        prop = run_propagation.invoke(
            {
                "db_path": DB_PATH,
                "op_date": date_str,
                "trigger_flight_id": flight_id,
                "initial_delay_minutes": delay,
            }
        )
        console.print(
            f"\n[bold]Cascade:[/] {prop['cascade_depth']} legs | "
            f"{prop['total_delay_minutes']} min total delay | "
            f"{prop['total_pax_impacted']} PAX impacted"
        )
        console.print(f"Chain: {' -> '.join(prop['cascade_chain'])}")

        scenarios = run_scenario_generation.invoke(
            {
                "db_path": DB_PATH,
                "op_date": date_str,
                "trigger_flight_id": flight_id,
                "initial_delay_minutes": delay,
            }
        )
        console.print("\n[bold]Recovery Scenarios:[/]")
        for s in scenarios:
            console.print(
                f"  [{s['scenario_id']}] {s['name']} "
                f"(feasibility: {s['feasibility']}, cost: {s['cost_index']:.1f})\n"
                f"      {s['description']}"
            )
        return

    # ── Full run with LangGraph + Claude ──────────────────────────────────
    from argos.agents.occ_graph import build_occ_graph, run_until_approval, resume_after_approval

    console.print("\n[cyan]Running OCC agent graph...[/]")
    state, graph = run_until_approval(
        db_path=DB_PATH,
        op_date=date_str,
        trigger_flight_id=flight_id,
        initial_delay_minutes=delay,
    )

    briefing = state.get("scenario_briefing", "(no briefing generated)")
    console.print(Panel(briefing, title="OCC Briefing — Awaiting Approval"))

    # Human approval step
    if approve in (1, 2, 3):
        chosen = approve
        notes = f"Auto-approved scenario {chosen} via CLI"
    else:
        console.print("\nScenarios:")
        for s in state.get("scenarios_raw", []):
            console.print(f"  [{s['scenario_id']}] {s['name']}")
        chosen = IntPrompt.ask("Approve scenario (1/2/3) or 0 to reject", default=0)
        notes = Prompt.ask("Approval notes", default="Approved by OCC manager")
        if chosen == 0:
            chosen_id = None
        else:
            chosen_id = chosen

    chosen_id = chosen if chosen in (1, 2, 3) else None
    final_state = resume_after_approval(graph, chosen_id, notes)
    console.print(
        Panel(
            final_state.get("execution_summary", "No summary"),
            title="OCC Action Log",
        )
    )


if __name__ == "__main__":
    app()
