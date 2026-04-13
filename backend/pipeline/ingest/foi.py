"""FOI CSV ingestion and QA."""

from __future__ import annotations

import pandas as pd


def load_and_clean_foi(csv_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
	"""
	Load and clean the FOI nutrient CSV for downstream processing.

	Returns:
		stations_df: one row per unique station with metadata
		readings_df: all cleaned readings
	"""
	df = pd.read_csv(csv_path, low_memory=False, encoding="utf-8")

	df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
	df["Station Code"] = pd.to_numeric(df["Station Code"], errors="coerce").astype("Int64")

	qualifier_col = "Q.2" if "Q.2" in df.columns else "Q"
	df["below_detection"] = df[qualifier_col].astype(str).str.strip() == "<"
	df.loc[df["below_detection"], "P(SOL) (mg/l)"] = (
		pd.to_numeric(df.loc[df["below_detection"], "P(SOL) (mg/l)"], errors="coerce") / 2
	)

	df["P(SOL) (mg/l)"] = pd.to_numeric(df["P(SOL) (mg/l)"], errors="coerce")
	df["NO3-N (mg/l)"] = pd.to_numeric(df["NO3-N (mg/l)"], errors="coerce")
	df["NO2-N (mg/l)"] = pd.to_numeric(df["NO2-N (mg/l)"], errors="coerce")
	df["Easting"] = pd.to_numeric(df["Easting"], errors="coerce")
	df["Northing"] = pd.to_numeric(df["Northing"], errors="coerce")

	df = df.dropna(subset=["Date", "Station Code"])

	df["year"] = df["Date"].dt.year
	counts = df.groupby(["Station Code", "year"])["P(SOL) (mg/l)"].transform("count")
	df["sparse_year"] = counts < 8

	station_medians = df.groupby("Station Code")["P(SOL) (mg/l)"].transform("median")
	df["likely_outlier"] = df["P(SOL) (mg/l)"] > (station_medians * 20)

	df = df.rename(
		columns={
			"Station Code": "station_code",
			"Location": "location_name",
			"Easting": "easting",
			"Northing": "northing",
			"Date": "reading_date",
			"P(SOL) (mg/l)": "p_sol_mg_l",
			"NO3-N (mg/l)": "no3_n_mg_l",
			"NO2-N (mg/l)": "no2_n_mg_l",
		}
	)

	stations_df = (
		df.groupby("station_code", dropna=False)
		.agg(
			location_name=("location_name", "first"),
			easting=("easting", "first"),
			northing=("northing", "first"),
			first_reading=("reading_date", "min"),
			last_reading=("reading_date", "max"),
			total_readings=("reading_date", "count"),
		)
		.reset_index()
	)

	stations_df["station_code"] = stations_df["station_code"].astype("Int64")

	readings_columns = [
		"station_code",
		"location_name",
		"easting",
		"northing",
		"reading_date",
		"year",
		"p_sol_mg_l",
		"no3_n_mg_l",
		"no2_n_mg_l",
		"below_detection",
		"sparse_year",
		"likely_outlier",
	]
	readings_df = df[readings_columns].copy()
	readings_df["station_code"] = readings_df["station_code"].astype("Int64")

	return stations_df, readings_df