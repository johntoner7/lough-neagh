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

Start the PostGIS database:

```bash
docker compose -f backend/docker-compose.yml up db
```

Then seed it:

```bash
cd backend
uv run python scripts/create_tables.py
uv run python scripts/seed_db.py
```

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

## Data Source & Methodology

Data comes from DAERA Freedom of Information releases (reference 26-57). Concentrations are *measured*, not estimated loads — they reflect what the river contained at the sampling point, not how much phosphorus entered the catchment upstream. Annual means are computed from raw readings; 5-year rolling means smooth short-term noise. Mann-Kendall tests detect monotonic trends.

WFD thresholds are normative (0.035 mg/l P(SOL) for "Good" status) but represent policy, not absolute toxicity. Lough Neagh's "Bad" classification hinges on exceedance of these thresholds within broader multi-year assessment frameworks.

## Live

[rivers.climategapni.com](https://rivers.climategapni.com)
