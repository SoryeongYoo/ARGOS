"""B7 회귀: fixture DB 에서 0분 지연은 아무 편도 지연시키지 않는다.

기체가 겹치게 배정되면 rotation edge 의 buffer 가 음수가 되고, 지연 0분인 트리거도
max(0, 0 − buffer) > 0 으로 연쇄 지연을 만든다 (B7 수정 전: 146개 트리거 중 145개).
"""

from datetime import date
from pathlib import Path

from argos.simulation.propagation import DelayPropagator

OP_DAY = date(2024, 6, 15)


def _graph(fixture_db_path: str):  # type: ignore[no-untyped-def]
    prop = DelayPropagator(Path(fixture_db_path))
    return prop, prop.build_rotation_graph(prop.load_flights(OP_DAY))


def test_no_negative_buffer_edges(fixture_db_path):
    _, G = _graph(fixture_db_path)
    negative = [
        (u, v, d["buffer_minutes"]) for u, v, d in G.edges(data=True) if d["buffer_minutes"] < 0
    ]
    assert negative == []


def test_zero_delay_trigger_never_cascades(fixture_db_path):
    prop, G = _graph(fixture_db_path)
    cascading = [fid for fid in G.nodes if prop.propagate(G, fid, 0).total_delay_minutes > 0]
    assert cascading == []
