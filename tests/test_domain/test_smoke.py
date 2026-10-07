"""scripts/_smoke_test.py 에서 이관한 도메인 스모크 테스트 (assert 그대로 유지)."""

from __future__ import annotations

from argos.data_gen.routes import ROUTES
from argos.domain.block_time import calculate_block_time
from argos.domain.far117 import max_fdp_hours
from argos.domain.mct import FlightType, get_mct


def test_route_count() -> None:
    assert len(ROUTES) == 60


def test_block_time_icn_nrt_b737() -> None:
    assert 130 < calculate_block_time(696, "B737-800", ci=50) < 165


def test_block_time_icn_jfk_b747() -> None:
    assert 700 < calculate_block_time(6066, "B747-8i", ci=85) < 800


def test_fdp_day_and_night() -> None:
    assert max_fdp_hours(8, 1) == 13.5
    assert max_fdp_hours(23, 2) == 10.0


def test_mct_icn_intl_intl() -> None:
    assert get_mct(FlightType.INTERNATIONAL, FlightType.INTERNATIONAL) == 60
