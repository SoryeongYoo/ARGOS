"""PostToolUse(Edit|Write) 훅: 수정된 .py 파일에 ruff check --fix + ruff format 적용.

stdin 으로 받은 훅 JSON 의 tool_input.file_path 를 대상으로 한다.
자동 수정 후에도 남는 ruff 오류는 stderr 로 내보내고 exit 2 → Claude 에게 전달된다.
ruff 를 찾지 못하거나 .py 가 아니면 조용히 종료한다.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _ruff() -> str | None:
    for candidate in (
        ROOT / "venv" / "Scripts" / "ruff.exe",
        ROOT / "venv" / "bin" / "ruff",
        ROOT / ".venv" / "Scripts" / "ruff.exe",
        ROOT / ".venv" / "bin" / "ruff",
    ):
        if candidate.exists():
            return str(candidate)
    return shutil.which("ruff")


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # Windows 기본 cp949 회피
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    path = Path(file_path)
    if path.suffix not in {".py", ".pyi"} or not path.exists():
        return 0
    ruff = _ruff()
    if ruff is None:
        return 0

    check = subprocess.run(
        [ruff, "check", "--fix", "--quiet", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    subprocess.run([ruff, "format", "--quiet", str(path)], cwd=ROOT, capture_output=True)
    if check.returncode != 0:
        print(f"ruff: 자동 수정 후 남은 오류 ({path.name})", file=sys.stderr)
        print(check.stdout + check.stderr, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
