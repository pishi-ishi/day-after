"""Navigator sections for performance (polar %, targets, manoeuvres, sails) and the season."""
from __future__ import annotations

import numpy as np

from ..core import timeutil
from . import html as H


def perf_data(a) -> dict | None:
    p = a.performance
    if p is None:
        return None
    return H.clean({
        "buckets": p.buckets, "targets": p.targets, "tws_max": p.tws_max,
        "manoeuvres": [{"t": m.t, "kind": m.kind, "tws": m.tws, "loss_m": m.loss_m, "loss_s": m.loss_s,
                        "stw_before": m.stw_before, "stw_min": m.stw_min, "recover_s": m.recover_s,
                        "twa_from": m.twa_from, "twa_to": m.twa_to} for m in p.manoeuvres],
    }, 2)


def _pct(v) -> str:
    return "–" if v is None or not np.isfinite(v) else f"{v:.0f} %"


def performance_section(a) -> str:
    p = a.performance
    if p is None:
        return ('<section id="performance" class="wrap"><h2>Performance</h2><p class="lede">No polar: add the boat\'s '
                'Expedition polar (boat.polar in race.dayafter.json) to compare speed with the polar.</p></section>')
    tz = a.tz
    hm = lambda t: timeutil.fmt_local(t, tz, "%H:%M")
    flagged = p.twa_source != "logged"
    legs = [x for x in p.phases if x.kind == "leg"]
    w = np.array([x.n for x in legs], float)
    overall = float(np.average([x.pct for x in legs], weights=w)) if legs else float("nan")
    best = max(legs, key=lambda x: x.pct) if legs else None
    worst = min(legs, key=lambda x: x.pct) if legs else None
    tk = [m for m in p.manoeuvres if m.kind == "tack"]
    gy = [m for m in p.manoeuvres if m.kind == "gybe"]
    tiles = [("Polar speed", _pct(overall), "median per second, all legs, time-weighted"),
             ("Best leg", _pct(best.pct) if best else "–", best.name if best else ""),
             ("Weakest leg", _pct(worst.pct) if worst else "–", worst.name if worst else ""),
             ("Manoeuvres", f"{len(tk)} tacks · {len(gy)} gybes",
              f"median loss {np.median([m.loss_m for m in p.manoeuvres]):.0f} m" if p.manoeuvres else "none found")]
    tiles_html = "".join(f'<div class="kpi"><div class="label">{H.esc(l)}</div><div class="value">{H.esc(v)}</div>'
                         f'<div class="note">{H.esc(n)}</div></div>' for l, v, n in tiles)
    head = ["Phase", "Seconds", "TWS kt", "|TWA|", "STW kt", "Polar kt", "Polar %", "p25–p75"]
    if flagged:
        head.append("Logged TWA %")
    head.append("VMG %")
    rows = []
    for x in p.phases:
        r = [H.esc(x.name + (" *" if x.indicative else "")), str(x.n), H.num(x.tws, 1), H.esc(f"{x.twa:.0f}°"),
             H.num(x.stw, 2), H.num(x.target, 2), H.esc(_pct(x.pct)), H.esc(f"{x.p25:.0f}–{x.p75:.0f}")]
        if flagged:
            r.append(H.esc(_pct(x.pct_logged)))
        r.append(H.esc(_pct(x.vmg_pct)))
        rows.append(r)
    phase_t = H.table(head, rows, num_cols=set(range(1, len(head))), stack=True,
                      row_class=lambda k: "hole" if p.phases[k].kind == "hole" else "")
    # bucket matrix
    tws0s = sorted({b["tws0"] for b in p.buckets})
    by = {(b["tws0"], b["pos"]): b for b in p.buckets}
    mrows = []
    for t0 in tws0s:
        r = [H.esc(f"{t0:.0f}–{t0 + 2:.0f}" + (" *" if t0 + 1 > p.tws_max else ""))]
        for pos in ("upwind", "reach", "downwind"):
            b = by.get((t0, pos))
            r.append(H.esc(f"{b['pct']:.0f} % ({b['n'] // 60} min)") if b else "–")
        mrows.append(r)
    matrix = H.table(["TWS kt", "Upwind (< 70°)", "Reach (70–120°)", "Downwind (> 120°)"], mrows, num_cols={1, 2, 3})
    trows = [[H.esc(f"{x['tws0']:.0f}–{x['tws1']:.0f}" + (" *" if x["indicative"] else "")), H.esc(x["side"]),
              H.esc(f"{x['twa']:.0f}° / {x['polar_twa']:.0f}°"), H.esc(f"{x['stw']:.1f} / {x['polar_stw']:.1f}"),
              H.esc(f"{x['vmg']:.1f} / {x['polar_vmg']:.1f}"), H.esc(_pct(x["vmg"] / x["polar_vmg"] * 100))]
             for x in p.targets]
    targets_t = H.table(["TWS kt", "Side", "TWA ours / polar", "STW kt ours / polar", "VMG kt ours / polar", "VMG %"],
                        trows, num_cols={2, 3, 4, 5})
    side = lambda v: f"{abs(v):.0f}° {'stbd' if v > 0 else 'port'}"
    man_rows = [[H.esc(hm(m.t)), H.esc(m.kind), H.esc(f"{side(m.twa_from)} → {side(m.twa_to)}"), H.num(m.tws, 0),
                 H.esc(f"{m.stw_before:.1f} → {m.stw_min:.1f}"), H.num(m.loss_m, 0), H.num(m.loss_s, 0),
                 H.esc(f"{m.recover_s:.0f} s") if m.recover_s is not None else "> 3 min", H.esc(m.sail or "–")]
                for m in p.manoeuvres]
    man_t = H.table(["Time", "Kind", "TWA", "TWS kt", "STW kt in → min", "Loss m", "Loss s", "Back to 90 %", "Sail"],
                    man_rows, num_cols={0, 3, 5, 6, 7}, stack=True)
    sails = ""
    if p.by_sail:
        srows = [[H.esc(s["sail"]), H.esc(f"{hm(s['t0'])}–{hm(s['t1'])}"), H.num(s["tws"], 1), H.esc(f"{s['twa']:.0f}°"),
                  H.esc(_pct(s["pct"])), H.esc(f"{s['p25']:.0f}–{s['p75']:.0f}")] for s in p.by_sail]
        sails = ('<h3 class="sub-h">By sail</h3>' +
                 H.table(["Sail", "When", "TWS kt", "|TWA|", "Polar %", "p25–p75"], srows, num_cols={2, 3, 4, 5}))
    else:
        sails = ('<p class="small">No sail changes were logged as Expedition events, so there is no by-sail view. Log '
                 'sail changes and reefs as events during the race to get one.</p>')
    notes = "".join(f"<li>{H.esc(n)}</li>" for n in p.notes)
    return f"""
<section id="performance" class="wrap">
  <h2>Performance</h2>
  <p class="lede">Corrected boat speed against the polar ({H.esc(p.polar_name)}), second by second while moving
  (above 3 kt). Phases quote the median and the middle half (p25–p75); VMG % compares upwind VMG with the polar's best.
  * above the polar's top row ({p.tws_max:.0f} kt): indicative only.</p>
  <div class="kpis">{tiles_html}</div>
  {phase_t}
  {"<ul class='warnings'>" + notes + "</ul>" if notes else ""}
  {H.figure("chart-polarpct", "Polar % by wind speed and point of sail (median of each 2 kt band).", matrix, "Table view: TWS × point of sail")}
  <h3 class="sub-h">Targets</h3>
  <p class="lede">Njord-style: in each 2 kt band, the seconds with our best VMG (75th–95th percentile) show the angle
  and speed we actually sail when going well, against the polar's targets.</p>
  {H.figure("chart-targets", "Target angles: ours (the 75th–95th percentile of VMG) against the polar's.", targets_t, "Table view: targets")}
  <h3 class="sub-h">Tacks and gybes</h3>
  <p class="lede">Each manoeuvre's loss is the distance along the wind given up from 15 s before the turn to 45 s after
  it, against holding the VMG we had before. Ranked worst first.</p>
  {H.figure("chart-manoeuvres", "Loss per tack and gybe against the wind speed.")}
  {man_t}
  {sails}
</section>"""


def season_section(season: dict | None, a) -> str:
    if not season or not season.get("races"):
        return ""
    races = season["races"]
    perf = {}
    for r in season.get("perf", []):
        perf.setdefault(r["race_id"], {})[r["pos"]] = r["pct"]
    rows = []
    for r in races:
        pp = perf.get(r["race_id"], {})
        rows.append([H.esc(timeutil.fmt_local(r["gun"], r["tz"] or a.tz, "%d %b %Y")), H.esc(r["name"]),
                     H.esc(f"{r['place']} of {r['finishers']}" if r["place"] else "–"),
                     H.esc(timeutil.fmt_duration(r["elapsed"])) if r["elapsed"] else "–", H.num(r["tws_mean"], 1),
                     H.esc(_pct(r["polar_pct"])), H.esc(_pct(pp.get("upwind"))), H.esc(_pct(pp.get("reach"))),
                     H.esc(_pct(pp.get("downwind"))), H.num(r["k"], 3)])
    race_t = H.table(["Date", "Race", "Place", "Elapsed", "TWS kt", "Polar %", "Upwind", "Reach", "Downwind",
                      "Speed factor"], rows, num_cols={3, 4, 5, 6, 7, 8, 9}, stack=True,
                     row_class=lambda k: "used" if races[k]["name"] == a.race_name else "")
    # models: mean over races
    agg: dict[tuple, list] = {}
    for m in season.get("models", []):
        agg.setdefault((m["model"], m["source"]), []).append(m)
    mrows = []
    for (model, src), ms in sorted(agg.items(), key=lambda kv: np.nanmean([x["tws_mae"] or 99 for x in kv[1]])):
        ratio = [x["tws_ratio"] for x in ms if x["tws_ratio"]]
        ch = [abs(x["change_error_s"]) / 60 for x in ms if x["change_error_s"] is not None]
        mrows.append([H.model_cell(model), H.esc("route table" if src == "route" else "GRIB at our position"),
                      str(len(ms)), H.esc(f"{(1 - np.mean(ratio)) * 100:.0f} % light" if ratio and np.mean(ratio) < 1
                                          else f"{(np.mean(ratio) - 1) * 100:.0f} % heavy" if ratio else "–"),
                      H.num(np.nanmean([x["tws_mae"] for x in ms if x["tws_mae"] is not None]), 1),
                      H.esc(f"{np.mean(ch):.0f} min" if ch else "–")])
    model_t = H.table(["Model", "Judged on", "Races", "Strength", "TWS error kt", "Change timing error"], mrows,
                      num_cols={2, 4, 5}, stack=True)
    h2h = sorted(season.get("head_to_head", []), key=lambda r: -r["races"])
    rivals = {r["boat"] for r in season.get("rivals", [])}
    hrows = [[H.esc(r["boat"]), str(r["races"]), H.esc(f"{r['ahead']} of {r['races']}"),
              H.esc(f"{r['mean_gap_s'] / 60:+.1f}")] for r in h2h if r["boat"] in rivals]
    h2h_t = H.table(["Rival", "Races", "Finished ahead of us", "Mean gap, corrected min"], hrows, num_cols={1, 3}) if hrows else ""
    cal = {}
    for c in season.get("calibration", []):
        cal.setdefault(c["race_id"], {})[c["check_id"]] = c
    crows = []
    for r in races:
        c = cal.get(r["race_id"], {})
        crows.append([H.esc(r["name"]), H.esc(c.get("speed", {}).get("value", "–")), H.esc(c.get("twa_up", {}).get("value", "–")),
                      H.esc(c.get("heading", {}).get("value", "–"))])
    cal_t = H.table(["Race", "Boat speed", "Upwind TWA", "Heading"], crows)
    return f"""
<section id="season" class="wrap">
  <h2>Season</h2>
  <p class="lede">Every race analysed with this copy of Day After ({len(races)} so far), from the season database.
  Re-running a race replaces its numbers.</p>
  {race_t}
  <h3 class="sub-h">Which model to trust on this coast</h3>
  {model_t}
  {"<h3 class='sub-h'>Head to head</h3>" + h2h_t if h2h_t else ""}
  <h3 class="sub-h">Calibration history</h3>
  {cal_t}
</section>"""
