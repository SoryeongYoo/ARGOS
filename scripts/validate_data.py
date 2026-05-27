"""Quality-gate for the synthetic dataset. Run before any ML training."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import typer
from rich.console import Console

from argos.config import get_settings
from argos.data_gen.validator import DataValidator

app = typer.Typer(help="ARGOS data quality validator")
console = Console()


@app.command()
def validate(
    db_path: str = typer.Option("", "--db", "-d", help="DuckDB path (default: from .env)"),
    fail_on_warning: bool = typer.Option(False, "--strict", help="Exit non-zero on warnings too"),
) -> None:
    settings = get_settings()
    path = db_path or str(settings.duckdb_path)

    if not Path(path).exists():
        console.print(f"[red]DB not found: {path}. Run generate_data.py first.")
        raise typer.Exit(1)

    validator = DataValidator(path)
    report = validator.run_all()
    report.print_summary()

    if not report.passed:
        console.print("[red]Validation FAILED — fix errors before ML training.")
        raise typer.Exit(2)
    if fail_on_warning and report.warnings:
        console.print("[yellow]Strict mode: warnings treated as failure.")
        raise typer.Exit(1)

    console.print("[bold green]Data quality gate PASSED. Ready for Week 3 ML training.")


if __name__ == "__main__":
    app()
