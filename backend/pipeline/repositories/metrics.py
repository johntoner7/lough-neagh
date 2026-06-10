"""Pipeline database operations for metrics tables.

All functions accept a SQLAlchemy engine and either return DataFrames (reads)
or write to the database (writes). No computation logic lives here.

Note on API reuse: the API layer uses psycopg async connections for the same
tables. SQL string constants are defined once here and re-exported so the API
repositories can import them if needed, but execution wrappers are separate.
"""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from api.constants import WFD_THRESHOLD_MG_L
from backend.pipeline.process.annual_refresh import build_annual_metrics_insert_df

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared SQL constants — importable by api/repositories if useful
# ---------------------------------------------------------------------------

ANNUAL_MEANS_SQL = """
    SELECT
        station_code,
        DATE_PART('year', reading_date)::INTEGER AS year,
        AVG(p_sol_mg_l)                          AS annual_mean_p_sol,
        COUNT(*)                                  AS reading_count,
        COUNT(*) < 8                              AS sparse_year,
        AVG(p_sol_mg_l) <= :threshold             AS wfd_compliant
    FROM readings
    WHERE p_sol_mg_l IS NOT NULL
      AND p_sol_mg_l > 0
      AND NOT likely_outlier
      {station_filter}
    GROUP BY station_code, year
    ORDER BY station_code, year
"""

ANNUAL_DATA_FOR_TRENDS_SQL = """
    SELECT station_code, year, annual_mean_p_sol, sparse_year
    FROM annual_metrics
    WHERE year >= 2010
      {station_filter}
    ORDER BY station_code, year
"""


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def fetch_existing_reading_keys(engine) -> pd.DataFrame:
    """Return (station_code, reading_date) for every row already in readings."""
    sql = text(
        "SELECT station_code::bigint AS station_code, reading_date FROM readings"
    )
    with engine.connect() as conn:
        result = conn.execute(sql)
        return pd.DataFrame(result.fetchall(), columns=["station_code", "reading_date"])

def fetch_annual_means(
    engine,
    station_codes: list[int] | None = None,
) -> pd.DataFrame:
    """Aggregate annual means from the readings table.

    Pass station_codes to restrict to affected stations (annual refresh);
    omit for a full recompute.
    """
    if station_codes is not None:
        sql = text(ANNUAL_MEANS_SQL.format(station_filter="AND station_code = ANY(:codes)"))
        params: dict = {"threshold": WFD_THRESHOLD_MG_L, "codes": station_codes}
    else:
        sql = text(ANNUAL_MEANS_SQL.format(station_filter=""))
        params = {"threshold": WFD_THRESHOLD_MG_L}

    with engine.connect() as conn:
        result = conn.execute(sql, params)
        df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    logger.info("fetch_annual_means: %d station-year rows", len(df))
    return df


def fetch_annual_data_for_trends(
    engine,
    station_codes: list[int] | None = None,
) -> pd.DataFrame:
    """Load post-2010 annual metrics for Mann-Kendall trend computation.

    Pass station_codes to restrict to affected stations (annual refresh);
    omit for a full recompute.
    """
    if station_codes is not None:
        sql = text(ANNUAL_DATA_FOR_TRENDS_SQL.format(station_filter="AND station_code = ANY(:codes)"))
        params: dict = {"codes": station_codes}
    else:
        sql = text(ANNUAL_DATA_FOR_TRENDS_SQL.format(station_filter=""))
        params = {}

    with engine.connect() as conn:
        result = conn.execute(sql, params)
        df = pd.DataFrame(result.fetchall(), columns=list(result.keys()))
    logger.info("fetch_annual_data_for_trends: %d rows", len(df))
    return df


# ---------------------------------------------------------------------------
# Write operations — full swap (used by full_pipeline)
# ---------------------------------------------------------------------------

def swap_annual_metrics(annual_df: pd.DataFrame, engine) -> None:
    """Atomically replace the entire annual_metrics table.

    Writes to a staging table first so the live table is never empty.
    """
    insert_df = build_annual_metrics_insert_df(annual_df)
    insert_df.to_sql(
        "annual_metrics_staging", engine,
        if_exists="replace", index=False, chunksize=1000, method="multi",
    )
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE annual_metrics RESTART IDENTITY"))
        conn.execute(text("""
            INSERT INTO annual_metrics
                (station_code, year, annual_mean_p_sol, reading_count,
                 sparse_year, wfd_compliant, rolling_mean_5yr)
            SELECT station_code, year, annual_mean_p_sol, reading_count,
                   sparse_year, wfd_compliant, rolling_mean_5yr
            FROM annual_metrics_staging
        """))
        conn.execute(text("DROP TABLE annual_metrics_staging"))
    logger.info("swap_annual_metrics: %d rows written", len(insert_df))


def swap_trend_results(trend_df: pd.DataFrame, engine) -> None:
    """Atomically replace the entire trend_results table.

    Writes to a staging table first so the live table is never empty.
    """
    insert_df = _prepare_trend_df(trend_df)
    insert_df.to_sql(
        "trend_results_staging", engine,
        if_exists="replace", index=False, method="multi",
    )
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE trend_results"))
        conn.execute(text("""
            INSERT INTO trend_results
                (station_code, trend_direction, p_value, sens_slope,
                 significant, years_analysed)
            SELECT station_code, trend_direction, p_value, sens_slope,
                   significant, years_analysed
            FROM trend_results_staging
        """))
        conn.execute(text("DROP TABLE trend_results_staging"))
    logger.info("swap_trend_results: %d rows written", len(insert_df))


# ---------------------------------------------------------------------------
# Write operations — partial update (used by annual_refresh)
# ---------------------------------------------------------------------------

def update_annual_metrics_for_stations(
    annual_df: pd.DataFrame,
    station_codes: list[int],
    engine,
) -> None:
    """Delete and reinsert annual_metrics rows for the given stations."""
    insert_df = build_annual_metrics_insert_df(annual_df)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM annual_metrics WHERE station_code = ANY(:codes)"),
            {"codes": station_codes},
        )
    insert_df.to_sql(
        "annual_metrics", engine,
        if_exists="append", index=False, chunksize=1000, method="multi",
    )
    logger.info(
        "update_annual_metrics_for_stations: %d rows across %d stations",
        len(insert_df), len(station_codes),
    )


def update_trend_results_for_stations(
    trend_df: pd.DataFrame,
    station_codes: list[int],
    engine,
) -> None:
    """Delete and reinsert trend_results rows for the given stations."""
    if trend_df.empty:
        logger.info("update_trend_results_for_stations: nothing to update")
        return
    insert_df = _prepare_trend_df(trend_df)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM trend_results WHERE station_code = ANY(:codes)"),
            {"codes": station_codes},
        )
    insert_df.to_sql(
        "trend_results", engine,
        if_exists="append", index=False, method="multi",
    )
    logger.info(
        "update_trend_results_for_stations: %d rows across %d stations",
        len(insert_df), len(station_codes),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _prepare_trend_df(trend_df: pd.DataFrame) -> pd.DataFrame:
    insert_df = trend_df[[
        "station_code", "trend_direction", "p_value", "sens_slope",
        "significant", "years_analysed",
    ]].copy()
    insert_df["station_code"] = insert_df["station_code"].astype("int64")
    insert_df["p_value"] = insert_df["p_value"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["sens_slope"] = insert_df["sens_slope"].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    insert_df["significant"] = insert_df["significant"].astype("bool")
    return insert_df
