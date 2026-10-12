"""Instrument calibration checks (HANDOVER §7.2, ACCEPTANCE M1). Each check returns a status
(ok / warn / fail / info), a value, a plain explanation and what to do about it.

The boat-speed check fits SOG⃗ = a·BSP·ĥ + c⃗ as complex least squares on steady rows (a = k·e^{iδ}): k is
the boat-speed factor, δ the heading offset and c the mean current. Directions use the compass convention
(real axis north, imaginary east), so arguments are bearings.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core import geo, truewind
from ..ingest.expedition_log import Log, Timeline

EXPECTED_CHANNELS = ("BSP", "AWA", "AWS", "HDG", "SOG", "COG", "Lat", "Lon", "TWS", "TWA", "TWD")
RECOMMENDED = {"Baro": "pressure is the best marker of a front or southerly change",
               "AirTemp": "a temperature drop confirms a change has passed"}


@dataclass
class Check:
    id: str
    title: str
    status: str
    value: str
    detail: str
    suggestion: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class SpeedFit:
    k: float
    delta: float
    current_kt: float
    current_set: float
    n: int


def steady(tl: Timeline, min_kt: float = 2.0, max_dhdg: float = 5.0) -> np.ndarray:
    """Rows sailing steadily: boat speed and SOG over `min_kt`, heading within `max_dhdg` over ±5 s."""
    hdg = tl["HDG"]
    dh = np.abs(geo.angdiff(np.roll(hdg, -5), np.roll(hdg, 5)))
    dh[:5] = np.nan
    dh[-5:] = np.nan
    ok = np.isfinite(tl["BSP"]) & np.isfinite(tl["SOG"]) & np.isfinite(hdg) & np.isfinite(tl["COG"])
    return ok & (tl["BSP"] > min_kt) & (tl["SOG"] > min_kt) & (np.nan_to_num(dh, nan=99) < max_dhdg)


def fit_speed(tl: Timeline, mask: np.ndarray) -> SpeedFit | None:
    if mask.sum() < 60:
        return None
    zs = tl["SOG"][mask] * np.exp(1j * np.radians(tl["COG"][mask]))
    zb = tl["BSP"][mask] * np.exp(1j * np.radians(tl["HDG"][mask]))
    (a, c), *_ = np.linalg.lstsq(np.c_[zb, np.ones_like(zb)], zs, rcond=None)
    return SpeedFit(k=float(abs(a)), delta=float(np.degrees(np.angle(a))), current_kt=float(abs(c)),
                    current_set=float(np.degrees(np.angle(c)) % 360), n=int(mask.sum()))


def direction_ratios(tl: Timeline, mask: np.ndarray) -> dict:
    out = {}
    for name, centre in (("southbound", 200.0), ("northbound", 20.0)):
        m = mask & (np.abs(geo.angdiff(tl["COG"], centre)) < 45)
        if m.sum() > 60:
            out[name] = float(np.mean(tl["SOG"][m]) / np.mean(tl["BSP"][m]))
    return out


def twa_compare(tl: Timeline, mask: np.ndarray, k: float) -> dict:
    """Logged vs recomputed (corrected boat speed) |TWA| and TWS on the masked rows."""
    tws_r, twa_r, _ = truewind.water(tl["AWS"], tl["AWA"], tl["BSP"] * k, tl["HDG"])
    m = mask & np.isfinite(tl["TWA"]) & np.isfinite(twa_r)
    if m.sum() < 60:
        return {}
    return {"n": int(m.sum()), "awa": float(np.median(np.abs(tl["AWA"][m]))),
            "twa_logged": float(np.median(np.abs(tl["TWA"][m]))), "twa_recomputed": float(np.median(np.abs(twa_r[m]))),
            "tws_logged": float(np.mean(tl["TWS"][m])), "tws_recomputed": float(np.mean(tws_r[m]))}


def sustained(mask: np.ndarray, min_s: int = 300, max_gap: int = 30) -> np.ndarray:
    """Only the parts of `mask` that last at least `min_s` seconds. Gaps of up to `max_gap` s (a tack, a wave)
    do not break a run, but the gap rows themselves stay excluded."""
    n = len(mask)
    filled = mask.copy()
    i = 0
    while i < n:  # bridge short gaps between True runs
        if mask[i]:
            i += 1
            continue
        j = i
        while j < n and not mask[j]:
            j += 1
        if i > 0 and j < n and j - i <= max_gap:
            filled[i:j] = True
        i = j
    out = np.zeros(n, dtype=bool)
    i = 0
    while i < n:  # keep runs that are long enough
        if not filled[i]:
            i += 1
            continue
        j = i
        while j < n and filled[j]:
            j += 1
        if j - i >= min_s:
            out[i:j] = True
        i = j
    return out & mask


def duplicate_groups(tl: Timeline, min_cover: float = 0.05, tol_mismatch: float = 0.01) -> list[list[str]]:
    """Channels carrying the same signal (equal on at least 99 % of the samples both have)."""
    n = len(tl)
    names = [c for c, v in tl.ch.items() if np.isfinite(v).sum() >= min_cover * n and np.nanstd(v) > 1e-9]
    groups: list[list[str]] = []
    used = set()
    for i, a in enumerate(names):
        if a in used:
            continue
        va = tl.ch[a]
        g = [a]
        for b in names[i + 1:]:
            if b in used:
                continue
            vb = tl.ch[b]
            both = np.isfinite(va) & np.isfinite(vb)
            if both.sum() < 0.9 * min(np.isfinite(va).sum(), np.isfinite(vb).sum()):
                continue
            if np.mean(np.abs(va[both] - vb[both]) > 1e-9) <= tol_mismatch:
                g.append(b)
        if len(g) > 1:
            used.update(g)
            groups.append(sorted(g))
    return groups


def run_checks(log: Log, tl: Timeline, k_override: float | None = None) -> tuple[list[Check], SpeedFit | None, float]:
    """All checks on the race window. Returns (checks, the speed fit, the boat-speed factor to use)."""
    checks: list[Check] = []
    mask = steady(tl)
    fit = fit_speed(tl, mask)
    k = k_override if k_override else (fit.k if fit else 1.0)
    if fit:
        err = fit.k - 1.0
        status = "fail" if abs(err) > 0.05 else "warn" if abs(err) > 0.02 else "ok"
        word = "low" if err > 0 else "high"
        checks.append(Check(
            "speed", "Boat speed", status, f"× {fit.k:.3f}",
            f"Over the ground the boat went {abs(err) * 100:.0f} % {'faster' if err > 0 else 'slower'} than the log "
            f"says, after allowing for {fit.current_kt:.2f} kt of current setting {fit.current_set:.0f}° T "
            f"({fit.n:,} steady seconds). The paddlewheel reads {abs(err) * 100:.0f} % {word}.",
            f"Calibrate boat speed by × {fit.k:.2f} in the instrument system before the next race. "
            + ("This report uses the corrected speed." if status != "ok" else ""),
            {"k": fit.k, "delta": fit.delta, "current_kt": fit.current_kt, "current_set": fit.current_set, "n": fit.n}))
        checks.append(Check(
            "heading", "Heading", "warn" if abs(fit.delta) > 3 else "ok", f"{fit.delta:+.1f}°",
            "The fit between heading and course over the ground leaves an offset of "
            f"{fit.delta:+.1f}°: heading is {'true and well aligned' if abs(fit.delta) <= 3 else 'off'}.",
            "" if abs(fit.delta) <= 3 else "Check the compass deviation and the magnetic variation setting."))
        ratios = direction_ratios(tl, mask)
        if ratios:
            checks.append(Check(
                "current", "Current (mean)", "info", f"{fit.current_kt:.2f} kt → {fit.current_set:.0f}° T",
                "SOG ÷ boat speed: " + ", ".join(f"{v:.2f} {way}" for way, v in ratios.items())
                + ". The difference between directions is the current; what is common to both is the speed error.",
                data=ratios))
    # upwind and downwind TWA, logged vs recomputed
    # upwind / downwind = at least five minutes on that point of sail (all moving rows: the steadiness filter
    # matters for the speed fit, not for comparing wind angles, and it would drop most of a beat in waves)
    awa = np.nan_to_num(np.abs(tl["AWA"]), nan=90.0)
    moving = (np.nan_to_num(tl["BSP"], nan=0.0) > 2) & (np.nan_to_num(tl["SOG"], nan=0.0) > 2)
    up = sustained(moving & (awa < 40), 300)
    down = sustained(moving & (awa > 120), 300)
    for cid, title, m in (("twa_up", "True wind angle upwind", up), ("twa_down", "True wind angle downwind", down)):
        c = twa_compare(tl, m, k)
        if not c:
            continue
        diff = c["twa_logged"] - c["twa_recomputed"]
        bad = abs(diff) > 5
        checks.append(Check(
            cid, title, "warn" if bad else "ok", f"{c['twa_logged']:.0f}° logged · {c['twa_recomputed']:.0f}° recomputed",
            f"Median over {c['n'] // 60} min: the instruments show {c['twa_logged']:.0f}°, true wind recomputed from "
            f"the apparent wind with corrected boat speed gives {c['twa_recomputed']:.0f}° "
            f"(TWS {c['tws_logged']:.1f} vs {c['tws_recomputed']:.1f} kt)."
            + (f" The logged TWA reads about {abs(diff):.0f}° {'wide' if diff > 0 else 'narrow'}." if bad else ""),
            "The instrument system computes true wind from the uncalibrated boat speed: fix boat speed first, then "
            "re-check true wind angle on both tacks. This report uses the recomputed true wind." if bad else "",
            c))
    # apparent wind symmetry upwind
    if up.sum() > 600:
        a = tl["AWA"]
        port, stbd = up & (a < 0), up & (a > 0)
        if port.sum() > 120 and stbd.sum() > 120:
            p, s = float(np.median(-a[port])), float(np.median(a[stbd]))
            checks.append(Check("awa_sym", "Apparent wind, port vs starboard", "warn" if abs(p - s) > 3 else "ok",
                                f"{p:.0f}° port · {s:.0f}° stbd",
                                "Upwind the median apparent wind angle should match on both tacks."
                                + (f" It differs by {abs(p - s):.0f}°: the masthead unit may be misaligned." if abs(p - s) > 3 else ""),
                                "Align the wind vane (AWA offset) by half the difference." if abs(p - s) > 3 else "",
                                {"port": p, "stbd": s}))
    # channel health
    groups = duplicate_groups(tl)
    if groups:
        checks.append(Check(
            "channels", "Instrument channels", "warn", f"{len(groups)} duplicated group(s)",
            "These channels carry exactly the same signal, so most are mapped to the wrong source: "
            + "; ".join(" = ".join(g) for g in groups) + ".",
            "Check the channel mapping in Expedition (Instruments): each channel should come from its own sensor. "
            "Day After uses only the first channel of each group.", {"groups": groups}))
    n = len(tl)
    const = sorted(c for c, v in tl.ch.items() if np.isfinite(v).sum() >= 0.05 * n and np.nanstd(v) < 1e-9)
    if const:
        checks.append(Check("constant", "Constant channels", "info", ", ".join(const),
                            "These channels never changed during the race.", data={"channels": const}))
    missing_core = [c for c in EXPECTED_CHANNELS if not log.has(c)]
    missing_rec = [c for c in RECOMMENDED if not log.has(c)]
    if missing_core or missing_rec:
        checks.append(Check(
            "missing", "Channels not logged", "fail" if missing_core else "warn", ", ".join(missing_core + missing_rec),
            " ".join(f"{c}: {why}." for c, why in RECOMMENDED.items() if c in missing_rec)
            + (f" Core channels missing: {', '.join(missing_core)}." if missing_core else ""),
            "Turn on " + " and ".join(missing_rec + missing_core) + " in Expedition's log settings."))
    return checks, fit, k
