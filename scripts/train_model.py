"""
Train LightGBM delay prediction model.

Usage:
    python scripts/train_model.py
    python scripts/train_model.py --cutoff 2024-01-01 --model-path models/delay.lgb
    python scripts/train_model.py --rounds 800
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from argos.config import get_settings
from argos.prediction.features import compute_route_stats, engineer_features, load_raw_data
from argos.prediction.model import DelayPredictor

app = typer.Typer(help="Train ARGOS LightGBM delay prediction model")
console = Console()


@app.command()
def train(
    cutoff: Optional[str] = typer.Option(
        None, "--cutoff", "-c",
        help="Train/test split date YYYY-MM-DD. Default: last 20%% of data by date.",
    ),
    model_path: str = typer.Option(
        "models/delay_predictor.lgb", "--model-path", "-m",
        help="Output path for trained model file.",
    ),
    num_boost_round: int = typer.Option(
        600, "--rounds", "-n", help="Maximum LightGBM boosting rounds.",
    ),
) -> None:
    settings = get_settings()
    db_path = Path(settings.duckdb_path)

    if not db_path.exists():
        console.print(f"[red]DuckDB not found: {db_path}. Run generate_data.py first.")
        raise typer.Exit(1)

    console.rule("[bold cyan]ARGOS Delay Prediction Training")

    # ── Load ──────────────────────────────────────────────────────────────────
    console.print(f"Loading flights from [cyan]{db_path}[/]...")
    df = load_raw_data(db_path)

    n_total = len(df)
    delay_rate = (df["dep_delay_minutes"] >= 15).mean()
    console.print(
        f"[green]{n_total:,} flights[/]  |  "
        f"delay rate (≥15 min): [yellow]{delay_rate:.1%}[/]  |  "
        f"date range: {df['flight_date'].min().date()} → {df['flight_date'].max().date()}"
    )

    if n_total < 1_000:
        console.print(
            "[yellow]Warning: fewer than 1,000 records. "
            "Generate ≥1 year of data for a meaningful model."
        )

    # ── Train / test split (time-based) ──────────────────────────────────────
    if cutoff:
        split_ts = pd.Timestamp(cutoff)
    else:
        split_ts = df["flight_date"].quantile(0.80)

    train_df = df[df["flight_date"] < split_ts].copy()
    test_df = df[df["flight_date"] >= split_ts].copy()

    console.print(
        f"Train: [green]{len(train_df):,}[/] flights  (<{split_ts.date()})  |  "
        f"Test: [green]{len(test_df):,}[/] flights  (≥{split_ts.date()})"
    )

    if len(train_df) < 500:
        console.print("[red]Too few training samples. Extend date range and re-generate data.")
        raise typer.Exit(1)

    # ── Feature engineering ──────────────────────────────────────────────────
    route_stats = compute_route_stats(train_df)

    X_train_full, y_train_full = engineer_features(train_df, route_stats)
    X_test, y_test = engineer_features(test_df, route_stats)

    # Use the last 10% of train as a temporal validation set for early stopping
    val_idx = int(len(X_train_full) * 0.90)
    X_tr = X_train_full.iloc[:val_idx]
    y_tr = y_train_full.iloc[:val_idx]
    X_val = X_train_full.iloc[val_idx:]
    y_val = y_train_full.iloc[val_idx:]

    # ── Train ─────────────────────────────────────────────────────────────────
    console.print(f"\nTraining LightGBM (max {num_boost_round} rounds, early stopping)...")
    predictor = DelayPredictor()
    train_metrics = predictor.fit(X_tr, y_tr, X_val, y_val, num_boost_round=num_boost_round)

    # ── Threshold tuning (maximise F1 on validation set) ─────────────────────
    opt_threshold = predictor.tune_threshold(X_val, y_val, metric="f1")
    console.print(f"Optimal decision threshold (val F1): [yellow]{opt_threshold:.2f}[/]")

    # ── Evaluate ──────────────────────────────────────────────────────────────
    test_metrics = predictor.evaluate(X_test, y_test)

    metrics_table = Table(title="Test-Set Metrics", show_header=True, header_style="bold")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", justify="right")
    metrics_table.add_row("ROC-AUC",               f"{test_metrics['roc_auc']:.4f}")
    metrics_table.add_row("Avg Precision (AP)",    f"{test_metrics['avg_precision']:.4f}")
    metrics_table.add_row("Precision (>=15 min)",  f"{test_metrics['precision']:.3f}")
    metrics_table.add_row("Recall (>=15 min)",     f"{test_metrics['recall']:.3f}")
    metrics_table.add_row("F1 (>=15 min)",         f"{test_metrics['f1']:.3f}")
    metrics_table.add_row("Actual delay rate",     f"{test_metrics['delay_rate_actual']:.1%}")
    metrics_table.add_row("Predicted delay rate",  f"{test_metrics['delay_rate_predicted']:.1%}")
    console.print(metrics_table)

    imp_table = Table(title="Top Feature Importance (gain)", show_header=True, header_style="bold")
    imp_table.add_column("Feature", style="cyan")
    imp_table.add_column("Gain", justify="right")
    for _, row in predictor.feature_importance(top_n=10).iterrows():
        imp_table.add_row(row["feature"], f"{row['importance_gain']:,.0f}")
    console.print(imp_table)

    # ── Save ──────────────────────────────────────────────────────────────────
    out_path = Path(model_path)
    predictor.save(out_path)
    console.print(f"\n[bold green]Model saved -> {out_path}")
    console.print(
        f"  Train AUC: {train_metrics['train_auc']:.4f}  |  "
        f"Val AUC: {train_metrics.get('val_auc', 'n/a')}"
    )


if __name__ == "__main__":
    app()
