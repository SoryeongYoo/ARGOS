"""
에이전트/개발자용 단일 검증 명령.

Usage:
    python scripts/verify.py          # 전체 단계 (아래 _steps 순서)
    python scripts/verify.py --fast   # pytest 에서 slow 마커 제외

단계: ruff check → ruff format --check → mypy → import contracts → doc links → pytest
모든 단계를 끝까지 실행한 뒤 요약표를 출력한다. 하나라도 실패하면 exit 1.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent.parent
LINT_TARGETS = ["src", "tests", "scripts"]
# lint-imports 는 console script 만 제공한다. 같은 venv 를 쓰도록 sys.executable 로 띄운다.
LINT_IMPORTS = "from importlinter.cli import lint_imports_command; lint_imports_command()"

app = typer.Typer(add_completion=False)
console = Console()


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _steps(fast: bool) -> list[tuple[str, list[str]]]:
    py = sys.executable
    pytest_cmd = [py, "-m", "pytest", "-q"]
    if fast:
        pytest_cmd += ["-m", "not slow"]
    return [
        ("ruff check", [py, "-m", "ruff", "check", *LINT_TARGETS]),
        ("ruff format", [py, "-m", "ruff", "format", "--check", *LINT_TARGETS]),
        ("mypy", [py, "-m", "mypy", "src"]),
        ("import contracts", [py, "-c", LINT_IMPORTS]),
        ("doc links", [py, "scripts/check_doc_links.py"]),
        ("pytest" + (" (fast)" if fast else ""), pytest_cmd),
    ]


def _run(name: str, command: list[str]) -> StepResult:
    console.rule(f"[bold]{name}")
    start = time.perf_counter()
    # contract 이름이 한글이라 Windows 콘솔(cp949)에서도 깨지지 않게 UTF-8 로 출력시킨다
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(command, cwd=ROOT, env=env)
    return StepResult(name, command, proc.returncode, time.perf_counter() - start)


@app.command()
def verify(
    fast: bool = typer.Option(False, "--fast", help="pytest 에서 slow 마커 테스트 제외"),
) -> None:
    results = [_run(name, cmd) for name, cmd in _steps(fast)]

    table = Table(title="verify summary")
    table.add_column("step")
    table.add_column("result")
    table.add_column("time", justify="right")
    for r in results:
        status = "[green]PASS[/]" if r.ok else f"[red]FAIL (exit {r.returncode})[/]"
        table.add_row(r.name, status, f"{r.seconds:.1f}s")
    console.print(table)

    failed = [r.name for r in results if not r.ok]
    if failed:
        console.print(f"[red bold]FAILED: {', '.join(failed)}")
        raise typer.Exit(1)
    console.print("[green bold]ALL PASSED")


if __name__ == "__main__":
    app()
