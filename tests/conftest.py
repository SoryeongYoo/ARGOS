"""공용 pytest fixture.

DB 의존 테스트는 로컬 data/db/argos.duckdb 대신 세션마다 임시 경로에 생성한
하루치(2024-06-15, seed 42) 합성 데이터를 쓴다. 새 클론이나 CI 에서도 skip 없이 돈다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

FIXTURE_DATE = date(2024, 6, 15)
FIXTURE_SEED = 42


@pytest.fixture(scope="session")
def fixture_db_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    """임시 DuckDB 경로. 60개 노선 전체, FIXTURE_DATE 하루치 데이터."""
    from argos.config import Settings
    from argos.data_gen.generator import SyntheticDataGenerator
    from argos.data_gen.routes import ROUTES

    db_path: Path = tmp_path_factory.mktemp("argos_db") / "argos.duckdb"
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        DUCKDB_PATH=db_path,
        RANDOM_SEED=FIXTURE_SEED,
    )
    SyntheticDataGenerator(settings).run(ROUTES, FIXTURE_DATE, FIXTURE_DATE)
    return str(db_path)
