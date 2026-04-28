"""Station-to-waterbody and segment-to-station join logic."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

_DATA_RAW = Path(__file__).parents[3] / "data" / "raw"


def enrich_stations(
	stations_df: pd.DataFrame,
	wfd_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
	"""
	Join FOI stations to WFD monitoring sites.

	Matched rows keep WFD geometry and metadata. Unmatched rows use FOI easting/northing
	as fallback point geometry in EPSG:29902.
	"""
	stations = stations_df.copy()
	stations["station_code"] = pd.to_numeric(stations["station_code"], errors="coerce").astype("Int64")

	wfd = wfd_gdf.copy()
	if "station_code_int" not in wfd.columns:
		raise ValueError("wfd_gdf must include station_code_int")

	if wfd.crs is None:
		wfd = wfd.set_crs(epsg=29902)
	elif wfd.crs.to_epsg() != 29902:
		wfd = wfd.to_crs(epsg=29902)

	wfd = wfd.rename(columns={"station_code_int": "station_code"})

	merged = stations.merge(
		wfd[["station_code", "wfd_site_id", "wfd_name", "river_waterbody_id", "catchment_name", "geometry"]],
		on="station_code",
		how="left",
	)

	fallback_geometry = gpd.points_from_xy(merged["easting"], merged["northing"], crs="EPSG:29902")
	matched_mask = merged["geometry"].notna()
	merged.loc[~matched_mask, "geometry"] = fallback_geometry[~matched_mask]
	merged["wfd_matched"] = matched_mask

	enriched = gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:29902")
	return enriched


def join_segments_to_stations(
	stations: gpd.GeoDataFrame,
	shapefile_path: Path | str | None = None,
) -> gpd.GeoDataFrame:
	"""Nearest-station join for river segment geometries.

	Loads the EHS river segment shapefile, finds the closest monitoring station
	for each segment, and returns a GeoDataFrame ready for DB insertion.

	Both inputs are expected in EPSG:29902; reprojection is applied if needed so
	that ``nearest_dist_m`` is in metres.

	Returns columns: rseg_cd, rwb_cd, strahler, nearest_station_code,
	nearest_dist_m, geom (EPSG:29902 LINESTRING).
	"""
	if shapefile_path is None:
		shapefile_path = _DATA_RAW / "river_segments" / "ehsgis_EHS_RiverSegment.shp"
	shapefile_path = Path(shapefile_path)
	if not shapefile_path.exists():
		raise FileNotFoundError(f"River segment shapefile not found: {shapefile_path}")

	segs = gpd.read_file(str(shapefile_path))
	if segs.crs is None:
		segs = segs.set_crs(epsg=29902)
	elif segs.crs.to_epsg() != 29902:
		segs = segs.to_crs(epsg=29902)

	station_pts = stations[["station_code", "geometry"]].copy().reset_index(drop=True)
	if station_pts.crs is None:
		station_pts = station_pts.set_crs(epsg=29902)
	elif station_pts.crs.to_epsg() != 29902:
		station_pts = station_pts.to_crs(epsg=29902)

	segs_slim = segs[["RWB_CD", "RSEG_CD", "STRAHLER", "geometry"]].copy().reset_index(drop=True)

	joined = gpd.sjoin_nearest(
		segs_slim,
		station_pts,
		how="left",
		distance_col="nearest_dist_m",
	)

	# sjoin_nearest suffixes colliding non-geometry columns; handle both forms
	sc_col = "station_code" if "station_code" in joined.columns else "station_code_right"

	# deduplicate: sjoin_nearest can produce ties for equidistant stations
	joined = joined.loc[~joined.index.duplicated(keep="first")]

	result = gpd.GeoDataFrame(
		{
			"rseg_cd": joined["RSEG_CD"].values,
			"rwb_cd": joined["RWB_CD"].values,
			"strahler": pd.array(joined["STRAHLER"].where(pd.notna(joined["STRAHLER"]), other=None), dtype="Float64"),
			"nearest_station_code": pd.to_numeric(joined[sc_col], errors="coerce").astype("Int64"),
			"nearest_dist_m": joined["nearest_dist_m"].astype(float),
		},
		geometry=joined.geometry.values,
		crs="EPSG:29902",
	)
	return result