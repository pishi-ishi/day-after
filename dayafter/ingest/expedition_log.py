"""Expedition instrument logs (`log-YYYYMonDD.csv`, FILE_FORMATS §1) and the 1 Hz timeline built from them.

The CSV is sparse: each row is `boat, Utc, id, value, id, value, …` with only the channels that changed.
Header blocks (`!Boat` names, `!boat` ids, `!v` version) repeat whenever the logged channel set changes;
ids are global, so the maps of every block (and every file of a multi-day race) are merged. `Utc` is the
Excel serial in UTC. Boat 0 is our boat.

The timeline bins samples to whole seconds keeping the last value in each second (angles must never be
averaged arithmetically) and forward-fills gaps of up to 3 s.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

from ..core import timeutil

FFILL_S = 3


@dataclass
class Log:
    paths: list[str]
    names: dict[int, str]
    samples: dict[str, tuple[np.ndarray, np.ndarray]]
    version: str = ""
    header_blocks: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def channels(self) -> list[str]:
        return sorted(self.samples)

    def has(self, name: str) -> bool:
        return name in self.samples and len(self.samples[name][0]) > 0

    def count(self, name: str) -> int:
        return len(self.samples[name][0]) if name in self.samples else 0

    @property
    def t_first(self) -> float:
        return min(float(t[0]) for t, _ in self.samples.values() if len(t))

    @property
    def t_last(self) -> float:
        return max(float(t[-1]) for t, _ in self.samples.values() if len(t))

    def timeline(self, t0: float, t1: float, names: list[str] | None = None, ffill: int = FFILL_S) -> "Timeline":
        """1 Hz arrays for [t0, t1] (whole seconds). Channels not logged come back as NaN on demand."""
        a, b = int(np.floor(t0)), int(np.ceil(t1))
        n = b - a + 1
        grid = np.arange(a, b + 1, dtype=np.int64)
        ch = {}
        for name in (names if names is not None else self.channels):
            if name in self.samples:
                ch[name] = to_grid(*self.samples[name], a, n, ffill)
        return Timeline(t=grid, ch=ch)


@dataclass
class Timeline:
    t: np.ndarray            # epoch seconds, 1 Hz, int64
    ch: dict[str, np.ndarray]

    def __len__(self) -> int:
        return len(self.t)

    def __getitem__(self, name: str) -> np.ndarray:
        v = self.ch.get(name)
        return v if v is not None else np.full(len(self.t), np.nan)

    def has(self, name: str) -> bool:
        return name in self.ch and bool(np.isfinite(self.ch[name]).any())

    def window(self, t0: float, t1: float) -> "Timeline":
        m = (self.t >= t0) & (self.t <= t1)
        return Timeline(t=self.t[m], ch={k: v[m] for k, v in self.ch.items()})

    def index(self, t: float) -> int:
        """Grid index of second `t` (clamped)."""
        return int(np.clip(int(round(t)) - int(self.t[0]), 0, len(self.t) - 1))


def to_grid(t: np.ndarray, v: np.ndarray, start: int, n: int, ffill: int = FFILL_S) -> np.ndarray:
    """Sparse samples (sorted by time) -> 1 Hz grid of n seconds from `start`: last value per second,
    forward-filled across gaps of at most `ffill` seconds."""
    out = np.full(n, np.nan)
    k = np.floor(t - start).astype(np.int64)
    m = (k >= 0) & (k < n) & np.isfinite(v)
    k, v = k[m], v[m]
    if not len(k):
        return out
    last = np.r_[k[1:] != k[:-1], True]  # last sample in each second (input is time-sorted)
    out[k[last]] = v[last]
    if ffill > 0:
        valid = np.isfinite(out)
        idx = np.where(valid, np.arange(n), -1)
        prev = np.maximum.accumulate(idx)
        age = np.arange(n) - prev
        fill = ~valid & (prev >= 0) & (age <= ffill)
        out[fill] = out[prev[fill]]
    return out


def looks_like_log(first_line: str) -> bool:
    return first_line.startswith("!Boat,")


def read_logs(paths: list[str], boat: int = 0) -> Log:
    """Read one or more Expedition log files (a multi-day race has one per day) for one boat.

    Rows are gathered into flat lists of strings (C-level `extend`, no per-sample Python work) and converted and
    split per channel with numpy, which keeps a 20 MB race log to about a second."""
    names: dict[int, str] = {}
    version, blocks, warnings = "", 0, []
    t_str: list[str] = []
    counts: list[int] = []
    id_str: list[str] = []
    val_str: list[str] = []
    boat_s = str(boat)
    for path in sorted(paths):
        pending_names: list[str] | None = None
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("!"):
                    if line.startswith("!Boat"):
                        pending_names = line.rstrip("\r\n").split(",")
                        blocks += 1
                    elif line.startswith("!boat") and pending_names is not None:
                        ids = line.rstrip("\r\n").split(",")
                        for nm, i in zip(pending_names[2:], ids[2:]):  # skip Boat, Utc
                            i = i.strip()
                            if i.lstrip("-").isdigit():
                                prev = names.get(int(i))
                                if prev is not None and prev != nm.strip():
                                    warnings.append(f"channel id {i} renamed from {prev!r} to {nm!r}")
                                names[int(i)] = nm.strip()
                    elif line.startswith("!v"):
                        version = line.strip()[1:]
                    continue
                p = line.rstrip("\r\n").split(",")
                if len(p) < 4 or p[0].strip() != boat_s:
                    continue
                n = (len(p) - 2) // 2
                t_str.append(p[1])
                counts.append(n)
                id_str.extend(p[2:2 + 2 * n:2])
                val_str.extend(p[3:3 + 2 * n:2])
    samples: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if t_str:
        tt = (_to_float(t_str) - timeutil.EXCEL_EPOCH_DAYS) * 86400.0
        t_all = np.repeat(tt, counts)
        cid = _to_float(id_str)
        val = _to_float(val_str)
        good = np.isfinite(cid) & np.isfinite(val) & np.isfinite(t_all)
        cid, val, t_all = cid[good].astype(np.int64), val[good], t_all[good]
        order = np.lexsort((t_all, cid))  # by channel, then time
        cid, val, t_all = cid[order], val[order], t_all[order]
        uniq, first = np.unique(cid, return_index=True)
        bounds = list(first) + [len(cid)]
        for k, c in enumerate(uniq):
            a, b = bounds[k], bounds[k + 1]
            name = names.get(int(c), f"ch{int(c)}")
            if name in samples:  # two ids with one name: keep both, distinguished by id
                name = f"{name}#{int(c)}"
            samples[name] = (t_all[a:b], val[a:b])
    if not samples:
        warnings.append(f"no data rows for boat {boat}")
    return Log(paths=[os.path.abspath(p) for p in sorted(paths)], names=names, samples=samples, version=version,
               header_blocks=blocks, warnings=warnings)


def _to_float(items: list[str]) -> np.ndarray:
    """Strings -> floats, with NaN for blanks and anything that is not a number. `map(float)` runs in C and beats
    numpy's string conversion by a wide margin; the slow path only runs when a bad token is present."""
    try:
        return np.fromiter(map(float, items), dtype=float, count=len(items))
    except ValueError:
        out = np.empty(len(items))
        for i, x in enumerate(items):
            try:
                out[i] = float(x)
            except ValueError:
                out[i] = np.nan
        return out
