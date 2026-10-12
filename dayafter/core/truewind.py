"""True wind from apparent wind (ported from the Flinders reference `llama.py::true_wind`).

Boat frame: x forward, y to starboard. The apparent wind blows *from* AWA, so its velocity is
−AWS·(cos AWA, sin AWA). Adding the boat's velocity gives the true wind: through the water with boat speed
along the heading, or over the ground with SOG along COG. TWA is signed (+ starboard), TWD = HDG + TWA.
"""
from __future__ import annotations

import numpy as np


def _solve(aws, awa, vx, vy):
    r = np.radians(np.asarray(awa, dtype=float))
    aws = np.asarray(aws, dtype=float)
    tx = -aws * np.cos(r) + vx
    ty = -aws * np.sin(r) + vy
    tws = np.hypot(tx, ty)
    twa = (np.degrees(np.arctan2(-ty, -tx)) + 180.0) % 360.0 - 180.0
    return tws, twa


def water(aws, awa, bsp, hdg):
    """True wind through the water from (corrected) boat speed: (TWS, TWA, TWD)."""
    tws, twa = _solve(aws, awa, np.asarray(bsp, dtype=float), 0.0)
    return tws, twa, (np.asarray(hdg, dtype=float) + twa) % 360.0


def ground(aws, awa, sog, cog, hdg):
    """True wind over the ground (what a forecast predicts): (TWS, TWD). Independent of the log's boat speed."""
    rel = np.radians(np.asarray(cog, dtype=float) - np.asarray(hdg, dtype=float))
    sog = np.asarray(sog, dtype=float)
    tws, twa = _solve(aws, awa, sog * np.cos(rel), sog * np.sin(rel))
    return tws, (np.asarray(hdg, dtype=float) + twa) % 360.0
