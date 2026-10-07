from argos.data_gen.routes import ROUTES
from argos.domain.block_time import calculate_block_time
from argos.domain.far117 import max_fdp_hours
from argos.domain.mct import FlightType, get_mct

assert len(ROUTES) == 60, f"Expected 60 routes, got {len(ROUTES)}"

bt_nrt = calculate_block_time(696, "B737-800", ci=50)
assert 130 < bt_nrt < 165, f"ICN-NRT block time out of range: {bt_nrt}"

bt_jfk = calculate_block_time(6066, "B747-8i", ci=85)
assert 700 < bt_jfk < 800, f"ICN-JFK block time out of range: {bt_jfk}"

fdp_day = max_fdp_hours(8, 1)
assert fdp_day == 13.5, f"FDP limit wrong: {fdp_day}"

fdp_night = max_fdp_hours(23, 2)
assert fdp_night == 10.0, f"FDP night limit wrong: {fdp_night}"

mct = get_mct(FlightType.INTERNATIONAL, FlightType.INTERNATIONAL)
assert mct == 60, f"MCT wrong: {mct}"

print("PASS - all smoke tests OK")
print(f"  Routes: {len(ROUTES)}")
print(f"  ICN-NRT (B737, CI=50): {bt_nrt} min")
print(f"  ICN-JFK (B747, CI=85): {bt_jfk} min")
print(f"  FDP 08:00/1seg: {fdp_day} h")
print(f"  FDP 23:00/2seg: {fdp_night} h")
print(f"  ICN intl-intl MCT: {mct} min")
