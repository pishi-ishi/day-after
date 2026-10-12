"""Polars in Expedition layout (TWS then TWA/BSP pairs) or ORC-certificate layout (FILE_FORMATS §4).

Both become one table of boat speed by TWS row and whole degrees of |TWA|. Lookup is bilinear in TWS ×
|TWA|; below the first TWS row speed scales linearly to zero, above the last row it is clamped and the
result is flagged as indicative.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

from .routes import read_text


@dataclass
class Polar:
    name: str
    tws: np.ndarray            # TWS rows (kt), ascending
    table: np.ndarray          # BSP at whole degrees of |TWA| 0..180, one row per TWS
    beat_angle: np.ndarray     # per TWS row
    beat_bsp: np.ndarray
    run_angle: np.ndarray
    run_bsp: np.ndarray
    source: str = ""

    @property
    def tws_max(self) -> float:
        return float(self.tws[-1])

    def target(self, tws, twa) -> np.ndarray:
        """Polar boat speed for arrays of TWS (kt) and TWA (deg, any sign)."""
        tws = np.asarray(tws, dtype=float)
        a = np.clip(np.abs(np.asarray(twa, dtype=float)), 0.0, 180.0)
        ts = np.clip(tws, 0.0, self.tws[-1])
        i = np.clip(np.searchsorted(self.tws, ts, side="right") - 1, 0, len(self.tws) - 2)
        f = np.clip((ts - self.tws[i]) / (self.tws[i + 1] - self.tws[i]), 0.0, 1.0)
        a0 = np.floor(a).astype(int)
        a1 = np.minimum(a0 + 1, 180)
        g = a - a0
        safe0 = np.where(np.isfinite(a), a0, 0)
        safe1 = np.where(np.isfinite(a), a1, 0)
        row = lambda k: self.table[k, safe0] * (1 - g) + self.table[k, safe1] * g
        out = row(i) * (1 - f) + row(i + 1) * f
        low = ts < self.tws[0]
        if np.any(low):  # below the lowest row: scale the first row down to zero
            first = self.table[0, safe0] * (1 - g) + self.table[0, safe1] * g
            out = np.where(low, first * ts / self.tws[0], out)
        return np.where(np.isfinite(tws) & np.isfinite(a), out, np.nan)

    def indicative(self, tws) -> np.ndarray:
        """True where the TWS is above the polar's top row (results there are clamped)."""
        return np.asarray(tws, dtype=float) > self.tws[-1]

    def targets(self, tws) -> dict:
        """Upwind and downwind target angles and speeds at the given TWS."""
        t = np.clip(np.asarray(tws, dtype=float), self.tws[0], self.tws[-1])
        return {"beat_angle": np.interp(t, self.tws, self.beat_angle), "beat_bsp": np.interp(t, self.tws, self.beat_bsp),
                "run_angle": np.interp(t, self.tws, self.run_angle), "run_bsp": np.interp(t, self.tws, self.run_bsp)}


def _build(name: str, rows: list[tuple[float, list[tuple[float, float]]]], source: str) -> Polar:
    rows = sorted(rows, key=lambda r: r[0])
    tws = np.array([r[0] for r in rows])
    grid = np.arange(181)
    table, beat_a, beat_b, run_a, run_b = [], [], [], [], []
    for _, pairs in rows:
        pairs = sorted({(float(a), float(b)) for a, b in pairs})
        A = np.array([p[0] for p in pairs])
        B = np.array([p[1] for p in pairs])
        if A[0] > 0:
            A, B = np.r_[0.0, A], np.r_[0.0, B]
        table.append(np.interp(grid, A, B))
        nz = [(a, b) for a, b in pairs if a > 0]
        beat = nz[0]  # the first pair after (0, 0): beat angle and speed
        beat_a.append(beat[0])
        beat_b.append(beat[1])
        off_grid = [(a, b) for a, b in nz if 130 <= a < 180 and a % 5]
        run = max(off_grid, key=lambda p: p[1] * np.cos(np.radians(180 - p[0]))) if off_grid else \
            max(((a, b) for a, b in nz if a >= 130), key=lambda p: p[1] * -np.cos(np.radians(p[0])))
        run_a.append(run[0])
        run_b.append(run[1])
    return Polar(name=name, tws=tws, table=np.array(table), beat_angle=np.array(beat_a), beat_bsp=np.array(beat_b),
                 run_angle=np.array(run_a), run_bsp=np.array(run_b), source=source)


def read_polar(path: str) -> Polar:
    text = read_text(path)
    lines = [l for l in text.splitlines() if l.strip()]
    name = os.path.splitext(os.path.basename(path))[0]
    if lines and lines[0].replace(" ", "").lower().startswith("twa/tws"):
        return _read_orc(lines, name, path)
    rows = []
    for l in lines:
        if l.startswith("!"):
            continue
        v = [float(x) for x in l.replace(",", " ").split()]
        rows.append((v[0], [(v[i], v[i + 1]) for i in range(1, len(v) - 1, 2)]))
    return _build(name, rows, path)


def _read_orc(lines: list[str], name: str, path: str) -> Polar:
    """ORC table: TWS across the columns; 'Upwind' beat angles, '0' beat VMG, TWA rows of BSP, '180' run VMG,
    'Downwind' gybe angles. Beat BSP = VMG / cos(beat angle); run BSP = VMG / cos(180 - gybe angle)."""
    head = lines[0].split("\t") if "\t" in lines[0] else lines[0].split()
    tws = [float(x) for x in head[1:] if x.strip()]
    data = {}
    for l in lines[1:]:
        parts = l.split("\t") if "\t" in l else l.split()
        data[parts[0].strip().lower()] = [float(x) for x in parts[1:] if x.strip()]
    rows = []
    for j, w in enumerate(tws):
        beat_a, beat_vmg = data["upwind"][j], data["0"][j]
        gybe_a, run_vmg = data["downwind"][j], data["180"][j]
        pairs = [(beat_a, beat_vmg / np.cos(np.radians(beat_a)))]
        for k, v in data.items():
            if k.replace(".", "").isdigit() and 0 < float(k) < 180:
                pairs.append((float(k), v[j]))
        pairs.append((gybe_a, run_vmg / np.cos(np.radians(180 - gybe_a))))
        pairs.append((180.0, run_vmg))
        rows.append((w, pairs))
    return _build(name, rows, path)
