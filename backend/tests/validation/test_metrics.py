from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")


KEY_STATIONS = {
    10233: "Six Mile Water",
    10212: "River Main",
    10380: "Moyola",
    10361: "Ballinderry",
    10328: "Blackwater",
    10271: "Upper Bann",
}


def main() -> None:
    engine = create_engine(_database_url())
    failures: list[str] = []

    print("=== TEST 5: METRICS SANITY CHECK ===")

    with engine.begin() as connection:
        # 1. Count annual metrics rows
        metrics_count = connection.execute(text("SELECT COUNT(*) FROM annual_metrics")).scalar_one()
        print(f"\nannual_metrics row count: {metrics_count}")
        if int(metrics_count) < 1000:
            failures.append(f"Expected >1000 annual_metrics rows, got {metrics_count}")

        # 2. For key stations, show annual means for key years
        print("\nAnnual P(SOL) means for key stations (mg/l):")
        for station_code, station_name in sorted(KEY_STATIONS.items()):
            for year in [1990, 2000, 2010, 2024]:
                result = connection.execute(
                    text(
                        f"""
                        SELECT annual_mean_p_sol, reading_count, sparse_year
                        FROM annual_metrics
                        WHERE station_code = {station_code} AND year = {year}
                        """
                    )
                ).fetchone()
                if result:
                    mean_val, count, sparse = result
                    sparse_flag = " [SPARSE]" if sparse else ""
                    print(f"  {station_name:25} {year}: {mean_val:6.3f} ({count:2d} readings){sparse_flag}")
                else:
                    print(f"  {station_name:25} {year}: no data")

        # 3. Sparse year flags
        sparse_count = connection.execute(
            text("SELECT COUNT(*) FROM annual_metrics WHERE sparse_year = TRUE")
        ).scalar_one()
        print(f"\nStation-years flagged sparse (<8 readings): {sparse_count}")

        # 4. WFD compliance count
        compliant_count = connection.execute(
            text(
                """
                SELECT COUNT(DISTINCT station_code)
                FROM annual_metrics
                WHERE year = 2024 AND wfd_compliant = TRUE
                """
            )
        ).scalar_one()
        total_2024_count = connection.execute(
            text(
                """
                SELECT COUNT(DISTINCT station_code)
                FROM annual_metrics
                WHERE year = 2024 AND annual_mean_p_sol IS NOT NULL
                """
            )
        ).scalar_one()
        print(
            f"\nStations currently above WFD threshold (2024 annual mean > 0.035): "
            f"{int(total_2024_count) - int(compliant_count)} out of {total_2024_count} with data"
        )

        # 5. Trend results for key stations
        print("\nTrend analysis (post-2010, Mann-Kendall):")
        for station_code, station_name in sorted(KEY_STATIONS.items()):
            result = connection.execute(
                text(
                    f"""
                    SELECT trend_direction, p_value, sens_slope, significant, years_analysed
                    FROM trend_results
                    WHERE station_code = {station_code}
                    """
                )
            ).fetchone()
            if result:
                trend, p_val, slope, sig, yrs = result
                sig_str = " [SIG]" if sig else ""
                slope_str = f"{slope:.6f}" if slope is not None else "null"
                print(
                    f"  {station_name:25} {trend:20} (slope={slope_str}, p={p_val:.3f} if p else 'N/A'){sig_str}"
                )
            else:
                print(f"  {station_name:25} no trend results")

        # 6. Verify rolling means are null for 2023-2024 (incomplete window)
        rolling_2023 = connection.execute(
            text("SELECT COUNT(*) FROM annual_metrics WHERE year = 2023 AND rolling_mean_5yr IS NOT NULL")
        ).scalar_one()
        rolling_2024 = connection.execute(
            text("SELECT COUNT(*) FROM annual_metrics WHERE year = 2024 AND rolling_mean_5yr IS NOT NULL")
        ).scalar_one()
        print(f"\nRolling means (should be null for incomplete windows):")
        print(f"  2023 stations with rolling mean: {rolling_2023} (expect mostly 0)")
        print(f"  2024 stations with rolling mean: {rolling_2024} (expect 0)")

        if int(rolling_2024) > 10:
            failures.append(f"Expected rolling_mean_5yr null for 2024, got {rolling_2024} non-null")

    print("\n--- Result ---")
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("PASS")


if __name__ == "__main__":
    main()
