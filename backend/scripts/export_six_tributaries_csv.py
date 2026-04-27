"""Export annual metrics for the six main tributaries to a CSV file.

Usage:
    uv run python -m backend.scripts.export_six_tributaries_csv
    uv run python -m backend.scripts.export_six_tributaries_csv --output my_file.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg2

KEY_STATIONS = {
    10212: "River Main",
    10233: "Six Mile Water",
    10271: "Upper Bann",
    10328: "Blackwater",
    10361: "Ballinderry",
    10380: "Moyola",
}

DEFAULT_OUTPUT = Path("data/six_main_tributaries_metrics.csv")


def export(output: Path, database_url: str) -> None:
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT am.station_code, am.year, am.annual_mean_p_sol,
               am.rolling_mean_5yr, am.reading_count
        FROM annual_metrics am
        WHERE am.station_code = ANY(%s)
        ORDER BY am.station_code, am.year
        """,
        (list(KEY_STATIONS.keys()),),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    with open(output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["river", "year", "annual_mean", "rolling_mean", "n_readings"])
        for station_code, year, annual_mean, rolling_mean, reading_count in rows:
            writer.writerow([
                KEY_STATIONS[station_code],
                year,
                None if annual_mean is None else float(annual_mean),
                None if rolling_mean is None else float(rolling_mean),
                int(reading_count) if reading_count is not None else 0,
            ])

    print(f"Wrote {len(rows)} rows to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export six-tributary metrics to CSV.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5433/phosphorus_db")
    export(args.output, url)
