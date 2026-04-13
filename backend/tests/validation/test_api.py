"""TEST 6 — API endpoint validation.

Run with:
    uvicorn backend.api.main:app --port 8000 &
    python backend/tests/validation/test_api.py
"""

from __future__ import annotations

import subprocess
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"
STATION_CODE = 10233  # Six Mile Water


def start_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--port", "8000", "--log-level", "error"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait for it to be ready
    for _ in range(20):
        try:
            httpx.get(f"{BASE_URL}/health", timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("API server did not start in time")


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        raise AssertionError(f"FAIL: {label}")


def run_tests(client: httpx.Client) -> None:
    failures: list[str] = []

    # 1. Health check
    print("\n=== 1. GET /health ===")
    r = client.get("/health")
    check("status 200", r.status_code == 200)
    data = r.json()
    check("status=ok", data.get("status") == "ok", str(data))
    check("database field present", "database" in data, str(data))
    print(f"  database: {data['database']}")

    # 2. /stations/geojson?year=2024
    print("\n=== 2. GET /stations/geojson?year=2024 ===")
    r = client.get("/stations/geojson", params={"year": 2024})
    check("status 200", r.status_code == 200)
    fc = r.json()
    check("type=FeatureCollection", fc.get("type") == "FeatureCollection")
    features_2024 = fc["features"]
    meta = fc["metadata"]
    check("has features", len(features_2024) > 0, f"{len(features_2024)} features")
    print(f"  total_stations:        {meta['total_stations']}")
    print(f"  stations_with_data:    {meta['stations_with_data']}")
    print(f"  stations_above_threshold: {meta['stations_above_threshold']}")
    means_2024 = [
        f["properties"]["annual_mean_p_sol"]
        for f in features_2024
        if f["properties"]["annual_mean_p_sol"] is not None
    ]
    mean_2024 = sum(means_2024) / len(means_2024) if means_2024 else None
    print(f"  mean P(SOL) 2024:      {mean_2024:.4f} mg/l" if mean_2024 else "  mean P(SOL) 2024: n/a")

    # 3. /stations/geojson?year=1990 — should be higher than 2024
    print("\n=== 3. GET /stations/geojson?year=1990 ===")
    r = client.get("/stations/geojson", params={"year": 1990})
    check("status 200", r.status_code == 200)
    features_1990 = r.json()["features"]
    means_1990 = [
        f["properties"]["annual_mean_p_sol"]
        for f in features_1990
        if f["properties"]["annual_mean_p_sol"] is not None
    ]
    mean_1990 = sum(means_1990) / len(means_1990) if means_1990 else None
    print(f"  mean P(SOL) 1990:      {mean_1990:.4f} mg/l" if mean_1990 else "  mean P(SOL) 1990: n/a")
    print(f"  mean P(SOL) 2024:      {mean_2024:.4f} mg/l" if mean_2024 else "  mean P(SOL) 2024: n/a")
    if mean_1990 and mean_2024:
        check("1990 mean > 2024 mean (improvement narrative)", mean_1990 > mean_2024,
              f"{mean_1990:.4f} vs {mean_2024:.4f}")

    # 4. Catchment filter — Blackwater
    print("\n=== 4. GET /stations/geojson?year=2024&catchment=Blackwater ===")
    r = client.get("/stations/geojson", params={"year": 2024, "catchment": "Blackwater"})
    check("status 200", r.status_code == 200)
    fc_bw = r.json()
    features_bw = fc_bw["features"]
    check("fewer features than full set", len(features_bw) < len(features_2024),
          f"{len(features_bw)} vs {len(features_2024)}")
    wrong_catchment = [
        f for f in features_bw
        if f["properties"]["catchment_name"] not in (None, "Blackwater")
    ]
    check("all features have catchment_name=Blackwater", len(wrong_catchment) == 0,
          f"{len(wrong_catchment)} mismatched")
    print(f"  Blackwater stations: {len(features_bw)}")

    # 5. Station timeseries — Six Mile Water (10233)
    print(f"\n=== 5. GET /stations/{STATION_CODE}/timeseries ===")
    r = client.get(f"/stations/{STATION_CODE}/timeseries")
    check("status 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    ts = r.json()
    check("station_code matches", ts["station_code"] == STATION_CODE)
    series = ts["series"]
    check("series not empty", len(series) > 0, f"{len(series)} points")
    print(f"  location: {ts['location_name']}")
    print(f"  trend: {ts['trend_direction']} (significant={ts['trend_significant']})")
    print(f"  series points: {len(series)}")
    print("  First 3 years:")
    for pt in series[:3]:
        print(f"    {pt['year']}: {pt['annual_mean_p_sol']} mg/l")
    print("  Last 3 years:")
    for pt in series[-3:]:
        print(f"    {pt['year']}: {pt['annual_mean_p_sol']} mg/l")

    # 6. GET /catchments
    print("\n=== 6. GET /catchments ===")
    r = client.get("/catchments")
    check("status 200", r.status_code == 200)
    catchment_names = r.json()
    check("is a list", isinstance(catchment_names, list))
    check("has catchments", len(catchment_names) > 0, f"{len(catchment_names)} catchments")
    print(f"  catchments ({len(catchment_names)}): {catchment_names[:8]}{'...' if len(catchment_names) > 8 else ''}")

    # 7. GET /catchments/Blackwater/summary?year=2024
    print("\n=== 7. GET /catchments/Blackwater/summary?year=2024 ===")
    r = client.get("/catchments/Blackwater/summary", params={"year": 2024})
    check("status 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    summary = r.json()
    check("catchment_name=Blackwater", summary["catchment_name"] == "Blackwater")
    check("has station_count", summary["station_count"] > 0)
    print(f"  station_count:         {summary['station_count']}")
    print(f"  mean_p_sol:            {summary['mean_p_sol']}")
    print(f"  pct_above_threshold:   {summary['pct_above_threshold']}")


def main() -> None:
    server_proc = start_server()
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            try:
                run_tests(client)
                print("\n✓ PASS — all TEST 6 checks passed")
            except AssertionError as exc:
                print(f"\n✗ FAIL — {exc}")
                sys.exit(1)
    finally:
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    main()
