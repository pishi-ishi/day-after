"""Forecast at our position: each GRIB model sampled along our own track and compared with what we logged.

The route tables give each model's forecast along its own optimal route (plan.py). Here every GRIB model
is read where we actually were, so the models are judged on the same water at the same time. Forecast
10 m wind is scaled to masthead height by the boat's `masthead_factor` (1.0 unless set). ACCESS reaches
Day After only through route tables: Expedition encrypts its GRIBs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

from ..core import geo
from ..core.wxmodel import rank as model_rank
from ..ingest import bom as bom_mod
from ..ingest.grib import Cube, load_cubes, model_from_filename  # noqa: F401 (re-export)
from . import weather
from .race import binned_wind

STEP_S = 600.0


@dataclass
class ModelAtUs:
    model: str
    path: str
    run: float                   # model run (UTC epoch)
    downloaded: float | None     # when Expedition fetched the file
    t: np.ndarray                # 10-min bin centres along the race
    tws: np.ndarray              # forecast, masthead-scaled
    twd: np.ndarray
    gust: np.ndarray
    mslp: np.ndarray
    t2m: np.ndarray
    rain: np.ndarray             # mm/h
    change_t: float | None
    scores: dict = field(default_factory=dict)
    windows: list[dict] = field(default_factory=list)   # per phase: forecast vs observed means


@dataclass
class Station:
    name: str
    wmo: str
    lat: float
    lon: float
    t: np.ndarray
    wind_kt: np.ndarray
    gust_kt: np.ndarray
    wind_dir: np.ndarray
    press: np.ndarray


@dataclass
class ForecastAtUs:
    obs_t: np.ndarray
    obs_tws: np.ndarray
    obs_twd: np.ndarray
    models: list[ModelAtUs]
    masthead_factor: float
    notes: list[str]
    stations: list[Station] = field(default_factory=list)

    def ranked(self) -> list[str]:
        return [m.model for m in sorted(self.models, key=lambda m: m.scores.get("score", 99))]


def pick_runs(cubes: list[Cube], gun: float, t0: float, t1: float, lat, lon) -> list[Cube]:
    """Per model, the forecast we had at the gun: the latest run among files downloaded before the gun (by the
    download stamp in Expedition's file name; by run time when there is no stamp) that covers the race track.
    With nothing from before the gun, the earliest run that covers it. Ties on the run go to the file with more
    fields (GFS 0.25° carries pressure and temperature, Expedition's GFS 0.11° only wind and rain), then the
    longer forecast."""
    by: dict[str, list[Cube]] = {}
    for c in cubes:
        lo, hi = c.t_range
        if not (lo <= t1 and hi >= t0) or not c.covers(np.nanmin(lat), np.nanmin(lon)) or \
                not c.covers(np.nanmax(lat), np.nanmax(lon)):
            continue
        by.setdefault(c.model, []).append(c)
    out = []
    for model, cs in by.items():
        before = [c for c in cs if (c.downloaded if c.downloaded is not None else c.ref) <= gun]
        if before:
            out.append(max(before, key=lambda c: (c.ref, len(c.params), c.t_range[1], c.downloaded or 0)))
        else:
            out.append(max(cs, key=lambda c: (-c.ref, len(c.params), c.t_range[1])))
    return sorted(out, key=lambda c: (model_rank(c.model), c.model))


def _window_stats(t, fc, ob, a, b) -> dict | None:
    m = (t >= a) & (t <= b) & np.isfinite(fc) & np.isfinite(ob)
    if m.sum() < 1:
        return None
    f, o = float(np.mean(fc[m])), float(np.mean(ob[m]))
    return {"fc": f, "obs": o, "fc_min": float(np.min(fc[m])), "fc_max": float(np.max(fc[m])),
            "obs_min": float(np.min(ob[m])), "obs_max": float(np.max(ob[m])), "ratio": f / o if o > 0 else None,
            "n": int(m.sum())}


def forecast_at_us(gribs: list[str], tl, wind, start: float, finish: float, gun: float,
                   observed_change: float | None, phases=(), masthead_factor: float = 1.0,
                   bom_files: list[str] = (), tz: str | None = None, log=None) -> ForecastAtUs | None:
    say = log or (lambda m: None)
    t = tl.t.astype(float)
    ot, ows, owd = binned_wind(t, wind.tws_g, wind.twd_g, start, finish, STEP_S)
    if len(ot) < 3:
        return None
    lat = np.interp(ot, t, tl["Lat"])
    lon = np.interp(ot, t, tl["Lon"])
    notes: list[str] = []
    cubes: list[Cube] = []
    if gribs:
        say(f"reading {len(gribs)} GRIB file(s)")
        cubes, notes = load_cubes(gribs, tz)
    chosen = pick_runs(cubes, gun, start, finish, lat, lon)
    models = []
    for c in chosen:
        tws, twd = c.wind(ot, lat, lon)
        tws = tws * masthead_factor
        gust = c.sample("gust", ot, lat, lon) * masthead_factor
        m = ModelAtUs(model=c.model, path=c.path, run=c.ref, downloaded=c.downloaded, t=ot, tws=tws, twd=twd, gust=gust,
                      mslp=c.sample("mslp", ot, lat, lon), t2m=c.sample("t2m", ot, lat, lon),
                      rain=c.sample("prate", ot, lat, lon), change_t=None)
        ok = np.isfinite(tws) & np.isfinite(ows)
        s: dict = {"n": int(ok.sum())}
        if ok.any():
            d = tws[ok] - ows[ok]
            s.update(tws_bias=float(np.mean(d)), tws_mae=float(np.mean(np.abs(d))),
                     tws_ratio=float(np.mean(tws[ok]) / np.mean(ows[ok])))
            okd = ok & np.isfinite(twd) & np.isfinite(owd)
            s["twd_mae"] = float(np.mean(np.abs(geo.angdiff(twd[okd], owd[okd])))) if okd.any() else None
        ch = weather.detect_change(ot, twd, tws)
        if ch is not None:
            m.change_t = ch.t
            if observed_change is not None:
                s["change_error_s"] = float(ch.t - observed_change)
        parts = [s.get("tws_mae", 99) / 5.0, (s.get("twd_mae") or 180) / 30.0]
        if "change_error_s" in s:
            parts.append(abs(s["change_error_s"]) / 3600.0)
        s["score"] = float(np.mean(parts))
        m.scores = s
        for ph in phases:
            w = _window_stats(ot, tws, ows, ph.t0, ph.t1)
            if w:
                m.windows.append({"name": ph.name, "kind": ph.kind, "t0": ph.t0, "t1": ph.t1, **w})
        models.append(m)
    if gribs and not models:
        notes.append("no readable GRIB covers our track during the race")
    stations = []
    for p in bom_files:
        try:
            d = bom_mod.read_axf(p)
        except (OSError, ValueError) as e:
            notes.append(f"{os.path.basename(p)}: {e}")
            continue
        k = (d["t"] >= start - 3600) & (d["t"] <= finish + 3600)
        if k.sum() < 2:
            continue
        stations.append(Station(d["name"], d["wmo"], d["lat"], d["lon"], d["t"][k], d["wind_kt"][k],
                                d["gust_kt"][k], d["wind_dir"][k], d["press_msl"][k]))
    if bom_files and not stations:
        notes.append("the BOM station files hold no observations from the race window (download them within "
                      "72 h of the finish)")
    return ForecastAtUs(obs_t=ot, obs_tws=ows, obs_twd=owd, models=models, masthead_factor=masthead_factor,
                        notes=notes, stations=stations)


def headline_models(fa: ForecastAtUs) -> list[ModelAtUs]:
    """At most three models for charts and headlines (BRAND §2): GFS and ECMWF in their own colours, plus the
    best-verified other model in neutral grey. Tables list every model."""
    core = [m for m in fa.models if m.model in ("ECMWF", "GFS", "ACCESS")]
    rest = sorted((m for m in fa.models if m not in core), key=lambda m: m.scores.get("score", 99))
    return (core + rest)[:3]


def light_pct(ratio: float | None) -> int | None:
    """0.62 -> 38 (% light); negative means the model was too strong."""
    return None if ratio is None else int(round((1 - ratio) * 100))


def grib_along_route(gribs: list[str], route, tz: str, gun: float | None = None, encrypted: list[str] = (),
                     masthead_factor: float = 1.0) -> dict | None:
    """Every GRIB model sampled along one route (its times and positions): what each model says the boat on
    that route would meet. Used by the Day Before briefing and the crew edition for models without a route
    table. Per model the latest run downloaded before `gun` (default: the route's start)."""
    cubes, notes = load_cubes(gribs, tz)
    t, lat, lon = route.t, route.lat, route.lon
    chosen = pick_runs(cubes, gun if gun is not None else float(t[0]), float(t[0]), float(t[-1]), lat, lon)
    models = []
    for c in chosen:
        tws, twd = c.wind(t, lat, lon)
        tws = tws * masthead_factor
        ch = weather.detect_change(t, twd, tws)
        models.append({"model": c.model, "run": c.ref, "downloaded": c.downloaded, "file": os.path.basename(c.path),
                       "t": t, "tws": tws, "twd": twd, "gust": c.sample("gust", t, lat, lon) * masthead_factor,
                       "mslp": c.sample("mslp", t, lat, lon), "change": None if ch is None else ch.t})
    notes = [n for n in notes if "encrypted by Expedition" not in n]
    if encrypted:
        names = sorted({model_from_filename(p)[0] for p in encrypted})
        notes.append(f"{len(encrypted)} GRIB file(s) ({', '.join(names)}) are encrypted by Expedition and were "
                     "skipped; those models appear through their route tables only")
    if not models and not notes:
        return None
    return {"route_model": route.model, "models": models, "notes": notes}
