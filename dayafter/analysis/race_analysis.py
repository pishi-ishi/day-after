"""Day After for one race: every analysis on the boat's log, in order, from a race folder (HANDOVER §5).

One run feeds every edition; the editions differ in depth and tone, never in the numbers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

from ..core import timeutil
from ..ingest import course as course_mod
from ..ingest import detect, events as events_mod, project as project_mod, results as results_mod, yb
from ..ingest.course import Course
from ..ingest.expedition_log import Log, Timeline, read_logs
from ..ingest.polar import Polar, read_polar
from ..ingest.routes import RouteSummary, RouteTable, read_route_summary, read_route_table
from . import calibration, plan, race
from .briefing import _yb_title


@dataclass
class RaceAnalysis:
    folder: str
    project: dict
    inputs: detect.Inputs
    tz: str
    race_name: str
    boat: str
    gun: float
    gun_source: str
    start: float
    finish: float                       # official (gun + corrected ÷ TCC) when results exist
    finish_source: str
    finish_point: float | None          # closest approach to the finish mark
    result: results_mod.Result | None
    results: list[results_mod.Result]
    course: Course
    line: tuple | None
    passages: list[race.Passage]
    log: Log
    tl: Timeline
    wind: race.Wind
    checks: list[calibration.Check]
    fit: calibration.SpeedFit | None
    k: float
    holes: list[tuple[float, float]]
    change: race.ObservedChange | None
    phases: list[race.Phase]
    routes: list[RouteTable]            # one per model: the latest run
    all_routes: list[RouteTable]
    summaries: list[RouteSummary]
    splits: list[plan.Split]
    forecasts: list[plan.ForecastCheck]
    model_rank: list[str]
    events: list[events_mod.Event]
    polar: Polar | None
    warnings: list[str] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return self.finish - self.gun

    def passage(self, name: str) -> race.Passage | None:
        return next((p for p in self.passages if p.name == name), None)


def merge_inputs(folders: list[str]) -> detect.Inputs:
    merged = detect.scan(folders[0])
    for f in folders[1:]:
        extra = detect.scan(f)
        for k, v in extra.__dict__.items():
            if isinstance(v, list):
                getattr(merged, k).extend(x for x in v if x not in getattr(merged, k))
    return merged


def _resolve(folder: str, path: str) -> str:
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(folder, path))


def choose_course(inputs: detect.Inputs, proj: dict, routes: list[RouteTable], folder: str,
                  warnings: list[str]) -> Course:
    c = proj.get("course") or {}
    if c.get("file"):
        p = _resolve(folder, c["file"])
        return course_mod.read_gpx(p) if p.lower().endswith(".gpx") else course_mod.read_course_csv(p)
    if c.get("marks_route") and inputs.marks_xml:
        try:
            return course_mod.read_marks_xml(inputs.marks_xml[0], c["marks_route"])
        except KeyError as e:
            warnings.append(str(e))
    if inputs.course_csv:
        return course_mod.read_course_csv(inputs.course_csv[0])
    if inputs.gpx:
        return course_mod.read_gpx(inputs.gpx[0])
    if routes:
        from_route = course_mod.course_from_route(routes[0])
        if len(from_route.marks) >= 3:
            return from_route
    raise FileNotFoundError("no course: add course.csv or a GPX route, or name an Expedition route in race.dayafter.json")


def analyse(folder: str, extra_folders: list[str] | None = None, project: dict | None = None,
            log=None) -> RaceAnalysis:
    say = log or (lambda msg: None)
    folders = [folder] + list(extra_folders or [])
    inputs = merge_inputs(folders)
    proj = project if project is not None else project_mod.load(folder)
    race_cfg, boat_cfg, course_cfg = proj.get("race") or {}, proj.get("boat") or {}, proj.get("course") or {}
    tz = race_cfg.get("tz") or timeutil.DEFAULT_TZ
    warnings: list[str] = []

    if not inputs.logs:
        raise FileNotFoundError(f"no Expedition log (log-YYYYMonDD.csv) under {', '.join(folders)}")
    say(f"reading {len(inputs.logs)} log file(s)")
    lg = read_logs(inputs.logs)
    warnings += lg.warnings

    evs: list[events_mod.Event] = []
    for p in inputs.expedition_db:
        try:
            evs += events_mod.read_expedition_db(p)
        except Exception as e:  # noqa: BLE001 - an unreadable events store must not stop the report
            warnings.append(f"events in {os.path.basename(p)} not read: {e}")
    for p in inputs.events_csv:
        evs += events_mod.read_events_csv(p, tz)
    evs.sort(key=lambda e: e.t)

    all_routes, summaries = [], []
    for p in inputs.route_tables:
        try:
            all_routes.append(read_route_table(p, variation_override=race_cfg.get("variation_deg_e")))
        except (ValueError, KeyError, IndexError) as e:
            warnings.append(f"route table {os.path.basename(p)} skipped: {e}")
    for p in inputs.route_summaries:
        try:
            summaries.append(read_route_summary(p, tz))
        except (ValueError, KeyError) as e:
            warnings.append(f"route summary {os.path.basename(p)} skipped: {e}")
    latest: dict[str, RouteTable] = {}
    for r in all_routes:
        if r.model not in latest or (r.created or 0) > (latest[r.model].created or 0):
            latest[r.model] = r
    from ..core.wxmodel import rank as model_rank_order
    routes = sorted(latest.values(), key=lambda r: (model_rank_order(r.model), r.model))

    course = choose_course(inputs, proj, routes, folder, warnings)
    course_mod.assign_roles(course, course_cfg.get("turning_mark") or None)
    course_mod.validate(course)
    warnings += course.warnings

    results = []
    for p in inputs.results:
        results += results_mod.read_results(p)
    boat_name = boat_cfg.get("name") or "Llama II"
    me = results_mod.find(results, boat_name) if results else None
    if results and me is None:
        warnings.append(f"{boat_name} is not in the results")

    yb_gun = None
    for p in inputs.yb_setup:
        try:
            yb_gun = yb.read_race_setup(p).get("gun") or yb_gun
        except (OSError, ValueError):
            pass
    route_start = float(np.median([r.start for r in routes])) if routes else None
    gun, gun_source, notes = race.pick_gun(race_cfg.get("gun_local"), tz, [e.t for e in evs if e.kind == "gun"],
                                           race.tmtogun_zero(lg), route_start, yb_gun)
    warnings += notes
    if yb_gun and abs(yb_gun - gun) > 300:
        warnings.append(f"YB's race setup start ({timeutil.fmt_local(yb_gun, tz, '%a %H:%M')}) differs from the gun "
                        f"({timeutil.fmt_local(gun, tz, '%a %H:%M')}); the gun from the {gun_source} is used")

    elapsed_official = me.elapsed if me is not None and me.elapsed else None
    end_guess = gun + elapsed_official if elapsed_official else lg.t_last
    say("building the 1 Hz timeline")
    tl = lg.timeline(gun - 900, min(lg.t_last, end_guess + 1800))

    line = race.start_line(lg, gun)
    start = race.start_crossing(tl, line, course.marks[1], gun) if line and len(course.marks) > 1 else None
    if start is None:
        warnings.append("no start-line crossing found (no line pings logged?); the race clock starts at the gun")
        start = gun
    passages = race.mark_passages(tl, course, start)
    missed = [p.name for p in passages if p.t is None]
    if missed:
        warnings.append("marks not reached within 2 nm: " + ", ".join(missed))
    fin_pass = next((p for p in reversed(passages) if p.role == "finish" and p.t is not None), None)
    if elapsed_official:
        finish, finish_source = gun + elapsed_official, "official results (corrected ÷ TCC)"
    elif fin_pass is not None:
        finish, finish_source = fin_pass.t, "closest approach to the finish mark"
    else:
        finish, finish_source = float(tl.t[-1]), "end of the log"
        warnings.append("no finish found; the analysis runs to the end of the log")

    say("calibration")
    race_tl = tl.window(start, finish)
    checks, fit, k = calibration.run_checks(lg, race_tl, boat_cfg.get("bsp_factor"))
    wind = race.derive_wind(tl, k)
    t = tl.t.astype(float)
    hole_list = race.holes(tl, start, finish)
    change = race.observed_change(t, wind.tws_g, wind.twd_g, start, finish)
    phase_marks = course_cfg.get("phase_marks") or race.default_phase_marks(course)
    ph = race.phases(tl, start, passages, phase_marks, change.onset if change else None, hole_list, k,
                     course_cfg.get("mark_labels"))

    say("plan vs reality")
    spl = plan.splits(passages, routes)
    fcs = [plan.forecast_vs_observed(r, t, wind.tws_g, wind.twd_g, start, finish, change.onset if change else None,
                                     gun, finish - gun) for r in routes]
    polar = None
    polar_path = boat_cfg.get("polar")
    try:
        if polar_path:
            polar = read_polar(_resolve(folder, polar_path))
        elif inputs.polars:
            polar = read_polar(inputs.polars[0])
    except (OSError, ValueError, KeyError, IndexError) as e:
        warnings.append(f"polar not read: {e}")

    name = race_cfg.get("name") or _yb_title(inputs) or os.path.basename(os.path.abspath(folder)).replace("_", " ")
    return RaceAnalysis(
        folder=os.path.abspath(folder), project=proj, inputs=inputs, tz=tz, race_name=name, boat=boat_name, gun=gun,
        gun_source=gun_source, start=start, finish=finish, finish_source=finish_source,
        finish_point=fin_pass.t if fin_pass else None, result=me, results=results, course=course, line=line,
        passages=passages, log=lg, tl=tl, wind=wind, checks=checks, fit=fit, k=k, holes=hole_list, change=change,
        phases=ph, routes=routes, all_routes=all_routes, summaries=summaries, splits=spl, forecasts=fcs,
        model_rank=plan.rank_models(fcs), events=events_mod.in_window(evs, gun - 3600, finish + 3600), polar=polar,
        warnings=warnings)
