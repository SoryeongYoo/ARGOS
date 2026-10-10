"""domain.rotation: ICN 왕복의 블록인 기준 구간."""

import pytest

from argos.domain.rotation import (
    CREW_CHECK_IN_MINUTES,
    CREW_POST_FLIGHT_MINUTES,
    aircraft_rotation_span,
    crew_duty_span,
    crew_fdp_span,
    icn_block_in_offset,
)


def test_crew_constants_are_unchanged():
    assert CREW_CHECK_IN_MINUTES == 60
    assert CREW_POST_FLIGHT_MINUTES == 30


@pytest.mark.parametrize(("block", "turn"), [(0, 0), (1, 45), (180, 45), (240, 60), (720, 60)])
def test_spans_share_block_in_offset(block, turn):
    offset = 2 * block + turn
    assert icn_block_in_offset(block, turn) == offset
    assert aircraft_rotation_span(block, turn) == offset + turn
    assert crew_duty_span(block, turn) == 60 + offset + 30
    assert crew_fdp_span(block, turn) == 60 + offset


def test_crew_duty_span_examples():
    # test_crew.py 에 있던 _crew_footprint 기대값
    assert crew_duty_span(180, 45) == 495
    assert crew_duty_span(240, 60) == 630


def test_aircraft_rotation_span_example():
    # test_aircraft.py 주석의 예: 2*120 + 2*45 = 330
    assert aircraft_rotation_span(120, 45) == 330


def test_fdp_excludes_post_flight():
    assert crew_duty_span(180, 45) - crew_fdp_span(180, 45) == CREW_POST_FLIGHT_MINUTES


@pytest.mark.parametrize(
    "fn", [icn_block_in_offset, aircraft_rotation_span, crew_duty_span, crew_fdp_span]
)
@pytest.mark.parametrize(
    ("block", "turn", "name"), [(-1, 45, "block_minutes"), (120, -1, "turn_minutes")]
)
def test_negative_input_rejected(fn, block, turn, name):
    with pytest.raises(ValueError, match=name):
        fn(block, turn)
