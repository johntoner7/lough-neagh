"""Unit tests for pure metric computation functions.

No database or file I/O — all tests run from in-process DataFrames.
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.pipeline.process.metrics import compute_rolling_means, compute_trend_results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _station(years: list[int], values: list[float], sparse: list[bool] | None = None) -> pd.DataFrame:
    """Build a single-station annual metrics DataFrame."""
    if sparse is None:
        sparse = [False] * len(years)
    return pd.DataFrame({
        "station_code": [1] * len(years),
        "year": years,
        "annual_mean_p_sol": values,
        "sparse_year": sparse,
    })


def _rolling(df: pd.DataFrame, year: int) -> float | None:
    val = df.loc[df["year"] == year, "rolling_mean_5yr"].iloc[0]
    return None if val is None else float(val)


# ---------------------------------------------------------------------------
# compute_rolling_means
# ---------------------------------------------------------------------------

class TestComputeRollingMeans:
    def test_null_when_window_incomplete(self):
        """Rolling mean is null when fewer than 5 years surround the target."""
        df = _station([2000, 2001, 2002], [0.1, 0.2, 0.3])
        result = compute_rolling_means(df)
        # 2001 needs 1999..2003 — only 3 years available
        assert _rolling(result, 2001) is None

    def test_computed_for_central_year_in_complete_window(self):
        """Rolling mean equals mean of 5 values when all non-sparse."""
        df = _station(list(range(2000, 2005)), [0.1, 0.2, 0.3, 0.4, 0.5])
        result = compute_rolling_means(df)
        assert _rolling(result, 2002) == pytest.approx(0.3)

    def test_excludes_sparse_years_from_mean(self):
        """Sparse years contribute to window count but not to the mean."""
        df = _station(
            list(range(2000, 2005)),
            [0.1, 0.2, 0.3, 0.4, 0.5],
            sparse=[True, False, False, False, False],
        )
        result = compute_rolling_means(df)
        # Window for 2002: 2000(sparse), 2001, 2002, 2003, 2004 → 4 valid
        # Mean of 0.2, 0.3, 0.4, 0.5 = 0.35
        assert _rolling(result, 2002) == pytest.approx(0.35)

    def test_null_when_fewer_than_3_valid_in_window(self):
        """Rolling mean is null when < 3 non-sparse years in the 5-year window."""
        df = _station(
            list(range(2000, 2005)),
            [0.1, 0.2, 0.3, 0.4, 0.5],
            sparse=[True, True, True, False, False],
        )
        result = compute_rolling_means(df)
        # Window for 2002: only 2 non-sparse years (2003, 2004) → null
        assert _rolling(result, 2002) is None

    def test_exactly_3_valid_computes_mean(self):
        """Exactly 3 non-sparse years in window is sufficient."""
        df = _station(
            list(range(2000, 2005)),
            [0.1, 0.2, 0.3, 0.4, 0.5],
            sparse=[True, True, False, False, False],
        )
        result = compute_rolling_means(df)
        # 3 valid: 2002(0.3), 2003(0.4), 2004(0.5) → mean = 0.4
        assert _rolling(result, 2002) == pytest.approx(0.4)

    def test_end_years_are_null(self):
        """First and last 2 years of a series always have incomplete windows."""
        df = _station(list(range(2000, 2010)), [0.1] * 10)
        result = compute_rolling_means(df)
        assert _rolling(result, 2000) is None
        assert _rolling(result, 2001) is None
        assert _rolling(result, 2008) is None
        assert _rolling(result, 2009) is None

    def test_multiple_stations_independent(self):
        """Rolling mean is computed independently per station."""
        s1 = _station(list(range(2000, 2005)), [0.1] * 5)
        s2 = s1.copy()
        s2["station_code"] = 2
        s2["annual_mean_p_sol"] = [0.2] * 5
        df = pd.concat([s1, s2], ignore_index=True)
        result = compute_rolling_means(df)
        assert result.loc[(result["station_code"] == 1) & (result["year"] == 2002), "rolling_mean_5yr"].iloc[0] == pytest.approx(0.1)
        assert result.loc[(result["station_code"] == 2) & (result["year"] == 2002), "rolling_mean_5yr"].iloc[0] == pytest.approx(0.2)

    def test_original_dataframe_not_mutated(self):
        df = _station(list(range(2000, 2005)), [0.1] * 5)
        original_cols = set(df.columns)
        compute_rolling_means(df)
        assert set(df.columns) == original_cols
        assert "rolling_mean_5yr" not in df.columns


# ---------------------------------------------------------------------------
# compute_trend_results
# ---------------------------------------------------------------------------

class TestComputeTrendResults:
    def test_increasing_trend(self):
        df = _station(
            list(range(2010, 2020)),
            [0.01 * (i + 1) for i in range(10)],
        )
        result = compute_trend_results(df)
        assert result.loc[result["station_code"] == 1, "trend_direction"].iloc[0] == "increasing"

    def test_decreasing_trend(self):
        df = _station(
            list(range(2010, 2020)),
            [0.10 - 0.01 * i for i in range(10)],
        )
        result = compute_trend_results(df)
        assert result.loc[result["station_code"] == 1, "trend_direction"].iloc[0] == "decreasing"

    def test_insufficient_data_fewer_than_8_non_sparse(self):
        df = _station(list(range(2010, 2015)), [0.1, 0.2, 0.3, 0.4, 0.5])
        result = compute_trend_results(df)
        assert result.loc[result["station_code"] == 1, "trend_direction"].iloc[0] == "insufficient data"
        assert result.loc[result["station_code"] == 1, "p_value"].iloc[0] is None

    def test_sparse_years_excluded_from_trend(self):
        """Sparse years don't count toward the 8-year minimum."""
        # 10 years total but 5 are sparse → only 5 valid → insufficient
        df = _station(
            list(range(2010, 2020)),
            [0.1] * 10,
            sparse=[True, True, True, True, True, False, False, False, False, False],
        )
        result = compute_trend_results(df)
        assert result.loc[result["station_code"] == 1, "trend_direction"].iloc[0] == "insufficient data"

    def test_no_trend_flat_series(self):
        df = _station(list(range(2010, 2020)), [0.05] * 10)
        result = compute_trend_results(df)
        direction = result.loc[result["station_code"] == 1, "trend_direction"].iloc[0]
        assert direction in ("no trend", "increasing", "decreasing")

    def test_significant_field_reflects_p_value(self):
        df = _station(
            list(range(2010, 2020)),
            [0.01 * (i + 1) for i in range(10)],
        )
        result = compute_trend_results(df)
        row = result.loc[result["station_code"] == 1].iloc[0]
        assert row["significant"] == (row["p_value"] < 0.05)

    def test_multiple_stations_in_single_call(self):
        s1 = _station(list(range(2010, 2020)), [0.01 * (i + 1) for i in range(10)])
        s2 = _station(list(range(2010, 2020)), [0.1] * 10)
        s2["station_code"] = 2
        df = pd.concat([s1, s2], ignore_index=True)
        result = compute_trend_results(df)
        assert len(result) == 2
        assert set(result["station_code"]) == {1, 2}

    def test_output_schema(self):
        df = _station(list(range(2010, 2020)), [0.05] * 10)
        result = compute_trend_results(df)
        expected_cols = {"station_code", "trend_direction", "p_value", "sens_slope", "significant", "years_analysed"}
        assert expected_cols.issubset(set(result.columns))
