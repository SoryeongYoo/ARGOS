"""
Data quality validator for ARGOS flight dataset.
Run before any ML training to ensure the synthetic data is internally consistent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from rich.console import Console
from rich.table import Table

log = logging.getLogger(__name__)
console = Console()


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str        # "error" | "warning" | "info"
    message: str
    affected_rows: int = 0
    detail: str = ""


@dataclass
class ValidationReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == "warning"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def print_summary(self) -> None:
        t = Table(title="ARGOS Data Quality Report", show_lines=True)
        t.add_column("Check", style="cyan", no_wrap=True)
        t.add_column("Status", justify="center")
        t.add_column("Affected rows", justify="right")
        t.add_column("Message", style="dim")

        for r in self.results:
            if r.passed:
                status = "[green]PASS"
            elif r.severity == "warning":
                status = "[yellow]WARN"
            else:
                status = "[red]FAIL"
            t.add_row(r.name, status, f"{r.affected_rows:,}", r.message)

        console.print(t)
        if self.passed:
            console.print(f"[bold green]Result: PASS ({len(self.warnings)} warnings)")
        else:
            console.print(f"[bold red]Result: FAIL ({len(self.errors)} errors, {len(self.warnings)} warnings)")


class DataValidator:
    """Runs a battery of quality checks against the DuckDB flights dataset."""

    # Korean Air industry benchmark: ~78% OTP within 15 min
    OTP_THRESHOLD_MIN = 15
    OTP_BENCHMARK = 0.70     # fail below 70%; warn below 78%
    OTP_WARN_LEVEL = 0.78

    # Sanity bounds
    MAX_REASONABLE_DELAY_MIN = 720   # 12 hours — beyond this is data error
    MAX_CANCEL_RATE = 0.05

    def __init__(self, db_path: str | Path):
        self._path = str(db_path)

    def _conn(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(self._path, read_only=True)

    # ── Individual checks ─────────────────────────────────────────────────────

    def check_table_populated(self) -> CheckResult:
        with self._conn() as con:
            n = con.execute("SELECT COUNT(*) FROM flights").fetchone()[0]
        ok = n > 0
        return CheckResult(
            "table_populated", ok, "error" if not ok else "info",
            f"{n:,} flight records found", affected_rows=n,
        )

    def check_no_duplicate_ids(self) -> CheckResult:
        with self._conn() as con:
            dupes = con.execute(
                "SELECT COUNT(*) FROM (SELECT flight_id FROM flights GROUP BY 1 HAVING COUNT(*) > 1)"
            ).fetchone()[0]
        return CheckResult(
            "no_duplicate_flight_ids", dupes == 0, "error",
            "Duplicate flight_ids" if dupes else "All flight_ids unique",
            affected_rows=dupes,
        )

    def check_required_fields_not_null(self) -> CheckResult:
        required = [
            "flight_id", "flight_number", "route_id", "origin_iata", "dest_iata",
            "aircraft_registration", "aircraft_type", "scheduled_dep_utc",
            "scheduled_arr_utc", "block_time_minutes", "distance_nm",
        ]
        with self._conn() as con:
            nulls = 0
            for col in required:
                n = con.execute(f"SELECT COUNT(*) FROM flights WHERE {col} IS NULL").fetchone()[0]
                nulls += n
        return CheckResult(
            "required_fields_not_null", nulls == 0, "error",
            f"{nulls} nulls in required fields" if nulls else "Required fields complete",
            affected_rows=nulls,
        )

    def check_timestamp_ordering(self) -> CheckResult:
        """arr must be after dep for operated flights."""
        with self._conn() as con:
            bad = con.execute(
                """SELECT COUNT(*) FROM flights
                   WHERE status != 'CNX'
                     AND actual_dep_utc IS NOT NULL
                     AND actual_arr_utc IS NOT NULL
                     AND actual_arr_utc <= actual_dep_utc"""
            ).fetchone()[0]
        return CheckResult(
            "timestamp_ordering", bad == 0, "error",
            f"{bad} flights where arr ≤ dep" if bad else "All arrival timestamps after departure",
            affected_rows=bad,
        )

    def check_load_factor_range(self) -> CheckResult:
        with self._conn() as con:
            bad = con.execute(
                "SELECT COUNT(*) FROM flights WHERE load_factor < 0 OR load_factor > 1"
            ).fetchone()[0]
        return CheckResult(
            "load_factor_range", bad == 0, "error",
            f"{bad} flights with load_factor outside [0,1]" if bad else "Load factors in valid range",
            affected_rows=bad,
        )

    def check_delay_code_consistency(self) -> CheckResult:
        """Flights with dep_delay > 15 min should have a delay code."""
        with self._conn() as con:
            missing_code = con.execute(
                """SELECT COUNT(*) FROM flights
                   WHERE dep_delay_minutes > 15
                     AND delay_code IS NULL
                     AND status != 'CNX'"""
            ).fetchone()[0]
            extra_code = con.execute(
                """SELECT COUNT(*) FROM flights
                   WHERE dep_delay_minutes = 0
                     AND delay_code IS NOT NULL"""
            ).fetchone()[0]
        bad = missing_code + extra_code
        return CheckResult(
            "delay_code_consistency", bad == 0, "warning",
            f"{missing_code} delayed flights missing code; {extra_code} on-time with code" if bad
            else "Delay codes consistent with delay minutes",
            affected_rows=bad,
        )

    def check_cancelled_flight_integrity(self) -> CheckResult:
        """CNX flights should have no actual times and zero pax."""
        with self._conn() as con:
            bad = con.execute(
                """SELECT COUNT(*) FROM flights
                   WHERE status = 'CNX'
                     AND (actual_dep_utc IS NOT NULL
                          OR actual_arr_utc IS NOT NULL
                          OR pax_boarded > 0)"""
            ).fetchone()[0]
        return CheckResult(
            "cancelled_flight_integrity", bad == 0, "error",
            f"{bad} cancelled flights with actual times or pax" if bad
            else "Cancelled flights have clean nulls",
            affected_rows=bad,
        )

    def check_cancellation_rate(self) -> CheckResult:
        with self._conn() as con:
            total, cnx = con.execute(
                "SELECT COUNT(*), SUM(CASE WHEN status='CNX' THEN 1 ELSE 0 END) FROM flights"
            ).fetchone()
        rate = cnx / total if total else 0.0
        ok = rate <= self.MAX_CANCEL_RATE
        return CheckResult(
            "cancellation_rate", ok, "warning" if not ok else "info",
            f"{rate:.2%} cancellation rate ({'> ' if not ok else '≤ '}{self.MAX_CANCEL_RATE:.0%} limit)",
            affected_rows=int(cnx),
        )

    def check_otp_benchmark(self) -> CheckResult:
        """On-Time Performance: % of operated flights departing within 15 min."""
        with self._conn() as con:
            total, on_time = con.execute(
                f"""SELECT COUNT(*), SUM(CASE WHEN dep_delay_minutes <= {self.OTP_THRESHOLD_MIN} THEN 1 ELSE 0 END)
                    FROM flights WHERE status != 'CNX'"""
            ).fetchone()
        otp = on_time / total if total else 0.0
        if otp < self.OTP_BENCHMARK:
            severity, passed = "error", False
        elif otp < self.OTP_WARN_LEVEL:
            severity, passed = "warning", False
        else:
            severity, passed = "info", True
        return CheckResult(
            "otp_benchmark", passed, severity,
            f"OTP D+15 = {otp:.1%} (benchmark: {self.OTP_WARN_LEVEL:.0%})",
            affected_rows=int(total - on_time),
        )

    def check_unreasonable_delays(self) -> CheckResult:
        with self._conn() as con:
            bad = con.execute(
                f"SELECT COUNT(*) FROM flights WHERE dep_delay_minutes > {self.MAX_REASONABLE_DELAY_MIN}"
            ).fetchone()[0]
        return CheckResult(
            "no_unreasonable_delays", bad == 0, "warning",
            f"{bad} flights with delay > {self.MAX_REASONABLE_DELAY_MIN} min" if bad
            else f"No delays exceed {self.MAX_REASONABLE_DELAY_MIN} min",
            affected_rows=bad,
        )

    def check_route_coverage(self) -> CheckResult:
        """Every route in the routes table should have flights."""
        with self._conn() as con:
            empty_routes = con.execute(
                """SELECT COUNT(*) FROM routes r
                   WHERE NOT EXISTS (SELECT 1 FROM flights f WHERE f.route_id = r.route_id)"""
            ).fetchone()[0]
        return CheckResult(
            "route_coverage", empty_routes == 0, "warning",
            f"{empty_routes} routes have no flights" if empty_routes else "All routes have flights",
            affected_rows=empty_routes,
        )

    def check_aircraft_reference_integrity(self) -> CheckResult:
        """All aircraft_registration values must exist in the aircraft table."""
        with self._conn() as con:
            orphans = con.execute(
                """SELECT COUNT(DISTINCT f.aircraft_registration) FROM flights f
                   WHERE NOT EXISTS (SELECT 1 FROM aircraft a WHERE a.registration = f.aircraft_registration)"""
            ).fetchone()[0]
        return CheckResult(
            "aircraft_ref_integrity", orphans == 0, "error",
            f"{orphans} unrecognised registrations" if orphans else "All registrations in fleet table",
            affected_rows=orphans,
        )

    def check_block_time_plausibility(self) -> CheckResult:
        """Block times should be within ±20% of route definition."""
        with self._conn() as con:
            bad = con.execute(
                """SELECT COUNT(*) FROM flights f
                   JOIN route_aircraft ra ON ra.route_id = f.route_id
                                        AND ra.aircraft_type = f.aircraft_type
                   WHERE ABS(f.block_time_minutes - ra.block_time_min) > ra.block_time_min * 0.20"""
            ).fetchone()[0]
        return CheckResult(
            "block_time_plausibility", bad == 0, "warning",
            f"{bad} flights with block time >20% off route definition" if bad
            else "Block times within ±20% of route definition",
            affected_rows=bad,
        )

    def check_date_range(self) -> CheckResult:
        """All flights should be within the expected generation period."""
        with self._conn() as con:
            row = con.execute(
                "SELECT MIN(scheduled_dep_utc)::DATE, MAX(scheduled_dep_utc)::DATE FROM flights"
            ).fetchone()
        if row[0] is None:
            return CheckResult("date_range", False, "error", "No flights", 0)
        return CheckResult(
            "date_range", True, "info",
            f"Date range: {row[0]} → {row[1]}",
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def run_all(self) -> ValidationReport:
        checks = [
            self.check_table_populated,
            self.check_no_duplicate_ids,
            self.check_required_fields_not_null,
            self.check_timestamp_ordering,
            self.check_load_factor_range,
            self.check_delay_code_consistency,
            self.check_cancelled_flight_integrity,
            self.check_cancellation_rate,
            self.check_otp_benchmark,
            self.check_unreasonable_delays,
            self.check_route_coverage,
            self.check_aircraft_reference_integrity,
            self.check_block_time_plausibility,
            self.check_date_range,
        ]
        report = ValidationReport()
        for check_fn in checks:
            try:
                result = check_fn()
            except Exception as exc:
                result = CheckResult(
                    check_fn.__name__, False, "error", f"Check raised: {exc}"
                )
                log.exception("Validator check failed: %s", check_fn.__name__)
            report.results.append(result)
        return report
