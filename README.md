# NI River Phosphorus

35 years of phosphorus monitoring data (1990–2024) from the Northern Ireland Department of Agriculture, Environment and Rural Affairs, mapped across 70+ river and tributary stations. Lough Neagh is the sump — most tributaries flow into it, making their water quality directly relevant to the lake's ecological status (currently "Bad" under WFD classification). The app reveals whether phosphorus concentrations have changed over three decades and which tributaries are the worst offenders.

## Key Findings

- **1990 baseline**: Mean P(SOL) concentration across all stations was approximately 0.078 mg/l — 2.2× the WFD "Good" threshold of 0.035 mg/l
- **2024 snapshot**: Mean concentration around 0.072 mg/l — marginal decline, still well above threshold
- **Moyola regression**: Post-2015 downward trend reversed; a statistically significant worsening confirmed by Mann-Kendall test, coinciding with dairy herd expansion following EU milk quota abolition

## Features

- Animated timeline stepping through 1990–2024, colour-coded by WFD compliance threshold
- Per-catchment filter to isolate individual river systems
- Cattle density layer (2015–2024 farm census data) overlaid on the map
- Storm overflow layer (NI Water modelled spills, 2025 snapshot) shown at 2024, sized by predicted spills per year
- Click any station to open a detail drawer with a 35-year phosphorus chart, 5-year rolling mean, and Mann-Kendall trend classification
- Sparkline panel for the six key Lough Neagh tributaries

## Stack

Python + FastAPI backend, PostGIS for spatial storage, GeoPandas for geometry handling. React + Vite + TypeScript on the frontend, Mapbox GL for the map, Zod for API response validation. Docker Compose locally, Railway in production.

## Setup

Clone the repo.

**Backend** — requires [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
cd backend
uv sync
```

**Frontend:**

```bash
cd frontend
npm install
```

Copy the env file and fill in your values:

```bash
cp .env.example .env
```

The three required values:

```
DATABASE_URL=postgresql://user:password@localhost:5433/phosphorus_db
MAPBOX_TOKEN=<your_token>
VITE_API_BASE_URL=http://localhost:8000
```

Start the PostGIS database (port 5433, matching `DATABASE_URL`):

```bash
docker compose -f backend/docker-compose.yml up -d db
```

Create the PostGIS extensions and the schema:

```bash
cd backend
uv run python -m scripts.init_db
uv run python -m scripts.create_tables
```

Then load the data. The pipeline reads `data/raw/` by relative path, so it must
be run **from the repo root**, not from `backend/`:

```bash
cd ..
backend/.venv/bin/python -m backend.scripts.run_pipeline --dry-run
backend/.venv/bin/python -m backend.scripts.run_pipeline
```

The dry run validates every source file and the database connection without
writing anything; drop the flag to load for real. A full run takes several
minutes — it ingests 35 years of readings and computes Mann-Kendall trends per
station. Note that `data/raw/` is git-ignored: the source files listed under
[Data Sources](#data-sources) have to be present locally before the pipeline
will pass its pre-flight checks.

Start the API on port 8000:

```bash
cd backend
uv run uvicorn api.main:app --reload --port 8000
```

Start the frontend dev server on port 5173:

```bash
cd frontend
npm run dev
```

## Data Sources

| Dataset | Source | Period |
|---|---|---|
| River nutrient readings | DAERA FOI 26-57 | 1990–2024 |
| WFD monitoring sites, water bodies, lake classifications | DAERA / UK EA | 2016, 2024 |
| Farm census (ward level) + OSNI ward boundaries | NISRA, Ordnance Survey NI | 2015–2024 |
| Storm overflow modelled spills | NI Water Corporate Asset Register | Nov 2025 snapshot |

The storm overflow figures are modelled rather than measured, and NI Water has
only modelled the most densely populated areas — around half of the registered
assets carry no estimate at all. Those are drawn as hollow rings on the map,
which means "no published estimate", not "never spills".

## Methodology

Data comes from DAERA Freedom of Information releases (reference 26-57). Concentrations are *measured*, not estimated loads — they reflect what the river contained at the sampling point, not how much phosphorus entered the catchment upstream. Annual means are computed from raw readings; 5-year rolling means smooth short-term noise. Mann-Kendall tests detect monotonic trends.

WFD thresholds are normative (0.035 mg/l P(SOL) for "Good" status) but represent policy, not absolute toxicity. Lough Neagh's "Bad" classification hinges on exceedance of these thresholds within broader multi-year assessment frameworks.

## Live

[rivers.climategapni.com](https://rivers.climategapni.com)
