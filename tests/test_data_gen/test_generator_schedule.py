"""B7 회귀: 합성 스케줄의 기체 배정과 편명이 물리적으로 가능한지.

- 같은 기체의 rotation(출발 ~ aircraft_rotation_span)이 겹치지 않는다.
  결항편도 계획상 기체를 잡는다.
- 같은 날(UTC) 같은 편명은 한 편뿐이다 (B7: KE0005 가 ICN-ORD, ICN-HNL 에 동시에 있었음).
- 기단 규모와 인도일은 ADR 0007 을 따른다.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from argos.config import Settings
from argos.data_gen import generator as gen_mod
from argos.data_gen.generator import FLEET, FLEET_BY_TYPE, SyntheticDataGenerator
from argos.data_gen.routes import ROUTES
from argos.domain.fleet import min_turn_minutes
from argos.domain.rotation import aircraft_rotation_span

START = date(2024, 6, 14)
END = date(2024, 6, 17)  # 여러 날: 장거리 rotation(최대 33h)이 다음 날로 넘어가는 경우 포함


def _generate(start: date = START, end: date = END, routes=ROUTES) -> pd.DataFrame:
    g = SyntheticDataGenerator(Settings(_env_file=None, RANDOM_SEED=42))  # type: ignore[call-arg]
    return g.generate_flights(routes, g.generate_route_params(routes), start, end)


@pytest.fixture(scope="module")
def flights() -> pd.DataFrame:
    return _generate()


def test_fleet_size_per_adr_0007():
    counts = {t: len(v) for t, v in FLEET_BY_TYPE.items()}
    assert counts == {"B737-800": 54, "A321neo": 10, "B777-300ER": 72, "B787-9": 9, "B747-8i": 5}


def test_registrations_unique_and_delivered_before_data_start():
    regs = [a["registration"] for a in FLEET]
    assert len(regs) == len(set(regs))
    assert max(a["delivery_date"] for a in FLEET) < date(2022, 1, 1)


def test_no_same_tail_rotation_overlap(flights):
    df = flights.sort_values(["aircraft_registration", "scheduled_dep_utc"])
    spans = [
        aircraft_rotation_span(b, min_turn_minutes(t))
        for b, t in zip(df.block_time_minutes, df.aircraft_type, strict=True)
    ]
    df = df.assign(end=df.scheduled_dep_utc + pd.to_timedelta(spans, unit="m"))
    nxt = df.groupby("aircraft_registration").scheduled_dep_utc.shift(-1)
    overlap = df[nxt < df.end]
    assert overlap.empty, overlap[["aircraft_registration", "route_id", "scheduled_dep_utc"]]


def test_tail_type_matches_flight_type(flights):
    reg_type = {a["registration"]: a["aircraft_type"] for a in FLEET}
    assert (flights.aircraft_registration.map(reg_type) == flights.aircraft_type).all()


def test_flight_number_unique_per_utc_day(flights):
    key = flights.assign(d=flights.scheduled_dep_utc.dt.date).groupby(["d", "flight_number"])
    dup = key.size()
    assert (dup == 1).all(), dup[dup > 1]


def test_flight_number_stable_per_route_slot(flights):
    """같은 노선·같은 시간대 편은 매일 같은 편명이다."""
    f = flights.assign(slot_hour=flights.scheduled_dep_utc.dt.hour)
    assert (f.groupby(["route_id", "slot_hour"]).flight_number.nunique() == 1).all()


def test_flight_numbers_independent_of_previous_generators():
    """편명 카운터가 인스턴스 사이에 공유되면 두 번째 생성 결과가 달라진다."""
    a = _generate(START, START)
    b = _generate(START, START)
    assert list(a.flight_number) == list(b.flight_number)


def test_insufficient_fleet_raises(monkeypatch):
    """기체가 모자라면 겹치게 배정하지 않고 실패한다."""
    tiny = {t: v[:1] for t, v in FLEET_BY_TYPE.items()}
    monkeypatch.setattr(gen_mod, "FLEET_BY_TYPE", tiny)
    nrt = [r for r in ROUTES if r.route_id == "ICN-NRT"]  # 하루 4편, 기체 1대로는 불가능
    with pytest.raises(ValueError, match="B737-800"):
        _generate(START, START + timedelta(days=1), routes=nrt)
