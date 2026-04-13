#!/bin/bash
# Docker integration test — Phase 9
#
# Prerequisites:
#   - Docker and docker-compose installed
#   - Data files present (annex_a.csv, WFD shapefiles) for a seeded DB
#   - Run from the project root: ./tests/validation/test_docker.sh
#
# The test brings up the full stack, waits for readiness, runs API checks,
# then tears down. Prints PASS or FAIL with per-check detail.

set -euo pipefail

API="http://localhost:8000"
PASS=0
FAIL=0

check() {
  local name="$1"
  local result="$2"
  local expected="$3"
  if echo "$result" | grep -q "$expected"; then
    echo "  [PASS] $name"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name"
    echo "         expected to find: $expected"
    echo "         got: $(echo "$result" | head -c 200)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Docker integration test ==="
echo ""

# ── 1. Build and start ─────────────────────────────────────────────────────
echo "Starting stack (docker-compose up --build -d)..."
docker-compose up --build -d

# ── 2. Wait for API to be ready ────────────────────────────────────────────
echo "Waiting for API to be ready (up to 60s)..."
for i in $(seq 1 12); do
  if curl -sf "$API/health" > /dev/null 2>&1; then
    echo "API ready after $((i * 5))s."
    break
  fi
  if [ "$i" -eq 12 ]; then
    echo "[FAIL] API did not become ready within 60 seconds."
    docker-compose logs api
    docker-compose down
    exit 1
  fi
  sleep 5
done

echo ""
echo "--- Running checks ---"
echo ""

# ── 3. Health check ────────────────────────────────────────────────────────
HEALTH=$(curl -sf "$API/health" || echo "CURL_FAILED")
check "GET /health returns status ok"       "$HEALTH" '"status":"ok"'
check "GET /health reports DB connected"    "$HEALTH" '"database":"connected"'

# ── 4. Stations GeoJSON ────────────────────────────────────────────────────
STATIONS=$(curl -sf "$API/stations/geojson?year=2024" || echo "CURL_FAILED")
check "GET /stations/geojson returns FeatureCollection" "$STATIONS" '"type":"FeatureCollection"'
check "GET /stations/geojson contains features array"   "$STATIONS" '"features":'
check "GET /stations/geojson contains metadata"         "$STATIONS" '"metadata":'

# ── 5. Station timeseries (Six Mile Water) ─────────────────────────────────
SERIES=$(curl -sf "$API/stations/10233/timeseries" || echo "CURL_FAILED")
check "GET /stations/10233/timeseries returns station_code"  "$SERIES" '"station_code":10233'
check "GET /stations/10233/timeseries contains series array" "$SERIES" '"series":'

# Check for roughly 35 years of data by looking for year 1990 and 2024
check "Timeseries contains year 1990" "$SERIES" '"year":1990'
check "Timeseries contains year 2024" "$SERIES" '"year":2024'

# ── 6. Catchments endpoint ─────────────────────────────────────────────────
CATCHMENTS=$(curl -sf "$API/catchments" || echo "CURL_FAILED")
check "GET /catchments returns an array" "$CATCHMENTS" '\['

# ── 7. Tear down ───────────────────────────────────────────────────────────
echo ""
echo "Stopping stack (docker-compose down)..."
docker-compose down

# ── 8. Summary ─────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [ "$FAIL" -eq 0 ]; then
  echo "PASS"
  exit 0
else
  echo "FAIL"
  exit 1
fi
