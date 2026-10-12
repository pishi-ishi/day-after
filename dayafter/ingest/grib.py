"""GRIB1 and GRIB2 decoding in pure Python + numpy (FILE_FORMATS §9).

Covers what Expedition and Saildocs deliver: GRIB2 regular lat/lon grids (template 3.0), products 4.0 and 4.8,
packing 5.0 (simple), 5.2 (complex) and 5.3 (complex with spatial differencing), several fields per message;
GRIB1 lat/lon grids with simple packing. Files that Expedition encrypts (`grbenc01`: ACCESS, UM) are refused
with `EncryptedGrib`; anything else unsupported raises `UnsupportedGrib` naming the template.

Fields come out in standard units (wind kt, pressure hPa, temperature °C, rain mm/h after `rates()`, cloud %),
on rows south → north and columns west → east.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import struct
from dataclasses import dataclass

import numpy as np

from ..core.wxmodel import canonical_model

MS_TO_KT = 1.0 / 0.514444


class EncryptedGrib(Exception):
    pass


class UnsupportedGrib(Exception):
    pass


@dataclass
class Field:
    param: str             # u10 v10 gust mslp t2m prate acc cloud (acc = accumulation, see rates())
    ref: float             # model run (epoch s)
    valid: float           # valid time (end of the interval for statistics)
    start: float           # start of the statistical interval (= valid for instantaneous fields)
    lat0: float            # first row latitude (south)
    lon0: float
    dlat: float            # > 0
    dlon: float
    values: np.ndarray     # (nj, ni)
    centre: int = 0

    @property
    def shape(self):
        return self.values.shape


# GRIB2 (discipline, category, number) -> (param, scale, offset): value_std = raw * scale + offset
_G2 = {
    (0, 2, 2): ("u10", MS_TO_KT, 0.0), (0, 2, 3): ("v10", MS_TO_KT, 0.0), (0, 2, 22): ("gust", MS_TO_KT, 0.0),
    (0, 3, 0): ("mslp", 0.01, 0.0), (0, 3, 1): ("mslp", 0.01, 0.0), (0, 0, 0): ("t2m", 1.0, -273.15),
    (0, 1, 7): ("prate", 3600.0, 0.0), (0, 1, 52): ("prate_or_acc", 1.0, 0.0), (0, 1, 8): ("acc", 1.0, 0.0),
    (0, 1, 193): ("acc_m", 1000.0, 0.0), (0, 6, 1): ("cloud", 1.0, 0.0), (0, 6, 192): ("cloud", 100.0, 0.0),
}
# GRIB1 table 2 parameter -> (param, scale, offset)
_G1 = {33: ("u10", MS_TO_KT, 0.0), 34: ("v10", MS_TO_KT, 0.0), 180: ("gust", MS_TO_KT, 0.0), 2: ("mslp", 0.01, 0.0),
       11: ("t2m", 1.0, -273.15), 59: ("prate", 3600.0, 0.0), 61: ("acc", 1.0, 0.0), 71: ("cloud", 1.0, 0.0)}
_UNIT_S = {0: 60, 1: 3600, 2: 86400, 10: 3 * 3600, 11: 6 * 3600, 12: 12 * 3600, 13: 1}


def _sm(b: bytes) -> int:
    """Sign-and-magnitude integer (GRIB's signed encoding)."""
    v = int.from_bytes(b, "big")
    top = 1 << (len(b) * 8 - 1)
    return -(v & (top - 1)) if v & top else v


def _bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))


def _read(bits: np.ndarray, pos: int, width: int, count: int) -> np.ndarray:
    if width == 0 or count == 0:
        return np.zeros(count, dtype=np.int64)
    chunk = bits[pos:pos + width * count]
    if len(chunk) < width * count:
        raise UnsupportedGrib("data section shorter than its header says")
    w = (1 << np.arange(width - 1, -1, -1, dtype=np.int64))
    return chunk.reshape(count, width).astype(np.int64) @ w


def _ibm(b: bytes) -> float:
    s = -1.0 if b[0] & 0x80 else 1.0
    e = (b[0] & 0x7F) - 64
    m = int.from_bytes(b[1:4], "big") / float(1 << 24)
    return s * m * 16.0 ** e


def _epoch(y, mo, d, h, mi, s=0) -> float:
    return dt.datetime(y, mo, d, h, mi, s, tzinfo=dt.timezone.utc).timestamp()


# ---------------------------------------------------------------------------------------------- GRIB2

def _unpack_complex(sec5: bytes, sec7: bytes, n: int, template: int) -> np.ndarray:
    nbits = sec5[19]
    mvm = sec5[22]
    ng = int.from_bytes(sec5[31:35], "big")
    ref_w, bits_w = sec5[35], sec5[36]
    ref_l, inc_l = int.from_bytes(sec5[37:41], "big"), sec5[41]
    last_l, bits_l = int.from_bytes(sec5[42:46], "big"), sec5[46]
    data = sec7[5:]
    pos_byte = 0
    order = nd = 0
    ival, minimum = [], 0
    if template == 3:
        order, nd = sec5[47], sec5[48]
        for _ in range(order):
            ival.append(_sm(data[pos_byte:pos_byte + nd]))
            pos_byte += nd
        minimum = _sm(data[pos_byte:pos_byte + nd])
        pos_byte += nd
    bits = _bits(data)
    pos = pos_byte * 8
    refs = _read(bits, pos, nbits, ng)
    pos += -(-nbits * ng // 8) * 8
    widths = _read(bits, pos, bits_w, ng) + ref_w
    pos += -(-bits_w * ng // 8) * 8
    lengths = _read(bits, pos, bits_l, ng) * inc_l + ref_l
    pos += -(-bits_l * ng // 8) * 8
    if ng:
        lengths[-1] = last_l
    vals = np.empty(int(lengths.sum()), dtype=np.float64)
    miss = np.zeros(len(vals), dtype=bool)
    k = 0
    for g in range(ng):
        L, W, R = int(lengths[g]), int(widths[g]), int(refs[g])
        if W == 0:
            vals[k:k + L] = R
            if mvm >= 1 and nbits > 0 and R == (1 << nbits) - 1:
                miss[k:k + L] = True
            elif mvm == 2 and nbits > 0 and R == (1 << nbits) - 2:
                miss[k:k + L] = True
        else:
            x = _read(bits, pos, W, L)
            pos += W * L
            vals[k:k + L] = R + x
            if mvm >= 1:
                miss[k:k + L] |= x == (1 << W) - 1
            if mvm == 2:
                miss[k:k + L] |= x == (1 << W) - 2
        k += L
    if template == 3 and order:
        good = np.flatnonzero(~miss)
        d = vals[good] + minimum
        f = np.empty(len(d))
        f[:order] = ival[:order]
        if order == 1:
            f[1:] = d[1:]
            f = np.cumsum(f)
        else:  # order 2: f[i] = d[i] + 2 f[i-1] - f[i-2]
            for i in range(2, len(d)):
                f[i] = d[i] + 2 * f[i - 1] - f[i - 2]
        vals[good] = f
    vals[miss] = np.nan
    if len(vals) != n:
        raise UnsupportedGrib(f"decoded {len(vals)} values, expected {n}")
    return vals


def _grid30(sec3: bytes):
    """Template 3.0 (regular lat/lon) or 3.40 (regular Gaussian). Gaussian rows are spaced evenly to within
    1e-4° away from the poles, so a Gaussian subarea is treated as regular between its first and last row."""
    tpl = int.from_bytes(sec3[12:14], "big")
    if tpl not in (0, 40):
        raise UnsupportedGrib(f"grid template 3.{tpl} (supported: 3.0 lat/lon, 3.40 Gaussian)")
    ni, nj = int.from_bytes(sec3[30:34], "big"), int.from_bytes(sec3[34:38], "big")
    la1, lo1 = _sm(sec3[46:50]) / 1e6, _sm(sec3[50:54]) / 1e6
    la2, lo2 = _sm(sec3[55:59]) / 1e6, _sm(sec3[59:63]) / 1e6
    di = _sm(sec3[63:67]) / 1e6
    if tpl == 0:
        dj = _sm(sec3[67:71]) / 1e6
    else:
        dj = abs(la2 - la1) / (nj - 1) if nj > 1 else 1.0
        if max(abs(la1), abs(la2)) > 80:
            raise UnsupportedGrib("Gaussian grid near a pole")
    return ni, nj, la1, lo1, la2, lo2, abs(di), abs(dj), sec3[71]


def _orient(v: np.ndarray, ni, nj, la1, lo1, la2, lo2, di, dj, scan) -> tuple[np.ndarray, float, float]:
    """Rows south -> north, columns west -> east, whatever the scanning mode."""
    if scan & 0x20:
        v = v.reshape(ni, nj).T
    else:
        v = v.reshape(nj, ni)
    if scan & 0x10:  # alternate rows reversed
        v = v.copy()
        v[1::2] = v[1::2, ::-1]
    if scan & 0x80:  # -i: east -> west
        v = v[:, ::-1]
    if not scan & 0x40:  # -j: north -> south
        v = v[::-1]
    lat0 = min(la1, la2)
    lon0 = lo1 if not scan & 0x80 else lo2
    return v, lat0, lon0


def _decode2(msg: bytes, raw: bool = False) -> list[Field]:
    disc = msg[6]
    p = 16
    end = len(msg) - 4
    sec1 = sec3 = sec4 = sec5 = sec6 = None
    out = []
    while p < end:
        L = int.from_bytes(msg[p:p + 4], "big")
        num = msg[p + 4]
        sec = msg[p:p + L]
        if num == 1:
            sec1 = sec
        elif num == 3:
            sec3 = sec
        elif num == 4:
            sec4 = sec
        elif num == 5:
            sec5 = sec
        elif num == 6:
            sec6 = sec
        elif num == 7:
            out.append(_field2(disc, sec1, sec3, sec4, sec5, sec6, sec, raw))
        p += L
    return [f for f in out if f is not None]


def _field2(disc, sec1, sec3, sec4, sec5, sec6, sec7, raw: bool = False) -> Field | None:
    """One field. With `raw`, every parameter comes back in its GRIB units, named 'discipline.category.number'."""
    cat, num = sec4[9], sec4[10]
    spec = (f"{disc}.{cat}.{num}", 1.0, 0.0) if raw else _G2.get((disc, cat, num))
    pdt = int.from_bytes(sec4[7:9], "big")
    if spec is None or pdt not in (0, 8):
        return None
    lev_type = sec4[22]
    if spec[0] in ("u10", "v10") and lev_type == 103 and int.from_bytes(sec4[24:28], "big") != 10:
        return None
    ref = _epoch(int.from_bytes(sec1[12:14], "big"), sec1[14], sec1[15], sec1[16], sec1[17], sec1[18])
    unit = _UNIT_S.get(sec4[17])
    if unit is None:
        raise UnsupportedGrib(f"time unit {sec4[17]}")
    start = ref + int.from_bytes(sec4[18:22], "big") * unit
    valid = start
    if pdt == 8:
        valid = _epoch(int.from_bytes(sec4[34:36], "big"), sec4[36], sec4[37], sec4[38], sec4[39], sec4[40])
    template = int.from_bytes(sec5[9:11], "big")
    n = int.from_bytes(sec5[5:9], "big")
    R = struct.unpack(">f", sec5[11:15])[0]
    E, D = _sm(sec5[15:17]), _sm(sec5[17:19])
    nbits = sec5[19]
    if template == 0:
        raw = _read(_bits(sec7[5:]), 0, nbits, n).astype(np.float64) if nbits else np.zeros(n)
    elif template in (2, 3):
        raw = _unpack_complex(sec5, sec7, n, template)
    else:
        raise UnsupportedGrib(f"data template 5.{template} (supported: 5.0, 5.2, 5.3)")
    vals = (R + raw * 2.0 ** E) / 10.0 ** D
    ni, nj, la1, lo1, la2, lo2, di, dj, scan = _grid30(sec3)
    if sec6 is not None and sec6[5] == 0:  # a bitmap: values only where the bit is set
        bm = _bits(sec6[6:])[:ni * nj].astype(bool)
        full = np.full(ni * nj, np.nan)
        full[bm] = vals[:bm.sum()]
        vals = full
    elif sec6 is not None and sec6[5] not in (0, 255):
        raise UnsupportedGrib(f"bitmap indicator {sec6[5]}")
    grid, lat0, lon0 = _orient(vals, ni, nj, la1, lo1, la2, lo2, di, dj, scan)
    name, scale, off = spec
    if name == "prate_or_acc":  # ICON / AIFS precipitation: an accumulation when statistically processed
        name, scale = ("acc", 1.0) if pdt == 8 else ("prate", 3600.0)
    if name == "acc_m":
        name = "acc"
    return Field(param=name, ref=ref, valid=valid, start=start, lat0=lat0, lon0=lon0, dlat=dj, dlon=di,
                 values=grid * scale + off, centre=int.from_bytes(sec1[5:7], "big"))


# ---------------------------------------------------------------------------------------------- GRIB1

def _decode1(msg: bytes) -> list[Field]:
    p = 8
    pds = msg[p:p + int.from_bytes(msg[p:p + 3], "big")]
    p += len(pds)
    spec = _G1.get(pds[8])
    lev_type, lev = pds[9], int.from_bytes(pds[10:12], "big")
    if spec is None or (spec[0] in ("u10", "v10") and not (lev_type == 105 and lev == 10)):
        return []
    flags = pds[7]
    gds = bms = None
    if flags & 0x80:
        gds = msg[p:p + int.from_bytes(msg[p:p + 3], "big")]
        p += len(gds)
    if flags & 0x40:
        bms = msg[p:p + int.from_bytes(msg[p:p + 3], "big")]
        p += len(bms)
    bds = msg[p:p + int.from_bytes(msg[p:p + 3], "big")]
    if gds is None or gds[5] != 0:
        raise UnsupportedGrib("GRIB1 grid other than lat/lon")
    if bds[3] & 0xF0:
        raise UnsupportedGrib("GRIB1 packing other than simple grid-point packing")
    century = pds[24]
    year = (century - 1) * 100 + pds[12]
    ref = _epoch(year, pds[13], pds[14], pds[15], pds[16])
    unit = _UNIT_S.get(pds[17])
    if unit is None:
        raise UnsupportedGrib(f"GRIB1 time unit {pds[17]}")
    tri, p1, p2 = pds[20], pds[18], pds[19]
    if tri == 10:
        start = valid = ref + int.from_bytes(pds[18:20], "big") * unit
    elif tri in (2, 3, 4, 5):
        start, valid = ref + p1 * unit, ref + p2 * unit
    else:
        start = valid = ref + p1 * unit
    D = _sm(pds[26:28])
    E = _sm(bds[4:6])
    R = _ibm(bds[6:10])
    nbits = bds[10]
    ni, nj = int.from_bytes(gds[6:8], "big"), int.from_bytes(gds[8:10], "big")
    s24 = lambda b: _sm(b) / 1000.0
    la1, lo1, la2, lo2 = s24(gds[10:13]), s24(gds[13:16]), s24(gds[17:20]), s24(gds[20:23])
    di, dj = int.from_bytes(gds[23:25], "big") / 1000.0, int.from_bytes(gds[25:27], "big") / 1000.0
    scan = gds[27]
    npts = ni * nj
    mask = None
    if bms is not None:
        mask = _bits(bms[6:])[:npts].astype(bool)
        count = int(mask.sum())
    else:
        count = npts
    raw = _read(_bits(bds[11:]), 0, nbits, count).astype(np.float64) if nbits else np.zeros(count)
    vals = (R + raw * 2.0 ** E) / 10.0 ** D
    if mask is not None:
        full = np.full(npts, np.nan)
        full[mask] = vals
        vals = full
    grid, lat0, lon0 = _orient(vals, ni, nj, la1, lo1, la2, lo2, di, dj, scan)
    name, scale, off = spec
    return [Field(param=name, ref=ref, valid=valid, start=start, lat0=lat0, lon0=lon0, dlat=dj, dlon=di,
                  values=grid * scale + off, centre=pds[4])]


# ---------------------------------------------------------------------------------------------- files

def read_grib(path: str, raw: bool = False) -> list[Field]:
    """Every field Day After uses, in standard units; with `raw`, every GRIB2 field in its own units."""
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:8] == b"grbenc01":
        raise EncryptedGrib(f"{os.path.basename(path)} is encrypted by Expedition and cannot be read")
    out: list[Field] = []
    i = 0
    while True:
        j = buf.find(b"GRIB", i)
        if j < 0 or j + 8 > len(buf):
            break
        ed = buf[j + 7]
        if ed == 2:
            total = int.from_bytes(buf[j + 8:j + 16], "big")
            out += _decode2(buf[j:j + total], raw)
        elif ed == 1:
            total = int.from_bytes(buf[j + 4:j + 7], "big")
            out += _decode1(buf[j:j + total])
        else:
            total = 4
        i = j + max(total, 4)
    return out


_NAME = re.compile(r"^(?:EX|SD)_(?P<model>.+?)(?:_\d{2,4})?_(?P<stamp>\d{2}[A-Za-z]{3}\d{2}_\d{6})", re.I)


def model_from_filename(path: str) -> tuple[str, dt.datetime | None]:
    """'EX_ECMWF_025_26Sep26_060031.grb' -> ('ECMWF', naive local download time 2026-09-26 06:00:31).
    Expedition stamps its downloads with the PC's local clock."""
    base = os.path.basename(path)
    m = _NAME.match(base)
    if not m:
        return canonical_model(os.path.splitext(base)[0]), None
    label = m.group("model").replace("_Sydney", "").replace("_Global", "")
    try:
        stamp = dt.datetime.strptime(m.group("stamp"), "%d%b%y_%H%M%S")
    except ValueError:
        stamp = None
    return canonical_model(label), stamp


class Cube:
    """All fields of one model run: interpolation in space (bilinear) and time (linear)."""

    def __init__(self, model: str, fields: list[Field], path: str = "", downloaded: float | None = None):
        self.model, self.path, self.downloaded = model, path, downloaded
        self.ref = max(f.ref for f in fields) if fields else float("nan")
        self.series: dict[str, list[Field]] = {}
        for f in fields:
            self.series.setdefault(f.param, []).append(f)
        for v in self.series.values():
            v.sort(key=lambda f: f.valid)
        self._rates()

    def _rates(self) -> None:
        """Accumulations -> rain rate (mm/h) at the end of each interval."""
        acc = self.series.pop("acc", None)
        if not acc or "prate" in self.series:
            return
        rates = []
        prev = None
        for f in acc:
            if prev is not None and abs(prev.start - f.start) < 1 and f.valid > prev.valid:  # since the run start
                v = (f.values - prev.values) / ((f.valid - prev.valid) / 3600.0)
            elif f.valid > f.start:  # one interval each
                v = f.values / ((f.valid - f.start) / 3600.0)
            else:
                prev = f
                continue
            rates.append(Field("prate", f.ref, f.valid, f.valid, f.lat0, f.lon0, f.dlat, f.dlon, np.maximum(v, 0.0), f.centre))
            prev = f
        if rates:
            self.series["prate"] = rates

    @property
    def params(self) -> list[str]:
        return sorted(self.series)

    def covers(self, lat, lon) -> bool:
        f = self.series.get("u10", [None])[0]
        if f is None:
            return False
        nj, ni = f.shape
        lat, lon = np.asarray(lat), np.asarray(lon)
        return bool(np.all((lat >= f.lat0) & (lat <= f.lat0 + (nj - 1) * f.dlat) &
                           (lon >= f.lon0) & (lon <= f.lon0 + (ni - 1) * f.dlon)))

    @property
    def t_range(self) -> tuple[float, float]:
        v = self.series.get("u10", [])
        return (v[0].valid, v[-1].valid) if v else (np.nan, np.nan)

    def sample(self, param: str, t, lat, lon) -> np.ndarray:
        """Bilinear in space, linear in time; NaN outside the grid or the forecast range."""
        t, lat, lon = (np.atleast_1d(np.asarray(x, dtype=float)) for x in (t, lat, lon))
        fs = self.series.get(param)
        out = np.full(len(t), np.nan)
        if not fs:
            return out
        times = np.array([f.valid for f in fs])
        stack = np.array([f.values for f in fs])  # (nt, nj, ni)
        f0 = fs[0]
        nt, nj, ni = stack.shape
        y = (lat - f0.lat0) / f0.dlat
        x = (lon - f0.lon0) / f0.dlon
        ok = (y >= 0) & (y <= nj - 1) & (x >= 0) & (x <= ni - 1) & (t >= times[0]) & (t <= times[-1])
        if not ok.any():
            return out
        j0 = np.clip(np.floor(y[ok]).astype(int), 0, nj - 2) if nj > 1 else np.zeros(ok.sum(), int)
        i0 = np.clip(np.floor(x[ok]).astype(int), 0, ni - 2) if ni > 1 else np.zeros(ok.sum(), int)
        fy, fx = y[ok] - j0, x[ok] - i0
        k = np.clip(np.searchsorted(times, t[ok], side="right") - 1, 0, max(nt - 2, 0))
        ft = np.zeros(ok.sum()) if nt == 1 else np.clip((t[ok] - times[k]) / np.maximum(times[k + 1] - times[k], 1), 0, 1)

        def at(kk):
            a = stack[kk, j0, i0]
            b = stack[kk, j0, np.minimum(i0 + 1, ni - 1)]
            c = stack[kk, np.minimum(j0 + 1, nj - 1), i0]
            d = stack[kk, np.minimum(j0 + 1, nj - 1), np.minimum(i0 + 1, ni - 1)]
            return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

        v0 = at(k)
        v1 = at(np.minimum(k + 1, nt - 1))
        out[ok] = v0 * (1 - ft) + v1 * ft
        return out

    def wind(self, t, lat, lon) -> tuple[np.ndarray, np.ndarray]:
        """(TWS kt, TWD ° true) at the given times and places."""
        u, v = self.sample("u10", t, lat, lon), self.sample("v10", t, lat, lon)
        return np.hypot(u, v), (np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0


def load_cubes(paths: list[str], tz: str | None = None) -> tuple[list[Cube], list[str]]:
    """One Cube per file that holds 10 m wind; returns (cubes, notes about skipped files). With `tz`, the
    download stamp in Expedition's file name is read as local time in that zone."""
    from ..core.timeutil import local_to_epoch
    cubes, notes = [], []
    for p in sorted(paths):
        model, stamp = model_from_filename(p)
        try:
            fields = read_grib(p)
        except EncryptedGrib as e:
            notes.append(str(e))
            continue
        except UnsupportedGrib as e:
            notes.append(f"{model} ({os.path.basename(p)}): {e}; skipped")
            continue
        if not any(f.param == "u10" for f in fields):
            continue
        cubes.append(Cube(model, fields, p, local_to_epoch(stamp, tz) if stamp and tz else None))
    return cubes, notes
