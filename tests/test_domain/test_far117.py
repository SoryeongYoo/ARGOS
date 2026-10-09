"""FAR 117 골든 테스트 — far117.py 의 표와 한도 상수를 현재 값 그대로 고정한다.

규정 값 변경 시 근거(규정 조항)를 PR에 명시할 것.

이 파일은 현재 동작을 고정하는 것이 목적이다. 기대값을 바꿔야 한다면 먼저
far117.py 를 고치고, 그 근거(14 CFR 117 조항 / 국토교통부 운항기술기준 조항)를
PR 설명에 적은 뒤 이 파일을 같은 PR 에서 갱신한다.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from argos.domain import far117
from argos.domain.far117 import (
    augmented_required,
    check_cumulative_limits,
    is_fdp_legal,
    is_in_wocl,
    max_fdp_hours,
    required_rest_hours,
)

# 보고 시각(현지, 0-23) → 구간 수 1~6 별 최대 FDP(시간), 비증원 승무원
GOLDEN_APPENDIX_B: dict[int, list[float]] = {
    0: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    1: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    2: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    3: [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
    4: [10.0, 10.0, 10.0, 10.0, 9.0, 9.0],
    5: [12.0, 12.0, 12.0, 12.0, 11.5, 11.0],
    6: [13.0, 13.0, 12.0, 12.0, 11.5, 11.0],
    7: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    8: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    9: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    10: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    11: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    12: [13.5, 13.0, 12.0, 12.0, 11.5, 11.0],
    13: [13.0, 13.0, 12.0, 12.0, 11.5, 11.0],
    14: [13.0, 13.0, 12.0, 12.0, 11.5, 11.0],
    15: [13.0, 12.5, 12.0, 12.0, 11.5, 11.0],
    16: [12.5, 12.0, 11.5, 11.5, 11.0, 10.0],
    17: [12.5, 12.0, 11.5, 11.5, 11.0, 10.0],
    18: [12.0, 12.0, 11.5, 11.5, 11.0, 10.0],
    19: [12.0, 12.0, 11.5, 11.5, 11.0, 10.0],
    20: [11.5, 11.5, 11.0, 11.0, 10.5, 10.0],
    21: [11.0, 11.0, 10.5, 10.5, 10.0, 9.5],
    22: [10.5, 10.5, 10.0, 10.0, 9.5, 9.0],
    23: [10.0, 10.0, 10.0, 9.5, 9.0, 9.0],
}

_CELLS = [
    (hour, seg, limit)
    for hour, row in GOLDEN_APPENDIX_B.items()
    for seg, limit in enumerate(row, start=1)
]


# ── 표와 상수 ─────────────────────────────────────────────────────────────────


def test_appendix_b_table_is_unchanged() -> None:
    assert far117._APPENDIX_B == GOLDEN_APPENDIX_B


def test_rest_constants() -> None:
    assert far117._MIN_REST_HOURS == 10.0
    assert far117._MIN_REST_REDUCED == 8.0
    assert far117._MIN_REST_AUGMENTED == 8.0


def test_cumulative_and_extension_constants() -> None:
    assert far117.MAX_FT_CALENDAR_DAY_HOURS == 8.0
    assert far117.MAX_FT_28_DAY_HOURS == 100.0
    assert far117.MAX_FT_YEAR_HOURS == 1000.0
    assert far117.MAX_FDP_EXTENSION == 2.0
    assert far117.LONG_HAUL_MIN_CREW == 3


# ── max_fdp_hours ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("hour", "segments", "limit"), _CELLS)
def test_max_fdp_hours_every_cell(hour: int, segments: int, limit: float) -> None:
    assert max_fdp_hours(hour, segments) == limit


@pytest.mark.parametrize(("hour", "segments", "limit"), _CELLS)
def test_max_fdp_hours_augmented_adds_extension(hour: int, segments: int, limit: float) -> None:
    assert max_fdp_hours(hour, segments, augmented=True) == limit + 2.0


@pytest.mark.parametrize("segments", [7, 8, 12])
def test_max_fdp_hours_clamps_segments_above_six(segments: int) -> None:
    assert max_fdp_hours(10, segments) == max_fdp_hours(10, 6) == 11.0


@pytest.mark.parametrize("segments", [0, -1])
def test_max_fdp_hours_rejects_fewer_than_one_segment(segments: int) -> None:
    # 음수 인덱스로 6구간 값을 조용히 반환하던 동작 방지 (bug-backlog B1)
    with pytest.raises(ValueError, match="num_segments"):
        max_fdp_hours(10, segments)


@pytest.mark.parametrize(("hour", "wrapped"), [(24, 0), (31, 7), (-1, 23)])
def test_max_fdp_hours_wraps_report_hour(hour: int, wrapped: int) -> None:
    assert max_fdp_hours(hour, 1) == max_fdp_hours(wrapped, 1)


# ── is_fdp_legal ─────────────────────────────────────────────────────────────


def test_is_fdp_legal_boundary_is_inclusive() -> None:
    report = datetime(2024, 6, 15, 8, 30)
    assert is_fdp_legal(report, 13.5, 1) == (True, 13.5)
    assert is_fdp_legal(report, 13.51, 1) == (False, 13.5)


def test_is_fdp_legal_uses_report_hour_and_augmentation() -> None:
    report = datetime(2024, 6, 15, 23, 0)
    assert is_fdp_legal(report, 10.0, 2) == (True, 10.0)
    assert is_fdp_legal(report, 11.0, 2, augmented=True) == (True, 12.0)


# ── required_rest_hours ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prior_fdp", "augmented", "rest"),
    [
        (8.0, False, 10.0),
        (12.0, False, 10.0),  # 12h 이하는 기본 10h
        (12.5, False, 11.25),  # 12h 초과는 max(10, fdp * 0.9)
        (15.0, False, 13.5),
        (15.0, True, 8.0),
        (8.0, True, 8.0),
    ],
)
def test_required_rest_hours(prior_fdp: float, augmented: bool, rest: float) -> None:
    assert required_rest_hours(prior_fdp, augmented) == pytest.approx(rest)


# ── WOCL / 누적 한도 / 증원 필요 여부 ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("hour", "expected"),
    [(1, False), (2, True), (5, True), (6, False), (14, False)],
)
def test_is_in_wocl_window(hour: int, expected: bool) -> None:
    assert is_in_wocl(datetime(2024, 6, 15, hour, 59)) is expected


def test_check_cumulative_limits_boundaries() -> None:
    at_limit = check_cumulative_limits([100.0], [1000.0])
    assert at_limit == {
        "28_day_total": 100.0,
        "28_day_limit": 100.0,
        "28_day_legal": True,
        "year_total": 1000.0,
        "year_limit": 1000.0,
        "year_legal": True,
    }
    over = check_cumulative_limits([50.0, 50.5], [999.0, 1.5])
    assert over["28_day_legal"] is False
    assert over["year_legal"] is False


@pytest.mark.parametrize(
    ("fdp", "segments", "expected"),
    [(13.5, 1, False), (13.6, 1, True), (11.0, 6, False), (11.1, 9, True)],
)
def test_augmented_required_uses_0800_reference(fdp: float, segments: int, expected: bool) -> None:
    assert augmented_required(fdp, segments) is expected
