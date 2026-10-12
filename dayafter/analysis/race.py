"""Our boat's race from the 1 Hz timeline: gun, start crossing, mark passages, finish, holes, the observed
wind change and the phases (HANDOVER §7, ACCEPTANCE M1).

Definitions (validated on Flinders 2026):
- Start: first crossing of the pinged start line towards the course side at or after the gun.
- Mark passage: the first local minimum of distance to each mark in course order, once the boat has come
  within reach and moved away again by a small hysteresis (out-and-back courses pass marks twice).
- Official finish: gun + corrected ÷ TCC. The finish point passage is kept for the last phase.
- Hole: 30 s mean SOG below 3 kt for at least 10 min.
- Observed change: the largest sustained shift in 10-min means of the wind over the ground, refined at
  15 s to its *onset* (the old breeze collapsing into the lull) and its *shift* (the new direction settling).
- Phase statistics: distance from 1 Hz GPS positions; speed = distance / time; corrected STW = BSP × k;
  logged TWS (mean, 95th percentile) and TWD (circular mean).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np

from ..core import geo, timeutil, truewind
from ..ingest.course import Course, Mark
from ..ingest.expedition_log import Log, Timeline
from . import weather

HOLE_KT = 3.0
HOLE_MIN_S = 600
HOLE_SMOOTH_S = 30


# ---------------------------------------------------------------------------------------------- gun and start

def tmtogun_zero(log: Log) -> float | None:
    """When Expedition's countdown (TmToGun) reached zero, if it was running."""
    if not log.has("TmToGun"):
        return None
    t, v = log.samples["TmToGun"]
    for i in range(1, len(v)):
        if v[i - 1] > 0 >= v[i]:
            f = v[i - 1] / (v[i - 1] - v[i]) if v[i - 1] != v[i] else 1.0
            return float(round(t[i - 1] + f * (t[i] - t[i - 1])))
    k = int(np.argmin(np.abs(v)))
    return float(round(t[k])) if abs(v[k]) < 1e-3 else None


def pick_gun(gun_local: str | None, tz: str, gun_events: list[float], countdown: float | None,
             route_start: float | None, yb_gun: float | None) -> tuple[float, str, list[str]]:
    """The gun, best source first: race file; Expedition's Gun event nearest the countdown (or the routings'
    start, or YB); the countdown; the routings' start; YB's setup start (unreliable: 3 h early for Tollgate)."""
    notes: list[str] = []
    if gun_local:
        return timeutil.local_to_epoch(dt.datetime.fromisoformat(gun_local), tz), "race file", notes
    ref = countdown or route_start or yb_gun
    if gun_events:
        if ref is not None:
            g = min(gun_events, key=lambda t: abs(t - ref))
            if abs(g - ref) <= 900:
                if len(gun_events) > 1:
                    notes.append(f"{len(gun_events) - 1} other Gun event(s) in Expedition ignored")
                return g, "Expedition Gun event", notes
        elif len(gun_events) == 1:
            return gun_events[0], "Expedition Gun event", notes
    if countdown is not None:
        return countdown, "Expedition countdown (TmToGun)", notes
    if route_start is not None:
        return route_start, "route tables (common start)", notes
    if yb_gun is not None:
        notes.append("gun taken from YB's race setup, which is not always right; set gun_local in race.dayafter.json")
        return yb_gun, "YB race setup", notes
    raise ValueError("no gun time: set race.gun_local in race.dayafter.json")


def start_line(log: Log, gun: float) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """(port end, starboard end) from the last line pings logged before the gun."""
    ends = []
    for la, lo in (("Port lat", "Port lon"), ("Stbd lat", "Stbd lon")):
        if not (log.has(la) and log.has(lo)):
            return None
        t1, v1 = log.samples[la]
        t2, v2 = log.samples[lo]
        k1, k2 = np.flatnonzero(t1 <= gun), np.flatnonzero(t2 <= gun)
        if not len(k1) or not len(k2):
            return None
        ends.append((float(v1[k1[-1]]), float(v2[k2[-1]])))
    return ends[0], ends[1]


def start_crossing(tl: Timeline, line, toward: Mark, gun: float, slack: float = 0.25) -> float | None:
    """First crossing of the line towards the course side (the side `toward` lies on) at or after the gun."""
    (pla, plo), (sla, slo) = line
    xy = geo.LocalXY(pla, plo)
    px, py = 0.0, 0.0
    sx, sy = xy.xy(sla, slo)
    bx, by = xy.xy(tl["Lat"], tl["Lon"])
    mx, my = xy.xy(toward.lat, toward.lon)
    side = np.sign(sx * my - sy * mx)
    cross = (sx * by - sy * bx) * side
    L2 = sx * sx + sy * sy
    t = tl.t.astype(float)
    for i in range(1, len(t)):
        if t[i] < gun or not (np.isfinite(cross[i - 1]) and np.isfinite(cross[i])):
            continue
        if cross[i - 1] < 0 <= cross[i]:
            f = cross[i - 1] / (cross[i - 1] - cross[i])
            qx, qy = bx[i - 1] + f * (bx[i] - bx[i - 1]), by[i - 1] + f * (by[i] - by[i - 1])
            u = (qx * sx + qy * sy) / L2
            if -slack <= u <= 1 + slack:
                return float(t[i - 1] + f)
    return None


# ---------------------------------------------------------------------------------------------- marks

@dataclass
class Passage:
    index: int
    name: str
    role: str
    t: float | None
    dist_nm: float | None
    lat: float
    lon: float


def mark_passages(tl: Timeline, course: Course, t_from: float, radius_nm: float = 2.0) -> list[Passage]:
    """Passage time of every course mark after the start, in course order (closest approach)."""
    lat, lon, t = tl["Lat"], tl["Lon"], tl.t.astype(float)
    out = []
    tp = t_from
    ms = course.marks
    for k in range(1, len(ms)):
        m = ms[k]
        d = geo.haversine_nm(lat, lon, m.lat, m.lon)
        nxt = ms[k + 1] if k + 1 < len(ms) else None
        prv = ms[k - 1]
        leg_next = float(geo.haversine_nm(m.lat, m.lon, nxt.lat, nxt.lon)) if nxt else 1e9
        leg_prev = float(geo.haversine_nm(m.lat, m.lon, prv.lat, prv.lon))
        hyst = max(0.03, min(0.3, 0.4 * leg_next))
        reach = max(radius_nm, 0.15 * min(leg_prev, leg_next if nxt else leg_prev))
        best = None
        for i in range(max(0, int(tp - t[0])), len(t)):
            if not np.isfinite(d[i]):
                continue
            if best is None or d[i] < d[best]:
                best = i
            elif d[best] < reach and d[i] > d[best] + hyst:
                break
        if best is None or d[best] > reach:
            out.append(Passage(k, m.name, m.role, None, None if best is None else float(d[best]), m.lat, m.lon))
            continue
        tp = float(t[best])
        out.append(Passage(k, m.name, m.role, tp, float(d[best]), m.lat, m.lon))
    return out


# ---------------------------------------------------------------------------------------------- holes and wind

def runs(mask: np.ndarray, t: np.ndarray, min_s: float) -> list[tuple[float, float]]:
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if t[j - 1] - t[i] >= min_s - 1:
                out.append((float(t[i]), float(t[j - 1])))
            i = j
        else:
            i += 1
    return out


def rolling_mean(v: np.ndarray, width_s: int) -> np.ndarray:
    """Centred rolling mean ignoring NaN (1 Hz input)."""
    k = max(1, width_s // 2)
    ok = np.isfinite(v)
    c = np.cumsum(np.r_[0.0, np.where(ok, v, 0.0)])
    n = np.cumsum(np.r_[0, ok.astype(int)])
    i = np.arange(len(v))
    lo, hi = np.clip(i - k, 0, len(v)), np.clip(i + k + 1, 0, len(v))
    cnt = n[hi] - n[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cnt > 0, (c[hi] - c[lo]) / np.maximum(cnt, 1), np.nan)


def holes(tl: Timeline, t0: float, t1: float, kt: float = HOLE_KT, min_s: int = HOLE_MIN_S,
          smooth_s: int = HOLE_SMOOTH_S) -> list[tuple[float, float]]:
    w = tl.window(t0, t1)
    sog = rolling_mean(w["SOG"], smooth_s)
    return runs(np.nan_to_num(sog, nan=99.0) < kt, w.t.astype(float), min_s)


def binned_wind(t: np.ndarray, tws: np.ndarray, twd: np.ndarray, t0: float, t1: float, step: float = 600.0):
    """Means over [t0, t1] in `step` bins, labelled at bin centres; direction weighted by speed."""
    edges = np.arange(t0, t1, step)
    ct, ws, wd = [], [], []
    for a in edges:
        m = (t >= a) & (t < a + step) & np.isfinite(tws) & np.isfinite(twd)
        if m.sum() < 0.3 * step:
            continue
        ct.append(a + step / 2)
        ws.append(float(np.mean(tws[m])))
        wd.append(geo.circmean(twd[m], tws[m]))
    return np.array(ct), np.array(ws), np.array(wd)


@dataclass
class ObservedChange:
    change: weather.Change
    onset: float      # the old breeze collapses (start of the lull), or the shift if there is no lull
    shift: float      # the new direction settles

    @property
    def t(self) -> float:
        return self.onset


def observed_change(t: np.ndarray, tws: np.ndarray, twd: np.ndarray, t0: float, t1: float) -> ObservedChange | None:
    ct, ws, wd = binned_wind(t, tws, twd, t0, t1)
    ch = weather.detect_change(ct, wd, ws)
    if ch is None:
        return None
    # refine at 15 s around the coarse swing
    a, b = ch.t_from - 900, ch.t_to + 900
    ft, fs, fd = binned_wind(t, tws, twd, max(t0, a), min(t1, b), step=15.0)
    shift = ch.t
    closer_new = np.abs(geo.angdiff(fd, ch.twd_to)) < np.abs(geo.angdiff(fd, ch.twd_from))
    hold = 8  # two minutes of 15 s bins
    for i in range(len(ft)):
        if closer_new[i:i + hold].all() and len(closer_new[i:i + hold]) == hold:
            shift = float(ft[i] - 7.5)
            break
    onset = shift
    lull = fs < 0.75 * ch.tws_before
    k = int(np.searchsorted(ft, shift))
    j = k - 1
    while j >= 0 and lull[j] and ft[j] >= shift - 600:
        j -= 1
    if j < k - 1:
        onset = float(ft[j + 1] - 7.5)
    ch.t = onset
    return ObservedChange(change=ch, onset=onset, shift=shift)


# ---------------------------------------------------------------------------------------------- phases

@dataclass
class Phase:
    name: str
    kind: str          # leg | hole
    t0: float
    t1: float
    minutes: float
    dist_nm: float
    sog: float
    stw_c: float
    tws: float
    tws_p95: float
    twd: float


def track_length_nm(lat: np.ndarray, lon: np.ndarray) -> float:
    ok = np.isfinite(lat) & np.isfinite(lon)
    la, lo = lat[ok], lon[ok]
    if len(la) < 2:
        return 0.0
    return float(np.sum(geo.haversine_nm(la[:-1], lo[:-1], la[1:], lo[1:])))


def phase_stats(tl: Timeline, name: str, kind: str, t0: float, t1: float, k: float) -> Phase:
    w = tl.window(t0, t1)
    dist = track_length_nm(w["Lat"], w["Lon"])
    minutes = (t1 - t0) / 60.0
    tws = w["TWS"]
    has_tws = np.isfinite(tws).any()
    return Phase(name=name, kind=kind, t0=t0, t1=t1, minutes=minutes, dist_nm=dist,
                 sog=dist / (minutes / 60.0) if minutes > 0 else float("nan"),
                 stw_c=float(np.nanmean(w["BSP"] * k)) if np.isfinite(w["BSP"]).any() else float("nan"),
                 tws=float(np.nanmean(tws)) if has_tws else float("nan"),
                 tws_p95=float(np.nanpercentile(tws, 95)) if has_tws else float("nan"),
                 twd=geo.circmean(w["TWD"]))


def default_phase_marks(course: Course) -> list[str]:
    """Without a list in the race file: the turning mark and course corners (bearing change of 60° or more)."""
    ms = course.marks
    out = []
    tm = course.turning_mark
    for i in range(1, len(ms) - 1):
        a = geo.bearing_deg(ms[i - 1].lat, ms[i - 1].lon, ms[i].lat, ms[i].lon)
        b = geo.bearing_deg(ms[i].lat, ms[i].lon, ms[i + 1].lat, ms[i + 1].lon)
        corner = abs(float(geo.angdiff(b, a))) >= 60
        near_turn = tm is not None and ms[i] is not tm and float(geo.haversine_nm(ms[i].lat, ms[i].lon, tm.lat, tm.lon)) < 1
        if ms[i] is tm or (corner and not near_turn):
            out.append(ms[i].name)
    return out


def phases(tl: Timeline, start: float, passages: list[Passage], phase_marks: list[str], change: float | None,
           hole_list: list[tuple[float, float]], k: float, labels: dict[str, str] | None = None,
           end_name: str = "finish point") -> list[Phase]:
    """Legs between the start, the phase marks and the finish point, split at the change; holes added as
    their own (overlapping) rows."""
    labels = labels or {}
    label = lambda n: labels.get(n, n)
    wanted = {n.strip().lower() for n in phase_marks}
    cuts = [(start, "Start")]
    for p in passages:
        if p.t is not None and (p.name.lower() in wanted) and p.role != "finish":
            cuts.append((p.t, label(p.name)))
    end = next((p for p in reversed(passages) if p.role == "finish" and p.t is not None), None)
    end_t = end.t if end is not None else max(pp.t for pp in passages if pp.t is not None)
    cuts.append((end_t, end_name))
    if change is not None and cuts[0][0] < change < cuts[-1][0]:
        cuts.append((change, "the change"))
    cuts.sort()
    out = [phase_stats(tl, f"{a[1]} → {b[1]}", "leg", a[0], b[0], k) for a, b in zip(cuts, cuts[1:])]
    for i, (h0, h1) in enumerate(hole_list):
        near = min(cuts, key=lambda c: abs(c[0] - (h0 + h1) / 2))[1]
        out.append(phase_stats(tl, f"Hole near {near}" if near not in ("Start", end_name) else "Hole", "hole", h0, h1, k))
    out.sort(key=lambda p: (p.t0, p.kind != "leg"))
    return out


# ---------------------------------------------------------------------------------------------- derived wind

@dataclass
class Wind:
    """True wind recomputed from the apparent wind: through the water with corrected boat speed, and over the
    ground (what forecasts predict)."""
    tws_w: np.ndarray
    twa_w: np.ndarray
    twd_w: np.ndarray
    tws_g: np.ndarray
    twd_g: np.ndarray
    stw_c: np.ndarray
    k: float
    meta: dict = field(default_factory=dict)


def derive_wind(tl: Timeline, k: float) -> Wind:
    stw = tl["BSP"] * k
    tws_w, twa_w, twd_w = truewind.water(tl["AWS"], tl["AWA"], stw, tl["HDG"])
    tws_g, twd_g = truewind.ground(tl["AWS"], tl["AWA"], tl["SOG"], tl["COG"], tl["HDG"])
    return Wind(tws_w=tws_w, twa_w=twa_w, twd_w=twd_w, tws_g=tws_g, twd_g=twd_g, stw_c=stw, k=k)
