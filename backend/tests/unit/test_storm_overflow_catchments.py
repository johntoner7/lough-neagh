"""Unit tests for storm overflow catchment resolution.

No database or file I/O — all tests run from in-process DataFrames.
"""

from __future__ import annotations

import pandas as pd

from backend.pipeline.process.storm_overflow_catchments import (
    normalise_waterbody_id,
    resolve_catchments,
)


WATERBODY_TO_CATCHMENT = {
    "GBNI1NB030308243": "Lough Neagh Peripherals",
    "GBNI1NB060604048": "Upper Bann",
}
KNOWN = {"Lough Neagh Peripherals", "Upper Bann", "Blackwater", "Main", "Moyola"}


def _overflows(rows: list[tuple[str | None, str | None]]) -> pd.DataFrame:
    return pd.DataFrame({
        "receiving_waterbody_id": [r[0] for r in rows],
        "local_management_area": [r[1] for r in rows],
    })


# ---------------------------------------------------------------------------
# normalise_waterbody_id
# ---------------------------------------------------------------------------

class TestNormaliseWaterbodyId:
    def test_strips_uk_prefix(self):
        assert normalise_waterbody_id("UKGBNI1NB030308243") == "GBNI1NB030308243"

    def test_leaves_unprefixed_id_alone(self):
        assert normalise_waterbody_id("GBNI1NB030308243") == "GBNI1NB030308243"

    def test_undefined_becomes_none(self):
        assert normalise_waterbody_id("Undefined") is None

    def test_missing_becomes_none(self):
        assert normalise_waterbody_id(None) is None


# ---------------------------------------------------------------------------
# resolve_catchments
# ---------------------------------------------------------------------------

class TestResolveCatchments:
    def test_waterbody_id_resolves_with_uk_prefix(self):
        df = _overflows([("UKGBNI1NB060604048", "Six Mile Water")])
        assert resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)[0] == "Upper Bann"

    def test_waterbody_wins_over_management_area(self):
        df = _overflows([("UKGBNI1NB030308243", "River Blackwater")])
        result = resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)
        assert result[0] == "Lough Neagh Peripherals"

    def test_undefined_waterbody_falls_back_to_renamed_area(self):
        df = _overflows([("Undefined", "River Blackwater")])
        assert resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)[0] == "Blackwater"

    def test_area_mapping_to_itself(self):
        df = _overflows([("Undefined", "Moyola")])
        assert resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)[0] == "Moyola"

    def test_unknown_waterbody_and_area_stays_none(self):
        df = _overflows([("UKGBNI9ZZ999", "Lough Melvin and Arney")])
        assert resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)[0] is None

    def test_area_outside_known_catchments_is_rejected(self):
        """A catchment the stations table has never heard of is not invented here."""
        df = _overflows([("Undefined", "Quoile")])
        assert resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)[0] is None

    def test_missing_values_stay_none_not_nan(self):
        df = _overflows([(None, None)])
        result = resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)
        assert result[0] is None

    def test_resolves_row_by_row(self):
        df = _overflows([
            ("UKGBNI1NB060604048", "Upper Bann"),
            ("Undefined", "Braid and Main"),
            ("Undefined", None),
        ])
        assert list(resolve_catchments(df, WATERBODY_TO_CATCHMENT, KNOWN)) == [
            "Upper Bann", "Main", None,
        ]
