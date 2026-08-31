"""Resolve a catchment name for each storm overflow.

Two-step resolution, in priority order:

1. Receiving Waterbody ID → the catchment of the monitoring station on that
   waterbody. NI Water prefixes the WFD waterbody code with "UK"; the WFD site
   data already in the stations table does not, so the prefix is stripped first.
2. Local Management Area → catchment, for the ~600 assets whose receiving
   waterbody is recorded as "Undefined".

Anything unresolved stays null rather than being guessed at — the catchment
dropdown simply will not show those assets.
"""

from __future__ import annotations

import pandas as pd

# NI Water management areas whose name differs from the WFD catchment name used
# throughout the app. Areas not listed here map to themselves (Upper Bann,
# Lower Bann, Ballinderry, Moyola, Six Mile Water).
LMA_TO_CATCHMENT = {
    "River Blackwater": "Blackwater",
    "Braid and Main": "Main",
    "Lough Neagh": "Lough Neagh Peripherals",
}

_UNDEFINED_WATERBODY = {"undefined", "nan", "none", ""}


def normalise_waterbody_id(value: object) -> str | None:
    """Strip NI Water's "UK" prefix so the ID matches stations.river_waterbody_id."""
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _UNDEFINED_WATERBODY:
        return None
    return text[2:] if text.startswith("UK") else text


def resolve_catchments(
    overflows: pd.DataFrame,
    waterbody_to_catchment: dict[str, str],
    known_catchments: set[str] | None = None,
) -> pd.Series:
    """
    Return a catchment name per row, indexed like `overflows`.

    `waterbody_to_catchment` maps a WFD river waterbody ID (no "UK" prefix) to
    the catchment name recorded for stations on it. `known_catchments` optionally
    restricts the management-area fallback to catchments that actually exist in
    the stations table, so a rename upstream surfaces as nulls rather than as a
    catchment the rest of the app has never heard of.
    """
    by_waterbody = (
        overflows["receiving_waterbody_id"]
        .map(normalise_waterbody_id)
        .map(waterbody_to_catchment)
    )

    by_area = overflows["local_management_area"].map(
        lambda area: _resolve_area(area, known_catchments)
    )

    resolved = by_waterbody.fillna(by_area)
    # NaN would reach PostGIS as the float nan rather than NULL.
    return resolved.astype(object).where(resolved.notna(), None)


def _resolve_area(area: object, known_catchments: set[str] | None) -> str | None:
    if area is None or (isinstance(area, float) and pd.isna(area)):
        return None
    name = str(area).strip()
    if not name:
        return None
    catchment = LMA_TO_CATCHMENT.get(name, name)
    if known_catchments is not None and catchment not in known_catchments:
        return None
    return catchment
