"""Wind-change detection and weather signs, shared by forecasts (route tables, GRIBs) and observations.

A *change* (HANDOVER §7.10) is the largest wind-direction swing of at least 60° within at most 60 min
whose new direction then holds (within ±30°) for at least 30 min; the mean breeze in the 30 min before and
after must also differ by 60° or more. Directions are interpolated onto a
10-minute grid through speed-weighted wind vectors, so light and variable air counts for little.
Supporting signs: pressure bottoming then jumping, temperature dropping, rain starting.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core import geo

STEP_S = 600.0


@dataclass
class WindGrid:
    t: np.ndarray
    twd: np.ndarray
    tws: np.ndarray


@dataclass
class Change:
    t: float                 # best estimate of when the change passes (epoch s)
    t_from: float            # start and end of the swing on the grid
    t_to: float
    twd_from: float          # mean direction in the 30 min before / after the swing (° true)
    twd_to: float
    swing: float             # signed degrees; + veer (clockwise), − back
    tws_before: float
    tws_after: float
    lat: float | None = None
    lon: float | None = None
    signs: dict = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return "veer" if self.swing > 0 else "back"


def wind_grid(t, twd, tws=None, *, step: float = STEP_S, t0: float | None = None, t1: float | None = None) -> WindGrid:
    t = np.asarray(t, dtype=float)
    twd = np.asarray(twd, dtype=float)
    spd = np.ones_like(twd) if tws is None else np.asarray(tws, dtype=float)
    ok = np.isfinite(t) & np.isfinite(twd) & np.isfinite(spd)
    if ok.sum() < 2:
        return WindGrid(np.array([]), np.array([]), np.array([]))
    t, twd, spd = t[ok], twd[ok], spd[ok]
    a = t[0] if t0 is None else max(t0, t[0])
    b = t[-1] if t1 is None else min(t1, t[-1])
    tg = np.arange(np.ceil(a / step) * step, b + 1e-6, step)
    return WindGrid(tg, geo.interp_direction(tg, t, twd, spd), np.interp(tg, t, spd))


def _mean_dir(g: WindGrid, a: float, b: float) -> tuple[float, float]:
    m = (g.t >= a) & (g.t <= b)
    if not m.any():
        return float("nan"), float("nan")
    return geo.circmean(g.twd[m], g.tws[m]), float(np.nanmean(g.tws[m]))


def detect_change(t, twd, tws=None, *, min_swing: float = 60.0, max_window: float = 3600.0, hold: float = 1800.0,
                  hold_tol: float = 30.0, step: float = STEP_S) -> Change | None:
    """The largest sustained direction swing in a series, or None."""
    g = wind_grid(t, twd, tws, step=step)
    n = len(g.t)
    if n < 3:
        return None
    K = int(round(max_window / step))
    H = int(round(hold / step))
    best = None
    for i in range(n):
        if not np.isfinite(g.twd[i]):
            continue
        for k in range(1, K + 1):
            j = i + k
            if j >= n:
                break
            if not np.isfinite(g.twd[j]):
                continue
            d = float(geo.angdiff(g.twd[j], g.twd[i]))
            if abs(d) < min_swing:
                continue
            end = min(n - 1, j + H)
            if end - j < max(1, H // 3):  # near the end of the data: at least 10 min of hold
                continue
            seg = g.twd[j:end + 1]
            if not np.all(np.abs(geo.angdiff(seg[np.isfinite(seg)], g.twd[j])) <= hold_tol):
                continue
            # The breeze before and after must differ too, so a passing flip in light air that ends with the
            # old breeze back is not a change.
            twd_from, _ = _mean_dir(g, g.t[i] - 1800.0, g.t[i])
            twd_to, _ = _mean_dir(g, g.t[j], g.t[j] + hold)
            if not (np.isfinite(twd_from) and np.isfinite(twd_to)):
                continue
            sw = float(geo.angdiff(twd_to, twd_from))
            if abs(sw) < min_swing:
                continue
            cand = (abs(sw), abs(d), -k, -i, i, j)
            if best is None or cand > best:
                best = cand
    if best is None:
        return None
    i, j = best[4], best[5]
    twd_from, tws_before = _mean_dir(g, g.t[i] - 1800.0, g.t[i])
    twd_to, tws_after = _mean_dir(g, g.t[j], g.t[j] + hold)
    return Change(t=float((g.t[i] + g.t[j]) / 2), t_from=float(g.t[i]), t_to=float(g.t[j]), twd_from=twd_from,
                  twd_to=twd_to, swing=float(geo.angdiff(twd_to, twd_from)), tws_before=tws_before, tws_after=tws_after)


def supporting_signs(change: Change, t, mslp=None, airt=None, rain=None) -> dict:
    """Pressure low and jump, temperature drop and rain onset around a change (absent fields skipped)."""
    t = np.asarray(t, dtype=float)
    tc = change.t
    out: dict = {}
    if mslp is not None and np.isfinite(mslp).sum() >= 2:
        p = np.asarray(mslp, dtype=float)
        w = (t >= tc - 3 * 3600) & (t <= tc + 3600) & np.isfinite(p)
        if w.any():
            k = np.flatnonzero(w)[int(np.argmin(p[w]))]
            after = (t >= t[k]) & (t <= t[k] + 3 * 3600) & np.isfinite(p)
            rise = float(np.max(p[after]) - p[k]) if after.any() else 0.0
            out["pressure_min"] = {"t": float(t[k]), "hpa": float(p[k])}
            out["pressure_rise_3h"] = rise
    if airt is not None and np.isfinite(airt).sum() >= 2:
        a = np.asarray(airt, dtype=float)
        before = (t >= tc - 3600) & (t <= tc) & np.isfinite(a)
        after = (t >= tc + 1800) & (t <= tc + 5400) & np.isfinite(a)
        if before.any() and after.any():
            out["temp_drop"] = float(np.mean(a[before]) - np.mean(a[after]))
    if rain is not None and np.isfinite(rain).sum() >= 1:
        r = np.asarray(rain, dtype=float)
        w = (t >= tc - 2 * 3600) & (t <= tc + 2 * 3600) & np.isfinite(r) & (r >= 0.05)
        if w.any():
            out["rain_onset"] = float(t[np.flatnonzero(w)[0]])
    return out


def hourly_shifts(g: WindGrid, *, min_shift: float = 15.0) -> list[dict]:
    """Direction change over each clock hour on the grid; only |shift| >= min_shift is returned."""
    out = []
    if len(g.t) < 2:
        return out
    start = np.ceil(g.t[0] / 3600.0) * 3600.0
    for h in np.arange(start, g.t[-1] - 3600.0 + 1e-6, 3600.0):
        a = np.interp(h, g.t, np.arange(len(g.t)))
        b = np.interp(h + 3600.0, g.t, np.arange(len(g.t)))
        ia, ib = int(round(a)), int(round(b))
        if not (np.isfinite(g.twd[ia]) and np.isfinite(g.twd[ib])):
            continue
        d = float(geo.angdiff(g.twd[ib], g.twd[ia]))
        if abs(d) >= min_shift:
            out.append({"t0": float(h), "t1": float(h + 3600.0), "from": float(g.twd[ia]), "to": float(g.twd[ib]),
                        "shift": d, "kind": "veer" if d > 0 else "back"})
    return out


COMPASS16 = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split()


def compass(deg: float) -> str:
    if deg is None or not np.isfinite(deg):
        return "–"
    return COMPASS16[int(((deg % 360) + 11.25) // 22.5) % 16]
