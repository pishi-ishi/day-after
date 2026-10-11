"""Day Before: the crew weather briefing built from Expedition route tables (no boat log needed).

Per model: the forecast along its own optimal route (meteogram), when the wind change comes and with
which signs, the ETA at the turning mark, the planned sails and the tacks, gybes and shifts. Across
models: the change window against the turning-mark ETAs, and every predicted finish (route tables and
"summary of all routes" files).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import numpy as np

from ..core import geo, magvar, timeutil
from ..core.wxmodel import canonical_model, rank
from ..ingest import course as course_mod
from ..ingest import detect, project as project_mod, yb
from ..ingest.routes import RouteSummary, RouteTable, read_route_summary, read_route_table
from . import weather

MAX_CREW_MODELS = 3


@dataclass
class ModelPlan:
    model: str
    route: RouteTable
    marks: list[dict]
    eta_turning: float | None
    change: weather.Change | None
    sail_runs: list[dict]
    manoeuvres: list[dict]
    shifts: list[dict]
    callouts: list[dict]
    stats: dict

    @property
    def finish(self) -> float:
        return self.route.finish


@dataclass
class Briefing:
    folder: str
    race_name: str
    boat: str
    tz: str
    gun: float
    gun_source: str
    plans: list[ModelPlan]
    other_routes: list[RouteTable]
    summaries: list[RouteSummary]
    course: course_mod.Course
    islands: list[course_mod.Island]
    window: dict | None
    finishes: list[dict]
    variation_text: str
    notes: str
    warnings: list[str] = field(default_factory=list)
    generated: float = field(default_factory=time.time)

    @property
    def turning_name(self) -> str:
        tm = self.course.turning_mark
        return tm.name if tm else ""

    @property
    def turning_label(self) -> str:
        return turning_label(self.turning_name)


def turning_label(name: str) -> str:
    """How the crew text names the turning mark: Windy GPX points are bare numbers."""
    if not name:
        return "the turning mark"
    return f"the turning mark (point {name})" if name.strip().isdigit() else name


# ---------------------------------------------------------------------------------------------- helpers

def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def route_mark_times(route: RouteTable, course: course_mod.Course) -> list[dict]:
    """Every mark the route reaches, with its time. The course's turning mark is flagged on its first
    passage: by name, else the closest mark row within 1 nm (rounding groups such as FI W/S/E sit close)."""
    out = [{"name": name, "occurrence": occ, "t": float(route.t[i]), "lat": float(route.lat[i]),
            "lon": float(route.lon[i]), "turning": False} for i, name, occ in route.mark_rows()]
    tm = course.turning_mark
    if tm is None or not out:
        return out
    named = [m for m in out if _norm(m["name"]) == _norm(tm.name)]
    if named:
        named[0]["turning"] = True
        return out
    d = [float(geo.haversine_nm(m["lat"], m["lon"], tm.lat, tm.lon)) for m in out]
    k = int(np.argmin(d))
    if d[k] < 1.0:
        out[k]["turning"] = True
    return out


def eta_at(route: RouteTable, lat: float, lon: float) -> float | None:
    """Time of the route's closest approach to a position (linear between rows); None if > 2 nm away."""
    d = geo.haversine_nm(route.lat, route.lon, lat, lon)
    if not np.isfinite(d).any():
        return None
    k = int(np.nanargmin(d))
    if d[k] > 2.0:
        return None
    best_t, best_d = float(route.t[k]), float(d[k])
    xy = geo.LocalXY(lat, lon)
    for a, b in ((k - 1, k), (k, k + 1)):
        if a < 0 or b >= len(route.t):
            continue
        ax, ay = xy.xy(route.lat[a], route.lon[a])
        bx, by = xy.xy(route.lat[b], route.lon[b])
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 <= 0:
            continue
        f = float(np.clip(-(ax * dx + ay * dy) / L2, 0.0, 1.0))
        dd = float(np.hypot(ax + f * dx, ay + f * dy))
        if dd < best_d:
            best_d, best_t = dd, float(route.t[a] + f * (route.t[b] - route.t[a]))
    return best_t


def sail_runs(route: RouteTable, min_run_s: float = 300.0) -> list[dict]:
    """Planned sails as runs. Runs shorter than `min_run_s` (artefacts of mark-rounding rows) are dropped."""
    runs: list[dict] = []
    for i, s in enumerate(route.sail_filled):
        if not s or (runs and runs[-1]["sail"] == s):
            continue
        if runs:
            runs[-1]["t1"] = float(route.t[i])
        runs.append({"sail": s, "t0": float(route.t[i]), "t1": route.finish})
    kept: list[dict] = []
    for k, r in enumerate(runs):
        short = r["t1"] - r["t0"] < min_run_s and k < len(runs) - 1
        if short:
            runs[k + 1]["t0"] = r["t0"] if not kept else runs[k + 1]["t0"]
            if kept:
                kept[-1]["t1"] = runs[k + 1]["t0"]
            continue
        if kept and kept[-1]["sail"] == r["sail"]:
            kept[-1]["t1"] = r["t1"]
        else:
            kept.append(dict(r))
    return kept


def manoeuvres(route: RouteTable) -> list[dict]:
    """Tacks and gybes where the route's TWA changes sign between consecutive rows."""
    twa = route.get("twa")
    out = []
    prev = None
    for j in range(len(twa)):
        if not np.isfinite(twa[j]) or twa[j] == 0:
            continue
        if prev is not None and np.sign(twa[prev]) != np.sign(twa[j]):
            a, b = abs(twa[prev]), abs(twa[j])
            kind = "tack" if max(a, b) < 90 else "gybe" if min(a, b) > 90 else "turn"
            mark = route.mark[j] or route.mark[prev]
            out.append({"t": float(route.t[j]), "kind": kind, "twa_from": float(twa[prev]), "twa_to": float(twa[j]),
                        "mark": mark})
        prev = j
    return out


def _arg(values: np.ndarray, fn) -> int | None:
    v = np.asarray(values, dtype=float)
    if not np.isfinite(v).any():
        return None
    return int(fn(np.where(np.isfinite(v), v, np.nan)))


def plan_stats(route: RouteTable) -> dict:
    s: dict = {}
    k = _arg(route.get("tws"), np.nanargmax)
    if k is not None:
        s["tws_max"] = {"t": float(route.t[k]), "kt": float(route.get("tws")[k])}
    k = _arg(route.get("twg"), np.nanargmax)
    if k is not None:
        s["gust_max"] = {"t": float(route.t[k]), "kt": float(route.get("twg")[k])}
    k = _arg(route.get("mslp"), np.nanargmin)
    if k is not None:
        s["mslp_min"] = {"t": float(route.t[k]), "hpa": float(route.get("mslp")[k])}
    return s


def _hm(t: float | None, tz: str) -> str:
    return timeutil.fmt_local(t, tz, "%H:%M")


def _span(sec: float) -> str:
    """'22 min' or '2 h 04 min'."""
    m = int(round(abs(sec) / 60.0))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def callouts(plan_route: RouteTable, change: weather.Change | None, eta: float | None, turning: str,
             stats: dict, tz: str) -> list[dict]:
    """'How to read this' sentences, in the order the crew will meet them."""
    out = []
    if "tws_max" in stats:
        g = stats.get("gust_max")
        gust = f" (gusts {g['kt']:.0f})" if g else ""
        out.append({"t": stats["tws_max"]["t"], "kind": "wind",
                    "text": f"Strongest breeze about {stats['tws_max']['kt']:.0f} kt{gust} around "
                            f"{_hm(stats['tws_max']['t'], tz)}."})
    if change is not None:
        sw = abs(change.swing)
        how = "swings round" if sw >= 150 else ("veers" if change.swing > 0 else "backs")
        out.append({"t": change.t, "kind": "change",
                    "text": f"The change: wind {how} from {weather.compass(change.twd_from)} to "
                            f"{weather.compass(change.twd_to)} around {_hm(change.t, tz)} "
                            f"({sw:.0f}°), {change.tws_before:.0f} → {change.tws_after:.0f} kt."})
        sg = change.signs
        if "pressure_min" in sg and sg.get("pressure_rise_3h", 0) >= 1.0:
            rise = sg["pressure_rise_3h"]
            tail = ("the pressure jump that comes with the change." if rise >= 2.5
                    else "a slow rise, not the sharp jump of a strong change.")
            out.append({"t": sg["pressure_min"]["t"], "kind": "pressure",
                        "text": f"Pressure bottoms at {sg['pressure_min']['hpa']:.1f} hPa around "
                                f"{_hm(sg['pressure_min']['t'], tz)}, then rises {rise:.1f} hPa in three hours: {tail}"})
        if sg.get("temp_drop", 0) >= 1.0:
            out.append({"t": change.t, "kind": "temperature",
                        "text": f"Air temperature drops about {sg['temp_drop']:.0f} °C after the change."})
        if "rain_onset" in sg:
            out.append({"t": sg["rain_onset"], "kind": "rain", "text": f"Rain from around {_hm(sg['rain_onset'], tz)}."})
        if eta is not None:
            dt = change.t - eta
            out.append({"t": eta, "kind": "rounding",
                        "text": f"Reaches {turning} at {_hm(eta, tz)}, about {_span(dt)} "
                                f"{'before' if dt > 0 else 'after'} the change."})
    elif eta is not None:
        out.append({"t": eta, "kind": "rounding",
                    "text": f"Reaches {turning} at {_hm(eta, tz)}. No sustained wind change on this route."})
    return sorted(out, key=lambda c: c["t"])


def change_window(plans: list[ModelPlan], tz: str, turning: str, has_turning: bool = True) -> dict | None:
    with_change = [p for p in plans if p.change is not None]
    if not with_change:
        return None
    times = [(p.model, p.change.t) for p in with_change]
    etas = [(p.model, p.eta_turning) for p in plans if p.eta_turning is not None]
    t0, t1 = min(t for _, t in times), max(t for _, t in times)
    before = [p.model for p in with_change if p.eta_turning is not None and p.eta_turning < p.change.t]
    after = [p.model for p in with_change if p.eta_turning is not None and p.eta_turning >= p.change.t]
    n = len(before) + len(after)
    if n == 0 and not has_turning:
        verdict = ("No turning mark was identified (name it as course.turning_mark in race.dayafter.json), so "
                   "there is no rounding-versus-change comparison.")
    elif n == 0:
        verdict = f"The routes do not pass {turning}, so there is no rounding-versus-change comparison."
    elif not after:
        verdict = f"Every model has us rounding {turning} before the change arrives."
    elif not before:
        verdict = f"Every model has the change arriving before we reach {turning}."
    else:
        verdict = (f"The models disagree: {', '.join(before)} {'has' if len(before) == 1 else 'have'} us rounding "
                   f"{turning} before the change; {', '.join(after)} {'brings' if len(after) == 1 else 'bring'} "
                   "the change first.")
    return {"t0": t0, "t1": t1, "changes": times, "etas": etas, "before": before, "after": after, "verdict": verdict}


def finish_table(routes: list[RouteTable], summaries: list[RouteSummary], gun: float) -> list[dict]:
    rows = []
    for r in routes:
        rows.append({"model": r.model, "label": r.label, "run": r.created, "source": "route table",
                     "finish": r.finish, "elapsed": r.finish - gun, "file": os.path.basename(r.path)})
    for s in summaries:
        for x in s.rows:
            if x.finish is None or x.is_reference and not x.label:
                continue
            rows.append({"model": x.model, "label": x.label, "run": x.created, "source": "summary",
                         "finish": x.finish, "elapsed": x.elapsed, "file": os.path.basename(s.path)})
    rows.sort(key=lambda r: (r["run"] or 0, rank(r["model"]), r["model"]))
    return rows


# ---------------------------------------------------------------------------------------------- build

def _choose_course(inputs: detect.Inputs, proj: dict, first_route: RouteTable | None,
                   warnings: list[str]) -> course_mod.Course:
    """Course, best first: marks.xml route named in the race file, course.csv, the marks the routing reached
    (when it names at least three), a GPX file, Expedition's active marks.xml route if it starts where the
    routes start, else whatever marks the routing named."""
    route_name = (proj.get("course") or {}).get("marks_route") or ""
    if route_name and inputs.marks_xml:
        try:
            return course_mod.read_marks_xml(inputs.marks_xml[0], route_name)
        except KeyError as e:
            warnings.append(str(e))
    if inputs.course_csv:
        return course_mod.read_course_csv(inputs.course_csv[0])
    from_route = course_mod.course_from_route(first_route) if first_route is not None else None
    if from_route is not None and len(from_route.marks) >= 3:
        return from_route
    if inputs.gpx:
        return course_mod.read_gpx(inputs.gpx[0])
    if inputs.marks_xml and first_route is not None:
        try:
            c = course_mod.read_marks_xml(inputs.marks_xml[0])
            if c.marks and geo.haversine_nm(c.marks[0].lat, c.marks[0].lon, first_route.lat[0], first_route.lon[0]) < 5:
                return c
        except KeyError:
            pass
    if from_route is not None and from_route.marks:
        return from_route
    return course_mod.Course(name="(no course)", marks=[], source="")


def _gun(proj: dict, inputs: detect.Inputs, routes: list[RouteTable], tz: str) -> tuple[float, str]:
    g = (proj.get("race") or {}).get("gun_local")
    if g:
        import datetime as dt
        return timeutil.local_to_epoch(dt.datetime.fromisoformat(g), tz), "race file"
    for p in inputs.yb_setup:
        try:
            s = yb.read_race_setup(p)
            if s.get("gun"):
                return float(s["gun"]), f"YB race setup ({s.get('title') or os.path.basename(p)})"
        except (OSError, ValueError):
            continue
    return min(r.start for r in routes), "first row of the route tables"


def _yb_title(inputs: detect.Inputs) -> str:
    """'1. Flinders Islet Race 2026' -> 'Flinders Islet Race 2026'."""
    import re
    for p in inputs.yb_setup:
        try:
            title = yb.read_race_setup(p).get("title") or ""
        except (OSError, ValueError):
            continue
        if title:
            return re.sub(r"^\s*\d+\.\s*", "", title).strip()
    return ""


def pick_models(available: list[str], requested: list[str] | str | None) -> list[str]:
    if isinstance(requested, str) and requested not in ("", "auto"):
        requested = [m.strip() for m in requested.split(",") if m.strip()]
    if isinstance(requested, list) and requested:
        wanted = [canonical_model(m) for m in requested]
        return [m for m in wanted if m in available]
    ordered = sorted(available, key=lambda m: (rank(m), m))
    return ordered[:MAX_CREW_MODELS]


def build_briefing(folder: str, *, models: list[str] | str | None = None, turning_mark: str | None = None,
                   log=None) -> Briefing:
    inputs = detect.scan(folder)
    proj = project_mod.load(folder)
    race = proj.get("race") or {}
    tz = race.get("tz") or timeutil.DEFAULT_TZ
    var_override = race.get("variation_deg_e")
    warnings: list[str] = []

    if not inputs.route_tables:
        raise FileNotFoundError(f"no Expedition route tables found under {folder}")
    routes = []
    for p in inputs.route_tables:
        try:
            r = read_route_table(p, variation_override=var_override)
        except (ValueError, KeyError, IndexError) as e:
            warnings.append(f"skipped {os.path.basename(p)}: {e}")
            continue
        warnings += [f"{os.path.basename(p)}: {w}" for w in r.warnings]
        routes.append(r)
    if not routes:
        raise ValueError("none of the route tables could be read")
    summaries = []
    for p in inputs.route_summaries:
        try:
            summaries.append(read_route_summary(p, tz))
        except (ValueError, KeyError) as e:
            warnings.append(f"skipped {os.path.basename(p)}: {e}")

    latest: dict[str, RouteTable] = {}
    for r in routes:
        cur = latest.get(r.model)
        if cur is None or (r.created or 0) > (cur.created or 0):
            latest[r.model] = r
    chosen = pick_models(list(latest), models if models else proj.get("crew_models"))
    if not chosen:
        raise ValueError(f"none of the requested models have a route table (have: {', '.join(sorted(latest))})")
    plan_routes = [latest[m] for m in chosen]
    other_routes = [r for r in routes if r not in plan_routes]

    course = _choose_course(inputs, proj, plan_routes[0], warnings)
    course_mod.assign_roles(course, turning_mark or (proj.get("course") or {}).get("turning_mark") or None)
    course_mod.validate(course)
    warnings += course.warnings
    islands = []
    for p in inputs.racenotes:
        try:
            islands += course_mod.read_racenotes(p)
        except Exception as e:  # noqa: BLE001 - decoration only
            warnings.append(f"racenotes not read: {e}")
    turning = course.turning_mark.name if course.turning_mark else ""
    label = turning_label(turning)

    gun, gun_source = _gun(proj, inputs, routes, tz)

    plans = []
    for r in plan_routes:
        marks = route_mark_times(r, course)
        eta = next((m["t"] for m in marks if m["turning"]), None)
        if eta is None and course.turning_mark is not None:
            eta = eta_at(r, course.turning_mark.lat, course.turning_mark.lon)
        ch = weather.detect_change(r.t, r.get("twd"), r.get("tws"))
        if ch is not None:
            ch.signs = weather.supporting_signs(ch, r.t, r.get("mslp") if r.has("mslp") else None,
                                                r.get("airt") if r.has("airt") else None,
                                                r.get("rain") if r.has("rain") else None)
            ch.lat = float(np.interp(ch.t, r.t, r.lat))
            ch.lon = float(np.interp(ch.t, r.t, r.lon))
        grid = weather.wind_grid(r.t, r.get("twd"), r.get("tws"))
        stats = plan_stats(r)
        plans.append(ModelPlan(model=r.model, route=r, marks=marks, eta_turning=eta, change=ch,
                               sail_runs=sail_runs(r), manoeuvres=manoeuvres(r), shifts=weather.hourly_shifts(grid),
                               callouts=callouts(r, ch, eta, label, stats, tz), stats=stats))

    notes = ""
    for p in inputs.notes:
        with open(p, encoding="utf-8", errors="replace") as f:
            notes += f.read().strip() + "\n\n"

    name = race.get("name") or _yb_title(inputs) or os.path.basename(os.path.abspath(folder)).replace("_", " ")
    all_var = np.concatenate([r.variation for r in plan_routes])
    return Briefing(
        folder=os.path.abspath(folder), race_name=name, boat=(proj.get("boat") or {}).get("name") or "", tz=tz,
        gun=gun, gun_source=gun_source, plans=plans, other_routes=other_routes, summaries=summaries, course=course,
        islands=islands, window=change_window(plans, tz, label, bool(turning)),
        finishes=finish_table(routes, summaries, gun), variation_text=magvar.describe(all_var, var_override),
        notes=notes.strip(), warnings=warnings,
    )
