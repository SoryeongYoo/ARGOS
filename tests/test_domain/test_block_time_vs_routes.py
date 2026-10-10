"""routes.py 블록타임(기준 출처)과 calculate_block_time()(추정기)의 차이 감시.

ADR 0001 갱신(2026-10-10): routes.py 가 블록타임의 기준 출처이고, calculate_block_time() 은
routes.py 에 없는 노선용 추정기다. 추정기가 기준에서 ±15% 넘게 벗어나는 (노선, 기종) 은
테스트를 실패시키지 않고 경고로 목록만 낸다. 값 수정은 사람이 결정한다 (routes.py 는 사람 결정
영역).
"""

import warnings

import pytest

from argos.data_gen.routes import ROUTES
from argos.domain.block_time import available_aircraft_types, calculate_block_time

TOLERANCE = 0.15


class BlockTimeDivergenceWarning(UserWarning):
    """추정기와 routes.py 블록타임 차이가 TOLERANCE 를 넘음."""


def _pairs() -> list[tuple[str, str, int, int]]:
    return [
        (r.route_id, t, b, calculate_block_time(r.distance_nm, t))
        for r in ROUTES
        for t, b in r.block_times.items()
    ]


def test_estimator_covers_every_route_type():
    """비교가 빈 검사가 되지 않도록: routes.py 의 모든 기종을 추정기가 계산할 수 있어야 한다."""
    used = {t for r in ROUTES for t in r.block_times}
    assert used <= set(available_aircraft_types())
    assert len(_pairs()) > 0


def test_estimator_within_tolerance_of_routes():
    """±15% 밖 (노선, 기종) 은 경고로 보고만 한다. pytest 요약의 warnings 에 나온다."""
    outliers = [
        f"{route} {atype}: routes={ref} est={est} ({(est - ref) / ref:+.1%})"
        for route, atype, ref, est in _pairs()
        if abs(est - ref) / ref > TOLERANCE
    ]
    if outliers:
        warnings.warn(
            f"{len(outliers)} pair(s) outside ±{TOLERANCE:.0%}: " + "; ".join(outliers),
            BlockTimeDivergenceWarning,
            stacklevel=1,
        )


def test_divergence_warning_does_not_fail(monkeypatch):
    """허용 범위를 0 으로 줄여도 실패하지 않고 경고만 낸다."""
    monkeypatch.setitem(globals(), "TOLERANCE", 0.0)
    with pytest.warns(BlockTimeDivergenceWarning):
        test_estimator_within_tolerance_of_routes()
