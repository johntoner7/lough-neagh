"""Station-to-waterbody join logic."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd


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