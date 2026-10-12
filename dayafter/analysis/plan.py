"""Plan vs reality: our mark times against each optimal route, and each route's forecast against the wind we
sailed in (HANDOVER §7.8–7.9, ACCEPTANCE M1).

Sign convention, used everywhere and labelled on every chart: Δ = actual − route, so positive means we were
behind the route (later), negative ahead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from ..core import geo
from ..ingest.routes import RouteTable
from . import weather
from .race import Passage, binned_wind


def _base(name: str) -> str:
    """'Cape Banks (ret)' -> 'capebanks'."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\((ret|return|2)\)", "", name.lower()))


@dataclass
class Split:
    mark: str
    actual: float | None
    route: dict[str, float | None]          # model -> route time at that mark
    delta: dict[str, float | None]          # model -> actual - route (s)


def match_route_marks(route: RouteTable, passages: list[Passage], window: int = 4) -> dict[int, int]:
    """Course passage index -> route row, in course order: same name (ignoring '(ret)'), else the nearest of
    the next few mark rows within 2 nm (route names such as 'Flinders Island S' for the course's 'FI S')."""
    rows = route.mark_rows()
    out: dict[int, int] = {}
    ptr = 0
    for p in passages:
        cand = rows[ptr:ptr + window]
        hit = next((k for k, (_, nm, _) in enumerate(cand) if _base(nm) == _base(p.name)), None)
        if hit is None:
            d = [float(geo.haversine_nm(route.lat[i], route.lon[i], p.lat, p.lon)) for i, _, _ in cand]
            if d and min(d) < 2.0:
                hit = int(np.argmin(d))
        if hit is not None:
            out[p.index] = cand[hit][0]
            ptr += hit + 1
    return out


def splits(passages: list[Passage], routes: list[RouteTable]) -> list[Split]:
    matches = {r.model: match_route_marks(r, passages) for r in routes}
    out = []
    for p in passages:
        rt, dl = {}, {}
        for r in routes:
            row = matches[r.model].get(p.index)
            rt[r.model] = float(r.t[row]) if row is not None else None
            dl[r.model] = (p.t - rt[r.model]) if (p.t is not None and rt[r.model] is not None) else None
        out.append(Split(mark=p.name, actual=p.t, route=rt, delta=dl))
    return out


@dataclass
class ForecastCheck:
    model: str
    t: np.ndarray                # route rows inside the race
    fc_tws: np.ndarray
    fc_twd: np.ndarray
    obs_tws: np.ndarray          # our 10-min mean wind over the ground at the same times
    obs_twd: np.ndarray
    change_t: float | None       # this model's change along its route
    scores: dict = field(default_factory=dict)


def forecast_vs_observed(route: RouteTable, obs_t: np.ndarray, obs_tws: np.ndarray, obs_twd: np.ndarray,
                         t0: float, t1: float, observed_change: float | None, gun: float,
                         actual_elapsed: float | None) -> ForecastCheck:
    """Each model along its own route (its forecast at the route's position and time) against what we
    measured at the same time (10-min means at our position)."""
    m = (route.t >= t0) & (route.t <= t1)
    t = route.t[m]
    fc_tws, fc_twd = route.get("tws")[m], route.get("twd")[m]
    ct, cs, cd = binned_wind(obs_t, obs_tws, obs_twd, t0, t1)
    o_tws = np.interp(t, ct, cs, left=np.nan, right=np.nan) if len(ct) > 1 else np.full(len(t), np.nan)
    o_twd = geo.interp_direction(t, ct, cd, cs) if len(ct) > 1 else np.full(len(t), np.nan)
    ch = weather.detect_change(route.t, route.get("twd"), route.get("tws"))
    ok = np.isfinite(fc_tws) & np.isfinite(o_tws)
    okd = np.isfinite(fc_twd) & np.isfinite(o_twd)
    scores = {"n": int(ok.sum())}
    if ok.any():
        diff = fc_tws[ok] - o_tws[ok]
        scores.update(tws_bias=float(np.mean(diff)), tws_mae=float(np.mean(np.abs(diff))),
                      tws_ratio=float(np.mean(fc_tws[ok]) / np.mean(o_tws[ok])))
    if okd.any():
        scores["twd_mae"] = float(np.mean(np.abs(geo.angdiff(fc_twd[okd], o_twd[okd]))))
    if ch is not None and observed_change is not None:
        scores["change_error_s"] = float(ch.t - observed_change)
    scores["predicted_elapsed"] = float(route.finish - gun)
    if actual_elapsed is not None:
        scores["elapsed_error_s"] = float(route.finish - gun - actual_elapsed)
    return ForecastCheck(model=route.model, t=t, fc_tws=fc_tws, fc_twd=fc_twd, obs_tws=o_tws, obs_twd=o_twd,
                         change_t=None if ch is None else ch.t, scores=scores)


def rank_models(checks: list[ForecastCheck]) -> list[str]:
    """Best-verified first: wind-speed error, then direction error, then change timing (equal weights on
    normalised errors). Used to choose the crew edition's models."""
    def score(c: ForecastCheck) -> float:
        s = c.scores
        parts = [s.get("tws_mae", 99) / 5.0, s.get("twd_mae", 180) / 30.0]
        if "change_error_s" in s:
            parts.append(abs(s["change_error_s"]) / 3600.0)
        return float(np.mean(parts))
    return [c.model for c in sorted(checks, key=score)]
