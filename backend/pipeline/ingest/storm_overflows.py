"""NI Water modelled storm overflow loader.

Source: NI Water Corporate Asset Register, modelled spill estimates published
November 2025. One row per storm overflow asset. Only densely populated areas
have been modelled, so roughly half the assets carry no spill estimate at all —
that distinction is preserved in the `modelled` column and must never be
rendered as "zero spills".
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).parents[3] / "data" / "raw" / "storm_overflows"

SHEET_NAME = "Modelled Results"

# Irish Grid sanity bounds — same range insert_stations validates against.
_EASTING_MAX = 400_000
_NORTHING_MAX = 470_000

_COLUMNS = [
    "car_id",
    "name",
    "spill_frequency",
    "spill_volume_m3",
    "classification",
    "modelled",
    "monitored",
    "receiving_waterbody_id",
    "receiving_waterbody_name",
    "local_management_area",
    "coord_is_discharge_point",
]


def find_source_xlsx() -> Path:
    """Locate the NI Water modelled spills workbook in data/raw/storm_overflows."""
    candidates = sorted(_DATA_ROOT.glob("*.xlsx"))
    if not candidates:
        raise FileNotFoundError(f"No storm overflow .xlsx found in {_DATA_ROOT}")
    return candidates[-1]


def _parse_coordinates(raw: pd.Series) -> pd.DataFrame:
    """Split the "easting,northing" Irish Grid string into numeric columns."""
    parts = raw.astype(str).str.split(",", n=1, expand=True)
    return pd.DataFrame({
        "easting": pd.to_numeric(parts[0].str.strip(), errors="coerce"),
        "northing": pd.to_numeric(parts[1].str.strip(), errors="coerce"),
    })


def load_storm_overflows(xlsx_path: str | Path | None = None) -> gpd.GeoDataFrame:
    """
    Load modelled storm overflows from the NI Water workbook.

    Maps source fields to:
    - car_id (from CARID), name
    - spill_frequency, spill_volume_m3 (null where not modelled)
    - classification (Unsatisfactory / Satisfactory / To be Determined / Not Modelled)
    - modelled: whether NI Water produced a spill estimate for this asset
    - monitored: whether the asset carries a monitor
    - receiving_waterbody_id / _name, local_management_area
    - coord_is_discharge_point: False where the point is the asset, not the outfall
    - geometry (POINT, EPSG:29902)

    Assets whose coordinates are missing or outside the Irish Grid are dropped —
    unlike a monitoring station, an overflow with no location has no use here.
    """
    path = Path(xlsx_path) if xlsx_path else find_source_xlsx()
    raw = pd.read_excel(path, sheet_name=SHEET_NAME)

    frequency = pd.to_numeric(raw["Predicted Spill Frequency / Year"], errors="coerce")

    output = pd.DataFrame({
        "car_id": raw["CARID"].astype(str).str.strip(),
        "name": raw["Name"].astype(str).str.strip(),
        "spill_frequency": frequency,
        "spill_volume_m3": pd.to_numeric(
            raw["Predicted Spill Volume / Year (m3)"], errors="coerce"
        ),
        "classification": raw["Storm Overflow Classification"],
        "modelled": frequency.notna(),
        "monitored": raw["Monitored"].astype(str).str.strip().str.lower().eq("yes"),
        "receiving_waterbody_id": raw["Receiving Waterbody ID"],
        "receiving_waterbody_name": raw["Receiving Waterbody Name"],
        "local_management_area": raw["Local Management Area"],
        "coord_is_discharge_point": raw["Coordinate Description"].eq(
            "Discharge Point Coordinates"
        ),
    })

    coords = _parse_coordinates(raw["XY Coordinates"])
    output = pd.concat([output, coords], axis=1)

    valid = (
        output["easting"].between(0, _EASTING_MAX)
        & output["northing"].between(0, _NORTHING_MAX)
    )
    if not valid.all():
        rejected = output.loc[~valid, "car_id"].tolist()
        logger.warning(
            "Dropping %d storm overflows with missing or out-of-range coordinates: %s",
            len(rejected), ", ".join(rejected[:20]),
        )
        output = output[valid]

    duplicates = int(output["car_id"].duplicated().sum())
    if duplicates:
        logger.warning("%d duplicate CARID values found — keeping first", duplicates)
        output = output.drop_duplicates(subset=["car_id"], keep="first")

    geometry = [
        Point(e, n) for e, n in zip(output["easting"], output["northing"], strict=True)
    ]
    gdf = gpd.GeoDataFrame(output[_COLUMNS].copy(), geometry=geometry, crs="EPSG:29902")

    logger.info(
        "Loaded %d storm overflows (%d modelled, %d awaiting modelling)",
        len(gdf), int(gdf["modelled"].sum()), int((~gdf["modelled"]).sum()),
    )
    return gdf
