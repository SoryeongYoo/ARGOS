"""Initialize DuckDB schema without generating data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import duckdb
from rich.console import Console

from argos.config import get_settings
from argos.data_gen.schemas import ALL_DDL, IATA_DELAY_CODES

console = Console()


def main() -> None:
    settings = get_settings()
    db_path = Path(settings.duckdb_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        for ddl in ALL_DDL:
            con.execute(ddl)

        import pandas as pd
        codes_df = pd.DataFrame(
            [{"code": k, "description": v} for k, v in IATA_DELAY_CODES.items()]
        )
        con.execute("DELETE FROM delay_codes_ref")
        con.execute("INSERT INTO delay_codes_ref SELECT * FROM codes_df")

        tables = con.execute("SHOW TABLES").fetchall()
        console.print(f"[green]DB initialized at {db_path}")
        console.print(f"Tables: {[t[0] for t in tables]}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
