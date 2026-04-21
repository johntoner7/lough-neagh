# NI River Phosphorus API — Backend Reference

FastAPI application serving 35 years of DAERA river phosphorus monitoring data for Northern Ireland (1990–2024). PostgreSQL + PostGIS backend, read-only (GET requests only).

---

## Configuration

| Setting | Value |
|---|---|
| Framework | FastAPI 1.0.0 |
| CORS | `*` (all origins), GET only |
| Database | PostgreSQL + PostGIS via psycopg2 |
| DB connection | `DATABASE_URL` env var or `postgresql://user:password@localhost:5433/phosphorus_db` |

---

## System Endpoints

### `GET /`
Returns API metadata and available year range.
```json
{
  "name": "NI River Phosphorus API",
  "years": { "min": 1990, "max": 2024 },
  "endpoints": { ... }
}
```

### `GET /health`
Database connectivity check.
```json
{ "status": "ok", "database": "connected" | "unavailable" }
```

### `GET /config`
Returns public client config (Mapbox token).
```json
{ "mapbox_token": "..." }
```

---

## Stations (`/stations`)

### `GET /stations/years`
All years with data.
**Response:** `[1990, 1991, ..., 2024]`

---

### `GET /stations/geojson`
All stations as GeoJSON FeatureCollection with annual phosphorus metrics.

**Query params:**
| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `year` | int | ✓ | — | Year for annual metrics |
| `catchment` | str | ✗ | null | Filter to one catchment |
| `wfd_matched_only` | bool | ✗ | false | Only WFD-matched stations |
| `with_data_only` | bool | ✗ | false | Only stations with data for that year |
| `metric` | `"annual"` \| `"rolling"` | ✗ | `"annual"` | Metric to use for map values |

**Response:** GeoJSON FeatureCollection
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { ... },
      "properties": {
        "station_code": 123,
        "location_name": "...",
        "catchment_name": "...",
        "river_waterbody_id": "...",
        "wfd_matched": true,
        "annual_mean_p_sol": 0.042,
        "rolling_mean_5yr": 0.038,
        "metric_p_sol": 0.042,
        "wfd_compliant": false,
        "sparse_year": false,
        "trend_direction": "decreasing",
        "trend_significant": true,
        "sens_slope": -0.0012
      }
    }
  ],
  "metadata": {
    "year": 2023,
    "total_stations": 180,
    "stations_with_data": 163,
    "stations_above_threshold": 42,
    "wfd_threshold_mg_l": 0.035,
    "data_note": null
  }
}
```

---

### `GET /stations/{station_code}/timeseries`
Full 1990–2024 time series for one station.

**Path param:** `station_code` (int)
**Returns:** 404 if not found

**Response:**
```json
{
  "station_code": 123,
  "location_name": "...",
  "catchment_name": "...",
  "trend_direction": "decreasing",
  "trend_significant": true,
  "sens_slope": -0.0012,
  "series": [
    {
      "year": 1990,
      "annual_mean_p_sol": 0.058,
      "rolling_mean_5yr": null,
      "reading_count": 12,
      "sparse_year": false,
      "wfd_compliant": false
    }
  ]
}
```

---

## Catchments (`/catchments`)

### `GET /catchments`
All distinct catchment names.
**Response:** `["Bann", "Bush", ...]`

---

### `GET /catchments/{catchment_name}/summary`
Aggregate stats for all stations in a catchment for a given year.

**Path param:** `catchment_name` (str)
**Query param:** `year` (int, required)
**Returns:** 404 if not found

**Response:**
```json
{
  "catchment_name": "Bann",
  "year": 2023,
  "station_count": 18,
  "mean_p_sol": 0.041,
  "pct_above_threshold": 55.6,
  "stations": [ ...StationProperties... ]
}
```

---

## Lakes (`/lakes`)

### `GET /lakes/geojson`
All lake polygons with WFD ecological status classifications.

**Response:** GeoJSON FeatureCollection
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { ... },
      "properties": {
        "lake_id": "IE_EA_L_26510",
        "lake_name": "Lough Neagh",
        "ecological_status": "Poor",
        "total_phosphorus": "Bad",
        "label_text": "Lough Neagh — Phosphorus: Bad"
      }
    }
  ]
}
```

---

## Farms (`/farms`)

### `GET /farms/years`
Available years in farm census data.
**Response:** `[2015, 2016, ..., 2024]`

---

### `GET /farms/geojson`
OSNI ward boundaries joined with NISRA livestock census data.

**Query param:** `year` (int, optional, default `2024`, clamped to 2015–2024)

**Response:** GeoJSON FeatureCollection
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { ... },
      "properties": {
        "ward_name": "Antrim Town",
        "ward_code": "N08000001",
        "num_farms": 45,
        "area_ha": 8200.5,
        "cattle": 3200,
        "sheep": 1500,
        "pigs": 200,
        "cattle_per_ha": 0.39,
        "lu_per_ha": 0.65
      }
    }
  ],
  "metadata": { "year": 2024 }
}
```

`lu_per_ha` = `(cattle × 1) + (sheep × 0.15) + (pigs × 0.25)` / area_ha

---

## Database Schema

| Table | Key Columns | Purpose |
|---|---|---|
| `stations` | `station_code` PK, `location_name`, `catchment_name`, `river_waterbody_id`, `wfd_matched`, `geom` | Station metadata + PostGIS geometry |
| `annual_metrics` | `station_code`, `year`, `annual_mean_p_sol`, `rolling_mean_5yr`, `wfd_compliant`, `sparse_year`, `reading_count` | Per-year phosphorus measurements |
| `trend_results` | `station_code`, `trend_direction`, `significant`, `sens_slope` | Mann-Kendall trend analysis |
| `lakes` | `lake_id`, `lake_name`, `ecological_status`, `total_phosphorus`, `label_text`, `geometry` | Lake polygons + WFD status |
| `farm_census_wards` | `year`, `ward_name`, `ward_code`, `num_farms`, `area_ha`, `cattle`, `sheep`, `pigs`, `cattle_per_ha`, `lu_per_ha`, `geometry` | NISRA farm census by ward |

**WFD compliance threshold:** `0.035 mg/l P(SOL)` — stations above this are non-compliant.

All geometries stored in an Irish grid projection and transformed to WGS84 (EPSG:4326) at query time via PostGIS `ST_Transform()`.
