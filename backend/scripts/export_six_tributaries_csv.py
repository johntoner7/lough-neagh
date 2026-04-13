import csv

import psycopg2

OUTPUT = 'data/six_main_tributaries_metrics.csv'
KEY_STATIONS = {
    10212: 'River Main',
    10233: 'Six Mile Water',
    10271: 'Upper Bann',
    10328: 'Blackwater',
    10361: 'Ballinderry',
    10380: 'Moyola',
}

conn = psycopg2.connect('postgresql://user:password@localhost:5433/phosphorus_db')
cur = conn.cursor()

cur.execute(
    '''
    SELECT
        am.station_code,
        am.year,
        am.annual_mean_p_sol,
        am.rolling_mean_5yr,
        am.reading_count
    FROM annual_metrics am
    WHERE am.station_code = ANY(%s)
    ORDER BY am.station_code, am.year
    ''',
    (list(KEY_STATIONS.keys()),),
)
rows = cur.fetchall()

with open(OUTPUT, 'w', newline='') as file_obj:
    writer = csv.writer(file_obj)
    writer.writerow(['river', 'year', 'annual_mean', 'rolling_mean', 'n_readings'])
    for station_code, year, annual_mean, rolling_mean, reading_count in rows:
        writer.writerow([
            KEY_STATIONS[station_code],
            year,
            None if annual_mean is None else float(annual_mean),
            None if rolling_mean is None else float(rolling_mean),
            int(reading_count) if reading_count is not None else 0,
        ])

cur.close()
conn.close()

print(f'Wrote {len(rows)} rows to {OUTPUT}')
