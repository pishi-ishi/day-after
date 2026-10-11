"""Geometry and angle helpers (nautical miles, degrees). Ported from the Flinders reference scripts."""
from __future__ import annotations

import re

import numpy as np

R_NM = 3440.065  # mean Earth radius in nautical miles

_DDM = re.compile(r"^\s*(\d+)\s+(\d+(?:\.\d+)?)\s*([nsewNSEW])\s*$")


def parse_ddm(text: str) -> float:
    """'33 51.6390s' -> -33.86065. Degrees, decimal minutes, hemisphere letter (Expedition route tables)."""
    m = _DDM.match(text)
    if not m:
        raise ValueError(f"not a degrees-and-minutes position: {text!r}")
    v = int(m.group(1)) + float(m.group(2)) / 60.0
    return -v if m.group(3).lower() in "sw" else v


def haversine_nm(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * R_NM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial great-circle bearing, degrees true in [0, 360)."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    y = np.sin(lon2 - lon1) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(lon2 - lon1)
    return (np.degrees(np.arctan2(y, x)) + 360.0) % 360.0


def wrap360(a):
    return np.mod(a, 360.0)


def angdiff(a, b):
    """Signed smallest difference a - b in degrees, in [-180, 180). Positive = clockwise (veer)."""
    return (np.asarray(a, dtype=float) - np.asarray(b, dtype=float) + 180.0) % 360.0 - 180.0


def circmean(deg, weights=None) -> float:
    """Circular (vector) mean in [0, 360); NaNs ignored; NaN if nothing left or the vectors cancel."""
    a = np.radians(np.asarray(deg, dtype=float))
    w = np.ones_like(a) if weights is None else np.asarray(weights, dtype=float)
    m = np.isfinite(a) & np.isfinite(w)
    if not m.any():
        return float("nan")
    s = float(np.sum(np.sin(a[m]) * w[m]))
    c = float(np.sum(np.cos(a[m]) * w[m]))
    if abs(s) < 1e-12 and abs(c) < 1e-12:
        return float("nan")
    return float((np.degrees(np.arctan2(s, c)) + 360.0) % 360.0)


def to_uv(direction_deg, speed=None):
    """Direction (degrees, 'from' or 'to' alike) and optional speed -> (east, north) components."""
    r = np.radians(np.asarray(direction_deg, dtype=float))
    sp = 1.0 if speed is None else np.asarray(speed, dtype=float)
    return sp * np.sin(r), sp * np.cos(r)


def from_uv(u, v):
    return (np.degrees(np.arctan2(u, v)) + 360.0) % 360.0


def interp_direction(t_new, t, direction_deg, speed=None):
    """Interpolate directions in time through their vectors (speed-weighted when speed is given)."""
    u, v = to_uv(direction_deg, speed)
    ok = np.isfinite(u) & np.isfinite(v) & np.isfinite(t)
    if ok.sum() < 2:
        return np.full(np.shape(t_new), np.nan)
    ui = np.interp(t_new, t[ok], u[ok], left=np.nan, right=np.nan)
    vi = np.interp(t_new, t[ok], v[ok], left=np.nan, right=np.nan)
    return from_uv(ui, vi)


class LocalXY:
    """Equirectangular projection around (lat0, lon0) in nautical miles; fine for course-sized areas."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = float(lat0), float(lon0)
        self.kx = 60.0 * np.cos(np.radians(self.lat0))

    def xy(self, lat, lon):
        return (np.asarray(lon, dtype=float) - self.lon0) * self.kx, (np.asarray(lat, dtype=float) - self.lat0) * 60.0

    def latlon(self, x, y):
        return self.lat0 + np.asarray(y, dtype=float) / 60.0, self.lon0 + np.asarray(x, dtype=float) / self.kx
