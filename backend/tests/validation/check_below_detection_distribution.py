from __future__ import annotations

import pandas as pd


def main() -> None:
    df = pd.read_csv("data/raw/foi/annex_a.csv", low_memory=False)
    below = df[df["Q.2"].astype(str).str.strip() == "<"].copy()

    df["year"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce").dt.year
    below["year"] = pd.to_datetime(below["Date"], dayfirst=True, errors="coerce").dt.year

    print("=== BELOW DETECTION DISTRIBUTION ===")
    print(f"Total below-detection: {len(below)}")
    print(f"As % of all rows: {100*len(below)/len(df):.1f}%")

    print("\nBelow-detection counts by year:")
    year_counts = below["year"].value_counts().sort_index()
    print(year_counts.to_string())

    key = [10233, 10212, 10380, 10361, 10328, 10271]
    key_below = below[below["Station Code"].isin(key)]
    print(f"\nBelow-detection in 6 key tributary stations: {len(key_below)}")

    print("\nP(SOL) value range for below-detection readings:")
    print(pd.to_numeric(below["P(SOL) (mg/l)"], errors="coerce").describe())

    print("\nTop 10 stations by below-detection count:")
    print(below["Station Code"].value_counts().head(10).to_string())

    top_year = int(year_counts.idxmax())
    top_year_count = int(year_counts.max())
    top_year_share = (top_year_count / len(below)) * 100
    print("\nTop year concentration:")
    print(f"{top_year}: {top_year_count} ({top_year_share:.1f}% of below-detection rows)")


if __name__ == "__main__":
    main()
