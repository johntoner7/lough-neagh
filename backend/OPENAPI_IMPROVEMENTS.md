# OpenAPI Improvements

FastAPI generates an OpenAPI schema automatically from type hints and `Query()`
descriptors. The `/docs` UI is often the first thing a reviewer looks at — these
changes make it accurate and complete with minimal code.

---

## 1. Enforce and document the farms year range

Currently `/farms/geojson?year=1990` silently clamps to 2015 with no indication
in the docs. Replace silent clamping with a validated range so the schema is honest:

```python
# routes/farms.py
from fastapi import Query

@router.get("/geojson", response_model=FarmCollection)
def get_farms_geojson(
    response: Response,
    year: int = Query(
        2024,
        ge=2015,
        le=2024,
        description="Farm census year. NISRA data available 2015–2024.",
    ),
) -> FarmCollection:
    ...
```

FastAPI will now return a 422 with a clear message for out-of-range values, and
`/docs` will show `minimum: 2015, maximum: 2024` on the parameter.

Remove `_clamp_year()` — it's no longer needed.

---

## 2. Add examples to complex parameters

The `bbox` and `year` params benefit from concrete examples in the schema:

```python
from fastapi import Query
from typing import Annotated

# In get_stations_geojson:
bbox: Annotated[str | None, Query(
    default=None,
    description="Bounding box filter in WGS84: minLon,minLat,maxLon,maxLat",
    example="-7.5,54.2,-5.8,55.1",
)] = None

year: Annotated[int, Query(
    description="Year to return annual metrics for (1990–2024)",
    example=2023,
)] = ...
```

These show up as pre-filled examples in the `/docs` "Try it out" panel.

---

## 3. Add response examples to Pydantic models

OpenAPI can include a sample response body in `/docs` via model `Config`:

```python
class StationTimeSeries(BaseModel):
    station_code: int
    location_name: str
    # ...

    model_config = {
        "json_schema_extra": {
            "example": {
                "station_code": 10233,
                "location_name": "Six Mile Water at Antrim",
                "catchment_name": "Six Mile Water",
                "trend_direction": "decreasing",
                "trend_significant": True,
                "sens_slope": -0.0012,
                "series": [
                    {"year": 1990, "annual_mean_p_sol": 0.082, "rolling_mean_5yr": None,
                     "reading_count": 12, "sparse_year": False, "wfd_compliant": False}
                ]
            }
        }
    }
```

---

## 4. Tag descriptions

Router tags (`stations`, `catchments`, etc.) appear as section headers in `/docs`.
Add descriptions to give them context:

```python
# main.py
app = FastAPI(
    title="NI River Phosphorus API",
    openapi_tags=[
        {"name": "stations", "description": "River monitoring stations with annual phosphorus metrics and WFD compliance."},
        {"name": "catchments", "description": "Catchment-level aggregations across all stations."},
        {"name": "lakes", "description": "Lake polygons with WFD ecological status classifications."},
        {"name": "farms", "description": "Ward-level NISRA livestock census data (agricultural P-pressure proxy)."},
    ],
    ...
)
```

---

## 5. Document 404 responses

FastAPI only documents the happy-path response by default. Add `responses=` to
endpoints that can return 404:

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse

@router.get(
    "/{station_code}/timeseries",
    response_model=StationTimeSeries,
    responses={404: {"description": "Station not found"}},
)
def get_station_timeseries(...):
    ...
```

The 404 will appear as a documented response code in `/docs` and the generated schema.
