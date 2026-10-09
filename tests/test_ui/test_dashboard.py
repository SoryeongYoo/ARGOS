"""대시보드 스모크 테스트: Streamlit AppTest 로 실제 스크립트를 실행한다.

DB 는 conftest 의 fixture DB 를 DUCKDB_PATH 로 넘긴다. deprecated API 경고는
실패로 본다. Python 경고는 filterwarnings 로, Streamlit 의 deprecation 안내(화면 경고와
streamlit.deprecation_util 로그)는 _assert_clean 으로 잡는다.
st.tabs 는 모든 탭 내용을 한 번의 실행에서 렌더링하므로, 탭 "전환"은 각 탭의
요소가 렌더링됐는지와 탭 안의 버튼 동작이 예외 없이 다시 실행되는지로 확인한다.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

DASHBOARD = Path(__file__).resolve().parents[2] / "src" / "argos" / "ui" / "dashboard.py"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.filterwarnings("error::DeprecationWarning"),
    pytest.mark.filterwarnings("error::FutureWarning"),
    # protobuf C 확장이 import 시점에 내는 Python 3.14 관련 경고. 대시보드 코드와 무관
    pytest.mark.filterwarnings("ignore:Type google._upb._message:DeprecationWarning"),
]


@pytest.fixture
def app(fixture_db_path: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[AppTest]:
    import streamlit as st

    monkeypatch.setenv("DUCKDB_PATH", fixture_db_path)
    st.cache_data.clear()
    at = AppTest.from_file(str(DASHBOARD), default_timeout=60)
    at.run()
    yield at
    st.cache_data.clear()


def _assert_clean(at: AppTest, caplog: pytest.LogCaptureFixture) -> None:
    assert not at.exception, [e.message for e in at.exception]
    shown = [w.value for w in at.warning if "deprecat" in str(w.value).lower()]
    logged = [r.getMessage() for r in caplog.records if r.name == "streamlit.deprecation_util"]
    assert not shown and not logged, shown + logged


def test_initial_render(app: AppTest, caplog: pytest.LogCaptureFixture) -> None:
    _assert_clean(app, caplog)
    assert [t.label for t in app.tabs] == ["OCC 운항 관제", "UAM / ACROSS"]
    assert any(c.value.startswith("DB:") for c in app.sidebar.caption)


def test_occ_tab_simulation(app: AppTest, caplog: pytest.LogCaptureFixture) -> None:
    occ = app.tabs[0]
    assert occ.metric[0].label == "총 항공편"

    app.sidebar.button[0].click().run()

    _assert_clean(app, caplog)
    assert "sim_result" in app.session_state
    labels = [m.label for m in app.tabs[0].metric]
    assert "연쇄 깊이" in labels

    # 회복 시나리오 승인 버튼 (현재는 표시만, D1)
    app.button(key="approve_0").click().run()
    _assert_clean(app, caplog)


def test_uam_tab_submit(app: AppTest, caplog: pytest.LogCaptureFixture) -> None:
    uam = app.tabs[1]
    assert uam.subheader[0].value.startswith("UAM 버티포트 네트워크")

    submit = next(b for b in uam.button if b.label == "ACROSS에 제출")
    submit.click().run()

    _assert_clean(app, caplog)
    results = list(app.tabs[1].success) + list(app.tabs[1].error)
    assert results, "ACROSS 제출 결과가 표시되지 않았다"
