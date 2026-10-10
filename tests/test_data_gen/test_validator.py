"""Unit tests for the data quality validator."""

import uuid
from datetime import UTC, datetime

import duckdb
import pytest

from argos.data_gen.validator import DataValidator, ValidationReport


@pytest.fixture
def clean_db(tmp_path):
    """DuckDB with a small but clean flight dataset."""
    db_path = tmp_path / "test.duckdb"
    con = duckdb.connect(str(db_path))

    con.execute("""
        CREATE TABLE routes (
            route_id VARCHAR PRIMARY KEY, origin_iata VARCHAR, origin_icao VARCHAR,
            dest_iata VARCHAR, dest_icao VARCHAR, dest_name VARCHAR,
            region VARCHAR, distance_nm INTEGER, frequency_per_day FLOAT
        )
    """)
    con.execute("""
        CREATE TABLE aircraft (
            registration VARCHAR PRIMARY KEY, aircraft_type VARCHAR, icao_type VARCHAR,
            manufacturer_serial VARCHAR, delivery_date DATE,
            seat_config_y INTEGER, seat_config_c INTEGER, seat_config_f INTEGER,
            max_payload_kg INTEGER, mtow_kg INTEGER
        )
    """)
    con.execute("""
        CREATE TABLE route_aircraft (
            route_id VARCHAR, aircraft_type VARCHAR, block_time_min INTEGER, priority INTEGER,
            PRIMARY KEY (route_id, aircraft_type)
        )
    """)
    con.execute("""
        CREATE TABLE delay_codes_ref (code VARCHAR PRIMARY KEY, description VARCHAR)
    """)
    con.execute("""
        CREATE TABLE flights (
            flight_id VARCHAR PRIMARY KEY, flight_number VARCHAR, route_id VARCHAR,
            origin_iata VARCHAR, dest_iata VARCHAR, aircraft_registration VARCHAR,
            aircraft_type VARCHAR, scheduled_dep_utc TIMESTAMPTZ, scheduled_arr_utc TIMESTAMPTZ,
            actual_dep_utc TIMESTAMPTZ, actual_arr_utc TIMESTAMPTZ,
            block_time_minutes INTEGER, distance_nm INTEGER,
            dep_delay_minutes INTEGER DEFAULT 0, arr_delay_minutes INTEGER DEFAULT 0,
            delay_code VARCHAR(2), delay_subcode VARCHAR, delay_responsibility VARCHAR(3),
            pax_boarded INTEGER DEFAULT 0, load_factor FLOAT, fuel_uplift_kg INTEGER,
            cargo_kg INTEGER, status VARCHAR(3) DEFAULT 'SCH', cancel_reason VARCHAR
        )
    """)

    # Seed reference data
    con.execute(
        "INSERT INTO routes VALUES "
        "('ICN-NRT','ICN','RKSI','NRT','RJAA','Tokyo Narita','Japan',696,4.0)"
    )
    con.execute(
        "INSERT INTO aircraft VALUES "
        "('HL7401','B737-800','B738','MSN1','2010-01-01',147,8,0,20000,79016)"
    )
    con.execute("INSERT INTO route_aircraft VALUES ('ICN-NRT','B737-800',145,0)")
    con.execute("INSERT INTO delay_codes_ref VALUES ('71','ATC en-route demand')")

    dep = datetime(2024, 6, 1, 1, 0, tzinfo=UTC)
    arr = datetime(2024, 6, 1, 3, 25, tzinfo=UTC)
    con.execute(
        """
        INSERT INTO flights VALUES (?, 'KE001', 'ICN-NRT', 'ICN', 'NRT', 'HL7401', 'B737-800',
            ?, ?, ?, ?, 145, 696, 0, 0, NULL, NULL, NULL, 140, 0.90, 8500, 2000, 'ARR', NULL)
    """,
        [str(uuid.uuid4()), dep, arr, dep, arr],
    )

    con.close()
    return str(db_path)


def test_clean_dataset_passes_all_checks(clean_db):
    report = DataValidator(clean_db).run_all()
    assert report.passed
    errors = report.errors
    assert errors == [], f"Unexpected errors: {[e.name for e in errors]}"


def test_duplicate_ids_detected(clean_db):
    con = duckdb.connect(clean_db)
    fid = str(uuid.uuid4())
    dep = datetime(2024, 6, 2, 1, 0, tzinfo=UTC)
    arr = datetime(2024, 6, 2, 3, 25, tzinfo=UTC)
    for _ in range(2):
        try:
            con.execute(
                """
                INSERT INTO flights VALUES (?, 'KE002','ICN-NRT','ICN','NRT','HL7401','B737-800',
                    ?,?,?,?,145,696,0,0,NULL,NULL,NULL,130,0.85,8000,1500,'ARR',NULL)
            """,
                [fid, dep, arr, dep, arr],
            )
        except Exception:
            pass  # second insert violates PK — expected
    con.close()

    report = DataValidator(clean_db).run_all()
    dup_check = next(r for r in report.results if r.name == "no_duplicate_flight_ids")
    assert dup_check.passed  # PK constraint prevents duplicates in DuckDB


def test_timestamp_ordering_detects_bad_data(clean_db):
    con = duckdb.connect(clean_db)
    dep = datetime(2024, 6, 3, 10, 0, tzinfo=UTC)
    arr = datetime(2024, 6, 3, 8, 0, tzinfo=UTC)  # arr BEFORE dep — invalid
    con.execute(
        """
        INSERT INTO flights VALUES (?, 'KE003','ICN-NRT','ICN','NRT','HL7401','B737-800',
            ?,?,?,?,145,696,0,0,NULL,NULL,NULL,130,0.85,8000,1500,'ARR',NULL)
    """,
        [str(uuid.uuid4()), dep, dep, dep, arr],
    )
    con.close()

    report = DataValidator(clean_db).run_all()
    ts_check = next(r for r in report.results if r.name == "timestamp_ordering")
    assert not ts_check.passed
    assert ts_check.affected_rows >= 1


def test_load_factor_out_of_range_detected(clean_db):
    con = duckdb.connect(clean_db)
    dep = datetime(2024, 6, 4, 1, 0, tzinfo=UTC)
    arr = datetime(2024, 6, 4, 3, 25, tzinfo=UTC)
    con.execute(
        """
        INSERT INTO flights VALUES (?, 'KE004','ICN-NRT','ICN','NRT','HL7401','B737-800',
            ?,?,?,?,145,696,0,0,NULL,NULL,NULL,130,1.50,8000,1500,'ARR',NULL)
    """,
        [str(uuid.uuid4()), dep, dep, dep, arr],
    )
    con.close()

    report = DataValidator(clean_db).run_all()
    lf_check = next(r for r in report.results if r.name == "load_factor_range")
    assert not lf_check.passed


def test_otp_benchmark_warn_when_low(clean_db):
    con = duckdb.connect(clean_db)
    dep = datetime(2024, 6, 5, 1, 0, tzinfo=UTC)
    # Insert 10 massively delayed flights
    for i in range(10):  # noqa: B007 — 미사용 루프 변수, 로직 검토 필요
        arr = dep + __import__("datetime").timedelta(minutes=145 + 300)
        con.execute(
            """
            INSERT INTO flights VALUES (?, 'KE010','ICN-NRT','ICN','NRT','HL7401','B737-800',
                ?,?,?,?,145,696,300,300,'71',NULL,'ATC',130,0.85,8000,1500,'ARR',NULL)
        """,
            [str(uuid.uuid4()), dep, dep, dep, arr],
        )
    con.close()

    report = DataValidator(clean_db).run_all()
    otp_check = next(r for r in report.results if r.name == "otp_benchmark")
    # With 1 clean + 10 delayed(300min), OTP will be ~9% → fail
    assert not otp_check.passed


def test_cancelled_flight_integrity(clean_db):
    con = duckdb.connect(clean_db)
    dep = datetime(2024, 6, 6, 1, 0, tzinfo=UTC)
    arr = datetime(2024, 6, 6, 3, 25, tzinfo=UTC)
    # CNX flight with actual times — integrity violation
    con.execute(
        """
        INSERT INTO flights VALUES (?, 'KE005','ICN-NRT','ICN','NRT','HL7401','B737-800',
            ?,?,?,?,145,696,0,0,NULL,NULL,NULL,0,0.0,0,0,'CNX',NULL)
    """,
        [str(uuid.uuid4()), dep, arr, dep, arr],
    )  # actual times present on CNX
    con.close()

    report = DataValidator(clean_db).run_all()
    cnx_check = next(r for r in report.results if r.name == "cancelled_flight_integrity")
    assert not cnx_check.passed


def test_validation_report_structure():
    report = ValidationReport()
    assert report.passed  # empty report = no errors
    assert report.errors == []
    assert report.warnings == []


def _insert(con, fnum, reg, dep, block=145):
    from datetime import timedelta

    arr = dep + timedelta(minutes=block)
    con.execute(
        """
        INSERT INTO flights VALUES (?, ?, 'ICN-NRT', 'ICN', 'NRT', ?, 'B737-800',
            ?, ?, ?, ?, ?, 696, 0, 0, NULL, NULL, NULL, 140, 0.90, 8500, 2000, 'ARR', NULL)
    """,
        [str(uuid.uuid4()), fnum, reg, dep, arr, dep, arr, block],
    )


def test_aircraft_rotation_overlap_is_error(clean_db):
    """B7: 같은 기체가 앞 rotation(2·145 + 2·45 = 380분) 안에 다시 출발하면 오류."""
    con = duckdb.connect(clean_db)
    # clean_db 의 KE001 은 2024-06-01 01:00 HL7401. 06:19 출발은 1분 겹침
    _insert(con, "KE009", "HL7401", datetime(2024, 6, 1, 7, 19, tzinfo=UTC))
    con.close()
    report = DataValidator(clean_db).run_all()
    check = next(r for r in report.results if r.name == "no_aircraft_rotation_overlap")
    assert not check.passed
    assert check.severity == "error"
    assert check.affected_rows == 1
    assert not report.passed


def test_aircraft_rotation_back_to_back_is_ok(clean_db):
    con = duckdb.connect(clean_db)
    _insert(con, "KE009", "HL7401", datetime(2024, 6, 1, 7, 20, tzinfo=UTC))  # 정확히 380분 뒤
    con.close()
    check = next(
        r
        for r in DataValidator(clean_db).run_all().results
        if r.name == "no_aircraft_rotation_overlap"
    )
    assert check.passed


def test_duplicate_flight_number_same_day_is_error(clean_db):
    """B7: 같은 UTC 날짜에 같은 편명이 두 번 나오면 오류."""
    con = duckdb.connect(clean_db)
    con.execute(
        "INSERT INTO aircraft VALUES "
        "('HL7402','B737-800','B738','MSN2','2010-01-01',147,8,0,20000,79016)"
    )
    _insert(con, "KE001", "HL7402", datetime(2024, 6, 1, 9, 0, tzinfo=UTC))
    con.close()
    report = DataValidator(clean_db).run_all()
    check = next(r for r in report.results if r.name == "no_duplicate_flight_number_per_day")
    assert not check.passed
    assert check.severity == "error"
    assert not report.passed
