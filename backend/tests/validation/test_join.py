from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from backend.pipeline.ingest.foi import load_and_clean_foi
from backend.pipeline.ingest.wfd_sites import load_wfd_sites
from backend.pipeline.process.join import enrich_stations


EXPECTED_TOTAL = 1201
EXPECTED_MATCHED = 525
EXPECTED_UNMATCHED = 676
KEY_STATIONS = {
    10233: "Six Mile Water",
    10212: "River Main",
    10380: "Moyola",
    10361: "Ballinderry",
    10328: "Blackwater",
    10271: "Upper Bann",
}


def _resolve_paths() -> tuple[Path, Path]:
    foi = Path("data/raw/foi/annex_a.csv")
    wfd = Path("data/raw/wfd_sites/WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson")

    if not foi.exists():
        foi = Path("annex_a.csv")
    if not wfd.exists():
        wfd = Path("WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson")

    if not foi.exists():
        raise FileNotFoundError("FOI CSV not found")
    if not wfd.exists():
        raise FileNotFoundError("WFD sites GeoJSON not found")

    return foi, wfd


def main() -> None:
    foi_path, wfd_path = _resolve_paths()

    stations_df, _ = load_and_clean_foi(str(foi_path))
    wfd_gdf = load_wfd_sites(str(wfd_path))
    enriched = enrich_stations(stations_df, wfd_gdf)

    failures: list[str] = []

    print("=== TEST 2: JOIN SANITY CHECK ===")
    print(f"FOI source: {foi_path}")
    print(f"WFD source: {wfd_path}")
    print(f"Total station count: {len(enriched)}")

    if len(enriched) != EXPECTED_TOTAL:
        failures.append(f"Expected total {EXPECTED_TOTAL}, got {len(enriched)}")

    counts = enriched["wfd_matched"].value_counts(dropna=False)
    matched = int(counts.get(True, 0))
    unmatched = int(counts.get(False, 0))
    print("wfd_matched counts:")
    print(counts.to_string())

    if matched != EXPECTED_MATCHED:
        failures.append(f"Expected matched {EXPECTED_MATCHED}, got {matched}")
    if unmatched != EXPECTED_UNMATCHED:
        failures.append(f"Expected unmatched {EXPECTED_UNMATCHED}, got {unmatched}")

    print("\nKey tributary station checks:")
    for station_code, name in KEY_STATIONS.items():
        row = enriched[enriched["station_code"] == station_code]
        if row.empty:
            failures.append(f"Missing key station {name} ({station_code})")
            print(f"- {name} ({station_code}): missing")
            continue

        record = row.iloc[0]
        print(
            f"- {name} ({station_code}): "
            f"matched={bool(record['wfd_matched'])}, "
            f"catchment={record.get('catchment_name')}, "
            f"river_waterbody_id={record.get('river_waterbody_id')}, "
            f"geometry={record.geometry.wkt[:60]}..."
        )
        if not bool(record["wfd_matched"]):
            failures.append(f"Key station not matched: {name} ({station_code})")

    null_geom_count = int(enriched.geometry.isna().sum())
    print(f"\nNull geometry count: {null_geom_count}")
    if null_geom_count > 0:
        failures.append(f"Found {null_geom_count} stations with null geometry")

    minx, miny, maxx, maxy = enriched.total_bounds
    print(f"Bounding box: minx={minx:.1f}, miny={miny:.1f}, maxx={maxx:.1f}, maxy={maxy:.1f}")
    if not (150000 <= minx <= 370000 and 150000 <= maxx <= 370000):
        failures.append("Easting bounds outside expected NI range")
    if not (300000 <= miny <= 470000 and 300000 <= maxy <= 470000):
        failures.append("Northing bounds outside expected NI range")

    output_path = Path("tests/validation/stations_map.png")
    fig, ax = plt.subplots(figsize=(8, 10))
    enriched.plot(column="wfd_matched", categorical=True, legend=True, markersize=6, ax=ax)
    ax.set_title("Stations coloured by wfd_matched")
    ax.set_xlabel("Easting")
    ax.set_ylabel("Northing")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved map: {output_path}")

    print("\n--- Result ---")
    if failures:
        print("FAIL")
        for issue in failures:
            print(f"- {issue}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    main()