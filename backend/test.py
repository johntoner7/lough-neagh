import geopandas as gpd
import pandas as pd
from pathlib import Path

wfd_path = Path('WFD_River_and_Lake_Monitoring_Sites_-1026036712144107026.geojson')
wfd = gpd.read_file(wfd_path)
foi_path = Path('annex_a.csv')
foi = pd.read_csv(foi_path, low_memory=False)

# Strip F prefix from monitoring code and convert to int
wfd['station_code_int'] = wfd['monitoring'].str.lstrip('F').astype(int)

foi_codes = set(foi['Station Code'].unique())
wfd_codes = set(wfd['station_code_int'].unique())

overlap = foi_codes & wfd_codes
print(f'Overlap after stripping F prefix: {len(overlap)}')
print(f'WFD total sites: {len(wfd_codes)}, FOI total stations: {len(foi_codes)}')
print(f'WFD stations NOT in FOI: {len(wfd_codes - foi_codes)}')
print(f'FOI stations NOT in WFD: {len(foi_codes - wfd_codes)}')

# Check the 6 key tributary mouth stations specifically
key_stations = {10233: 'Six Mile Water', 10212: 'River Main', 10380: 'Moyola',
                10361: 'Ballinderry', 10328: 'Blackwater', 10271: 'Upper Bann'}
print('\n=== KEY TRIBUTARY STATIONS IN WFD SHAPEFILE? ===')
for code, name in key_stations.items():
    match = wfd[wfd['station_code_int'] == code]
    if len(match) > 0:
        row = match.iloc[0]
        print(f'✓ {name} ({code}): WFD waterbody={row["river_wate"]}, catchment={row["catchment"]}')
    else:
        print(f'✗ {name} ({code}): NOT FOUND in WFD shapefile')

# For matched stations, show what waterbody IDs attach
print('\n=== SAMPLE MATCHED STATIONS WITH WFD WATERBODY IDS ===')
matched_wfd = wfd[wfd['station_code_int'].isin(foi_codes)]
print(matched_wfd[['station_code_int', 'monitori_1', 'river_wate', 'catchment']].head(20).to_string())

# FOI-only stations — likely decommissioned or non-WFD designated
foi_only = foi_codes - wfd_codes
print(f'\nSample FOI-only station codes (not in WFD): {sorted(list(foi_only))[:20]}')