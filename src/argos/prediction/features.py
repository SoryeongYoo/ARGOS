"""Feature engineering for LightGBM delay prediction."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

BINARY_TARGET_COL: str = "is_delayed"  # dep_delay_minutes >= DELAY_THRESHOLD

FEATURE_COLS: list[str] = [
    # Schedule
    "dep_hour_utc",
    "dep_month",
    "dep_dow",
    # Route
    "distance_nm",
    "block_time_minutes",
    # Categorical (LightGBM handles natively as category dtype)
    "aircraft_type",
    "region",
    # Historical route stats (computed from training window only)
    "route_hist_delay_prob",
    "route_hist_avg_delay",
    "route_hist_p75_delay",
    # Engineered flags
    "is_long_haul",
    "is_typhoon_season",
    "is_winter_icn",
    # Operational
    "load_factor",
]

CAT_COLS: list[str] = ["aircraft_type", "region"]
TARGET_COL: str = "dep_delay_minutes"
DELAY_THRESHOLD: int = 15  # minutes — IATA "on-time" definition
TARGET_CLIP_MAX: int = 720  # 12-hour cap for regression stability


def load_raw_data(db_path: Path) -> pd.DataFrame:
    """Load flight + route metadata from DuckDB, excluding cancelled flights."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute("""
            SELECT
                f.flight_id,
                f.route_id,
                f.aircraft_type,
                f.dep_hour_utc,
                f.dep_month,
                f.dep_dow,
                f.distance_nm,
                f.block_time_minutes,
                f.load_factor,
                f.scheduled_dep_utc::DATE AS flight_date,
                f.dep_delay_minutes,
                r.region
            FROM flights f
            JOIN routes r ON f.route_id = r.route_id
            WHERE f.status != 'CNX'
              AND f.dep_delay_minutes IS NOT NULL
            ORDER BY f.scheduled_dep_utc
        """).df()
    finally:
        con.close()

    df["flight_date"] = pd.to_datetime(df["flight_date"])
    return df


def compute_route_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-route historical delay statistics from a training DataFrame.

    Must be called on training data only to prevent label leakage.
    """
    g = df.groupby("route_id")["dep_delay_minutes"]
    stats = pd.DataFrame(
        {
            "route_hist_delay_prob": g.apply(lambda x: (x >= DELAY_THRESHOLD).mean()),
            "route_hist_avg_delay": g.mean(),
            "route_hist_p75_delay": g.quantile(0.75),
        }
    ).reset_index()
    return stats


def engineer_features(
    df: pd.DataFrame,
    route_stats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Merge route stats and engineer derived features.

    Returns (X, y) where X has FEATURE_COLS and y is clipped delay minutes.
    route_stats must come from the training set to avoid data leakage.
    """
    df = df.merge(route_stats, on="route_id", how="left")

    # Fill routes not seen in training with global training-set means
    df["route_hist_delay_prob"] = df["route_hist_delay_prob"].fillna(
        df["route_hist_delay_prob"].mean()
    )
    df["route_hist_avg_delay"] = df["route_hist_avg_delay"].fillna(
        df["route_hist_avg_delay"].mean()
    )
    df["route_hist_p75_delay"] = df["route_hist_p75_delay"].fillna(
        df["route_hist_p75_delay"].mean()
    )

    df["is_long_haul"] = (df["distance_nm"] > 3000).astype(np.int8)
    df["is_typhoon_season"] = df["dep_month"].isin([6, 7, 8, 9]).astype(np.int8)
    df["is_winter_icn"] = df["dep_month"].isin([12, 1, 2]).astype(np.int8)

    for col in CAT_COLS:
        df[col] = df[col].astype("category")

    X = df[FEATURE_COLS].copy()

    # Binary target: 1 if delayed >= 15 min, 0 otherwise
    y = (df[TARGET_COL] >= DELAY_THRESHOLD).astype(np.int8)
    return X, y
