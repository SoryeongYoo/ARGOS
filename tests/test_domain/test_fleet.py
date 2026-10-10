"""domain.fleet: 광동체 분류, 턴타임, 기종 호환."""

import pytest

from argos.domain.fleet import (
    MIN_TURN_NARROW_MINUTES,
    MIN_TURN_WIDE_MINUTES,
    TYPE_SUBSTITUTES,
    WIDE_BODY_TYPES,
    compatible_types,
    is_wide_body,
    min_turn_minutes,
)

FLEET = ["B737-800", "A321neo", "B777-300ER", "B787-9", "B747-8i"]


def test_turn_constants_are_unchanged():
    assert MIN_TURN_NARROW_MINUTES == 45
    assert MIN_TURN_WIDE_MINUTES == 60


def test_wide_body_set_is_unchanged():
    assert WIDE_BODY_TYPES == {"B777-300ER", "B787-9", "B747-8i"}


@pytest.mark.parametrize("atype", ["B737-800", "A321neo"])
def test_narrow_body(atype):
    assert is_wide_body(atype) is False
    assert min_turn_minutes(atype) == 45


@pytest.mark.parametrize("atype", ["B777-300ER", "B787-9", "B747-8i"])
def test_wide_body(atype):
    assert is_wide_body(atype) is True
    assert min_turn_minutes(atype) == 60


@pytest.mark.parametrize("atype", ["A380-800", "", "b777-300er"])
def test_unregistered_type_falls_back_to_narrow(atype):
    """미등록 기종(대소문자만 다른 이름 포함)은 예외 없이 협동체로 처리한다."""
    assert is_wide_body(atype) is False
    assert min_turn_minutes(atype) == 45


def test_compatible_types_exact_first_then_priority():
    assert compatible_types("B737-800") == ["B737-800", "A321neo"]
    assert compatible_types("A321neo") == ["A321neo", "B737-800"]
    assert compatible_types("B777-300ER") == ["B777-300ER", "B787-9", "B747-8i"]
    assert compatible_types("B787-9") == ["B787-9", "B777-300ER"]
    assert compatible_types("B747-8i") == ["B747-8i", "B777-300ER", "B787-9"]


def test_compatible_types_unregistered_returns_self_only():
    assert compatible_types("A380-800") == ["A380-800"]
    assert compatible_types("") == [""]


@pytest.mark.parametrize("atype", FLEET)
def test_substitutes_never_cross_body_class(atype):
    """대체 기종은 같은 동체 분류 안에서만. 턴타임과 승무원 자격 그룹이 이 가정에 기댄다."""
    for sub in TYPE_SUBSTITUTES[atype]:
        assert is_wide_body(sub) == is_wide_body(atype)


def test_compatible_types_returns_fresh_list():
    """호출자가 결과를 바꿔도 domain 테이블은 바뀌지 않는다."""
    compatible_types("B737-800").append("X")
    assert compatible_types("B737-800") == ["B737-800", "A321neo"]


def test_substitutes_table_is_read_only():
    with pytest.raises(TypeError):
        TYPE_SUBSTITUTES["B737-800"] = ()  # type: ignore[index]
