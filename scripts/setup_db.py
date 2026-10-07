"""Initialize DuckDB schema without generating data.

Usage:
    python scripts/setup_db.py          # 바꿀 내용만 출력 (dry run)
    python scripts/setup_db.py --yes    # 실제 실행
"""

from pathlib import Path

import duckdb
import typer
from rich.console import Console

from argos.cli_guard import YES_HELP, describe_db, require_yes
from argos.config import get_settings
from argos.data_gen.schemas import ALL_DDL, IATA_DELAY_CODES

app = typer.Typer(add_completion=False, help="Initialize ARGOS DuckDB schema")
console = Console()


@app.command()
def main(yes: bool = typer.Option(False, "--yes", "-y", help=YES_HELP)) -> None:
    settings = get_settings()
    db_path = Path(settings.duckdb_path)

    require_yes(
        yes,
        [
            *describe_db(db_path),
            f"테이블 {len(ALL_DDL)}개 CREATE TABLE IF NOT EXISTS (기존 테이블과 데이터는 유지)",
            f"delay_codes_ref 전체 삭제 후 IATA 지연코드 {len(IATA_DELAY_CODES)}개 재삽입",
        ],
        console,
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path))
    try:
        for ddl in ALL_DDL:
            con.execute(ddl)

        import pandas as pd

        codes_df = pd.DataFrame(  # noqa: F841 — DuckDB replacement scan 이 SQL 에서 이름으로 참조
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
    app()
