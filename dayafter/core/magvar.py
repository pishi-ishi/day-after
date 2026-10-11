"""Magnetic variation for converting Expedition's magnetic route-table directions to true.

v1 uses a latitude-interpolated table for the NSW and Tasmanian coast (positive = east), anchored on
12.8° E at Sydney (checked against Expedition's Brg°M at Flinders 2026) and about 15° E at Hobart.
A project-file value always wins. The report states which value was used.
"""
from __future__ import annotations

import numpy as np

# (latitude, variation ° E) along the coast, 2026.
_TABLE_LAT = np.array([-43.5, -42.9, -33.85, -28.0])
_TABLE_VAR = np.array([15.15, 15.0, 12.8, 11.4])


def variation_deg_e(lat, override: float | None = None):
    """Variation in degrees east at the given latitude(s); `override` (from the project) wins."""
    if override is not None:
        return np.full(np.shape(lat), float(override)) if np.ndim(lat) else float(override)
    v = np.interp(np.asarray(lat, dtype=float), _TABLE_LAT, _TABLE_VAR)
    return v if np.ndim(lat) else float(v)


def describe(values, override: float | None = None) -> str:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if override is not None:
        return f"{override:.1f}° E (set in the race file)"
    if vals.size == 0:
        return "not needed"
    lo, hi = float(vals.min()), float(vals.max())
    span = f"{lo:.1f}° E" if abs(hi - lo) < 0.05 else f"{lo:.1f}–{hi:.1f}° E"
    return f"{span} (latitude table; set variation_deg_e in race.dayafter.json to override)"
