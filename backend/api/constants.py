"""Shared constants for the API."""

from __future__ import annotations

WFD_THRESHOLD_MG_L: float = 0.035

# NI Water modelled storm overflow spills — a single published snapshot, not a
# time series. Surfaced in API responses so clients can label it honestly.
STORM_OVERFLOW_SNAPSHOT: str = "NI Water modelled estimates, November 2025"
