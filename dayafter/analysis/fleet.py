"""Fleet comparison from YB tracks and the official results (HANDOVER §7.4–7.7, ACCEPTANCE M2).

- Progress along the course: constrained map-matching of each fix to the course polyline (see `progress`);
  it never goes backwards and cannot pass the turning mark before the rounding.
- Gates every N nm plus the turning mark and the finish; the finish gate is the official finish.
- Corrected gap at a gate = elapsed × TCC (boat) − elapsed × TCC (us); negative means the boat is ahead.
- Rounding effect: rounding time against the corrected time from the rounding to the finish (Pearson r).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

import numpy as np

from ..core import geo
from ..ingest.course import Course
from ..ingest.results import Result, norm_name


@dataclass
class Boat:
    name: str
    yb_id: int | None
    result: Result
    t: np.ndarray            # fixes (epoch s) inside the race window
    lat: np.ndarray
    lon: np.ndarray
    s: np.ndarray            # progress along the course, nm
    gates: np.ndarray        # elapsed seconds at each gate (NaN if not reached)
    rounding: float | None   # elapsed seconds at the turning mark
    source: str = "YB"
    yb_finish: float | None = None   # YB's finish (elapsed s), for the warning only

    @property
    def tcc(self) -> float:
        return float(self.result.tcc)

    @property
    def elapsed(self) -> float | None:
        return self.result.elapsed


@dataclass
class Fleet:
    gates: np.ndarray                 # gate distances, nm
    gate_labels: list[str]
    course_nm: float
    turning_nm: float | None
    boats: list[Boat]
    us: Boat | None
    rivals: list[str]
    gaps: dict[str, np.ndarray]       # boat -> corrected gap to us at each gate (s)
    ranks: dict[str, np.ndarray]      # boat -> corrected rank at each gate
    rounding_r: float | None
    warnings: list[str] = field(default_factory=list)

    def boat(self, name: str) -> Boat | None:
        key = norm_name(name)
        return next((b for b in self.boats if norm_name(b.name) == key), None)


# ---------------------------------------------------------------------------------------------- names

def match_names(yb_names: dict[int, str], results: list[Result], cutoff: float = 0.75) -> dict[int, Result]:
    """YB id -> result: exact match on normalised names, else difflib (spares and virtual trackers drop out)."""
    by_norm = {norm_name(r.yacht): r for r in results}
    out: dict[int, Result] = {}
    taken: set[str] = set()
    for i, n in yb_names.items():
        k = norm_name(n)
        if k in by_norm:
            out[i] = by_norm[k]
            taken.add(k)
    for i, n in yb_names.items():
        if i in out:
            continue
        left = [k for k in by_norm if k not in taken]
        hit = difflib.get_close_matches(norm_name(n), left, n=1, cutoff=cutoff)
        if hit:
            out[i] = by_norm[hit[0]]
            taken.add(hit[0])
    return out


# ---------------------------------------------------------------------------------------------- progress

def course_geometry(course: Course):
    lat0, lon0 = float(np.mean(course.lat)), float(np.mean(course.lon))
    xy = geo.LocalXY(lat0, lon0)
    x, y = xy.xy(course.lat, course.lon)
    seg = np.hypot(np.diff(x), np.diff(y))
    cum = np.r_[0.0, np.cumsum(seg)]
    return xy, x, y, cum


def rounding_time(t: np.ndarray, lat: np.ndarray, lon: np.ndarray, mark) -> float | None:
    """Time of the closest approach to the turning mark (it is passed only once)."""
    d = geo.haversine_nm(lat, lon, mark.lat, mark.lon)
    if not np.isfinite(d).any():
        return None
    k = int(np.nanargmin(d))
    return float(t[k]) if d[k] < 5.0 else None


def progress(t: np.ndarray, lat: np.ndarray, lon: np.ndarray, course: Course, geom=None, turn_t: float | None = None,
             turn_index: int | None = None, vmax_kt: float = 30.0, back_nm: float = 0.5) -> np.ndarray:
    """Along-course distance of every fix (nm), never decreasing.

    Each leg owns the region between the angle bisectors at its two ends, and progress on a leg is the projection
    onto it. A boat sailing wide outside a corner therefore keeps advancing (projecting onto the nearest point of the
    polyline would stall at the corner vertex). The state only moves forward, at most as far as `vmax_kt` allows
    since the previous fix, and never past the turning mark before the boat's closest approach to it: that keeps
    the outbound and return legs of an out-and-back course apart."""
    xy, cx, cy, cum = geom or course_geometry(course)
    nl = len(cx) - 1
    ax_, ay_ = np.diff(cx), np.diff(cy)
    ln = np.hypot(ax_, ay_)
    ux = np.divide(ax_, ln, out=np.zeros_like(ax_), where=ln > 0)
    uy = np.divide(ay_, ln, out=np.zeros_like(ay_), where=ln > 0)
    nx, ny = np.zeros(nl + 1), np.zeros(nl + 1)          # bisector normals at the inner vertices
    for v in range(1, nl):
        bx, by = ux[v - 1] + ux[v], uy[v - 1] + uy[v]
        nb = np.hypot(bx, by)
        nx[v], ny[v] = (bx / nb, by / nb) if nb > 1e-9 else (ux[v], uy[v])
    last_leg = nl - 1 if turn_index is None else max(0, turn_index - 1)  # legs allowed before the rounding
    fx, fy = xy.xy(lat, lon)

    def past(v, px, py):
        return (px - cx[v]) * nx[v] + (py - cy[v]) * ny[v] >= 0

    def along(j, px, py):
        return cum[j] + float(np.clip((px - cx[j]) * ux[j] + (py - cy[j]) * uy[j], 0.0, ln[j]))

    s = np.zeros(len(t))
    cur, prev, prev_t = 0, 0.0, None
    s_turn = cum[turn_index] if turn_index is not None else None
    for i in range(len(t)):
        px, py = fx[i], fy[i]
        if not (np.isfinite(px) and np.isfinite(py)):
            s[i] = prev
            continue
        limit = np.inf if prev_t is None else prev + vmax_kt * (t[i] - prev_t) / 3600.0 + back_nm
        known = s_turn is not None and turn_t is not None  # no rounding found: no turning constraint at all
        rounded = known and t[i] >= turn_t
        if rounded and cur < turn_index:
            # the closest approach to the turning mark: by definition the boat is at the mark on this fix, and on
            # the return legs from here (on an out-and-back course it never crosses the rounding marks' bisectors)
            cur, prev, prev_t = min(turn_index, nl - 1), max(prev, s_turn), t[i]
            s[i] = prev
            continue
        if known and not rounded:
            limit = min(limit, s_turn - 0.01)  # abeam of the turning mark is not round it
        top = min(nl - 1, last_leg) if known and not rounded else nl - 1
        j = cur
        while j < top and past(j + 1, px, py) and cum[j + 1] <= limit:
            j += 1
        cur = j
        prev = max(prev, min(along(j, px, py), limit))
        prev_t = t[i]
        s[i] = prev
    return s


def gate_times(t: np.ndarray, s: np.ndarray, gates: np.ndarray, gun: float, finish_elapsed: float | None,
               course_nm: float) -> np.ndarray:
    """Elapsed seconds when progress first reaches each gate (linear between fixes); the last gate is the finish."""
    out = np.full(len(gates), np.nan)
    for g_i, g in enumerate(gates):
        if g >= course_nm - 1e-6:
            out[g_i] = finish_elapsed if finish_elapsed is not None else np.nan
            continue
        j = np.flatnonzero(s >= g - 1e-9)
        if not len(j):
            continue
        j = int(j[0])
        if j == 0:
            out[g_i] = t[0] - gun
            continue
        f = (g - s[j - 1]) / (s[j] - s[j - 1]) if s[j] > s[j - 1] else 1.0
        out[g_i] = t[j - 1] + f * (t[j] - t[j - 1]) - gun
    return out


def default_rivals(us: Result, results: list[Result], n: int = 3) -> list[str]:
    """Same division, nearest TCC, finishers only."""
    pool = [r for r in results if r.finished and r.tcc and r.yacht != us.yacht and r.division == us.division]
    return [r.yacht for r in sorted(pool, key=lambda r: abs(r.tcc - us.tcc))[:n]]


def analyse_fleet(course: Course, gun: float, results: list[Result], our_name: str,
                  tracks: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]], yb_names: dict[int, str],
                  our_track: tuple[np.ndarray, np.ndarray, np.ndarray] | None, step_nm: float = 5.0,
                  rivals: list[str] | None = None, yb_finish: dict[int, float] | None = None,
                  turning_index: int | None = None) -> Fleet:
    geom = course_geometry(course)
    cum = geom[3]
    total = float(cum[-1])
    turn_nm = float(cum[turning_index]) if turning_index is not None else None
    gl = [round(float(g), 3) for g in np.arange(step_nm, total - step_nm / 2 + 1e-9, step_nm)]
    if turn_nm is not None:
        gl.append(turn_nm)  # exact, so the turning gate is the rounding itself
    gates = np.array(sorted(set(gl)) + [total])
    labels = [("finish" if i == len(gates) - 1 else
               "turning mark" if turn_nm is not None and abs(g - turn_nm) < 1e-3 else f"{g:g} nm") for i, g in enumerate(gates)]
    warnings: list[str] = []
    matched = match_names(yb_names, results)
    unmatched = [r.yacht for r in results if r.finished and r not in matched.values()]
    boats: list[Boat] = []
    us = None
    our_key = norm_name(our_name)
    for yid, res in matched.items():
        if yid not in tracks or not res.finished or not res.tcc:
            continue
        t, la, lo = tracks[yid]
        fin_abs = gun + res.elapsed
        m = (t >= gun - 600) & (t <= fin_abs + 600) & np.isfinite(la) & np.isfinite(lo)
        t, la, lo = t[m], la[m], lo[m]
        if len(t) < 3:
            continue
        tm = course.marks[turning_index] if turning_index is not None else None
        rt = rounding_time(t, la, lo, tm) if tm is not None else None
        s = progress(t, la, lo, course, geom, rt, turning_index)
        gt = gate_times(t, s, gates, gun, res.elapsed, total)
        rnd = None if rt is None else rt - gun
        b = Boat(name=res.yacht, yb_id=yid, result=res, t=t, lat=la, lon=lo, s=s, gates=gt, rounding=rnd,
                 yb_finish=(yb_finish or {}).get(yid))
        boats.append(b)
        if norm_name(res.yacht) == our_key:
            us = b
    me = next((r for r in results if norm_name(r.yacht) == our_key and r.finished and r.tcc), None)
    if us is None and me is not None and our_track is not None:  # not tracked by YB: our own log, same method
        t, la, lo = our_track
        m = (t >= gun - 600) & (t <= gun + me.elapsed + 600) & np.isfinite(la) & np.isfinite(lo)
        t, la, lo = t[m], la[m], lo[m]
        tm = course.marks[turning_index] if turning_index is not None else None
        rt = rounding_time(t, la, lo, tm) if tm is not None else None
        s = progress(t, la, lo, course, geom, rt, turning_index)
        us = Boat(name=me.yacht, yb_id=None, result=me, t=t, lat=la, lon=lo, s=s,
                  gates=gate_times(t, s, gates, gun, me.elapsed, total), rounding=None if rt is None else rt - gun,
                  source="log")
        boats.append(us)
    if unmatched:
        warnings.append("finishers without a YB track: " + ", ".join(unmatched))
    late = [(b.name, (b.yb_finish - b.elapsed) / 60) for b in boats if b.yb_finish and abs(b.yb_finish - b.elapsed) > 120]
    if late:
        warnings.append(f"YB's finish differs from the official elapsed by more than 2 min for {len(late)} boats "
                        f"(up to {max(abs(x) for _, x in late):.0f} min); the official times are used")
    gaps, ranks = {}, {}
    if us is not None:
        corr = {b.name: b.gates * b.tcc for b in boats}
        for b in boats:
            gaps[b.name] = corr[b.name] - corr[us.name]
        mat = np.array([corr[b.name] for b in boats])
        for i, b in enumerate(boats):
            ranks[b.name] = np.array([1 + int(np.sum(mat[:, g] < mat[i, g])) if np.isfinite(mat[i, g]) else -1
                                      for g in range(len(gates))])
    r = None
    pts = [(b.rounding, (b.elapsed - b.rounding) * b.tcc) for b in boats if b.rounding is not None and b.elapsed]
    if len(pts) >= 5:
        x, y = np.array(pts).T
        r = float(np.corrcoef(x, y)[0, 1])
    if rivals is None and us is not None:
        rivals = default_rivals(us.result, results)
    return Fleet(gates=gates, gate_labels=labels, course_nm=total, turning_nm=turn_nm, boats=boats, us=us,
                 rivals=rivals or [], gaps=gaps, ranks=ranks, rounding_r=r, warnings=warnings)
