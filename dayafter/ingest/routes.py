"""Expedition optimal-route tables and "summary of all routes" files (FILE_FORMATS §2–3).

Route tables hold local wall-clock times in the zone named by the first header cell (a Windows zone
ID), magnetic directions (`°M` columns, converted to true here) and degrees-decimal-minutes positions.
A row of commas separates the table from a `key,value` meta block.
"""
from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass, field

import numpy as np

from ..core import geo, magvar, timeutil
from ..core.wxmodel import canonical_model

TIME_FMT = "%d-%b-%Y %H:%M"
TIME_FMT_S = "%d-%b-%Y %H:%M:%S"

# <MODEL>_<GRIB day>_<GRIB hhmm>_<ddmonyyyy>.csv, e.g. GFS_25_1800_25sep2026.csv, ACCESS_1_25_1800_25sep2026.csv
_FNAME = re.compile(r"^(?P<model>.+?)_(?P<dd>\d{1,2})_(?P<hhmm>\d{4})_(?P<date>\d{1,2}[A-Za-z]{3}\d{4})", re.I)

# Route-table headers -> canonical keys. Directions marked °M are converted to true (key without _mag).
_NUMERIC = {
    "Twd": "twd", "Tws": "tws", "Twg": "twg", "Twa": "twa", "Targ": "targ", "Bsp": "bsp", "Bsp%": "bsp_pct",
    "Set": "set", "Drift": "drift", "Weight": "weight", "Brg": "brg", "Dist nm": "dist_nm", "Awa": "awa",
    "Aws": "aws", "SigWave H": "sigwave_h", "MeanWaveDir": "mean_wave_dir", "MeanWavePer": "mean_wave_per",
    "PrimaryWaveDir": "primary_wave_dir", "PrimaryWavePer": "primary_wave_per", "Swell dir": "swell_dir",
    "Swell H": "swell_h", "Swell period": "swell_per", "Wave Dir": "wave_dir", "Wave H": "wave_h",
    "Wave period": "wave_per", "MSLP": "mslp", "Rain": "rain", "AirT": "airt", "SST": "sst", "Cloud": "cloud",
    "CAPE": "cape", "LFTX": "lftx", "RH": "rh", "AirDens": "airdens",
}
_TEXT = {"Mark": "mark", "Sail": "sail", "Reef": "reef", "Other": "other", "Mode": "mode"}


def read_text(path: str) -> str:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _is_separator(line: str) -> bool:
    s = line.strip()
    return bool(s) and set(s) == {","}


def _num(cell: str) -> tuple[float, bool]:
    """'(-173)' -> (-173.0, True); '043' -> (43.0, False); '' -> (nan, False)."""
    s = cell.strip()
    if not s:
        return float("nan"), False
    paren = s.startswith("(") and s.endswith(")")
    if paren:
        s = s[1:-1]
    try:
        return float(s), paren
    except ValueError:
        return float("nan"), paren


def _split_header(name: str) -> tuple[str, str | None]:
    """'Twd°M' -> ('Twd', 'M'); 'Twd°T' -> ('Twd', 'T'); 'Tws' -> ('Tws', None)."""
    m = re.match(r"^(.*?)\s*°\s*([MT])$", name.strip())
    if m:
        return m.group(1), m.group(2)
    return name.strip(), None


@dataclass
class RouteTable:
    path: str
    model: str
    label: str
    name: str
    tz: str
    created: float | None
    t: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    mark: list[str]
    sail: list[str]
    sail_filled: list[str]
    reef: list[str]
    twa_paren: np.ndarray
    col: dict[str, np.ndarray]
    variation: np.ndarray
    meta: dict[str, str]
    grib_cycle: str | None = None
    warnings: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.t)

    def get(self, key: str) -> np.ndarray:
        return self.col.get(key, np.full(len(self.t), np.nan))

    def has(self, key: str) -> bool:
        return key in self.col and bool(np.isfinite(self.col[key]).any())

    @property
    def start(self) -> float:
        return float(self.t[0])

    @property
    def finish(self) -> float:
        return float(self.t[-1])

    @property
    def run_label(self) -> str:
        """Short label for this routing run, e.g. 'GFS 25 Sep 17:34'."""
        if self.created is None:
            return self.model
        return f"{self.model} {timeutil.fmt_local(self.created, self.tz, '%d %b %H:%M')}"

    def mark_rows(self) -> list[tuple[int, str, int]]:
        """(row index, mark name, occurrence number) for rows that reach a mark, in order."""
        seen: dict[str, int] = {}
        out = []
        for i, m in enumerate(self.mark):
            if m:
                key = m.strip().lower()
                seen[key] = seen.get(key, 0) + 1
                out.append((i, m.strip(), seen[key]))
        return out


def parse_filename(path: str) -> dict:
    m = _FNAME.match(os.path.basename(path))
    if not m:
        return {}
    return {"model_label": m.group("model"), "grib_cycle": f"{m.group('dd')}_{m.group('hhmm')}", "date": m.group("date")}


def looks_like_route_table(first_line: str) -> bool:
    cells = [c.strip() for c in first_line.split(",")]
    return len(cells) > 10 and "Mark" in cells and "Latitude" in cells and any(c.startswith("Twd") for c in cells)


def read_route_table(path: str, *, variation_override: float | None = None, tz: str | None = None) -> RouteTable:
    text = read_text(path)
    lines = text.splitlines()
    try:
        sep = next(i for i, l in enumerate(lines) if _is_separator(l))
    except StopIteration:
        sep = len(lines)
    rows = [r for r in csv.reader(io.StringIO("\n".join(lines[:sep]))) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError(f"{path}: empty route table")
    header = [h.strip() for h in rows[0]]
    data = rows[1:]
    warnings: list[str] = []

    meta: dict[str, str] = {}
    for l in lines[sep + 1:]:
        parts = next(csv.reader([l]), [])
        if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
            meta[parts[0].strip()] = parts[1].strip()

    zone_name = tz or timeutil.tz_from_windows_id(header[0])
    if zone_name is None:
        zone_name = timeutil.DEFAULT_TZ
        warnings.append(f"unknown time-zone header {header[0]!r}; assumed {zone_name}")

    idx = {h: i for i, h in enumerate(header) if h}
    n = len(data)

    def cell(r: list[str], i: int) -> str:
        return r[i] if i < len(r) else ""

    t = np.array([timeutil.parse_local(cell(r, 0), TIME_FMT, zone_name) for r in data], dtype=float)
    lat = np.array([geo.parse_ddm(cell(r, idx["Latitude"])) for r in data], dtype=float)
    lon = np.array([geo.parse_ddm(cell(r, idx["Longitude"])) for r in data], dtype=float)
    variation = np.asarray(magvar.variation_deg_e(lat, variation_override), dtype=float)

    col: dict[str, np.ndarray] = {}
    twa_paren = np.zeros(n, dtype=bool)
    text_cols: dict[str, list[str]] = {k: [""] * n for k in _TEXT.values()}
    for h, i in idx.items():
        if i == 0 or h in ("Latitude", "Longitude"):
            continue
        if h in _TEXT:
            text_cols[_TEXT[h]] = [cell(r, i).strip() for r in data]
            continue
        base, ref = _split_header(h)
        key = _NUMERIC.get(base) or re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")
        vals = np.empty(n)
        for j, r in enumerate(data):
            v, paren = _num(cell(r, i))
            vals[j] = v
            if key == "twa" and paren:
                twa_paren[j] = True
        if ref == "M":
            col[key + "_mag"] = vals
            col[key] = geo.wrap360(vals + variation)
        else:
            col[key] = vals

    sail_filled, last = [], ""
    for s in text_cols["sail"]:
        last = s or last
        sail_filled.append(last)

    fn = parse_filename(path)
    label = meta.get("Model") or fn.get("model_label") or os.path.splitext(os.path.basename(path))[0]
    created = None
    if meta.get("Created"):
        try:
            created = timeutil.parse_local(meta["Created"], TIME_FMT_S, zone_name)
        except ValueError:
            warnings.append(f"unreadable Created value {meta['Created']!r}")
    if n and np.any(np.diff(t) < 0):
        warnings.append("times are not in order")

    return RouteTable(
        path=path, model=canonical_model(label), label=label, name=meta.get("Name", ""), tz=zone_name,
        created=created, t=t, lat=lat, lon=lon, mark=text_cols["mark"], sail=text_cols["sail"],
        sail_filled=sail_filled, reef=text_cols["reef"], twa_paren=twa_paren, col=col, variation=variation,
        meta=meta, grib_cycle=fn.get("grib_cycle"), warnings=warnings,
    )


# ---------------------------------------------------------------------------------------------
# "summary of all routes" CSV

@dataclass
class SummaryRow:
    model: str
    label: str
    resolution: str
    run: str
    route_nm: float
    optimal_nm: float
    elapsed: float | None
    finish: float | None
    delta: float | None
    created: float | None

    @property
    def is_reference(self) -> bool:
        return self.model == "Reference"


@dataclass
class RouteSummary:
    path: str
    tz: str
    rows: list[SummaryRow]

    @property
    def created(self) -> float | None:
        vals = [r.created for r in self.rows if r.created is not None]
        return min(vals) if vals else None


def looks_like_route_summary(first_line: str) -> bool:
    return first_line.replace(" ", "").lower().startswith("draw,name,colour,routenm")


def _parse_summary_name(name: str) -> tuple[str, str, str]:
    """'G ACCESS SY High 06:34:23' -> ('ACCESS SY', 'High', '06:34:23'); 'G  High 06:38:43' -> ('', 'High', ...)."""
    toks = name.split()
    if toks and toks[0] == "G":
        toks = toks[1:]
    run = toks.pop() if toks and re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", toks[-1]) else ""
    res = toks.pop() if toks and toks[-1] in ("High", "Medium", "Med", "Low", "Normal", "Fine", "Coarse") else ""
    return " ".join(toks), res, run


def _float(s: str) -> float:
    try:
        return float(s.strip().replace("nm", ""))
    except ValueError:
        return float("nan")


def read_route_summary(path: str, tz: str = timeutil.DEFAULT_TZ) -> RouteSummary:
    rows = list(csv.DictReader(io.StringIO(read_text(path))))
    out = []
    for r in rows:
        r = {(k or "").strip(): (v or "") for k, v in r.items()}
        if not r.get("Name", "").strip():
            continue
        label, res, run = _parse_summary_name(r["Name"].strip())

        def when(key: str) -> float | None:
            s = r.get(key, "").strip()
            return timeutil.parse_local(s, TIME_FMT_S, tz) if s else None

        out.append(SummaryRow(
            model=canonical_model(label), label=label, resolution=res, run=run,
            route_nm=_float(r.get("Route nm", "")), optimal_nm=_float(r.get("Optimal nm", "")),
            elapsed=timeutil.parse_duration(r.get("Elapsed time", "")), finish=when("Finish"),
            delta=timeutil.parse_duration(r.get("Delta", "")), created=when("Created"),
        ))
    return RouteSummary(path=path, tz=tz, rows=out)
