"""
ICN 출발 왕복 rotation 의 시간 구간.

모든 rotation 은 ICN 출발 → 목적지 → ICN 복귀다 (conventions "ICN 출발 왕복 가정").
기체와 승무원은 같은 왕복을 타지만 묶이는 구간이 다르다. 그래서 공식을 하나로 합치지 않고
공통 기준(ICN 블록인)에서 이름을 나눠 정의한다.

    dep ──block──► 목적지 ──turn──► 출발 ──block──► ICN 블록인 ──turn──► 다음 ICN 출발 가능
    │◄──────────── icn_block_in_offset ────────────►│
    │◄──────────── aircraft_rotation_span ──────────────────────────────►│
 check-in ◄─60─ dep              ICN 블록인 ─30─► release
    │◄──────────── crew_duty_span (check-in ~ release) ─────────────────►│
    │◄──────────── crew_fdp_span (check-in ~ 블록인) ─────►│

모든 함수는 분 단위 정수를 받고 돌려준다. 턴타임은 `fleet.min_turn_minutes` 로 구해서 넘긴다.
"""

from __future__ import annotations

CREW_CHECK_IN_MINUTES = 60  # 출발 전 출근 보고
CREW_POST_FLIGHT_MINUTES = 30  # ICN 블록인 뒤 마무리 업무


def _require_non_negative(**values: int) -> None:
    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")


def icn_block_in_offset(block_minutes: int, turn_minutes: int) -> int:
    """ICN 출발부터 ICN 복귀 블록인까지 (분) = 2·block + turn (목적지 턴 1회).

    Raises:
        ValueError: block_minutes 또는 turn_minutes 가 음수일 때.
    """
    _require_non_negative(block_minutes=block_minutes, turn_minutes=turn_minutes)
    return 2 * block_minutes + turn_minutes


def aircraft_rotation_span(block_minutes: int, turn_minutes: int) -> int:
    """ICN 출발부터 다음 ICN 출발이 가능해질 때까지 (분) = 블록인 + ICN 턴.

    aircraft 최적화의 no-overlap 구간과 지연 전파의 rotation 최소 간격에 쓴다.
    """
    return icn_block_in_offset(block_minutes, turn_minutes) + turn_minutes


def crew_duty_span(block_minutes: int, turn_minutes: int) -> int:
    """승무원 근무 구간 (분) = check-in(60) + 블록인 + 마무리(30). 출발 60분 전부터 센다.

    crew 최적화의 no-overlap 구간이다. FAR 117 FDP 가 아니다 (`crew_fdp_span`).
    """
    return (
        CREW_CHECK_IN_MINUTES
        + icn_block_in_offset(block_minutes, turn_minutes)
        + CREW_POST_FLIGHT_MINUTES
    )


def crew_fdp_span(block_minutes: int, turn_minutes: int) -> int:
    """FAR 117 FDP 구간 (분) = check-in(60) + 블록인. 블록인 뒤 마무리 시간은 넣지 않는다.

    아직 런타임에서 쓰지 않는다. fdp-hard-constraint 계획에서 crew 의 FDP 판정을 이 값으로 바꾼다.
    """
    return CREW_CHECK_IN_MINUTES + icn_block_in_offset(block_minutes, turn_minutes)
