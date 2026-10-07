"""
문서 상대 링크 검사.

CLAUDE.md 와 docs/**/*.md 의 [text](path) 가 실제 파일·디렉터리를 가리키는지 확인한다.

Usage:
    python scripts/check_doc_links.py

http(s)/mailto 링크와 같은 문서 내 앵커(#...)는 건너뛴다. 코드 블록 안은 검사하지 않는다.
깨진 링크가 하나라도 있으면 exit 1.
"""

import re
from pathlib import Path
from urllib.parse import unquote

import typer
from rich.console import Console

ROOT = Path(__file__).resolve().parent.parent
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "#")

app = typer.Typer(add_completion=False)
console = Console()


def _doc_files() -> list[Path]:
    return [ROOT / "CLAUDE.md", *sorted((ROOT / "docs").rglob("*.md"))]


def _links(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    in_code = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        found.extend((lineno, m.group(1)) for m in LINK_RE.finditer(line))
    return found


@app.command()
def check() -> None:
    broken: list[str] = []
    total = 0
    for doc in _doc_files():
        for lineno, target in _links(doc.read_text(encoding="utf-8")):
            if target.startswith(SKIP_PREFIXES):
                continue
            total += 1
            path = unquote(target.split("#", 1)[0])
            if not (doc.parent / path).exists():
                broken.append(f"{doc.relative_to(ROOT)}:{lineno} -> {target}")

    for b in broken:
        console.print(f"[red]BROKEN[/] {b}")
    console.print(
        f"checked {total} relative links in {len(_doc_files())} files, {len(broken)} broken"
    )
    if broken:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
