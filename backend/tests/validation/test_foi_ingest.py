from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.pipeline.ingest.foi import load_and_clean_foi

EXPECTED_STATIONS = 1201
EXPECTED_DATE_MIN = pd.Timestamp("1990-01-02")
EXPECTED_DATE_MAX = pd.Timestamp("2024-12-11")
KEY_STATIONS = {
    10233: "Six Mile Water",
    10212: "River Main",
    10380: "Moyola",
    10361: "Ballinderry",
    10328: "Blackwater",
    10271: "Upper Bann",
}


def _resolve_csv_path() -> Path:
    candidate_paths = [
        Path("data/raw/foi/annex_a.csv"),
        Path("annex_a.csv"),
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not find FOI CSV at data/raw/foi/annex_a.csv or annex_a.csv")


def main() -> None:
    csv_path = _resolve_csv_path()
    stations_df, readings_df = load_and_clean_foi(str(csv_path))

    failures: list[str] = []

    print("=== TEST 1: FOI INGESTION SANITY CHECK ===")
    print(f"Using CSV: {csv_path}")
    print(f"stations_df shape: {stations_df.shape}")
    print(f"readings_df shape: {readings_df.shape}")

    total_rows = len(readings_df)
    unique_stations = readings_df["station_code"].nunique(dropna=True)
    date_min = readings_df["reading_date"].min()
    date_max = readings_df["reading_date"].max()

    print("\n--- Core profile ---")
    print(f"Total rows: {total_rows}")
    print(f"Unique stations: {unique_stations}")
    print(f"Date range: {date_min.date()} to {date_max.date()}")

    if unique_stations != EXPECTED_STATIONS:
        failures.append(f"Expected {EXPECTED_STATIONS} stations, got {unique_stations}")
    if date_min != EXPECTED_DATE_MIN or date_max != EXPECTED_DATE_MAX:
        failures.append(
            f"Expected date range {EXPECTED_DATE_MIN.date()} to {EXPECTED_DATE_MAX.date()}, "
            f"got {date_min.date()} to {date_max.date()}"
        )
    if not (165000 <= total_rows <= 175000):
        failures.append(f"Expected total rows ~170k, got {total_rows}")

    below_detection_count = int(readings_df["below_detection"].sum())
    below_detection_pct = (below_detection_count / total_rows) * 100
    print("\n--- QA flags ---")
    print(f"below_detection count: {below_detection_count} ({below_detection_pct:.1f}%)")
    if not (20000 <= below_detection_count <= 35000):
        failures.append(
            f"Expected below_detection roughly ~27k for full dataset, got {below_detection_count}"
        )

    below_subset = readings_df.loc[readings_df["below_detection"], ["station_code", "year"]].copy()
    year_counts = below_subset["year"].value_counts()
    if not year_counts.empty:
        top_year_share = (int(year_counts.max()) / below_detection_count) * 100
        print(f"Top-year share of below-detection: {top_year_share:.1f}%")
        if top_year_share > 40:
            failures.append(
                f"Below-detection appears overly clustered in one year ({top_year_share:.1f}%)"
            )

    key_codes = list(KEY_STATIONS.keys())
    key_below_count = int(
        readings_df.loc[
            readings_df["below_detection"] & readings_df["station_code"].isin(key_codes)
        ].shape[0]
    )
    print(f"Below-detection in 6 key tributary stations: {key_below_count}")
    if key_below_count > 500:
        failures.append(
            f"Unexpectedly high below-detection count in key tributary stations: {key_below_count}"
        )

    sparse_station_years = (
        readings_df.loc[readings_df["sparse_year"], ["station_code", "year"]]
        .drop_duplicates()
        .sort_values(["station_code", "year"])
    )
    print(f"Sparse station-years flagged: {len(sparse_station_years)}")

    moyola_sparse_years = sorted(
        sparse_station_years.loc[
            sparse_station_years["station_code"] == 10380, "year"
        ].tolist()
    )
    print(f"Moyola (10380) sparse years: {moyola_sparse_years}")
    for expected_year in [2015, 2016, 2020]:
        if expected_year not in moyola_sparse_years:
            failures.append(f"Expected Moyola sparse year {expected_year} not found")

    likely_outlier_count = int(readings_df["likely_outlier"].sum())
    print(f"likely_outlier count: {likely_outlier_count}")

    print("\n--- 2024 annual means for key stations ---")
    annual_2024 = (
        readings_df.loc[readings_df["year"] == 2024]
        .groupby("station_code", dropna=True)["p_sol_mg_l"]
        .mean()
    )

    for code, name in KEY_STATIONS.items():
        value = annual_2024.get(code)
        if pd.isna(value):
            print(f"{name} ({code}): no 2024 data")
            failures.append(f"Missing 2024 annual mean for {name} ({code})")
            continue

        print(f"{name} ({code}): {value:.4f} mg/l")
        if not (0.05 <= value <= 0.20):
            failures.append(
                f"{name} ({code}) 2024 annual mean out of expected range 0.05-0.20: {value:.4f}"
            )

    print("\n--- Result ---")
    if failures:
        print("FAIL")
        for reason in failures:
            print(f"- {reason}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    main()
