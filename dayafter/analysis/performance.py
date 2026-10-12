"""Performance against the polar: by phase, by TWS bucket × point of sail, Njord-style targets, by sail, and
manoeuvres ranked by their loss (HANDOVER §7.11).

Polar % is per second: corrected boat speed ÷ polar speed at the logged TWS and |TWA|, while the boat is
moving (corrected STW above 3 kt); a phase reports the median and quartiles. When calibration flags the
upwind TWA, upwind rows (|TWA| < 90°) use the true wind recomputed from the apparent wind and corrected
boat speed instead, and the report says so. Above the polar's top TWS row the polar is clamped and the
result marked indicative.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import race as race_mod

MOVING_KT = 3.0
UPWIND, DOWNWIND = 70.0, 120.0     # point of sail: upwind < 70° ≤ reach ≤ 120° < downwind
BUCKET_KT = 2.0


@dataclass
class PhasePerf:
    name: str
    kind: str
    n: int
    tws: float
    twa: float
    stw: float
    target: float
    pct: float
    p25: float
    p75: float
    pct_logged: float          # with the logged TWA everywhere (the acceptance table's convention)
    indicative: bool
    vmg_pct: float | None = None   # upwind phases: achieved VMG ÷ polar's best VMG


@dataclass
class Manoeuvre:
    t: float
    kind: str                  # tack | gybe
    twa_from: float
    twa_to: float
    tws: float
    stw_before: float
    stw_min: float
    loss_m: float              # distance lost to windward (tack) or leeward (gybe) against holding the entry VMG
    loss_s: float              # the same in seconds at the entry VMG
    recover_s: float | None    # until speed is back to 90 % of the entry speed
    sail: str = ""


@dataclass
class Performance:
    twa_source: str            # "logged" | "recomputed upwind"
    phases: list[PhasePerf]
    buckets: list[dict]        # {tws0, tws1, pos, n, pct, p25, p75}
    targets: list[dict]        # {tws0, tws1, side, n, stw, twa, vmg, polar_stw, polar_twa, polar_vmg}
    by_sail: list[dict]
    manoeuvres: list[Manoeuvre]
    polar_name: str
    tws_max: float
    notes: list[str] = field(default_factory=list)


def _pos(twa: np.ndarray) -> np.ndarray:
    a = np.abs(twa)
    return np.where(a < UPWIND, "upwind", np.where(a > DOWNWIND, "downwind", "reach"))


def _q(v: np.ndarray, p: float) -> float:
    return float(np.percentile(v, p)) if len(v) else float("nan")


def performance(a) -> Performance | None:
    """`a` is a RaceAnalysis with a polar."""
    P = a.polar
    if P is None:
        return None
    tl = a.tl
    t = tl.t.astype(float)
    w = a.wind
    stw = w.stw_c
    twa_log, tws_log = tl["TWA"], tl["TWS"]
    flagged = any(c.id == "twa_up" and c.status in ("warn", "fail") for c in a.checks)
    up = np.abs(twa_log) < 90
    if flagged:
        twa = np.where(up, w.twa_w, twa_log)
        tws = np.where(up, w.tws_w, tws_log)
    else:
        twa, tws = twa_log, tws_log
    target = P.target(tws, twa)
    target_log = P.target(tws_log, twa_log)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = stw / target * 100.0
        pct_log = stw / target_log * 100.0
    ok = (stw > MOVING_KT) & np.isfinite(pct) & (target > 0) & (t >= a.start) & (t <= a.finish)
    ok_log = (stw > MOVING_KT) & np.isfinite(pct_log) & (target_log > 0)
    tg = P.targets(tws)
    best_vmg_up = tg["beat_bsp"] * np.cos(np.radians(tg["beat_angle"]))
    vmg_up = stw * np.cos(np.radians(np.abs(twa)))

    phases = []
    for ph in a.phases:
        m = ok & (t >= ph.t0) & (t < ph.t1)
        ml = ok_log & (t >= ph.t0) & (t < ph.t1)
        if m.sum() < 60:
            continue
        upwind = float(np.mean(np.abs(twa[m]))) < UPWIND
        vmg = None
        if upwind:
            mv = m & (np.abs(twa) < 90) & (best_vmg_up > 0)
            if mv.sum() >= 60:
                vmg = float(np.median(vmg_up[mv] / best_vmg_up[mv] * 100))
        phases.append(PhasePerf(
            name=ph.name, kind=ph.kind, n=int(m.sum()), tws=float(np.mean(tws[m])), twa=float(np.mean(np.abs(twa[m]))),
            stw=float(np.mean(stw[m])), target=float(np.mean(target[m])), pct=float(np.median(pct[m])),
            p25=_q(pct[m], 25), p75=_q(pct[m], 75),
            pct_logged=float(np.median(pct_log[ml])) if ml.sum() else float("nan"),
            indicative=bool(np.mean(tws[m]) > P.tws_max), vmg_pct=vmg))

    # TWS bucket × point of sail
    pos = _pos(twa)
    buckets = []
    edges = np.arange(0, np.nanmax(np.where(ok, tws, 0)) + BUCKET_KT, BUCKET_KT)
    for lo in edges:
        for side in ("upwind", "reach", "downwind"):
            m = ok & (tws >= lo) & (tws < lo + BUCKET_KT) & (pos == side)
            if m.sum() < 120:
                continue
            buckets.append({"tws0": float(lo), "tws1": float(lo + BUCKET_KT), "pos": side, "n": int(m.sum()),
                            "pct": float(np.median(pct[m])), "p25": _q(pct[m], 25), "p75": _q(pct[m], 75),
                            "indicative": bool(lo + BUCKET_KT / 2 > P.tws_max)})

    # Njord-style targets: per bucket and side, the seconds in the 75th–95th percentile band of VMG
    targets = []
    steady = ok & (np.abs(np.gradient(np.unwrap(np.radians(np.nan_to_num(tl["HDG"]))))) < np.radians(2))
    for lo in edges:
        for side, sel in (("upwind", np.abs(twa) < 90), ("downwind", np.abs(twa) >= 90)):
            m = steady & sel & (tws >= lo) & (tws < lo + BUCKET_KT)
            if m.sum() < 300:
                continue
            vmg = stw * np.cos(np.radians(np.abs(twa)))
            if side == "downwind":
                vmg = -vmg
            v = vmg[m]
            band = m.copy()
            band[m] = (v >= np.percentile(v, 75)) & (v <= np.percentile(v, 95))
            mid = np.clip(lo + BUCKET_KT / 2, P.tws[0], P.tws_max)
            tg1 = P.targets(mid)
            pa = float(tg1["beat_angle"] if side == "upwind" else tg1["run_angle"])
            pb = float(tg1["beat_bsp"] if side == "upwind" else tg1["run_bsp"])
            targets.append({"tws0": float(lo), "tws1": float(lo + BUCKET_KT), "side": side, "n": int(band.sum()),
                            "stw": float(np.mean(stw[band])), "twa": float(np.mean(np.abs(twa[band]))),
                            "vmg": float(np.mean(vmg[band])), "polar_stw": pb, "polar_twa": pa,
                            "polar_vmg": float(abs(pb * np.cos(np.radians(pa)))),
                            "indicative": bool(lo + BUCKET_KT / 2 > P.tws_max)})

    # by sail (Expedition sail events)
    by_sail = []
    from .crew import sails_flown
    for s in sails_flown(a):
        m = ok & (t >= s["t0"]) & (t < s["t1"])
        if m.sum() < 120:
            continue
        by_sail.append({"sail": s["sail"], "t0": s["t0"], "t1": s["t1"], "n": int(m.sum()), "tws": float(np.mean(tws[m])),
                        "twa": float(np.mean(np.abs(twa[m]))), "pct": float(np.median(pct[m])),
                        "p25": _q(pct[m], 25), "p75": _q(pct[m], 75)})
    agg: dict[str, list] = {}
    for s in by_sail:
        agg.setdefault(s["sail"], []).append(s)

    notes = []
    if flagged:
        notes.append("Calibration flags the logged upwind TWA, so upwind seconds use the true wind recomputed from the "
                     "apparent wind and corrected boat speed; the “logged TWA” column shows the uncorrected figure.")
    if (tws[ok] > P.tws_max).any():
        notes.append(f"The polar stops at {P.tws_max:.0f} kt; above it the polar is clamped and results are indicative.")
    return Performance(twa_source="recomputed upwind" if flagged else "logged", phases=phases, buckets=buckets,
                       targets=targets, by_sail=by_sail, manoeuvres=manoeuvres(a, twa, tws, stw),
                       polar_name=P.name, tws_max=P.tws_max, notes=notes)


def manoeuvres(a, twa: np.ndarray, tws: np.ndarray, stw: np.ndarray) -> list[Manoeuvre]:
    """Tacks and gybes: the sign of a 10 s mean TWA flips and holds for 30 s on each side. Loss is the distance
    along the wind axis given up from 15 s before the flip to 45 s after it, against holding the VMG of the
    30 s before (15–45 s before the flip)."""
    t = a.tl.t.astype(float)
    sm = race_mod.rolling_mean(np.nan_to_num(twa), 10)
    sgn = np.sign(sm)
    out: list[Manoeuvre] = []
    i = int(np.searchsorted(t, a.start + 60))
    end = int(np.searchsorted(t, a.finish - 60))
    from .crew import sails_flown
    sails = sails_flown(a)
    while i < end:
        if sgn[i] != 0 and sgn[i - 1] != 0 and sgn[i] != sgn[i - 1]:
            b0, a1 = max(i - 30, 0), min(i + 30, len(t) - 1)
            if (sgn[b0:i] == sgn[i - 1]).all() and (sgn[i:a1] == sgn[i]).all() and stw[i - 20] > MOVING_KT:
                tw0, tw1 = float(np.nanmean(twa[i - 45:i - 15])), float(np.nanmean(twa[i + 15:i + 45]))
                if abs(tw0) < 90 and abs(tw1) < 90:
                    kind, sgn_vmg = "tack", 1.0
                elif abs(tw0) > 90 and abs(tw1) > 90:
                    kind, sgn_vmg = "gybe", -1.0
                else:
                    i += 1
                    continue
                vmg = sgn_vmg * stw * np.cos(np.radians(np.abs(twa)))
                v0 = float(np.nanmean(vmg[i - 45:i - 15]))
                seg = vmg[i - 15:i + 45]
                if v0 > 0.5 and np.isfinite(seg).sum() > 50:
                    loss = (v0 * 60 - float(np.nansum(seg))) * 1852 / 3600   # kt·s -> m
                    s0 = float(np.nanmean(stw[i - 45:i - 15]))
                    after = stw[i:i + 180]
                    rec = np.flatnonzero(after >= 0.9 * s0)
                    sail = next((s["sail"] for s in sails if s["t0"] <= t[i] < s["t1"]), "")
                    out.append(Manoeuvre(t=float(t[i]), kind=kind, twa_from=tw0, twa_to=tw1,
                                         tws=float(np.nanmean(tws[i - 30:i + 30])), stw_before=s0,
                                         stw_min=float(np.nanmin(stw[i - 15:i + 45])), loss_m=float(loss),
                                         loss_s=float(loss / (v0 * 1852 / 3600)),
                                         recover_s=float(rec[0]) if len(rec) else None, sail=sail))
                i += 60
                continue
        i += 1
    return sorted(out, key=lambda m: -m.loss_m)
