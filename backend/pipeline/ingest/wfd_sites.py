"""WFD monitoring sites loader."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd


def load_wfd_sites(geojson_path: str) -> gpd.GeoDataFrame:
	"""
	Load WFD monitoring sites and derive FOI-joinable station codes.

	Returns a GeoDataFrame with:
	- station_code_int
	- wfd_site_id
	- wfd_name
	- river_waterbody_id
	- catchment_name
	- geometry
	"""
	gdf = gpd.read_file(geojson_path)

	required = ["monitoring", "monitori_1", "river_wate", "catchment", "geometry"]
	missing = [column for column in required if column not in gdf.columns]
	if missing:
		raise ValueError(f"WFD sites file missing required columns: {missing}")

	gdf["station_code_int"] = pd.to_numeric(
		gdf["monitoring"].astype(str).str.strip().str.lstrip("F"), errors="coerce"
	).astype("Int64")

	gdf = gdf.rename(
		columns={
			"monitoring": "wfd_site_id",
			"monitori_1": "wfd_name",
			"river_wate": "river_waterbody_id",
			"catchment": "catchment_name",
		}
	)

	if gdf.crs is None:
		gdf = gdf.set_crs(epsg=29902)
	elif gdf.crs.to_epsg() != 29902:
		gdf = gdf.to_crs(epsg=29902)

	return gdf[
		[
			"station_code_int",
			"wfd_site_id",
			"wfd_name",
			"river_waterbody_id",
			"catchment_name",
			"geometry",
		]
	].copy()