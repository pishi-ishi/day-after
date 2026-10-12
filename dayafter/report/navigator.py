"""Navigator edition: the full, interactive Day After report (DESIGN.md, Editions). M1 scope: Overview,
Phases, Plan vs reality and Calibration. Every number shown comes from analysis/race_analysis.py."""
from __future__ import annotations

import os
import re

import numpy as np

from .. import __version__
from ..analysis import race as race_mod
from ..analysis import forecast as forecast_mod
from ..analysis.findings import Finding, findings, mark_display, mark_labeller
from ..analysis.race_analysis import RaceAnalysis
from ..analysis.weather import compass
from ..core import geo, timeutil
from . import html as H
from .perf_section import perf_data, performance_section, season_section

STATUS = {"ok": ("✓", "OK", "good"), "info": ("i", "Info", "info"), "warn": ("!", "Check", "warning"),
          "fail": ("✕", "Fix", "critical")}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "race"


def _dur(sec: float) -> str:
    m = int(round(abs(sec) / 60.0))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def _signed_min(sec: float | None) -> str:
    if sec is None or not np.isfinite(sec):
        return "–"
    m = int(round(sec / 60.0))
    return f"+{m}" if m > 0 else f"−{abs(m)}" if m < 0 else "0"


# ------------------------------------------------------------------------------------------- data for the page

def course_distances(a: RaceAnalysis) -> np.ndarray:
    ms = a.course.marks
    legs = [float(geo.haversine_nm(ms[i].lat, ms[i].lon, ms[i + 1].lat, ms[i + 1].lon)) for i in range(len(ms) - 1)]
    return np.r_[0.0, np.cumsum(legs)]


def _smooth_dir(d: np.ndarray, w: np.ndarray, width: int) -> np.ndarray:
    r = np.radians(d)
    u = race_mod.rolling_mean(np.sin(r) * w, width)
    v = race_mod.rolling_mean(np.cos(r) * w, width)
    return (np.degrees(np.arctan2(u, v)) + 360.0) % 360.0


def build_data(a: RaceAnalysis) -> dict:
    label = mark_labeller(a)
    display = mark_display(a)
    tl = a.tl.window(a.start - 60, a.finish + 60)
    idx = np.arange(0, len(tl), 10)
    w = a.wind
    off = int(tl.t[0] - a.tl.t[0])
    twa_bad = any(c.id == "twa_up" and c.status == "warn" for c in a.checks)
    twa = (w.twa_w if twa_bad else a.tl["TWA"])[off:off + len(tl)]
    sm = lambda v: race_mod.rolling_mean(v, 30)  # display: 30 s means sampled every 10 s
    track = {"t": [int(v) for v in tl.t[idx]], "lat": H.clean(tl["Lat"][idx], 5), "lon": H.clean(tl["Lon"][idx], 5),
             "sog": H.clean(sm(tl["SOG"])[idx], 1), "stw": H.clean(sm(w.stw_c[off:off + len(tl)])[idx], 1),
             "tws": H.clean(sm(tl["TWS"])[idx], 1), "twd": H.clean(_smooth_dir(tl["TWD"], tl["TWS"], 30)[idx], 0),
             "twa": H.clean(sm(twa)[idx], 0)}
    ct, cs, cd = race_mod.binned_wind(a.tl.t.astype(float), w.tws_g, w.twd_g, a.start, a.finish)
    phase_marks = {n.lower() for n in ((a.project.get("course") or {}).get("phase_marks") or
                                       race_mod.default_phase_marks(a.course))}
    tm = a.course.turning_mark
    passages = [{"name": p.name, "label": label(p.name), "t": p.t, "d": p.dist_nm,
                 "key": (p.name.lower() in phase_marks) or p.role == "finish" or (tm is not None and p.name == tm.name),
                 "turning": tm is not None and p.name == tm.name} for p in a.passages]
    dist = course_distances(a)
    smarks, delta, route_t = [], {r.model: [] for r in a.routes}, {r.model: [] for r in a.routes}
    for s, p in zip(a.splits, a.passages):
        if p.t is None:
            continue
        smarks.append({"name": p.name, "label": display(p.name), "x": round(float(dist[p.index]), 2), "t": p.t,
                       "turning": tm is not None and p.name == tm.name})
        for m in delta:  # whole minutes, rounded here once so the chart and the tables agree
            delta[m].append(None if s.delta[m] is None else int(round(s.delta[m] / 60.0)))
            route_t[m].append(s.route[m])
    lats = np.r_[tl["Lat"][np.isfinite(tl["Lat"])], [m.lat for m in a.course.marks]]
    lons = np.r_[tl["Lon"][np.isfinite(tl["Lon"])], [m.lon for m in a.course.marks]]
    land, coast = H.coastline((float(lats.min()), float(lats.max())), (float(lons.min()), float(lons.max())))
    islands = []
    for p in a.inputs.racenotes:
        try:
            from ..ingest.course import read_racenotes
            islands += [{"name": i.name, "lat": H.clean(i.lat, 5), "lon": H.clean(i.lon, 5)} for i in read_racenotes(p)]
        except Exception:  # noqa: BLE001 - decoration only
            pass
    ch = a.change
    return H.clean({
        "tz": a.tz, "boat": a.boat, "gun": a.gun, "start": a.start, "finish": a.finish, "track": track,
        "wind10": {"t": ct, "tws": cs, "twd": cd},
        "marks": [{"name": label(m.name), "lat": m.lat, "lon": m.lon, "role": m.role} for m in a.course.marks],
        "passages": passages, "holes": a.holes,
        "phases": [{"name": p.name, "short": p.name.split(" → ")[-1] if p.kind == "leg" else "hole", "kind": p.kind,
                    "t0": p.t0, "t1": p.t1} for p in a.phases],
        "change": None if ch is None else {"onset": ch.onset, "shift": ch.shift, "from": ch.change.twd_from,
                                           "to": ch.change.twd_to},
        "routes": [{"model": r.model, "t": r.t, "lat": r.lat, "lon": r.lon, "tws": r.get("tws"), "twd": r.get("twd")}
                   for r in a.routes],
        "splits": {"length": round(float(dist[-1]), 2), "marks": smarks, "models": [r.model for r in a.routes],
                   "delta": delta, "route": route_t},
        "forecasts": [{"model": f.model, "t": f.t, "tws": f.fc_tws, "twd": f.fc_twd, "change": f.change_t}
                      for f in a.forecasts],
        "land": land, "coast": coast, "islands": islands,
        "fleet": fleet_data(a),
        "grib": grib_data(a),
        "perf": perf_data(a),
    }, 5)


def fleet_data(a: RaceAnalysis) -> dict | None:
    f = a.fleet
    if f is None or f.us is None:
        return None
    rivals = []
    for k, name in enumerate(f.rivals[:4]):
        b = f.boat(name)
        if b is None:
            continue
        idx = np.arange(0, len(b.t))
        rivals.append({"name": b.name, "color": f"var(--r{k + 1})", "tcc": b.tcc,
                       "gaps": [None if not np.isfinite(v) else round(v / 60.0, 1) for v in f.gaps[b.name]],
                       "track": {"t": b.t[idx], "lat": b.lat[idx], "lon": b.lon[idx]}})
    rset = {r["name"] for r in rivals}
    pts = []
    for b in f.boats:
        if b.rounding is None or not b.elapsed:
            continue
        kind = "us" if b is f.us else "rival" if b.name in rset else "other"
        pts.append({"name": b.name, "x": a.gun + b.rounding, "y": round((b.elapsed - b.rounding) * b.tcc / 3600.0, 3),
                    "kind": kind, "place": b.result.place})
    return {"gates": f.gates, "labels": f.gate_labels, "turning": f.turning_nm, "course": f.course_nm, "us": f.us.name,
            "ranks": [int(x) for x in f.ranks[f.us.name]], "rivals": rivals, "scatter": pts, "r": f.rounding_r,
            "n": len(f.boats)}


def grib_data(a: RaceAnalysis) -> dict | None:
    fa = a.forecast
    if fa is None or not fa.models:
        return None
    return {"models": [{"model": m.model, "t": m.t, "tws": H.clean(m.tws, 1), "twd": H.clean(m.twd, 0),
                        "gust": H.clean(m.gust, 1), "change": m.change_t} for m in forecast_mod.headline_models(fa)],
            "obs": {"t": fa.obs_t, "tws": H.clean(fa.obs_tws, 1), "twd": H.clean(fa.obs_twd, 0)},
            "stations": [{"name": st.name, "t": st.t, "tws": H.clean(st.wind_kt, 0)} for st in fa.stations[:2]]}


def light_text(ratio: float | None) -> str:
    if ratio is None or not np.isfinite(ratio):
        return "–"
    return f"{(1 - ratio) * 100:.0f} % light" if ratio < 1 else f"{(ratio - 1) * 100:.0f} % heavy"


def _grib_section(a: RaceAnalysis) -> str:
    fa = a.forecast
    if fa is None:
        return ('<h3 class="sub-h">Forecast at our position</h3><p class="lede">No GRIB files in the race folder. Copy the '
                'race-morning GRIBs from Expedition\'s grib folder to judge every model where we actually sailed.</p>')
    tz = a.tz
    when = lambda t: timeutil.fmt_local(t, tz, "%a %H:%M") if t else "–"
    notes = "".join(f"<li>{H.esc(n)}</li>" for n in fa.notes)
    if not fa.models:
        return (f'<h3 class="sub-h">Forecast at our position</h3><p class="lede">No GRIB model covers our track during '
                f'the race.</p><ul class="warnings">{notes}</ul>')
    rows = []
    for m in sorted(fa.models, key=lambda m: m.scores.get("score", 99)):
        s = m.scores
        ce = s.get("change_error_s")
        rows.append([H.model_cell(m.model), H.esc(timeutil.fmt_local(m.run, "UTC", "%a %H") + "Z"), H.esc(when(m.downloaded)),
                     H.esc(f"{s['tws_bias']:+.1f}") if "tws_bias" in s else "–", H.num(s.get("tws_mae"), 1),
                     H.esc(light_text(s.get("tws_ratio"))), H.num(s.get("twd_mae"), 0),
                     H.esc(f"{_dur(ce)} {'late' if ce > 0 else 'early'}") if ce is not None else "no change",
                     H.esc(os.path.basename(m.path))])
    score = H.table(["Model", "Run", "Downloaded", "TWS bias kt", "TWS error kt", "Strength", "TWD error °",
                     "Change timing", "File"], rows, num_cols={3, 4, 6}, stack=True)
    legs = [p for p in a.phases]
    prow = []
    for ph in legs:
        w0 = next((w for m in fa.models for w in m.windows if w["name"] == ph.name), None)
        if w0 is None:
            continue
        row = [H.esc(ph.name), H.esc(f"{w0['obs']:.0f} ({w0['obs_min']:.0f}–{w0['obs_max']:.0f})")]
        for m in fa.models:
            w = next((x for x in m.windows if x["name"] == ph.name), None)
            row.append(H.esc(f"{w['fc']:.0f} · {light_text(w['ratio'])}") if w else "–")
        prow.append(row)
    phase_t = H.table(["Phase", "Measured kt"] + [f"{m.model} kt" for m in fa.models], prow,
                      num_cols=set(range(1, len(fa.models) + 2)),
                      row_class=lambda k: "hole" if legs[k].kind == "hole" else "")
    shown = ", ".join(m.model for m in forecast_mod.headline_models(fa))
    mh = (f" Forecast 10 m wind is scaled by {fa.masthead_factor:.2f} to masthead height." if fa.masthead_factor != 1
          else " Forecast wind is the model's 10 m wind, unscaled (set boat.masthead_wind_factor in the race file to scale it).")
    return f"""
  <h3 class="sub-h">Forecast at our position (GRIB)</h3>
  <p class="lede">Each model's GRIB read where we actually were, every 10 minutes, against the wind we measured there
  (over the ground, 10-min means). Per model this is the latest run we had downloaded before the gun.{H.esc(mh)}</p>
  {H.figure("chart-grib", f"Forecast at our position against what we measured: {shown} (the table lists every model).")}
  {score}
  <h3 class="sub-h">By phase</h3>
  {phase_t}
  {"<ul class='warnings'>" + notes + "</ul>" if notes else ""}"""


# ------------------------------------------------------------------------------------------- html

def _check_card(c) -> str:
    icon, word, tone = STATUS.get(c.status, STATUS["info"])
    fix = f'<p class="check-fix"><strong>What to do:</strong> {H.esc(c.suggestion)}</p>' if c.suggestion else ""
    return (f'<div class="check"><div class="check-head"><span class="status-icon {tone}" aria-hidden="true">{icon}</span>'
            f'<span class="check-word">{word}</span><strong>{H.esc(c.title)}</strong>'
            f'<span class="check-value">{H.esc(c.value)}</span></div><p>{H.esc(c.detail)}</p>{fix}</div>')


def render(a: RaceAnalysis, season: dict | None = None, edition: str = "navigator") -> str:
    tz = a.tz
    hm = lambda t: timeutil.fmt_local(t, tz, "%H:%M") if t is not None else "–"
    hms = lambda t: timeutil.fmt_local(t, tz, "%H:%M:%S") if t is not None else "–"
    label = mark_display(a)
    fs: list[Finding] = findings(a)
    zone = timeutil.utc_offset_label(a.gun, tz)
    race_day = timeutil.fmt_local(a.gun, tz, "%a %d %b %Y")

    # --- tiles
    n_fin = sum(r.finished for r in a.results)
    legs = [p for p in a.phases if p.kind == "leg"]
    sailed = sum(p.dist_nm for p in legs)
    course_len = float(course_distances(a)[-1])
    finals = {m: s.delta[m] for s in a.splits[-1:] for m in s.delta if s.delta[m] is not None}
    ref = min(finals, key=lambda m: abs(finals[m])) if finals else None
    speed = next((c for c in a.checks if c.id == "speed"), None)
    tiles = [
        ("Result", f"{a.result.place}{_ordinal_suffix(a.result.place)} of {n_fin}" if a.result and a.result.place else "–",
         f"corrected {timeutil.fmt_duration(a.result.corrected)}" if a.result and a.result.corrected else "no results yet"),
        ("Elapsed", timeutil.fmt_duration(a.elapsed), f"gun {hm(a.gun)} → finish {hm(a.finish)}"),
        ("Sailed", f"{sailed:.1f} nm", f"course {course_len:.1f} nm · {sailed / (a.elapsed / 3600):.1f} kt average"),
        ("Against the closest routing", f"{_signed_min(finals[ref])} min" if ref else "–",
         f"vs {ref}; " + ", ".join(f"{m} {_signed_min(v)}" for m, v in finals.items() if m != ref) if ref else "no route tables"),
    ]
    if speed is not None:
        tiles.append(("Boat speed", speed.value, "reads low: calibrate" if speed.status != "ok" else "calibrated"))
    tiles_html = "".join(f'<div class="kpi"><div class="label">{H.esc(l)}</div><div class="value">{H.esc(v)}</div>'
                         f'<div class="note">{H.esc(n)}</div></div>' for l, v, n in tiles)
    find_html = "".join(f'<div class="finding {f.kind}"><div class="finding-title">{H.esc(f.title)}</div>'
                        f'<p>{H.esc(f.text)}</p></div>' for f in fs)

    notes = "\n\n".join(x for x in [((a.project.get("notes") or {}).get("navigator") or "").strip()] if x)
    for p in a.inputs.notes:
        with open(p, encoding="utf-8", errors="replace") as fh:
            notes = (notes + "\n\n" + fh.read().strip()).strip()
    notes_html = f'<h3 class="sub-h">Navigator\'s notes</h3><div class="notes">{H.esc(notes)}</div>' if notes else ""

    # --- tables
    mark_rows = [[H.esc(label(p.name)), H.esc(hms(p.t)), H.num(p.dist_nm * 1852 if p.dist_nm is not None else None, 0)]
                 for p in a.passages]
    mark_rows.insert(0, ["Start (line crossing)", H.esc(hms(a.start)), "–"])
    marks_table = H.table(["Mark", "Passed", "Closest, m"], mark_rows, num_cols={1, 2})
    phase_rows = [[H.esc(p.name), H.esc(hm(p.t0)), H.esc(hm(p.t1)), H.num(p.minutes, 0), H.num(p.dist_nm, 2), H.num(p.sog, 2),
                   H.num(p.stw_c, 2), H.num(p.tws, 1), H.num(p.tws_p95, 1), H.esc(f"{p.twd:.0f}° {compass(p.twd)}")]
                  for p in a.phases]
    phases_table = H.table(["Phase", "From", "To", "Min", "Distance nm", "Speed kt", "STW corr. kt", "TWS kt", "TWS p95",
                            "TWD"], phase_rows, num_cols={1, 2, 3, 4, 5, 6, 7, 8},
                           row_class=lambda k: "hole" if a.phases[k].kind == "hole" else "")
    models = [r.model for r in a.routes]
    split_rows = []
    for s, p in zip(a.splits, a.passages):
        name = label(s.mark) + (" (finish point)" if p.role == "finish" else "")
        row = [H.esc(name), H.esc(hm(s.actual))]
        for m in models:
            row += [H.esc(hm(s.route[m])), H.esc(_signed_min(s.delta[m]))]
        split_rows.append(row)
    split_head = ["Mark", "Actual"] + [x for m in models for x in (f"{m} route", f"Δ {m} min")]
    splits_table = H.table(split_head, split_rows, num_cols=set(range(1, len(split_head))))
    score_rows = []
    for f in a.forecasts:
        s = f.scores
        score_rows.append([H.model_cell(f.model), str(s.get("n", 0)), H.esc(f"{s['tws_bias']:+.1f}") if "tws_bias" in s else "–",
                           H.num(s.get("tws_mae"), 1),
                           H.esc(f"{(1 - s['tws_ratio']) * 100:.0f} % light" if s.get("tws_ratio", 1) < 1 else
                                 f"{(s['tws_ratio'] - 1) * 100:.0f} % heavy") if "tws_ratio" in s else "–",
                           H.num(s.get("twd_mae"), 0),
                           H.esc(f"{_dur(s['change_error_s'])} {'late' if s['change_error_s'] > 0 else 'early'}") if "change_error_s" in s else "–",
                           H.esc(timeutil.fmt_duration(s["predicted_elapsed"])),
                           H.esc(_signed_min(-s["elapsed_error_s"]) + " min") if "elapsed_error_s" in s else "–"])
    score_table = H.table(["Model", "Rows", "TWS bias kt", "TWS error kt", "Strength", "TWD error °", "Change timing",
                           "Route elapsed", "Our elapsed vs route"], score_rows, num_cols={1, 2, 3, 5, 7, 8}, stack=True)
    fin_rows = [[H.esc("Actual"), H.esc(a.boat), H.esc(a.finish_source), H.esc(hms(a.finish)), H.esc(timeutil.fmt_duration(a.elapsed))]]
    for r in a.all_routes:
        fin_rows.append([H.esc(timeutil.fmt_local(r.created, tz, "%a %H:%M") if r.created else "–"), H.esc(r.model),
                         "route table", H.esc(hms(r.finish)), H.esc(timeutil.fmt_duration(r.finish - a.gun))])
    for sm in a.summaries:
        for x in sm.rows:
            if x.finish is None or (x.is_reference and not x.label):
                continue
            fin_rows.append([H.esc(timeutil.fmt_local(x.created, tz, "%a %H:%M") if x.created else "–"), H.esc(x.model),
                             "summary of all routes", H.esc(timeutil.fmt_local(x.finish, tz, "%a %H:%M:%S")),
                             H.esc(timeutil.fmt_duration(x.elapsed))])
    fin_table = H.table(["Run", "Model", "From", "Finish", "Elapsed"], fin_rows, num_cols={3, 4}, stack=True,
                        row_class=lambda k: "used" if k == 0 else "")
    checks_html = "".join(_check_card(c) for c in a.checks)
    fleet_html = _fleet_section(a)

    inputs = [f"Log: {', '.join(os.path.basename(p) for p in a.log.paths)} (Expedition {a.log.version or '?'}, "
              f"{len(a.log.channels)} channels)",
              f"Course: {os.path.basename(a.course.source.split('#')[0]) if a.course.source else '–'} "
              f"({len(a.course.marks)} marks, {course_len:.2f} nm)"]
    if a.results:
        inputs.append(f"Results: {', '.join(os.path.basename(p) for p in a.inputs.results)} ({len(a.results)} boats)")
    if a.all_routes:
        inputs.append("Route tables: " + ", ".join(f"{os.path.basename(r.path)}" for r in a.all_routes))
    if a.inputs.expedition_db:
        inputs.append(f"Events: Expedition.db ({len(a.events)} around the race)")
    if a.polar is not None:
        inputs.append(f"Polar: {a.polar.name}")
    if a.forecast is not None and a.forecast.models:
        inputs.append("GRIBs used: " + ", ".join(os.path.basename(m.path) for m in a.forecast.models)
                      + f" (of {len(a.inputs.gribs) + len(a.inputs.gribs_encrypted)} on file)")
    methods = [
        f"Times are {zone}. The gun comes from the {a.gun_source}; the start is the first crossing of the pinged line "
        f"({hms(a.start)}); the finish is the {a.finish_source} ({hms(a.finish)}).",
        "Mark times are the closest approach on the 1 Hz log, mark by mark in course order.",
        "Distances follow the 1 Hz GPS track. In very light air GPS jitter adds length, so speeds through holes read high.",
        f"Boat speed is multiplied by {a.k:.3f} (the calibration fit). Where the logged true wind angle is off, true wind "
        "is recomputed from the apparent wind with the corrected speed.",
        "Holes: 30 s mean SOG below 3 kt for 10 min or more. The change: the largest wind shift of 60° or more within "
        "an hour that then holds for half an hour, found in 10-min means of the wind over the ground and timed at the "
        "start of the transition (the old breeze dying).",
        "Forecasts: each model's wind along its own optimal route, against our 10-min mean wind over the ground at the "
        "same time. Δ = actual − route: positive means behind the route. GRIB models are read at our own position "
        "(bilinear in space, linear in time); the change in a forecast is found the same way as in our log.",
    ]
    warns = "".join(f"<li>{H.esc(x)}</li>" for x in a.warnings)
    category = (a.project.get("race") or {}).get("category") or ""
    generated = timeutil.fmt_local(__import__("time").time(), tz, "%a %d %b %Y %H:%M")
    parts = {
        "overview": f"""
<section id="overview" class="wrap">
  <h2>Overview</h2>
  <div class="kpis">{tiles_html}</div>
  <h3 class="sub-h">What decided the race</h3>
  <div class="findings">{find_html}</div>
  {notes_html}
  {H.figure("chart-map", "Our track (blue) with the optimal routes and the course. Drag to pan; click, then scroll to zoom.", marks_table, "Table view: mark passages")}
  {H.figure("chart-timeline", "Speed and wind through the race. The bar underneath is the phases; shaded: holes.", phases_table, "Table view: phases")}
</section>""",
        "phases": f"""
<section id="phases" class="wrap">
  <h2>Phases</h2>
  <p class="lede">Legs between the key marks, split where the wind changed; holes are listed on their own and overlap
  the legs around them.</p>
  {phases_table}
</section>""",
        "plan_head": f"""
  <p class="lede">Our time at every mark against each model's optimal route. Above the line we were behind the route,
  below it ahead.</p>
  {H.figure("chart-splits", "Minutes behind (+) or ahead (−) of each route, by distance along the course.")}
  {splits_table}""",
        "plan_rest": f"""
  <h3 class="sub-h">Forecast along each route</h3>
  {H.figure("chart-forecast", "Each model's wind along its own route against our measured wind (10-min means over the ground).")}
  {score_table}
  <p class="lede">TWS bias and error compare each route's forecast with our measured wind at the same time; “our elapsed
  vs route” uses the official elapsed time ({H.esc(timeutil.fmt_duration(a.elapsed))}), the mark table above the moment
  we passed the finish point.</p>
  {_grib_section(a)}
  <h3 class="sub-h">Predicted finishes</h3>
  {fin_table}""",
        "score_table": score_table,
        "fleet": fleet_html,
        "performance": performance_section(a),
        "calibration": f"""
<section id="calibration" class="wrap">
  <h2>Calibration</h2>
  <p class="lede">Checks on the instruments from the race itself. The corrections are applied in this report; fix them
  in the instrument system before the next race.</p>
  <div class="checks">{checks_html}</div>
</section>""",
        "season": season_section(season, a),
        "data": f"""
<section id="data" class="wrap">
  <h2>Data & method</h2>
  <ul>{"".join(f"<li>{H.esc(x)}</li>" for x in inputs)}</ul>
  <ul>{"".join(f"<li>{H.esc(x)}</li>" for x in methods)}</ul>
  {"<p><strong>Warnings</strong></p><ul class='warnings'>" + warns + "</ul>" if warns else ""}
</section>""",
        "footer": f"""
<footer class="wrap">
  <p>Coastline: Natural Earth (public domain) and © OpenStreetMap contributors (ODbL).</p>
  <p>Generated {H.esc(generated)} by Day After {H.esc(__version__)} ·
  <a href="https://github.com/pishi-ishi/day-after">github.com/pishi-ishi/day-after</a></p>
</footer>""",
        "sub": f"{a.boat} · {race_day} · gun {hm(a.gun)} {zone}" + (f" · {category}" if category else ""),
        "tiles": tiles_html, "findings": find_html, "fleet_compact": _fleet_section(a, compact=True),
        "findings_top": "".join(f'<div class="finding {f.kind}"><div class="finding-title">{H.esc(f.title)}</div>'
                                f'<p>{H.esc(f.text)}</p></div>' for f in fs[:6]), "notes": notes_html, "marks_table": marks_table,
    }
    if edition != "navigator":
        from .skipper import render_body
        body = render_body(a, parts, edition)
        title = f"Day After ({'skipper' if edition == 'skipper' else '7 Seas'}): {a.race_name}"
        return H.page(title, body, build_data(a), scripts=("charts.js", "navigator.js"),
                      description=f"Post-race report on {a.race_name} for {a.boat}.",
                      body_class="brand-7s" if edition == "7seas" else "")
    toc = "".join(f'<a href="#{i}">{H.esc(t)}</a>' for i, t in
                  [("overview", "Overview"), ("phases", "Phases"), ("plan", "Plan vs reality"), ("fleet", "Fleet"),
                   ("performance", "Performance"), ("calibration", "Calibration")]
                  + ([("season", "Season")] if season and season.get("races") else []) + [("data", "Data & method")])
    body = f"""
<header class="wrap cover">
  <div class="topbar"><div class="eyebrow">Day After · navigator edition</div>
  <button class="theme-btn" type="button">Theme: auto</button></div>
  <h1>{H.esc(a.race_name)}</h1>
  <p class="sub">{H.esc(parts["sub"])}</p>
</header>
<nav class="toc"><div class="wrap">{toc}</div></nav>
<main>
{parts["overview"]}
{parts["phases"]}
<section id="plan" class="wrap">
  <h2>Plan vs reality</h2>
{parts["plan_head"]}
{parts["plan_rest"]}
</section>
{parts["fleet"]}
{parts["performance"]}
{parts["calibration"]}
{parts["season"]}
{parts["data"]}
{parts["footer"]}
</main>"""
    return H.page(f"Day After: {a.race_name}", body, build_data(a), scripts=("charts.js", "navigator.js"),
                  description=f"Post-race analysis of {a.race_name} for {a.boat}.")


def _fleet_section(a: RaceAnalysis, compact: bool = False) -> str:
    f = a.fleet
    if f is None or f.us is None:
        return ('<section id="fleet" class="wrap"><h2>Fleet</h2><p class="lede">No fleet comparison: it needs the YB '
                'tracks (dayafter fetch-yb) and the results with TCCs.</p></section>')
    tz = a.tz
    mmss = lambda sec: timeutil.fmt_duration(abs(sec)).lstrip("0:") or "0"
    tiles = []
    for name in f.rivals[:4]:
        g = f.gaps.get(name)
        if g is None or not np.isfinite(g[-1]):
            continue
        tiles.append((name, f"{timeutil.fmt_duration(abs(g[-1]))[-5:] if abs(g[-1]) < 3600 else timeutil.fmt_duration(abs(g[-1]))}",
                      f"{'ahead of' if g[-1] < 0 else 'behind'} us on corrected time · TCC {f.boat(name).tcc:.3f}"))
    tiles_html = "".join(f'<div class="kpi"><div class="label">{H.esc(l)}</div><div class="value">{H.esc(v)}</div>'
                         f'<div class="note">{H.esc(n)}</div></div>' for l, v, n in tiles)
    head = ["Gate"] + ["Our rank"] + [f"{n} min" for n in f.rivals[:4]]
    rows = []
    for i, lab in enumerate(f.gate_labels):
        r = f.ranks[f.us.name][i]
        row = [H.esc(f"{f.gates[i]:.1f} nm" + ("" if lab.endswith("nm") else f" ({lab})")), str(r) if r > 0 else "–"]
        for n in f.rivals[:4]:
            v = f.gaps.get(n, np.full(len(f.gates), np.nan))[i]
            row.append(H.esc(f"{v / 60:+.1f}") if np.isfinite(v) else "–")
        rows.append(row)
    gate_table = H.table(head, rows, num_cols=set(range(1, len(head))))
    res_rows = []
    for b in sorted(f.boats, key=lambda b: b.result.place or 99):
        g = f.gaps.get(b.name, [np.nan])[-1]
        res_rows.append([str(b.result.place or "–"), H.esc(b.name), H.esc(b.result.division), H.num(b.tcc, 3),
                         H.esc(timeutil.fmt_duration(b.result.corrected)), H.esc(timeutil.fmt_duration(b.elapsed)),
                         H.esc(timeutil.fmt_duration(b.yb_finish)) if b.yb_finish else "–",
                         H.esc(f"{(b.yb_finish - b.elapsed) / 60:+.0f}") if b.yb_finish else "–",
                         H.esc(timeutil.fmt_local(a.gun + b.rounding, tz, "%H:%M")) if b.rounding is not None else "–",
                         H.esc(f"{g / 60:+.1f}") if np.isfinite(g) else "–"])
    res_table = H.table(["Place", "Yacht", "Div", "TCC", "Corrected", "Elapsed", "YB elapsed", "YB late, min", "Rounded",
                         "Gap to us, min"], res_rows, num_cols={0, 3, 4, 5, 6, 7, 8, 9},
                        row_class=lambda k: "used" if sorted(f.boats, key=lambda b: b.result.place or 99)[k] is f.us else "")
    r_txt = f" r = {f.rounding_r:.2f} over {len(f.boats)} finishers." if f.rounding_r is not None else ""
    if compact:  # skipper edition: us and the rivals only, no fleet map
        keep = [b for b in sorted(f.boats, key=lambda b: b.result.place or 99) if b is f.us or b.name in f.rivals[:4]]
        rows = [[str(b.result.place or "–"), H.esc(b.name), H.num(b.tcc, 3), H.esc(timeutil.fmt_duration(b.result.corrected)),
                 H.esc(timeutil.fmt_duration(b.elapsed)),
                 H.esc(timeutil.fmt_local(a.gun + b.rounding, tz, "%H:%M")) if b.rounding is not None else "–",
                 H.esc(f"{f.gaps.get(b.name, [np.nan])[-1] / 60:+.1f}") if b is not f.us else "–"] for b in keep]
        small = H.table(["Place", "Yacht", "TCC", "Corrected", "Elapsed", "Rounded", "Gap to us, min"], rows,
                        num_cols={0, 2, 3, 4, 5, 6}, row_class=lambda k: "used" if keep[k] is f.us else "")
        return f"""
<section id="fleet" class="wrap">
  <h2>Fleet</h2>
  <p class="lede">Corrected-time gaps to the boats we race, every {f.gates[1] - f.gates[0]:.0f} nm along the course
  (YB tracks, official TCCs).</p>
  <div class="kpis">{tiles_html}</div>
  {H.figure("chart-gaps", "Corrected-time gap to each rival along the course: below the line they were ahead of us.")}
  {H.figure("chart-rounding", "Rounding time against the corrected time home, every finisher." + r_txt)}
  {small}
</section>"""
    return f"""
<section id="fleet" class="wrap">
  <h2>Fleet</h2>
  <p class="lede">Corrected-time gaps to the boats we race (same division, nearest TCC unless the race file names them),
  every {f.gates[1] - f.gates[0]:.0f} nm along the course from the YB tracks. Elapsed times are corrected ÷ TCC from the
  official results; YB's own finish times run late and are shown only for comparison.</p>
  <div class="kpis">{tiles_html}</div>
  {H.figure("chart-gaps", "Corrected-time gap to each rival along the course: below the line they were ahead of us.", gate_table, "Table view: rank and gaps by gate")}
  {H.figure("chart-rounding", "Rounding time against the corrected time home, every finisher." + r_txt)}
  {H.figure("chart-fleetmap", "Our track and the rivals' YB tracks (10-minute fixes).")}
  <h3 class="sub-h">Results</h3>
  {res_table}
</section>"""


def _ordinal_suffix(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def filename(a: RaceAnalysis) -> str:
    return f"day_after_{_slug(a.race_name)}_navigator.html"


def write(a: RaceAnalysis, out: str | None = None, season: dict | None = None, edition: str = "navigator") -> str:
    if out is None:
        out = os.path.join(a.folder, "out", filename(a))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    text = render(a, season, edition)
    tmp = out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, out)
    return out
