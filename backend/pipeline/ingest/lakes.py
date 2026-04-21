"""Lake polygon loader and database insert helpers."""

from __future__ import annotations

import geopandas as gpd


def load_lakes(geojson_path: str) -> gpd.GeoDataFrame:
	"""
	Load WFD lake polygons from GeoJSON.

	Maps source fields to:
	- lake_id (from EU_CD)
	- lake_name (from LAKE_NAME)
	- ecological_status (from Ecological_Status)
	- total_phosphorus (from Total_Phosphorus)
	- label_text (hardcoded for Lough Neagh, null for others)
	- geometry (POLYGON, EPSG:29902)
	"""
	gdf = gpd.read_file(geojson_path)

	output = gdf.rename(columns={
		'EU_CD': 'lake_id',
		'LAKE_NAME': 'lake_name',
		'Ecological_Status': 'ecological_status',
		'Total_Phosphorus': 'total_phosphorus',
	}).copy()

	# Hardcode label for Lough Neagh only
	output['label_text'] = None
	output.loc[output['lake_id'] == 'UKGBNI3NB0032', 'label_text'] = 'Lough Neagh — Phosphorus: Bad'

	# Validate and convert CRS to Irish Grid (EPSG:29902)
	if output.crs is None:
		output = output.set_crs(epsg=4326)  # Assume WGS84 if not specified

	if output.crs.to_epsg() != 29902:
		output = output.to_crs(epsg=29902)

	# Simplify geometry for efficient storage (tolerance ~100m)
	output['geometry'] = output['geometry'].simplify(tolerance=0.001, preserve_topology=True)

	return output[['lake_id', 'lake_name', 'ecological_status', 'total_phosphorus', 'label_text', 'geometry']].copy()
