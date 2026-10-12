"""The Day Before crew briefing: one self-contained HTML page (opens offline on phones and laptops).

Audience: the whole crew. Sailing jargon is used freely; weather terms are explained (DESIGN.md, crew
edition). Every chart has a table twin, and every number comes from analysis/briefing.py.
"""
from __future__ import annotations

import os
import re

import numpy as np

from .. import __version__
from ..analysis.briefing import Briefing, ModelPlan
from ..analysis.weather import compass
from ..core import timeutil
from . import html as H

GLOSSARY = [
    ("GRIB", "The file a weather model's forecast comes in: wind, pressure, rain and more on a grid of points, "
             "usually every one to three hours. Expedition routes through it."),
    ("Model run", "Models restart every 6 or 12 hours from fresh observations (for example “GFS 12Z”). A newer run "
                  "usually beats an older one for the next day or two."),
    ("10 m wind", "Models forecast the wind 10 m above the sea, averaged over several minutes. The masthead sits higher "
                  "and often sees more breeze; gusts come on top."),
    ("Gust factor", "Gust divided by the mean wind. About 1.2–1.3 in a steady offshore breeze; 1.4 or more means squally, "
                    "unstable air, often behind a front."),
    ("Pressure gradient", "How quickly pressure changes across the chart. Isobars close together mean strong wind."),
    ("Trough", "A line or tongue of lower pressure. The wind often shifts and freshens as it passes, and it can bring "
               "showers and squalls."),
    ("Ridge", "A tongue of higher pressure: lighter, steadier breeze and settled weather."),
    ("Front", "The leading edge of a different air mass. On this coast a cold front usually brings a shift to the "
              "south-west or south, a pressure jump, a temperature drop and often rain."),
    ("Southerly buster", "A sudden, strong southerly change on the NSW coast, mostly in spring and summer. The breeze can "
                         "swing from a warm northerly to 30–50 kt from the south within minutes, with a sharp "
                         "temperature drop."),
    ("Coastal trapping", "Cool, shallow air held against the coast by the ranges. It lets a southerly surge run up the "
                         "coast faster and harder than the models show."),
    ("Veer and back", "A veer is a clockwise shift (north to east); a back is anticlockwise (north to west). The words "
                      "mean the same in both hemispheres."),
    ("Sea breeze", "An onshore breeze that builds on warm afternoons as the land heats and fades at dusk. Near the coast "
                   "it can add to, or cancel, the gradient breeze."),
    ("Meteogram", "A forecast drawn against time. Here: what the boat would meet along one model's route, with wind, "
                  "pressure, temperature and rain stacked on one time axis."),
    ("Ensemble", "Many runs of one model from slightly different starts. Agreement means confidence; a wide spread "
                 "means the forecast is uncertain."),
    ("Optimal route", "The fastest route Expedition finds through one model's forecast, sailing our polar. It assumes "
                      "that model is right, so compare the models before trusting one."),
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "race"


class _Fmt:
    def __init__(self, b: Briefing):
        self.tz, self.gun = b.tz, b.gun
        self.gun_day = timeutil.fmt_local(b.gun, b.tz, "%Y-%m-%d")

    def hm(self, t) -> str:
        return timeutil.fmt_local(t, self.tz, "%H:%M")

    def when(self, t) -> str:
        """'21:47', or 'Sun 00:31' when not on the gun's day."""
        if t is None or not np.isfinite(t):
            return "–"
        same = timeutil.fmt_local(t, self.tz, "%Y-%m-%d") == self.gun_day
        return timeutil.fmt_local(t, self.tz, "%H:%M" if same else "%a %H:%M")

    def run(self, t) -> str:
        return timeutil.fmt_local(t, self.tz, "%a %d %b %H:%M") if t else "–"


def _range(f: _Fmt, values) -> str:
    vals = [v for v in values if v is not None and np.isfinite(v)]
    if not vals:
        return "–"
    lo, hi = min(vals), max(vals)
    return f.when(lo) if abs(hi - lo) < 60 else f"{f.when(lo)}–{f.when(hi)}"


def _dur(sec: float) -> str:
    m = int(round(abs(sec) / 60))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


# ------------------------------------------------------------------------------------------- data

def _series(r, key):
    return H.clean(r.get(key), 1) if r.has(key) else None


def model_data(p: ModelPlan) -> dict:
    r = p.route
    ch = p.change
    return {
        "model": p.model, "label": r.label, "run": r.created, "file": os.path.basename(r.path),
        "t": [int(round(v)) for v in r.t], "tws": H.clean(r.get("tws"), 1), "twg": H.clean(r.get("twg"), 1),
        "twd": H.clean(r.get("twd"), 0), "twa": H.clean(r.get("twa"), 0), "mslp": H.clean(r.get("mslp"), 1),
        "airt": _series(r, "airt"), "rain": _series(r, "rain"), "sail": r.sail_filled, "mark": r.mark,
        "lat": H.clean(r.lat, 5), "lon": H.clean(r.lon, 5), "eta": p.eta_turning,
        "change": None if ch is None else H.clean({"t": ch.t, "t_from": ch.t_from, "t_to": ch.t_to, "from": ch.twd_from,
                                                   "to": ch.twd_to, "swing": ch.swing, "lat": ch.lat, "lon": ch.lon}, 4),
        "sails": H.clean(p.sail_runs), "manoeuvres": H.clean(p.manoeuvres), "marks": H.clean(p.marks, 5),
    }


def build_data(b: Briefing) -> dict:
    lats = np.concatenate([p.route.lat for p in b.plans] + [b.course.lat if b.course.marks else np.array([])])
    lons = np.concatenate([p.route.lon for p in b.plans] + [b.course.lon if b.course.marks else np.array([])])
    land, coast = H.coastline((float(np.nanmin(lats)), float(np.nanmax(lats))), (float(np.nanmin(lons)), float(np.nanmax(lons))))
    return {
        "tz": b.tz, "gun": int(round(b.gun)), "turning": b.turning_label,
        "models": [model_data(p) for p in b.plans],
        "window": H.clean(b.window, 0) if b.window else None,
        "course": [{"name": m.name, "lat": round(m.lat, 5), "lon": round(m.lon, 5), "role": m.role} for m in b.course.marks],
        "islands": [{"name": i.name, "lat": H.clean(i.lat, 5), "lon": H.clean(i.lon, 5)} for i in b.islands],
        "land": land, "coast": coast,
        "gribs": _grib_data(b.gribs),
        "after": H.clean(b.after, 5) if b.after else None,
    }


def _grib_data(g: dict | None) -> dict | None:
    if not g or not g["models"]:
        return None
    core = [m for m in g["models"] if m["model"] in ("ECMWF", "GFS", "ACCESS")]
    rest = [m for m in g["models"] if m not in core]
    shown = (core + rest)[:3]
    return {"route_model": g["route_model"],
            "models": [{"model": m["model"], "t": [int(round(v)) for v in m["t"]], "tws": H.clean(m["tws"], 1),
                        "twd": H.clean(m["twd"], 0), "gust": H.clean(m["gust"], 1), "mslp": H.clean(m["mslp"], 1),
                        "change": m["change"]} for m in shown]}


def _grib_section(b: Briefing, f: "_Fmt") -> str:
    g = b.gribs
    if not g:
        return ""
    notes = "".join(f"<li>{H.esc(n)}</li>" for n in g["notes"])
    if not g["models"]:
        return (f'<section id="gribs" class="wrap"><h2>Other models</h2><p class="lede">No readable GRIB covers the '
                f'route.</p><ul class="warnings">{notes}</ul></section>')
    ms = g["models"]
    t = ms[0]["t"]
    hours = [i for i in range(len(t)) if i == 0 or int(t[i] // 3600) != int(t[i - 1] // 3600)]
    rows = []
    for i in hours:
        row = [H.esc(f.when(t[i]))]
        for m in ms:
            row.append(H.esc(f"{H.num(m['tws'][i], 0)} {compass(m['twd'][i])}" if np.isfinite(m["tws"][i]) else "–"))
        rows.append(row)
    table = H.table(["Time"] + [m["model"] for m in ms], rows, num_cols=set(range(len(ms) + 1)) - {0})
    runs = "; ".join(f"{m['model']} {timeutil.fmt_local(m['run'], 'UTC', '%a %H')}Z run ({m['file']})" for m in ms)
    changes = ", ".join(f"{m['model']} {f.when(m['change'])}" for m in ms if m["change"])
    shown = _grib_data(g)["models"]
    rest = len(ms) - len(shown)
    return f"""
<section id="gribs" class="wrap">
  <h2>Every model along the {H.esc(g["route_model"])} route</h2>
  <p class="lede">The GRIB files read along one route, so the models can be compared on the same water at the same
  time, including models without a route table. {"Change times on this route: " + H.esc(changes) + "." if changes else ""}</p>
  {H.figure("chart-gribs", "Wind along the " + g["route_model"] + " route in each GRIB model"
            + (f" (the chart shows {len(shown)}; the table has all {len(ms)})" if rest else "") + ".", table, "Table view (on the hour)")}
  <p class="small">Runs: {H.esc(runs)}.</p>
  {"<ul class='warnings'>" + notes + "</ul>" if notes else ""}
</section>"""


def _after_section(b: Briefing, f: "_Fmt") -> str:
    A = b.after
    if not A:
        return ""
    turning = b.turning_label
    tiles = [("Result", f"{A['place']} of {A['of']}" if A.get("place") else "–", "on corrected time"),
             ("Elapsed", timeutil.fmt_duration(A["elapsed"]), f"finish {f.when(A['finish'])}"),
             (f"At {turning}", f.when(A["turning_t"]) if A.get("turning_t") else "–",
              "forecast " + _range(f, [p.eta_turning for p in b.plans])),
             ("The change", f.when(A["change"]["t"]) if A.get("change") else "none",
              ("forecast " + _range(f, [p.change.t for p in b.plans if p.change])) if A.get("change") else "")]
    tiles_html = "".join(f'<div class="kpi"><div class="label">{H.esc(l)}</div><div class="value">{H.esc(v)}</div>'
                         f'<div class="note">{H.esc(n)}</div></div>' for l, v, n in tiles)
    moments = "".join(f'<div class="finding"><div class="finding-title">{H.esc(m["title"])} · {H.esc(f.hm(m["t"]))}</div>'
                      f'<p>{H.esc(m["text"])}</p></div>' for m in A["moments"])
    sails = ""
    if A["sails"]:
        sails = "<p>Sails we flew: " + H.esc(" → ".join(f"{s['sail']} ({f.hm(s['t0'])})" for s in A["sails"])) + ".</p>"
    return f"""
<section id="happened" class="wrap">
  <h2>What actually happened</h2>
  <div class="kpis">{tiles_html}</div>
  <p class="lede">The forecasts below are the ones we had before the start: the {len(b.plans)} models that verified best
  against our log, best first. Our measured wind (blue) is drawn over each meteogram.</p>
  <div class="findings">{moments}</div>
  {sails}
</section>"""


# ------------------------------------------------------------------------------------------- html

def _signs_text(p: ModelPlan, f: _Fmt) -> str:
    if p.change is None:
        return "–"
    s, out = p.change.signs, []
    if "pressure_min" in s:
        out.append(f"pressure low {s['pressure_min']['hpa']:.1f} hPa at {f.hm(s['pressure_min']['t'])}, "
                   f"+{s.get('pressure_rise_3h', 0):.1f} hPa in 3 h")
    if s.get("temp_drop", 0) >= 1.0:
        out.append(f"air −{s['temp_drop']:.0f} °C")
    if "rain_onset" in s:
        out.append(f"rain from {f.hm(s['rain_onset'])}")
    return H.esc("; ".join(out) or "none")


def render(b: Briefing) -> str:
    f = _Fmt(b)
    turning = b.turning_label
    models = [p.model for p in b.plans]
    gun_label = timeutil.utc_offset_label(b.gun, b.tz)

    # --- at a glance
    tws_best = max((p for p in b.plans if "tws_max" in p.stats), key=lambda p: p.stats["tws_max"]["kt"], default=None)
    strongest = "–"
    strongest_note = ""
    if tws_best:
        strongest = f"{tws_best.stats['tws_max']['kt']:.0f} kt"
        g = max((p.stats["gust_max"]["kt"] for p in b.plans if "gust_max" in p.stats), default=None)
        strongest_note = (f"gusts to {g:.0f} kt · " if g else "") + f"{tws_best.model} {f.hm(tws_best.stats['tws_max']['t'])}"
    w = b.window
    kpis = [
        ("Change window", f"{f.when(w['t0'])}–{f.when(w['t1'])}" if w else "no clear change",
         f"{len(w['changes'])} of {len(b.plans)} models show it" if w else ""),
        (f"At {turning}", _range(f, [p.eta_turning for p in b.plans]), ", ".join(models)),
        ("Predicted finish", _range(f, [p.finish for p in b.plans]), "these routings"),
        ("Strongest wind", strongest, strongest_note),
    ]
    kpi_html = "".join(f'<div class="kpi"><div class="label">{H.esc(l)}</div><div class="value">{H.esc(v)}</div>'
                       f'<div class="note">{H.esc(n)}</div></div>' for l, v, n in kpis)
    verdict = w["verdict"] if w else "No model shows a clear, sustained wind change along its route."

    # --- the change
    change_rows = []
    for p in b.plans:
        c = p.change
        if c is None:
            change_rows.append([H.model_cell(p.model), "none", "–", "–", "–", H.esc(f.when(p.eta_turning)), "–"])
            continue
        rounds = "–"
        if p.eta_turning is not None:
            d = c.t - p.eta_turning
            rounds = f"{_dur(d)} {'before' if d > 0 else 'after'} the change"
        change_rows.append([
            H.model_cell(p.model), H.esc(f.when(c.t)),
            H.esc(f"{compass(c.twd_from)} {c.tws_before:.0f} kt → {compass(c.twd_to)} {c.tws_after:.0f} kt"),
            H.esc(f"{abs(c.swing):.0f}°"), _signs_text(p, f), H.esc(f.when(p.eta_turning)), H.esc(rounds)])
    change_table = H.table(["Model", "Change", "Wind before → after", "Shift", "Signs", f"At {turning}", "We round"],
                          change_rows, num_cols={1, 3, 5}, stack=True)

    # --- meteograms
    met_blocks = []
    for p in b.plans:
        r = p.route
        rows = [[H.esc(f.when(t)), H.esc(r.mark[i]), H.num(r.get("tws")[i]), H.num(r.get("twg")[i]),
                 H.num(r.get("twd")[i], 0), H.num(r.get("twa")[i], 0), H.num(r.get("mslp")[i]),
                 H.num(r.get("airt")[i]), H.num(r.get("rain")[i], 2), H.esc(r.sail_filled[i])]
                for i, t in enumerate(r.t)]
        table = H.table(["Time", "Mark", "Wind kt", "Gust kt", "Dir °T", "TWA", "hPa", "Air °C", "Rain mm/h", "Sail"],
                       rows, num_cols={0, 2, 3, 4, 5, 6, 7, 8})
        callouts = "".join(f'<li><span class="when">{H.esc(f.when(c["t"]))}</span> {H.esc(c["text"])}</li>' for c in p.callouts)
        meta = (f"run {f.run(r.created)} · {_dur(r.finish - b.gun)} elapsed · finish {f.when(r.finish)}"
                if r.created else f"{_dur(r.finish - b.gun)} elapsed · finish {f.when(r.finish)}")
        missing = [] if r.has("airt") else ["air temperature"]
        note = f" This routing has no {', '.join(missing)}." if missing else ""
        met_blocks.append(
            f'<article class="model" id="met-{H.esc(p.model)}"><h3>{H.model_key(p.model)} {H.esc(p.model)} '
            f'<small>{H.esc(meta)}</small></h3>'
            f'<figure class="chart"><div class="chart-body"></div><figcaption>Forecast along the {H.esc(p.model)} '
            f'optimal route ({H.esc(os.path.basename(r.path))}).{H.esc(note)} The bar under the charts is the planned sail.'
            f'</figcaption><details class="table-view"><summary>Table view</summary>{table}</details></figure>'
            f'<ul class="callouts">{callouts}</ul></article>')

    # --- side by side (table: on the hour)
    hours = np.arange(np.ceil(min(p.route.start for p in b.plans) / 3600) * 3600, max(p.finish for p in b.plans) + 1, 3600)
    cmp_rows = []
    for h in hours:
        row = [H.esc(f.when(h))]
        for p in b.plans:
            r = p.route
            if h < r.start or h > r.finish:
                row += ["–", "–", "–"]
                continue
            k = int(np.argmin(np.abs(r.t - h)))
            row += [H.num(r.get("tws")[k], 0), H.esc(f"{H.num(r.get('twd')[k], 0)} {compass(r.get('twd')[k])}"), H.num(r.get("mslp")[k])]
        cmp_rows.append(row)
    cmp_head = ["Time"] + [x for m in models for x in (f"{m} kt", f"{m} dir", f"{m} hPa")]
    cmp_table = H.table(cmp_head, cmp_rows, num_cols=set(range(len(cmp_head))) - {0})

    # --- sails and manoeuvres
    plan_rows = [[H.model_cell(p.model),
                  H.esc(" → ".join(f"{s['sail']} ({f.hm(s['t0'])})" for s in p.sail_runs))] for p in b.plans]
    man_rows = sorted(([H.esc(f.when(m["t"])), H.esc(p.model), H.esc(m["kind"]),
                        H.esc(f"{abs(m['twa_from']):.0f}° {'stbd' if m['twa_from'] > 0 else 'port'} → "
                              f"{abs(m['twa_to']):.0f}° {'stbd' if m['twa_to'] > 0 else 'port'}"), H.esc(m["mark"] or "")]
                       for p in b.plans for m in p.manoeuvres), key=lambda r: r[0])
    shift_rows = [[H.esc(p.model), H.esc(f"{f.hm(s['t0'])}–{f.hm(s['t1'])}"),
                   H.esc(f"{s['kind']} {abs(s['shift']):.0f}°"), H.esc(f"{compass(s['from'])} → {compass(s['to'])}")]
                  for p in b.plans for s in p.shifts]
    sails_tables = (H.table(["Model", "Planned sails (from the routing's sail chart)"], plan_rows)
                    + H.table(["Time", "Model", "Manoeuvre", "TWA", "At mark"], man_rows, num_cols={0})
                    + (H.table(["Model", "Hour", "Shift", "Direction"], shift_rows) if shift_rows else ""))

    # --- marks (map table view)
    mark_names, seen = [], set()
    for p in b.plans:
        for m in p.marks:
            key = (m["name"], m["occurrence"])
            if key not in seen:
                seen.add(key)
                mark_names.append(key)
    mark_rows = []
    for name, occ in mark_names:
        row = [H.esc(name + (f" ({occ})" if occ > 1 else ""))]
        for p in b.plans:
            t = next((m["t"] for m in p.marks if m["name"] == name and m["occurrence"] == occ), None)
            row.append(H.esc(f.when(t)))
        mark_rows.append(row)
    marks_table = H.table(["Mark"] + models, mark_rows, num_cols=set(range(1, len(models) + 1)))

    # --- finishes
    used = {(os.path.basename(p.route.path)) for p in b.plans}
    fin_rows = [[H.esc(f.run(r["run"])), H.esc(r["model"]), H.esc(r["source"]), H.esc(f.when(r["finish"])),
                 H.esc(timeutil.fmt_duration(r["elapsed"]))] for r in b.finishes]
    fin_table = H.table(["Run", "Model", "From", "Finish", "Elapsed"], fin_rows, num_cols={3, 4}, stack=True,
                       row_class=lambda k: "used" if b.finishes[k]["source"] == "route table" and b.finishes[k]["file"] in used else "")

    notes = f'<section id="notes" class="wrap"><h2>Navigator\'s notes</h2><div class="notes">{H.esc(b.notes)}</div></section>' if b.notes else ""
    glossary = "".join(f"<dt>{H.esc(t)}</dt><dd>{H.esc(d)}</dd>" for t, d in GLOSSARY)
    inputs = "".join(f"<li>{H.esc(os.path.basename(p.route.path))}: {H.esc(p.model)} ({H.esc(p.route.label)}), "
                     f"created {H.esc(f.run(p.route.created))}</li>" for p in b.plans)
    others = "".join(f"<li>{H.esc(os.path.basename(r.path))}: {H.esc(r.model)}, created {H.esc(f.run(r.created))} "
                     "(finish table only)</li>" for r in b.other_routes)
    sums = "".join(f"<li>{H.esc(os.path.basename(s.path))}</li>" for s in b.summaries)
    warns = "".join(f"<li>{H.esc(x)}</li>" for x in b.warnings)
    generated = timeutil.fmt_local(b.generated, b.tz, "%a %d %b %Y %H:%M")
    course_src = os.path.basename(b.course.source.split("#")[0]) if b.course.source else "none"
    after = b.after is not None
    toc_items = ([("happened", "What happened")] if after else []) + [
        ("glance", "The forecast" if after else "At a glance"), ("change", "The change"), ("meteograms", "Meteograms"),
        ("compare", "Side by side")] + ([("gribs", "Every model")] if b.gribs else []) + [
        ("sails", "Sails"), ("routes", "Map"), ("finishes", "Finishes"), ("glossary", "Glossary")]
    toc = "".join(f'<a href="#{i}">{H.esc(t)}</a>' for i, t in toc_items)
    eyebrow = "Day After · crew edition" if after else "Day Before · crew weather briefing"

    body = f"""
<header class="wrap cover">
  <div class="topbar"><div class="eyebrow">{H.esc(eyebrow)}</div>
  <button class="theme-btn" type="button">Theme: auto</button></div>
  <h1>{H.esc(b.race_name)}</h1>
  <p class="sub">{H.esc(b.boat + " · " if b.boat else "")}gun {H.esc(timeutil.fmt_local(b.gun, b.tz, "%a %d %b %H:%M"))} {H.esc(gun_label)} · models {H.esc(", ".join(models))}</p>
</header>
<nav class="toc"><div class="wrap">{toc}</div></nav>
<main>
{_after_section(b, f)}
<section id="glance" class="wrap">
  <h2>{"The forecast we had" if after else "At a glance"}</h2>
  <div class="kpis">{kpi_html}</div>
  <p class="verdict">{H.esc(verdict)}</p>
  <p class="lede">These are forecasts, not promises: each routing assumes its model is right and that we sail the polar.
  Watch the breeze and the barometer against the timings below, and expect the change early if the models start to disagree.</p>
</section>
<section id="change" class="wrap">
  <h2>When does the change come?</h2>
  <p class="lede">Each row is one model. ◆ is when its routing meets the change (the largest wind shift that holds for
  half an hour); ● is when it reaches {H.esc(turning)}. If ● comes before ◆, that model has us rounding before the change.
  The grey band spans the earliest to the latest model.</p>
  {H.figure("chart-window", "Change and rounding time per model, on the race clock. The table below holds the same times.")}
  {change_table}
</section>
<section id="meteograms" class="wrap">
  <h2>Meteograms along each route</h2>
  <div class="howto">
    <p><strong>How to read them.</strong> Each meteogram follows the boat along that model's optimal route, so time is
    also position on the course. Read down: <span class="met-key"><span class="swatch-line" style="border-top-color: var(--met-tws)"></span>wind speed</span>
    (dashed: gusts), wind direction (dots), <span class="met-key"><span class="swatch-line" style="border-top-color: var(--met-pressure)"></span>pressure</span>,
    <span class="met-key"><span class="swatch-line" style="border-top-color: var(--met-temp)"></span>air temperature</span> and
    <span class="met-key"><span class="swatch-line" style="border-top-color: var(--met-rain)"></span>rain</span>, Expedition's own colours.{
    ' Over the wind panels: <span class="met-key"><span class="swatch-line" style="border-top-color: var(--boat); border-top-width: 3px"></span>what we measured</span> (10-min means, blue dots for direction); the dashed line is when we actually rounded.' if after else ''}</p>
    <p>A front or southerly change shows up as the direction dots jumping, pressure bottoming and then rising, the
    temperature dropping and rain starting, usually within an hour or two of each other. The shaded band marks when
    the model's change passes; the solid line is our time at {H.esc(turning)}. Hover or tap for the numbers.</p>
  </div>
  {"".join(met_blocks)}
</section>
<section id="compare" class="wrap">
  <h2>The models side by side</h2>
  <p class="lede">The same forecasts on one set of axes. Where the lines part, the models disagree: that is where to
  watch the breeze and the barometer.</p>
  {H.figure("chart-compare", "Wind speed, direction and pressure along each model's route.", cmp_table, "Table view (on the hour)")}
</section>
{_grib_section(b, f)}
<section id="sails" class="wrap">
  <h2>Sails, tacks and gybes</h2>
  <p class="lede">The sail each routing picks from the sail chart, and where it tacks or gybes. Use it to have the next
  sail ready on deck before the breeze gets there. Very short changes at mark roundings are left out.</p>
  {H.figure("chart-sails", "Planned sails per model; ◆ marks a tack or gybe.", sails_tables, "Table view")}
</section>
<section id="routes" class="wrap">
  <h2>Routes on the course</h2>
  <p class="lede">Markers sit on the hour along each route; ◆ shows where each route meets the change. Drag to pan (two
  fingers on a phone); click the map, then scroll to zoom.</p>
  {H.figure("chart-map", "Optimal routes and course marks. Coast: Natural Earth · © OpenStreetMap contributors.", marks_table, "Table view (route time at each mark)")}
</section>
<section id="finishes" class="wrap">
  <h2>Predicted finish</h2>
  <p class="lede">Every predicted finish on file: the route tables used above (bold) plus Expedition's “summary of all
  routes”. Later runs usually know more.</p>
  {fin_table}
</section>
{notes}
<section id="glossary" class="wrap">
  <h2>Weather words</h2>
  <dl class="glossary">{glossary}</dl>
</section>
<footer class="wrap">
  <p><strong>Data.</strong> Route tables:</p><ul>{inputs}{others}</ul>
  {"<p>Route summaries:</p><ul>" + sums + "</ul>" if sums else ""}
  <p>Course from {H.esc(course_src)}; turning mark {H.esc(turning)}. Gun from the {H.esc(b.gun_source)}.
  Route-table directions are magnetic and were converted to true with a variation of {H.esc(b.variation_text)}.
  Times are {H.esc(gun_label)}.</p>
  {"<p><strong>Warnings.</strong></p><ul class='warnings'>" + warns + "</ul>" if warns else ""}
  <p>Coastline: Natural Earth (public domain) and © OpenStreetMap contributors (ODbL).</p>
  <p>Generated {H.esc(generated)} by Day After {H.esc(__version__)} · <a href="https://github.com/pishi-ishi/day-after">github.com/pishi-ishi/day-after</a></p>
</footer>
</main>"""
    title = f"Day After (crew): {b.race_name}" if after else f"Day Before: {b.race_name}"
    desc = (f"Crew edition for {b.race_name}: the forecast against what happened." if after
            else f"Crew weather briefing for {b.race_name}: models {', '.join(models)}.")
    return H.page(title, body, build_data(b), scripts=("charts.js", "day_before.js"), description=desc)


def filename(b: Briefing) -> str:
    return f"day_after_{_slug(b.race_name)}_crew.html" if b.after else f"day_before_{_slug(b.race_name)}.html"


def write(b: Briefing, out: str | None = None) -> str:
    if out is None:
        out = os.path.join(b.folder, "out", filename(b))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    html_text = render(b)
    tmp = out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(html_text)
    os.replace(tmp, out)
    return out
