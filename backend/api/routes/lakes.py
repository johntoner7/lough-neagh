"""Lakes GeoJSON endpoint."""

from __future__ import annotations

import json

import psycopg2.extras
from fastapi import APIRouter
from fastapi.responses import Response

from api.db import get_conn
from api.models import LakeCollection, LakeFeature, LakeProperties

router = APIRouter(prefix="/lakes", tags=["lakes"])


@router.get("/geojson", response_model=LakeCollection)
def get_lakes_geojson(response: Response) -> LakeCollection:
    """
    Fetch all lake polygons as a GeoJSON FeatureCollection.

    Returns lake polygons (WGS84) with properties:
    - lake_id: EU_CD from WFD
    - lake_name: official lake name
    - ecological_status: WFD ecological classification
    - total_phosphorus: WFD phosphorus classification
    - label_text: optional text label (e.g. "Lough Neagh — Phosphorus: Bad")
    """
    sql = """
        SELECT
            lake_id,
            lake_name,
            ecological_status,
            total_phosphorus,
            label_text,
            ST_AsGeoJSON(ST_Transform(geometry, 4326)) AS geometry_json
        FROM lakes
        ORDER BY lake_name
    """
    # Lake WFD data is updated annually — safe to cache for 24 hours.
    response.headers["Cache-Control"] = "public, max-age=86400"

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    features = []
    for row in rows:
        geom_json = row["geometry_json"]
        if not geom_json:
            continue
        features.append(LakeFeature(
            geometry=json.loads(geom_json),
            properties=LakeProperties(
                lake_id=row["lake_id"],
                lake_name=row["lake_name"],
                ecological_status=row["ecological_status"],
                total_phosphorus=row["total_phosphorus"],
                label_text=row["label_text"],
            ),
        ))

    return LakeCollection(features=features)
