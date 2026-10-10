"""
기단 분류, 지상 턴타임, 기종 호환.

aircraft·crew 최적화와 지연 전파가 같은 값을 쓰도록 여기서 한 번만 정의한다
(ADR 0001). 이전에는 세 모듈에 사본이 있었다.

턴타임은 ICN 과 목적지 공통의 최소 지상 시간이다. 승객 연결 기준인 MCT(`mct.py`)와는 다르다.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

WIDE_BODY_TYPES: frozenset[str] = frozenset({"B777-300ER", "B787-9", "B747-8i"})

MIN_TURN_NARROW_MINUTES = 45
MIN_TURN_WIDE_MINUTES = 60

# 요구 기종 → 운항상 대신 투입할 수 있는 기종 (우선순위 순)
TYPE_SUBSTITUTES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "B737-800": ("A321neo",),
        "A321neo": ("B737-800",),
        "B777-300ER": ("B787-9", "B747-8i"),
        "B787-9": ("B777-300ER",),
        "B747-8i": ("B777-300ER", "B787-9"),
    }
)


def is_wide_body(aircraft_type: str) -> bool:
    """광동체면 True. 미등록 기종은 False (협동체로 취급)."""
    return aircraft_type in WIDE_BODY_TYPES


def min_turn_minutes(aircraft_type: str) -> int:
    """기종별 최소 턴타임(분).

    미등록 기종은 예외 없이 협동체 값(45분)을 반환한다. 통합 전 세 모듈의 동작을 그대로 옮긴 것이다.
    """
    return MIN_TURN_WIDE_MINUTES if is_wide_body(aircraft_type) else MIN_TURN_NARROW_MINUTES


def compatible_types(required_type: str) -> list[str]:
    """required_type 편에 투입할 수 있는 기종. 정확 기종이 먼저, 이어서 대체 기종 우선순위 순.

    미등록 기종은 자기 자신만 반환한다.
    """
    return [required_type, *TYPE_SUBSTITUTES.get(required_type, ())]
