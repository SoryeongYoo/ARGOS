"""상태를 바꾸는 스크립트는 --yes 없이 아무것도 바꾸지 않아야 한다."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
runner = CliRunner()


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_script_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "db" / "argos.duckdb"
    monkeypatch.setenv("DUCKDB_PATH", str(db))
    return db


def test_setup_db_dry_run_creates_nothing(tmp_db: Path) -> None:
    result = runner.invoke(_load("setup_db").app, [])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert not tmp_db.exists()
    assert not tmp_db.parent.exists()


def test_setup_db_yes_creates_schema(tmp_db: Path) -> None:
    result = runner.invoke(_load("setup_db").app, ["--yes"])
    assert result.exit_code == 0, result.output
    assert tmp_db.exists()


def test_generate_data_dry_run_leaves_db_untouched(tmp_db: Path) -> None:
    runner.invoke(_load("setup_db").app, ["--yes"])
    before = tmp_db.read_bytes()

    result = runner.invoke(
        _load("generate_data").app, ["--start", "2024-06-15", "--end", "2024-06-15"]
    )
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "flights" in result.output
    assert tmp_db.read_bytes() == before


def test_train_model_dry_run_writes_no_model(tmp_db: Path, tmp_path: Path) -> None:
    runner.invoke(_load("setup_db").app, ["--yes"])
    model = tmp_path / "model.lgb"

    result = runner.invoke(_load("train_model").app, ["--model-path", str(model)])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert not model.exists()
