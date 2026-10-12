"""Findings: short, cautious sentences generated from the analysis (HANDOVER §7.13). Rule-based, so every
claim traces back to a number elsewhere in the report. Navigator notes are added verbatim by the report."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core import timeutil
from .race_analysis import RaceAnalysis
from .weather import compass


@dataclass
class Finding:
    kind: str      # result | plan | hole | change | forecast | calibration
    title: str
    text: str
    weight: float  # higher = more decisive


def _dur(sec: float) -> str:
    m = int(round(abs(sec) / 60.0))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def mark_labeller(a: RaceAnalysis):
    """Display names: the race file's labels; marks within 1 nm of the turning mark share its label
    (Flinders Islet's W, S and E rounding points)."""
    from ..core import geo
    labels = dict((a.project.get("course") or {}).get("mark_labels") or {})
    tm = a.course.turning_mark
    if tm is not None and tm.name in labels:
        for m in a.course.marks:
            if m.name not in labels and float(geo.haversine_nm(m.lat, m.lon, tm.lat, tm.lon)) < 1.0:
                labels[m.name] = labels[tm.name]
    return lambda n: labels.get(n, n)


def mark_display(a: RaceAnalysis):
    """Labels for tables and charts: unique even when several rounding points share a label
    ("Flinders Islet (FI W)", "Flinders Islet (FI S)", …)."""
    from collections import Counter
    label = mark_labeller(a)
    shared = Counter(label(m.name) for m in a.course.marks)
    return lambda n: f"{label(n)} ({n})" if label(n) != n and shared[label(n)] > 1 else label(n)


def findings(a: RaceAnalysis) -> list[Finding]:
    hm = lambda t: timeutil.fmt_local(t, a.tz, "%H:%M")  # clock reading, as in every table of the report
    out: list[Finding] = []
    label = mark_labeller(a)

    # result
    if a.result is not None and a.result.corrected:
        n = sum(r.finished for r in a.results)
        out.append(Finding("result", "Result",
                           f"{a.boat} finished {_ordinal(a.result.place)} of {n} on corrected time "
                           f"({timeutil.fmt_duration(a.result.corrected)}), {timeutil.fmt_duration(a.elapsed)} elapsed "
                           f"with a TCC of {a.result.tcc:.3f}.", 0.5))

    # plan vs reality: the closest route, and where we lost and gained against it
    finals = {m: s.delta[m] for s in a.splits[-1:] for m in s.delta if s.delta[m] is not None}
    if finals:
        ref = min(finals, key=lambda m: abs(finals[m]))
        others = ", ".join(f"{_dur(v)} {'behind' if v > 0 else 'ahead of'} {m}" for m, v in finals.items() if m != ref)
        out.append(Finding("plan", "Against the routings",
                           f"We finished {_dur(finals[ref])} {'behind' if finals[ref] > 0 else 'ahead of'} the {ref} "
                           f"route, the closest to what happened" + (f"; {others}." if others else "."), 0.7))
        seq = [(s.mark, s.delta.get(ref)) for s in a.splits if s.delta.get(ref) is not None]
        steps = [(seq[i - 1][0], seq[i][0], seq[i][1] - seq[i - 1][1]) for i in range(1, len(seq))]
        if steps:
            # consecutive rounding points of one mark (FI W, S, E) count as one place
            merged: list[list] = []
            for a0, b0, d in steps:
                if merged and label(merged[-1][1]) == label(b0) == label(a0):
                    merged[-1][1] = b0
                    merged[-1][2] += d
                elif merged and label(a0) == label(merged[-1][1]) and label(merged[-1][0]) == label(a0):
                    merged[-1] = [merged[-1][0], b0, merged[-1][2] + d]
                else:
                    merged.append([a0, b0, d])
            lost = max(merged, key=lambda s: s[2])
            gain = min(merged, key=lambda s: s[2])
            if lost[2] > 300:
                out.append(Finding("plan", "Biggest loss",
                                   f"Lost {_dur(lost[2])} to the {ref} route between {label(lost[0])} and {label(lost[1])}.",
                                   0.8 + lost[2] / 36000))
            if gain[2] < -300:
                out.append(Finding("plan", "Biggest gain",
                                   f"Gained {_dur(gain[2])} on the {ref} route between {label(gain[0])} and {label(gain[1])}.",
                                   0.7 + -gain[2] / 36000))

    # holes
    for ph in (p for p in a.phases if p.kind == "hole"):
        out.append(Finding("hole", "Parked",
                           f"Stopped for {_dur(ph.t1 - ph.t0)} ({hm(ph.t0)}–{hm(ph.t1)}) in {ph.tws:.0f} kt of breeze, "
                           f"covering {ph.dist_nm:.1f} nm.", 0.9 if ph.t1 - ph.t0 > 900 else 0.6))

    # the change
    if a.change is not None:
        c = a.change.change
        turn = next((p for p in a.passages if p.role == "turning_mark" and p.t is not None
                     and a.course.turning_mark is not None and p.name == a.course.turning_mark.name), None)
        rel = ""
        if turn is not None:
            d = a.change.onset - turn.t
            rel = (f", {_dur(d)} after we rounded {label(turn.name)} at {hm(turn.t)}" if d > 0
                   else f", {_dur(d)} before we rounded {label(turn.name)}")
        lull = f"; the breeze faded from {hm(a.change.onset)} and the new wind filled in from {hm(a.change.shift)}" \
            if a.change.shift - a.change.onset > 45 else ""
        timing = []
        for f in a.forecasts:
            e = f.scores.get("change_error_s")
            if e is not None:
                timing.append((abs(e), f"{f.model} {_dur(e)} {'late' if e > 0 else 'early'}"))
        timing.sort()
        out.append(Finding("change", "The change",
                           f"The wind went {compass(c.twd_from)} {c.tws_before:.0f} kt to {compass(c.twd_to)} "
                           f"{c.tws_after:.0f} kt at {hm(a.change.onset)}{rel}{lull}."
                           + (f" Forecast timing: {', '.join(t for _, t in timing)}." if timing else ""), 0.95))

    # forecast strength
    ratios = [(f.model, f.scores["tws_ratio"]) for f in a.forecasts if "tws_ratio" in f.scores]
    if ratios and all(r < 0.9 for _, r in ratios):
        out.append(Finding("forecast", "More wind than forecast",
                           "Every routing was light on wind speed against what we measured: "
                           + ", ".join(f"{m} by {(1 - r) * 100:.0f} %" for m, r in ratios) + ".", 0.75))
    elif ratios and all(r > 1.1 for _, r in ratios):
        out.append(Finding("forecast", "Less wind than forecast",
                           "Every routing was heavy on wind speed against what we measured: "
                           + ", ".join(f"{m} by {(r - 1) * 100:.0f} %" for m, r in ratios) + ".", 0.75))

    # calibration
    fixes = []
    for c in a.checks:
        if c.status not in ("fail", "warn"):
            continue
        if c.id == "speed":
            k = c.data["k"]
            fixes.append(f"boat speed reads {abs(k - 1) * 100:.0f} % {'low' if k > 1 else 'high'} (calibrate × {k:.2f})")
        elif c.id == "twa_up":
            d = c.data["twa_logged"] - c.data["twa_recomputed"]
            fixes.append(f"upwind TWA reads {abs(d):.0f}° {'wide' if d > 0 else 'narrow'}")
        elif c.id == "heading":
            fixes.append(f"heading is {c.value} off")
        elif c.id == "awa_sym":
            fixes.append("apparent wind differs between tacks")
        elif c.id == "missing":
            fixes.append(f"log {c.value}")
    if fixes:
        text = "; ".join(fixes)
        out.append(Finding("calibration", "Fix before the next race", text[0].upper() + text[1:] + ".", 0.6))
    return sorted(out, key=lambda f: -f.weight)


def _ordinal(n: int | None) -> str:
    if n is None:
        return "–"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
