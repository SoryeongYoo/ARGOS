"""상태를 바꾸는 CLI 스크립트용 확인 게이트.

--yes 없이 실행하면 무엇을 바꿀지만 출력하고 exit 0 으로 종료한다.
"""

import sys
from collections.abc import Sequence
from pathlib import Path

import typer
from rich.console import Console

YES_HELP = "실제로 실행한다. 없으면 바꿀 내용만 출력하고 종료"


def require_yes(yes: bool, plan: Sequence[str], console: Console) -> None:
    """yes 가 아니면 plan 을 출력하고 typer.Exit(0) 으로 종료한다."""
    if yes:
        return
    if not sys.stdout.isatty() and hasattr(sys.stdout, "reconfigure"):
        # 파이프(에이전트 도구 등)로 읽힐 때 Windows cp949 대신 UTF-8 로 내보낸다
        sys.stdout.reconfigure(encoding="utf-8")
    console.print("[bold yellow]DRY RUN[/] 아래 작업을 수행합니다. 실행하려면 --yes 를 붙이세요.")
    for line in plan:
        console.print(f"  - {line}")
    raise typer.Exit(0)


def describe_db(db_path: Path) -> list[str]:
    """DB 파일의 현재 상태(존재 여부, 테이블별 행 수)를 사람이 읽을 문장으로 반환."""
    if not db_path.exists():
        return [f"현재 상태: {db_path} 없음 (새로 생성)"]

    import duckdb

    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except duckdb.Error as exc:
        return [f"현재 상태: {db_path} 읽기 실패 ({exc.__class__.__name__})"]
    try:
        tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        counts = [
            f"{t}={con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,}"  # type: ignore[index]
            for t in tables
        ]
    finally:
        con.close()
    return [f"현재 상태: {db_path} ({', '.join(counts) or '테이블 없음'})"]
