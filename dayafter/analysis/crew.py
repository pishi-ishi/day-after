"""Crew edition: the Day Before briefing rebuilt after the race, with what actually happened laid over it.

Models: the two or three route-table models that verified best against our log (or the race file's
`crew_models`). On top of the forecast: our measured wind, our rounding, the observed change, the sails we
actually flew (Expedition sail events) and the race's key moments in a few lines each (DESIGN.md, crew
edition). Every number comes from the RaceAnalysis the navigator edition shows.
"""
from __future__ import annotations

import numpy as np

from ..core import timeutil
from . import briefing as briefing_mod
from . import forecast as forecast_mod
from .race import binned_wind
from .race_analysis import RaceAnalysis
from .weather import compass

MAX_MODELS = briefing_mod.MAX_CREW_MODELS


def crew_models(a: RaceAnalysis) -> list[str]:
    have = [r.model for r in a.routes]
    wanted = a.project.get("crew_models")
    if wanted and wanted != "auto":
        picked = briefing_mod.pick_models(have, wanted)
        if picked:
            return picked
    return [m for m in a.model_rank if m in have][:MAX_MODELS] or have[:MAX_MODELS]


def sails_flown(a: RaceAnalysis) -> list[dict]:
    """Headsail runs from Expedition sail events (the mainsail is left out), with reefs noted."""
    out: list[dict] = []
    for e in a.events:
        if e.kind != "sail" or not e.sail or e.t > a.finish:
            continue
        head = " + ".join(x for x in e.sail.split(" + ") if x.lower() not in ("main", "mainsail")) or e.sail
        t = max(e.t, a.start)
        if out and out[-1]["sail"] == head:
            continue
        if out:
            out[-1]["t1"] = t
        out.append({"t0": t, "t1": a.finish, "sail": head})
    out = [s for s in out if s["t1"] - s["t0"] >= 120]
    reefs = [{"t": e.t, "reef": e.reef, "text": e.text} for e in a.events if e.kind == "reef" and a.start <= e.t <= a.finish]
    return [dict(s, reefs=[r for r in reefs if s["t0"] <= r["t"] < s["t1"]]) for s in out]


def _leg_means(t, fc, obs, t0, t1):
    m = (t >= t0) & (t <= t1) & np.isfinite(fc) & np.isfinite(obs)
    return (float(np.mean(fc[m])), float(np.mean(obs[m]))) if m.sum() >= 2 else None


def key_moments(a: RaceAnalysis, models: list[str]) -> list[dict]:
    """Two or three moments, forecast against what we got: the leg the forecasts missed most before the change,
    the change itself, and the breeze after it."""
    hm = lambda t: timeutil.fmt_local(t, a.tz, "%H:%M")
    fcs = {f.model: f for f in a.forecasts if f.model in models}
    grib = {m.model: m for m in (a.forecast.models if a.forecast else [])}
    out = []
    change_t = a.change.onset if a.change else None
    legs = [p for p in a.phases if p.kind == "leg" and p.tws >= 10]

    def compare(p) -> tuple[list[str], list[float]]:
        parts, ratios = [], []
        for m in models:
            f = fcs.get(m)
            r = _leg_means(f.t, f.fc_tws, f.obs_tws, p.t0, p.t1) if f is not None else None
            if r:
                parts.append(f"{m} {r[0]:.0f}")
                ratios.append(r[0] / r[1])
        return parts, ratios

    before = [p for p in legs if change_t is None or p.t1 <= change_t + 60]
    scored = [(p, *compare(p)) for p in before]
    scored = [x for x in scored if x[2]]
    if scored:
        p, parts, ratios = max(scored, key=lambda x: abs(1 - np.mean(x[2])))
        miss = 1 - float(np.mean(ratios))
        word = "light" if miss > 0 else "heavy"
        txt = (f"We had {p.tws:.0f} kt of {compass(p.twd)} on average, up to {p.tws_p95:.0f} kt (95th percentile). The routings had {', '.join(parts)} kt: about {abs(miss) * 100:.0f} % {word}.")
        gm = [f"{m.model} {w['fc']:.0f}" for m in grib.values() for w in m.windows if w["name"] == p.name]
        if gm:
            txt += f" The race-morning GRIBs at our own position said {', '.join(gm)} kt."
        if miss > 0.2:
            txt += " When the breeze runs this far above the forecast, expect the routing's sail crossovers early."
        out.append({"title": p.name, "t": p.t0, "text": txt})

    if a.change is not None:
        c = a.change.change
        times = []
        for m in models:
            f = fcs.get(m)
            if f is not None and f.change_t is not None:
                d = f.change_t - a.change.onset
                times.append(f"{m} {hm(f.change_t)} ({abs(d) / 60:.0f} min {'late' if d > 0 else 'early'})")
        turn = next((p for p in a.passages if a.course.turning_mark is not None and p.name == a.course.turning_mark.name
                     and p.t is not None), None)
        txt = (f"The wind went from {compass(c.twd_from)} {c.tws_before:.0f} kt to {compass(c.twd_to)} "
               f"{c.tws_after:.0f} kt at {hm(a.change.onset)}")
        if a.change.shift - a.change.onset > 45:
            txt += f": the old breeze died first and the new one filled in from {hm(a.change.shift)}"
        txt += "."
        if turn is not None:
            d = a.change.onset - turn.t
            txt += f" We had rounded at {hm(turn.t)}, {abs(d) / 60:.0f} min {'before' if d > 0 else 'after'} it."
        if times:
            txt += f" Forecast: {', '.join(times)}."
        out.append({"title": "The change", "t": a.change.onset, "text": txt})

        after = [p for p in legs if p.t0 >= change_t - 60]
        if after:
            t0, t1 = after[0].t0, after[-1].t1
            ct, cs, _ = binned_wind(a.tl.t.astype(float), a.wind.tws_g, a.wind.twd_g, t0, t1)
            if len(cs):
                parts = []
                for m in models:
                    f = fcs.get(m)
                    r = _leg_means(f.t, f.fc_tws, f.obs_tws, t0, t1) if f is not None else None
                    if r:
                        mx = np.nanmax(np.where((f.t >= t0) & (f.t <= t1), f.fc_tws, np.nan))
                        parts.append(f"{m} {r[0]:.0f} (max {mx:.0f})")
                txt = (f"After the change we sailed in {np.mean(cs):.0f} kt of {compass(c.twd_to)}, 10-min means up to "
                       f"{np.max(cs):.0f} kt.")
                if parts:
                    txt += f" The routings had {', '.join(parts)} kt."
                out.append({"title": "After the change", "t": t0, "text": txt})
    return out


def after_data(a: RaceAnalysis, models: list[str]) -> dict:
    t = a.tl.t.astype(float)
    ct, cs, cd = binned_wind(t, a.wind.tws_g, a.wind.twd_g, a.start, a.finish)
    k = np.flatnonzero((t >= a.start) & (t <= a.finish))[::60]
    turn = next((p for p in a.passages if a.course.turning_mark is not None and p.name == a.course.turning_mark.name
                 and p.t is not None), None)
    res = a.result
    return {
        "boat": a.boat, "start": a.start, "finish": a.finish, "elapsed": a.elapsed,
        "place": res.place if res else None, "of": sum(r.finished for r in a.results) or None,
        "obs": {"t": ct, "tws": cs, "twd": cd},
        "track": {"t": t[k], "lat": a.tl["Lat"][k], "lon": a.tl["Lon"][k]},
        "turning_t": turn.t if turn else None,
        "change": None if a.change is None else {"t": a.change.onset, "shift": a.change.shift,
                                                 "from": a.change.change.twd_from, "to": a.change.change.twd_to,
                                                 "before": a.change.change.tws_before, "after": a.change.change.tws_after},
        "sails": sails_flown(a),
        "moments": key_moments(a, models),
        "models_note": "",
    }


def build_crew_briefing(a: RaceAnalysis) -> briefing_mod.Briefing:
    models = crew_models(a)
    by = {r.model: r for r in a.routes}
    plan_routes = [by[m] for m in models]
    tname = a.course.turning_mark.name if a.course.turning_mark else ""
    label = ((a.project.get("course") or {}).get("mark_labels") or {}).get(tname) or briefing_mod.turning_label(tname)
    plans = [briefing_mod.make_plan(r, a.course, label, a.tz) for r in plan_routes]
    islands = []
    from ..ingest import course as course_mod
    for p in a.inputs.racenotes:
        try:
            islands += course_mod.read_racenotes(p)
        except Exception:  # noqa: BLE001 - decoration only
            pass
    notes = ((a.project.get("notes") or {}).get("crew") or "").strip()
    gribs = None
    if a.inputs.gribs or a.inputs.gribs_encrypted:
        try:
            gribs = forecast_mod.grib_along_route(a.inputs.gribs, plans[0].route, a.tz, gun=a.gun,
                                                  encrypted=a.inputs.gribs_encrypted)
        except Exception:  # noqa: BLE001 - optional
            gribs = None
    from ..core import magvar
    all_var = np.concatenate([r.variation for r in plan_routes])
    b = briefing_mod.Briefing(
        folder=a.folder, race_name=a.race_name, boat=a.boat, tz=a.tz, gun=a.gun, gun_source=a.gun_source, plans=plans,
        other_routes=[r for r in a.all_routes if r not in plan_routes], summaries=a.summaries, course=a.course,
        islands=islands, window=briefing_mod.change_window(plans, a.tz, label, a.course.turning_mark is not None),
        finishes=briefing_mod.finish_table(a.all_routes, a.summaries, a.gun),
        variation_text=magvar.describe(all_var, (a.project.get("race") or {}).get("variation_deg_e")),
        notes=notes, warnings=[], gribs=gribs, turning_text=label)
    b.after = after_data(a, models)
    return b
