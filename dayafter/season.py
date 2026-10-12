"""The season database: one SQLite file holding derived numbers for every analysed race (DESIGN.md, Season).

Raw logs stay where they are; the database keeps results, polar % and targets, calibration, model
verification, fleet gaps and manoeuvres, keyed by race, so it stays small and can be rebuilt by running
`dayafter build` on each race folder again. Re-analysing a race replaces its rows.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

import numpy as np

SCHEMA = """
create table if not exists race (
  race_id text primary key, name text, boat text, gun real, tz text, folder text, course_nm real,
  place integer, finishers integer, elapsed real, corrected real, tcc real, k real, twa_source text,
  polar_pct real, tws_mean real, tws_max real, updated real
);
create table if not exists perf (
  race_id text, tws0 real, tws1 real, pos text, n integer, pct real, p25 real, p75 real, indicative integer
);
create table if not exists target (
  race_id text, tws0 real, tws1 real, side text, n integer, stw real, twa real, vmg real,
  polar_stw real, polar_twa real, polar_vmg real
);
create table if not exists sail_perf (
  race_id text, sail text, n integer, tws real, twa real, pct real
);
create table if not exists calibration (
  race_id text, check_id text, status text, value text, data text
);
create table if not exists model (
  race_id text, model text, source text, tws_bias real, tws_mae real, tws_ratio real, twd_mae real,
  change_error_s real
);
create table if not exists fleet (
  race_id text, boat text, division text, tcc real, place integer, elapsed real, corrected real,
  gap_s real, rounding real, rival integer
);
create table if not exists manoeuvre (
  race_id text, t real, kind text, tws real, loss_m real, loss_s real, sail text
);
"""
TABLES = ("perf", "target", "sail_perf", "calibration", "model", "fleet", "manoeuvre")


def default_path() -> str:
    """`season.sqlite` next to the app: beside the binary, or at the repository root from source.
    DAYAFTER_SEASON overrides it."""
    env = os.environ.get("DAYAFTER_SEASON")
    if env:
        return env
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "season.sqlite")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "season.sqlite")


def connect(path: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(path or default_path())
    con.executescript(SCHEMA)
    return con


def race_id(a) -> str:
    from .core import timeutil
    day = timeutil.fmt_local(a.gun, a.tz, "%Y-%m-%d")
    return f"{day} {a.race_name}"


def _f(v):
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def store(a, perf=None, path: str | None = None) -> str:
    """Write (or replace) one race. Returns its race id."""
    rid = race_id(a)
    con = connect(path)
    try:
        with con:
            con.execute("delete from race where race_id = ?", (rid,))
            for tname in TABLES:
                con.execute(f"delete from {tname} where race_id = ?", (rid,))
            res = a.result
            legs = [p for p in a.phases if p.kind == "leg"]
            overall = None
            if perf is not None and perf.phases:
                w = np.array([p.n for p in perf.phases], float)
                overall = float(np.average([p.pct for p in perf.phases], weights=w))
            course_nm = float(a.fleet.course_nm) if a.fleet is not None else None
            con.execute("insert into race values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                rid, a.race_name, a.boat, a.gun, a.tz, a.folder, course_nm,
                res.place if res else None, sum(r.finished for r in a.results) or None, _f(a.elapsed),
                _f(res.corrected) if res else None, _f(res.tcc) if res else None, _f(a.k),
                perf.twa_source if perf else None, overall,
                _f(np.average([p.tws for p in legs], weights=[p.minutes for p in legs])) if legs else None,
                _f(max((p.tws_p95 for p in legs), default=None)), time.time()))
            if perf is not None:
                con.executemany("insert into perf values (?,?,?,?,?,?,?,?,?)", [
                    (rid, b["tws0"], b["tws1"], b["pos"], b["n"], _f(b["pct"]), _f(b["p25"]), _f(b["p75"]),
                     int(b["indicative"])) for b in perf.buckets])
                con.executemany("insert into target values (?,?,?,?,?,?,?,?,?,?,?)", [
                    (rid, x["tws0"], x["tws1"], x["side"], x["n"], _f(x["stw"]), _f(x["twa"]), _f(x["vmg"]),
                     _f(x["polar_stw"]), _f(x["polar_twa"]), _f(x["polar_vmg"])) for x in perf.targets])
                con.executemany("insert into sail_perf values (?,?,?,?,?,?)", [
                    (rid, s["sail"], s["n"], _f(s["tws"]), _f(s["twa"]), _f(s["pct"])) for s in perf.by_sail])
                con.executemany("insert into manoeuvre values (?,?,?,?,?,?,?)", [
                    (rid, m.t, m.kind, _f(m.tws), _f(m.loss_m), _f(m.loss_s), m.sail) for m in perf.manoeuvres])
            con.executemany("insert into calibration values (?,?,?,?,?)", [
                (rid, c.id, c.status, c.value, json.dumps(c.data, default=float)) for c in a.checks])
            rows = []
            for f in a.forecasts:
                s = f.scores
                rows.append((rid, f.model, "route", _f(s.get("tws_bias")), _f(s.get("tws_mae")), _f(s.get("tws_ratio")),
                             _f(s.get("twd_mae")), _f(s.get("change_error_s"))))
            if a.forecast is not None:
                for m in a.forecast.models:
                    s = m.scores
                    rows.append((rid, m.model, "grib", _f(s.get("tws_bias")), _f(s.get("tws_mae")),
                                 _f(s.get("tws_ratio")), _f(s.get("twd_mae")), _f(s.get("change_error_s"))))
            con.executemany("insert into model values (?,?,?,?,?,?,?,?)", rows)
            f = a.fleet
            if f is not None and f.us is not None:
                con.executemany("insert into fleet values (?,?,?,?,?,?,?,?,?,?)", [
                    (rid, b.name, b.result.division, _f(b.tcc), b.result.place, _f(b.elapsed), _f(b.result.corrected),
                     _f(f.gaps.get(b.name, [np.nan])[-1]), _f(b.rounding), int(b.name in f.rivals)) for b in f.boats])
    finally:
        con.close()
    return rid


def load(path: str | None = None) -> dict:
    """Everything the Season views need, as plain lists of dicts (newest race last)."""
    p = path or default_path()
    if not os.path.exists(p):
        return {"races": []}
    con = connect(p)
    con.row_factory = sqlite3.Row
    try:
        q = lambda sql, *args: [dict(r) for r in con.execute(sql, args)]
        races = q("select * from race order by gun")
        return {
            "races": races,
            "perf": q("select race_id, pos, sum(n) n, sum(pct * n) / sum(n) pct from perf group by race_id, pos"),
            "targets": q("select * from target order by side, tws0"),
            "models": q("select race_id, model, source, tws_ratio, tws_mae, twd_mae, change_error_s from model"),
            "calibration": q("select race_id, check_id, status, value from calibration"),
            "rivals": q("select f.race_id, f.boat, f.tcc, f.gap_s, f.place from fleet f where f.rival = 1"),
            "head_to_head": q("""select boat, count(*) races, sum(case when gap_s < 0 then 1 else 0 end) ahead,
                                 avg(gap_s) mean_gap_s from fleet where boat != (select boat from race r
                                 where r.race_id = fleet.race_id) group by boat having races >= 1"""),
            "tcc": q("select boat, tcc, max(race_id) last_race from fleet group by boat"),
            "manoeuvres": q("select race_id, kind, count(*) n, avg(loss_m) loss_m, avg(tws) tws from manoeuvre "
                            "group by race_id, kind"),
        }
    finally:
        con.close()
