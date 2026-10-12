"""Navigator edition: the full, interactive Day After report (DESIGN.md, Editions). M1 scope: Overview,
Phases, Plan vs reality and Calibration. Every number shown comes from analysis/race_analysis.py."""
from __future__ import annotations

import os
import re

import numpy as np

from .. import __version__
from ..analysis import race as race_mod
from ..analysis.findings import Finding, findings, mark_display, mark_labeller
from ..analysis.race_analysis import RaceAnalysis
from ..analysis.weather import compass
from ..core import geo, timeutil
from . import html as H

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
    }, 5)


# ------------------------------------------------------------------------------------------- html

def _check_card(c) -> str:
    icon, word, tone = STATUS.get(c.status, STATUS["info"])
    fix = f'<p class="check-fix"><strong>What to do:</strong> {H.esc(c.suggestion)}</p>' if c.suggestion else ""
    return (f'<div class="check"><div class="check-head"><span class="status-icon {tone}" aria-hidden="true">{icon}</span>'
            f'<span class="check-word">{word}</span><strong>{H.esc(c.title)}</strong>'
            f'<span class="check-value">{H.esc(c.value)}</span></div><p>{H.esc(c.detail)}</p>{fix}</div>')


def render(a: RaceAnalysis) -> str:
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
        "same time. Δ = actual − route: positive means behind the route.",
    ]
    warns = "".join(f"<li>{H.esc(x)}</li>" for x in a.warnings)
    toc = "".join(f'<a href="#{i}">{H.esc(t)}</a>' for i, t in
                  [("overview", "Overview"), ("phases", "Phases"), ("plan", "Plan vs reality"), ("calibration", "Calibration"),
                   ("data", "Data & method")])
    category = (a.project.get("race") or {}).get("category") or ""
    body = f"""
<header class="wrap cover">
  <div class="topbar"><div class="eyebrow">Day After · navigator edition</div>
  <button class="theme-btn" type="button">Theme: auto</button></div>
  <h1>{H.esc(a.race_name)}</h1>
  <p class="sub">{H.esc(a.boat)} · {H.esc(race_day)} · gun {H.esc(hm(a.gun))} {H.esc(zone)}{H.esc(" · " + category if category else "")}</p>
</header>
<nav class="toc"><div class="wrap">{toc}</div></nav>
<main>
<section id="overview" class="wrap">
  <h2>Overview</h2>
  <div class="kpis">{tiles_html}</div>
  <h3 class="sub-h">What decided the race</h3>
  <div class="findings">{find_html}</div>
  {notes_html}
  {H.figure("chart-map", "Our track (blue) with the optimal routes and the course. Drag to pan; click, then scroll to zoom.", marks_table, "Table view: mark passages")}
  {H.figure("chart-timeline", "Speed and wind through the race. The bar underneath is the phases; shaded: holes.", phases_table, "Table view: phases")}
</section>
<section id="phases" class="wrap">
  <h2>Phases</h2>
  <p class="lede">Legs between the key marks, split where the wind changed; holes are listed on their own and overlap
  the legs around them.</p>
  {phases_table}
</section>
<section id="plan" class="wrap">
  <h2>Plan vs reality</h2>
  <p class="lede">Our time at every mark against each model's optimal route. Above the line we were behind the route,
  below it ahead.</p>
  {H.figure("chart-splits", "Minutes behind (+) or ahead (−) of each route, by distance along the course.")}
  {splits_table}
  <h3 class="sub-h">Forecast against what we sailed in</h3>
  {H.figure("chart-forecast", "Each model's wind along its own route against our measured wind (10-min means over the ground).")}
  {score_table}
  <p class="lede">TWS bias and error compare each route's forecast with our measured wind at the same time; “our elapsed
  vs route” uses the official elapsed time ({H.esc(timeutil.fmt_duration(a.elapsed))}), the mark table above the moment
  we passed the finish point.</p>
  <h3 class="sub-h">Predicted finishes</h3>
  {fin_table}
</section>
<section id="calibration" class="wrap">
  <h2>Calibration</h2>
  <p class="lede">Checks on the instruments from the race itself. The corrections are applied in this report; fix them
  in the instrument system before the next race.</p>
  <div class="checks">{checks_html}</div>
</section>
<section id="data" class="wrap">
  <h2>Data & method</h2>
  <ul>{"".join(f"<li>{H.esc(x)}</li>" for x in inputs)}</ul>
  <ul>{"".join(f"<li>{H.esc(x)}</li>" for x in methods)}</ul>
  {"<p><strong>Warnings</strong></p><ul class='warnings'>" + warns + "</ul>" if warns else ""}
</section>
<footer class="wrap">
  <p>Coastline: Natural Earth (public domain) and © OpenStreetMap contributors (ODbL).</p>
  <p>Generated {H.esc(timeutil.fmt_local(__import__("time").time(), tz, "%a %d %b %Y %H:%M"))} by Day After {H.esc(__version__)} ·
  <a href="https://github.com/pishi-ishi/day-after">github.com/pishi-ishi/day-after</a></p>
</footer>
</main>"""
    return H.page(f"Day After: {a.race_name}", body, build_data(a), scripts=("charts.js", "navigator.js"),
                  description=f"Post-race analysis of {a.race_name} for {a.boat}.")


def _ordinal_suffix(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def write(a: RaceAnalysis, out: str | None = None) -> str:
    if out is None:
        out = os.path.join(a.folder, "out", f"day_after_{_slug(a.race_name)}_navigator.html")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    text = render(a)
    tmp = out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, out)
    return out
