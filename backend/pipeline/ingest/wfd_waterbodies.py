"""WFD river water bodies loader and database insert helpers."""

from __future__ import annotations

import geopandas as gpd


def load_wfd_waterbodies(shp_path: str) -> gpd.GeoDataFrame:
	"""
	Load WFD river waterbody polygons.

	Maps source fields to:
	- river_waterbody_id (from localid)
	- catchment_name (best-effort from namespace)
	- geometry (MULTIPOLYGON, EPSG:29902)
	"""
	gdf = gpd.read_file(shp_path)

	id_candidates = ["localid", "LOCALID", "river_wate", "river_waterbody_id"]
	id_column = next((column for column in id_candidates if column in gdf.columns), None)
	if id_column is None:
		raise ValueError(f"Could not identify waterbody ID column in {gdf.columns.tolist()}")

	catchment_column = "namespace" if "namespace" in gdf.columns else None

	output = gdf.rename(columns={id_column: "river_waterbody_id"}).copy()
	if catchment_column:
		output = output.rename(columns={catchment_column: "catchment_name"})
	else:
		output["catchment_name"] = None

	output["river_waterbody_id"] = (
		output["river_waterbody_id"].astype(str).str.strip().str.replace(r"^UK", "", regex=True)
	)
	output = output[output["river_waterbody_id"] != ""].copy()

	if output.crs is None:
		output = output.set_crs(epsg=29902)
	elif output.crs.to_epsg() != 29902:
		output = output.to_crs(epsg=29902)

	return output[["river_waterbody_id", "catchment_name", "geometry"]].copy()


def insert_waterbodies(gdf: gpd.GeoDataFrame, engine) -> None:
	"""Insert waterbodies into PostGIS table `waterbodies` using replacement semantics."""
	gdf.to_postgis("waterbodies", engine, if_exists="replace", index=False)