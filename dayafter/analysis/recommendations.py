"""Decisions and recommendations for the skipper/owner edition: three to five plain sentences, each traced to a
number elsewhere in the report (the leadership weather-briefing style: bottom line first, then what to do)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core import timeutil
from .findings import mark_labeller
from .race_analysis import RaceAnalysis


@dataclass
class Recommendation:
    topic: str     # forecast | strategy | speed | manoeuvres | instruments
    title: str
    text: str
    weight: float


def bottom_line(a: RaceAnalysis) -> str:
    """One or two sentences: the result, and what decided it."""
    out = []
    if a.result is not None and a.result.place:
        n = sum(r.finished for r in a.results)
        out.append(f"{a.boat} finished {a.result.place} of {n} on corrected time in {timeutil.fmt_duration(a.elapsed)}.")
    f = a.fleet
    if f is not None and f.us is not None and f.rounding_r is not None and abs(f.rounding_r) >= 0.4:
        label = mark_labeller(a)
        late = f.rounding_r < 0
        out.append(f"The race was decided by when boats rounded {label(a.course.turning_mark.name)} relative to the "
                   f"wind change: the {'later' if late else 'earlier'} a boat rounded, the better it did.")
    ratios = [fc.scores["tws_ratio"] for fc in a.forecasts if "tws_ratio" in fc.scores]
    if ratios and all(r < 0.9 for r in ratios):
        out.append(f"Every forecast was light: we sailed in about {(1 / np.mean(ratios) - 1) * 100:.0f} % more wind "
                   "than the routings planned for.")
    return " ".join(out)


def recommendations(a: RaceAnalysis) -> list[Recommendation]:
    hm = lambda t: timeutil.fmt_local(t, a.tz, "%H:%M")
    label = mark_labeller(a)
    out: list[Recommendation] = []

    # which model to trust for what
    timed = [(abs(fc.scores["change_error_s"]), fc) for fc in a.forecasts if "change_error_s" in fc.scores]
    strength = [(abs(1 - fc.scores["tws_ratio"]), fc) for fc in a.forecasts if "tws_ratio" in fc.scores]
    if timed and strength:
        bt = min(timed, key=lambda x: x[0])[1]
        bs = min(strength, key=lambda x: x[0])[1]
        worst = max(timed, key=lambda x: x[0])[1]
        e = bt.scores["change_error_s"]
        txt = (f"For the timing of a change, lean on {bt.model}: it was {abs(e) / 60:.0f} min "
               f"{'late' if e > 0 else 'early'} here")
        if worst is not bt:
            e2 = worst.scores["change_error_s"]
            txt += f", while {worst.model} was {abs(e2) / 60:.0f} min {'late' if e2 > 0 else 'early'}"
        txt += f". For breeze strength, {bs.model} came closest ({(1 - bs.scores['tws_ratio']) * 100:.0f} % light)."
        if all(fc.scores.get("tws_ratio", 1) < 0.9 for _, fc in strength):
            txt += " Plan sail changes for more wind than any routing shows."
        out.append(Recommendation("forecast", "Which forecast to trust", txt, 0.9))

    # strategy: the rounding effect
    f = a.fleet
    if f is not None and f.us is not None and f.rounding_r is not None and abs(f.rounding_r) >= 0.4 and \
            f.us.rounding is not None and a.change is not None:
        podium = sorted((b for b in f.boats if b.result.place), key=lambda b: b.result.place)[:3]
        when = ", ".join(hm(a.gun + b.rounding) for b in podium if b.rounding is not None)
        ours = a.passage(a.course.turning_mark.name)
        t_round = ours.t if ours is not None and ours.t is not None else a.gun + f.us.rounding
        d = a.change.onset - t_round
        out.append(Recommendation(
            "strategy", "The rounding against the change",
            f"We rounded {label(a.course.turning_mark.name)} at {hm(t_round)}, {abs(d) / 60:.0f} min "
            f"{'before' if d > 0 else 'after'} the change; the podium rounded at {when}. When a change is due near the "
            "turning mark, weigh slowing the approach or sailing for position against arriving early.", 0.85))

    # speed: the weakest leg
    p = a.performance
    if p is not None and p.phases:
        legs = [x for x in p.phases if x.kind == "leg"]
        worst = min(legs, key=lambda x: x.pct) if legs else None
        if worst is not None and worst.pct < 92:
            tg = next((t for t in p.targets if t["side"] == ("upwind" if worst.twa < 90 else "downwind")
                       and t["tws0"] <= worst.tws < t["tws1"]), None)
            extra = ""
            if tg is not None:
                extra = (f" In {tg['tws0']:.0f}–{tg['tws1']:.0f} kt our best {tg['side']} angle was {tg['twa']:.0f}° "
                         f"at {tg['stw']:.1f} kt against the polar's {tg['polar_twa']:.0f}° at {tg['polar_stw']:.1f} kt.")
            vmg = f", {worst.vmg_pct:.0f} % of target VMG" if worst.vmg_pct is not None else ""
            out.append(Recommendation("speed", "Where the speed went",
                                      f"{worst.name} was our slowest leg at {worst.pct:.0f} % of polar speed{vmg}."
                                      + extra + " Practise that mode and agree the targets before the next race.", 0.75))

        big = [m for m in p.manoeuvres if m.loss_m > 100]
        if big:
            m = big[0]
            out.append(Recommendation("manoeuvres", "Manoeuvres in a breeze",
                                      f"The {m.kind} at {hm(m.t)} in {m.tws:.0f} kt cost {m.loss_m:.0f} m "
                                      f"({m.loss_s:.0f} s); {len(big)} manoeuvre{'s' if len(big) > 1 else ''} cost "
                                      "over 100 m each. Brief the gybe (or tack) in strong wind before it is needed.", 0.6))

    # instruments
    fixes = []
    for c in a.checks:
        if c.status not in ("warn", "fail"):
            continue
        if c.id == "speed":
            fixes.append(f"boat speed reads {abs(c.data['k'] - 1) * 100:.0f} % {'low' if c.data['k'] > 1 else 'high'}")
        elif c.id == "twa_up":
            fixes.append("the true wind angle upwind is off")
        elif c.id == "heading":
            fixes.append(f"heading is {c.value} off")
    if fixes:
        out.append(Recommendation("instruments", "Fix the instruments",
                                  "Before the next race: " + "; ".join(fixes) + ". Wrong numbers on deck give wrong "
                                  "targets and laylines; the navigator edition has the corrections.", 0.7))
    return sorted(out, key=lambda r: -r.weight)[:5]
