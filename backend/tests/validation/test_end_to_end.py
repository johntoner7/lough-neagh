"""TEST 11 — End-to-end validation and deployment gate.

Run with:
    uv run python backend/tests/validation/test_end_to_end.py

This script validates:
1) DB integrity and expected record coverage
2) API behaviour for key narrative checks
3) Spatial sanity for station 10233
4) Annual refresh idempotency on a small existing-data CSV slice
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

BASE_URL = "http://127.0.0.1:8000"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
KEY_STATIONS = [10212, 10233, 10271, 10328, 10361, 10380]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def add_result(results: list[CheckResult], name: str, ok: bool, detail: str = "") -> None:
    results.append(CheckResult(name=name, ok=ok, detail=detail))
    status = "OK" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"  [{status}] {name}{suffix}")


def start_server() -> subprocess.Popen:
    """Start API server and wait until /health is ready."""
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api.main:app",
            "--port",
            "8000",
            "--log-level",
            "error",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(40):
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
        time.sleep(0.5)

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    raise RuntimeError("API server did not start in time")


def run_db_checks(results: list[CheckResult]) -> None:
    print("\n=== 1) DB checks ===")

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        stations_count = int(conn.execute(text("SELECT COUNT(*) FROM stations")).scalar_one())
        readings_count = int(conn.execute(text("SELECT COUNT(*) FROM readings")).scalar_one())
        metrics_count = int(conn.execute(text("SELECT COUNT(*) FROM annual_metrics")).scalar_one())
        trends_count = int(conn.execute(text("SELECT COUNT(*) FROM trend_results")).scalar_one())

        add_result(results, "stations table has 1201 rows", stations_count == 1201, f"got {stations_count}")
        add_result(results, "readings table is ~170k", 165000 <= readings_count <= 175000, f"got {readings_count}")
        add_result(results, "annual_metrics populated", metrics_count > 1000, f"got {metrics_count}")
        add_result(results, "trend_results populated", trends_count > 100, f"got {trends_count}")

        key_metrics_rows = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM annual_metrics
                    WHERE station_code = ANY(:codes)
                    """
                ),
                {"codes": KEY_STATIONS},
            ).scalar_one()
        )
        add_result(
            results,
            "annual_metrics include six key stations",
            key_metrics_rows >= 6 * 30,
            f"rows for key stations={key_metrics_rows}",
        )

        key_trend_rows = int(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM trend_results
                    WHERE station_code = ANY(:codes)
                    """
                ),
                {"codes": KEY_STATIONS},
            ).scalar_one()
        )
        add_result(
            results,
            "trend_results include six key stations",
            key_trend_rows == 6,
            f"got {key_trend_rows}",
        )


def run_api_checks(results: list[CheckResult]) -> None:
    print("\n=== 2) API checks ===")

    with httpx.Client(base_url=BASE_URL, timeout=20) as client:
        health = client.get("/health")
        add_result(results, "/health returns 200", health.status_code == 200, f"status={health.status_code}")

        r1990 = client.get("/stations/geojson", params={"year": 1990})
        r2024 = client.get("/stations/geojson", params={"year": 2024})

        add_result(results, "/stations/geojson?year=1990 returns 200", r1990.status_code == 200)
        add_result(results, "/stations/geojson?year=2024 returns 200", r2024.status_code == 200)

        if r1990.status_code == 200 and r2024.status_code == 200:
            fc1990 = r1990.json()
            fc2024 = r2024.json()

            means_1990 = [
                f["properties"]["annual_mean_p_sol"]
                for f in fc1990["features"]
                if f["properties"]["annual_mean_p_sol"] is not None
            ]
            means_2024 = [
                f["properties"]["annual_mean_p_sol"]
                for f in fc2024["features"]
                if f["properties"]["annual_mean_p_sol"] is not None
            ]

            mean_1990 = sum(means_1990) / len(means_1990) if means_1990 else None
            mean_2024 = sum(means_2024) / len(means_2024) if means_2024 else None

            add_result(
                results,
                "1990 API mean P(SOL) > 0.15",
                mean_1990 is not None and mean_1990 > 0.15,
                f"mean_1990={mean_1990}",
            )
            add_result(
                results,
                "2024 API mean P(SOL) < 0.10",
                mean_2024 is not None and mean_2024 < 0.10,
                f"mean_2024={mean_2024}",
            )

            data_by_code = {
                int(f["properties"]["station_code"]): f["properties"]["annual_mean_p_sol"]
                for f in fc2024["features"]
            }
            missing = [code for code in KEY_STATIONS if data_by_code.get(code) is None]
            add_result(
                results,
                "all six key stations have non-null 2024 annual mean",
                len(missing) == 0,
                f"missing={missing}",
            )

        upper_bann = client.get("/stations/10271/timeseries")
        moyola = client.get("/stations/10380/timeseries")

        add_result(results, "/stations/10271/timeseries returns 200", upper_bann.status_code == 200)
        add_result(results, "/stations/10380/timeseries returns 200", moyola.status_code == 200)

        if upper_bann.status_code == 200:
            trend = upper_bann.json().get("trend_direction")
            add_result(
                results,
                "Upper Bann trend is not decreasing",
                trend != "decreasing",
                f"trend_direction={trend}",
            )

        if moyola.status_code == 200:
            series = moyola.json().get("series", [])
            y1990 = next((pt for pt in series if pt.get("year") == 1990), None)
            val = y1990.get("annual_mean_p_sol") if y1990 else None
            add_result(
                results,
                "Moyola 1990 annual mean > 0.10",
                val is not None and val > 0.10,
                f"value={val}",
            )


def run_spatial_check(results: list[CheckResult]) -> None:
    print("\n=== 3) Spatial check ===")

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    station_code,
                    location_name,
                    easting,
                    northing,
                    ST_Distance(
                        geom,
                        ST_SetSRID(ST_MakePoint(easting, northing), 29902)
                    ) AS dist_to_source_point
                FROM stations
                WHERE station_code = 10233
                """
            )
        ).mappings().first()

    if not row:
        add_result(results, "station 10233 exists for spatial check", False)
        return

    geom_matches_source = float(row["dist_to_source_point"] or 0.0) <= 1.0
    six_mile_named = "SIX MILE" in str(row["location_name"] or "").upper()
    in_reasonable_bounds = (
        150000 <= int(row["easting"]) <= 360000
        and 300000 <= int(row["northing"]) <= 470000
    )

    add_result(
        results,
        "station 10233 geometry matches source easting/northing",
        geom_matches_source,
        f"distance={row['dist_to_source_point']}",
    )
    add_result(
        results,
        "station 10233 is identified as Six Mile station",
        six_mile_named,
        f"location_name={row['location_name']}",
    )
    add_result(
        results,
        "station 10233 coordinates are within NI Irish Grid bounds",
        in_reasonable_bounds,
        f"easting={row['easting']}, northing={row['northing']}",
    )


def create_small_existing_csv(source_csv: Path, output_csv: Path, nrows: int = 250) -> None:
    """Write a small CSV slice from existing FOI file; rows should already exist in DB."""
    with source_csv.open("r", encoding="utf-8", newline="") as src, output_csv.open(
        "w", encoding="utf-8", newline=""
    ) as dst:
        reader = csv.reader(src)
        writer = csv.writer(dst)

        for idx, row in enumerate(reader):
            writer.writerow(row)
            if idx >= nrows:
                break


def run_prefect_check(results: list[CheckResult]) -> None:
    print("\n=== 4) Prefect annual refresh check ===")

    source_csv = Path("data/raw/foi/annex_a.csv")
    if not source_csv.exists():
        add_result(results, "annex_a.csv available for refresh test", False, "data/raw/foi/annex_a.csv not found")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        small_csv = Path(tmpdir) / "small_existing_slice.csv"
        create_small_existing_csv(source_csv, small_csv)

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "backend.pipeline.flows.annual_refresh",
                "--csv-path",
                str(small_csv),
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        add_result(
            results,
            "annual_refresh command exits successfully",
            proc.returncode == 0,
            f"returncode={proc.returncode}",
        )

        output = f"{proc.stdout}\n{proc.stderr}"
        add_result(
            results,
            "annual_refresh reports 0 new readings",
            "new_readings: 0" in output,
            "expected 'new_readings: 0' in output",
        )


def main() -> None:
    results: list[CheckResult] = []

    print("=== TEST 11: END-TO-END VALIDATION ===")
    print(f"Database URL: {DATABASE_URL}")

    try:
        run_db_checks(results)

        server = start_server()
        try:
            run_api_checks(results)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()

        run_spatial_check(results)
        run_prefect_check(results)

    except Exception as exc:
        add_result(results, "unexpected exception", False, str(exc))

    print("\n=== 5) Final report ===")
    failures = [r for r in results if not r.ok]
    for r in results:
        status = "PASS" if r.ok else "FAIL"
        suffix = f" — {r.detail}" if r.detail else ""
        print(f"- {status}: {r.name}{suffix}")

    if failures:
        print(f"\n✗ FAIL — {len(failures)} check(s) failed")
        raise SystemExit(1)

    print("\n✓ PASS — all Phase 11 checks passed")


if __name__ == "__main__":
    main()
