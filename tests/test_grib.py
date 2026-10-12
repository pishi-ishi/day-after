"""GRIB decoding: public test vectors checked against eccodes' output, synthetic GRIB1 / GRIB2 5.0 messages,
encrypted-file detection, and sampling in space and time."""
import json
import os
import struct

import numpy as np
import pytest

from dayafter.ingest import grib

HERE = os.path.dirname(__file__)
VEC = os.path.join(HERE, "..", "fixtures", "grib")
DATA = os.path.join(HERE, "..", "data", "flinders_2026", "gribs")


def _expected():
    with open(os.path.join(VEC, "expected.json"), encoding="utf-8") as f:
        return json.load(f)["files"]


@pytest.mark.parametrize("name", sorted(_expected()))
def test_vectors_match_eccodes(name):
    exp = _expected()[name]
    got = grib.read_grib(os.path.join(VEC, name), raw=True)
    assert len(got) == len(exp)
    for f, e in zip(got, exp):
        assert f.param == e["param"]
        assert list(f.shape) == e["shape"]
        assert f.valid == e["valid"]
        assert f.lat0 == pytest.approx(e["lat_south"], abs=1e-6)
        v = f.values
        assert int(np.isnan(v).sum()) == e["missing"]
        scale = max(abs(e["max"]), abs(e["min"]), 1e-12)
        assert np.nanmin(v) == pytest.approx(e["min"], abs=1e-9 * scale)
        assert np.nanmax(v) == pytest.approx(e["max"], abs=1e-9 * scale)
        assert np.nanmean(v) == pytest.approx(e["mean"], abs=1e-9 * scale)
        for j, i, x in e["samples"]:
            assert v[j, i] == pytest.approx(x, abs=1e-9 * scale)


def test_units_and_valid_time_of_statistical_fields():
    (tp,) = grib.read_grib(os.path.join(VEC, "ecmwf_tp_pdt8.grb2"))
    assert tp.param == "acc" and tp.valid > tp.start  # metres -> mm, valid at the end of the interval
    raw = grib.read_grib(os.path.join(VEC, "ecmwf_tp_pdt8.grb2"), raw=True)[0]
    assert np.allclose(tp.values, raw.values * 1000)
    (g,) = grib.read_grib(os.path.join(VEC, "icon_gust_pdt8_minutes.grb2"))
    assert g.param == "gust" and (g.valid - g.ref) % 3600 == 0 and g.valid > g.start
    u, v = grib.read_grib(os.path.join(VEC, "gfs_011_wind_gaussian.grb2"))
    assert (u.param, v.param) == ("u10", "v10") and u.dlat == pytest.approx(0.11715, abs=1e-4)


def test_encrypted_files_are_refused(tmp_path):
    p = tmp_path / "EX_ACCESS_Sydney_0013_26Sep26_060031.grb"
    p.write_bytes(b"grbenc01" + os.urandom(64))
    with pytest.raises(grib.EncryptedGrib):
        grib.read_grib(str(p))
    cubes, notes = grib.load_cubes([str(p)])
    assert cubes == [] and "encrypted" in notes[0]


def test_model_and_download_time_from_filename():
    m, stamp = grib.model_from_filename("EX_ECMWF_025_26Sep26_083458.grb")
    assert m == "ECMWF" and stamp.isoformat() == "2026-09-26T08:34:58"
    assert grib.model_from_filename("EX_EC_AIFS_025_26Sep26_072204.grb")[0] == "AIFS"
    assert grib.model_from_filename("EX_GFS_011_26Sep26_072204.grb")[0] == "GFS"


# ---------------------------------------------------------------- synthetic messages

def _bits(values, width):
    s = "".join(format(int(v), f"0{width}b") for v in values)
    s += "0" * (-len(s) % 8)
    return int(s, 2).to_bytes(len(s) // 8, "big") if s else b""


def _ibm(x: float) -> bytes:
    if x == 0:
        return b"\0\0\0\0"
    s = 0x80 if x < 0 else 0
    x = abs(x)
    e = 64
    while x >= 1:
        x /= 16
        e += 1
    while x < 1 / 16:
        x *= 16
        e -= 1
    return bytes([s | e]) + int(x * (1 << 24)).to_bytes(3, "big")


def _sm(v: int, n: int) -> bytes:
    return ((1 << (8 * n - 1)) | -v).to_bytes(n, "big") if v < 0 else v.to_bytes(n, "big")


def grib1_message(values: np.ndarray, *, param=33, lat1=-33.0, lon1=151.0, d=0.5, hour=6, nbits=12, dscale=1) -> bytes:
    """GRIB1, lat/lon grid scanning north -> south, simple packing (what Saildocs sends)."""
    nj, ni = values.shape
    flat = values.ravel()  # rows north -> south
    ref = float(np.floor(flat.min() * 10 ** dscale))
    scaled = flat * 10 ** dscale - ref
    E = 0
    while scaled.max() / 2 ** E > 2 ** nbits - 1:
        E += 1
    packed = np.round(scaled / 2 ** E).astype(int)
    pds = bytearray(28)
    pds[0:3] = (28).to_bytes(3, "big")
    pds[3], pds[4], pds[5], pds[6], pds[7], pds[8] = 2, 7, 81, 255, 0x80, param
    pds[9], pds[10:12] = 105, (10).to_bytes(2, "big")
    pds[12:17] = bytes([26, 9, 26, 0, 0])
    pds[17], pds[18], pds[19], pds[20] = 1, hour, 0, 0
    pds[24], pds[26:28] = 21, _sm(dscale, 2)
    gds = bytearray(32)
    gds[0:3] = (32).to_bytes(3, "big")
    gds[5] = 0
    gds[6:8], gds[8:10] = ni.to_bytes(2, "big"), nj.to_bytes(2, "big")
    gds[10:13], gds[13:16] = _sm(int(lat1 * 1000), 3), _sm(int(lon1 * 1000), 3)
    gds[16] = 0x80
    gds[17:20] = _sm(int((lat1 - (nj - 1) * d) * 1000), 3)
    gds[20:23] = _sm(int((lon1 + (ni - 1) * d) * 1000), 3)
    gds[23:25] = gds[25:27] = int(d * 1000).to_bytes(2, "big")
    gds[27] = 0  # +i, -j (north -> south)
    data = _bits(packed, nbits)
    bds = bytearray(11) + data
    bds[0:3] = len(bds).to_bytes(3, "big")
    bds[3] = 0
    bds[4:6] = _sm(E, 2)
    bds[6:10] = _ibm(ref)
    bds[10] = nbits
    body = bytes(pds) + bytes(gds) + bytes(bds)
    total = 8 + len(body) + 4
    return b"GRIB" + total.to_bytes(3, "big") + b"\x01" + body + b"7777"


def grib2_simple(fields: list[tuple[int, int, int, np.ndarray]], *, lat1=-35.0, lon1=150.5, d=0.25, nbits=16) -> bytes:
    """GRIB2 with one message holding several fields (sections 4-7 repeated), template 3.0 scanning south ->
    north, product 4.0 at 10 m, data 5.0 simple packing."""
    nj, ni = fields[0][3].shape
    sec1 = bytearray(21)
    sec1[0:4], sec1[4] = (21).to_bytes(4, "big"), 1
    sec1[5:7] = (7).to_bytes(2, "big")
    sec1[12:19] = bytes([0x07, 0xEA, 9, 26, 0, 0, 0])
    sec3 = bytearray(72)
    sec3[0:4], sec3[4] = (72).to_bytes(4, "big"), 3
    sec3[6:10] = (ni * nj).to_bytes(4, "big")
    sec3[12:14] = (0).to_bytes(2, "big")
    sec3[30:34], sec3[34:38] = ni.to_bytes(4, "big"), nj.to_bytes(4, "big")
    sec3[46:50], sec3[50:54] = _sm(int(lat1 * 1e6), 4), _sm(int(lon1 * 1e6), 4)
    sec3[55:59] = _sm(int((lat1 + (nj - 1) * d) * 1e6), 4)
    sec3[59:63] = _sm(int((lon1 + (ni - 1) * d) * 1e6), 4)
    sec3[63:67] = sec3[67:71] = int(d * 1e6).to_bytes(4, "big")
    sec3[71] = 0x40  # +i, +j (south -> north)
    body = bytes(sec1) + bytes(sec3)
    for cat, num, hour, vals in fields:
        sec4 = bytearray(34)
        sec4[0:4], sec4[4] = (34).to_bytes(4, "big"), 4
        sec4[7:9] = (0).to_bytes(2, "big")
        sec4[9], sec4[10], sec4[17] = cat, num, 1
        sec4[18:22] = hour.to_bytes(4, "big")
        sec4[22], sec4[23], sec4[24:28] = 103, 0, (10).to_bytes(4, "big")
        flat = vals.ravel()
        R = float(flat.min())
        D, E = 2, 0
        scaled = (flat - R) * 10 ** D
        packed = np.round(scaled).astype(int)
        sec5 = bytearray(21)
        sec5[0:4], sec5[4] = (21).to_bytes(4, "big"), 5
        sec5[5:9] = len(flat).to_bytes(4, "big")
        sec5[9:11] = (0).to_bytes(2, "big")
        sec5[11:15] = struct.pack(">f", R * 10 ** D)
        sec5[15:17], sec5[17:19], sec5[19] = _sm(E, 2), _sm(D, 2), nbits
        sec6 = bytes([0, 0, 0, 6, 6, 255])
        data = _bits(packed, nbits)
        sec7 = (5 + len(data)).to_bytes(4, "big") + b"\x07" + data
        body += bytes(sec4) + bytes(sec5) + sec6 + sec7
    total = 16 + len(body) + 4
    return b"GRIB\0\0\0\x02" + total.to_bytes(8, "big") + body + b"7777"


def test_grib1_simple_packing(tmp_path):
    vals = np.array([[5.0, 6.5, 8.0], [7.3, 9.0, 12.5]])  # north row first; 0.1 m/s resolution (dscale 1)
    p = tmp_path / "SD_GFS_test.grb"
    p.write_bytes(grib1_message(vals, hour=6) + grib1_message(vals * 2, hour=12))
    fs = grib.read_grib(str(p))
    assert [f.param for f in fs] == ["u10", "u10"]
    f = fs[0]
    assert f.lat0 == pytest.approx(-33.5) and f.lon0 == pytest.approx(151.0) and f.dlat == pytest.approx(0.5)
    assert np.allclose(f.values, vals[::-1] * grib.MS_TO_KT, atol=0.02)  # rows now south -> north
    assert fs[1].valid - fs[1].ref == 12 * 3600


def test_grib2_simple_packing_and_multi_field(tmp_path):
    u = np.arange(12, dtype=float).reshape(3, 4) + 0.5
    v = -np.arange(12, dtype=float).reshape(3, 4)
    p = tmp_path / "EX_GFS_025_26Sep26_060000.grb"
    p.write_bytes(grib2_simple([(2, 2, 0, u), (2, 3, 0, v), (2, 2, 3, u * 2), (2, 3, 3, v * 2)]))
    fs = grib.read_grib(str(p))
    assert [f.param for f in fs] == ["u10", "v10", "u10", "v10"]
    assert np.allclose(fs[0].values, u * grib.MS_TO_KT, atol=1e-6)
    assert np.allclose(fs[1].values, v * grib.MS_TO_KT, atol=1e-6)
    cube = grib.Cube("GFS", fs, str(p))
    lat0, lon0 = -35.0, 150.5
    # bilinear in space is exact for a field linear in i and j; linear in time between the two steps
    t_mid = cube.t_range[0] + 1.5 * 3600
    got = cube.sample("u10", [t_mid], [lat0 + 0.125], [lon0 + 0.375])[0]
    at = lambda g: (g[0, 1] + g[0, 2] + g[1, 1] + g[1, 2]) / 4  # centre of cells (j 0.5, i 1.5)
    assert got == pytest.approx((at(u) + at(u * 2)) / 2 * grib.MS_TO_KT, rel=1e-9)
    assert np.isnan(cube.sample("u10", [t_mid], [lat0 - 1], [lon0])[0])  # outside the grid
    tws, twd = cube.wind([cube.t_range[0]], [lat0], [lon0 + 0.25])  # u 1.5, v -1: wind from the north-west
    assert twd[0] == pytest.approx((np.degrees(np.arctan2(-1.5, 1.0)) + 360) % 360)


def test_accumulations_become_rates():
    mk = lambda start, valid, v: grib.Field("acc", 0.0, valid, start, -35, 150, 1, 1, np.full((2, 2), v))
    # accumulated since the run start: 0-3 h 3 mm, 0-6 h 9 mm -> 1 mm/h then 2 mm/h
    c = grib.Cube("ECMWF", [mk(0, 3 * 3600, 3.0), mk(0, 6 * 3600, 9.0),
                            grib.Field("u10", 0.0, 0, 0, -35, 150, 1, 1, np.zeros((2, 2)))])
    assert [float(f.values[0, 0]) for f in c.series["prate"]] == [1.0, 2.0]
    # one interval per message (ICON): 3-6 h 6 mm -> 2 mm/h
    c = grib.Cube("ICON", [mk(3 * 3600, 6 * 3600, 6.0)])
    assert float(c.series["prate"][0].values[0, 0]) == 2.0


@pytest.mark.data
def test_flinders_gribs_match_eccodes():
    eccodes = pytest.importorskip("eccodes")
    if not os.path.isdir(DATA):
        pytest.skip("private Flinders data not present")
    eccodes.codes_grib_multi_support_on()
    names = [n for n in sorted(os.listdir(DATA)) if n.endswith("_26Sep26_083458.grb")]
    checked = 0
    for n in names:
        p = os.path.join(DATA, n)
        try:
            mine = grib.read_grib(p, raw=True)
        except grib.EncryptedGrib:
            continue
        ref = []
        with open(p, "rb") as fh:
            while (h := eccodes.codes_grib_new_from_file(fh)) is not None:
                ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
                vals = eccodes.codes_get_values(h)
                g = np.where(vals == eccodes.codes_get(h, "missingValue"), np.nan, vals).reshape(nj, ni)
                ref.append(g[::-1] if eccodes.codes_get(h, "jScansPositively") == 0 else g)
                eccodes.codes_release(h)
        mine = [f for f in mine]
        assert len(mine) == len(ref), n
        for f, g in zip(mine, ref):
            assert np.allclose(f.values, g, rtol=1e-9, atol=1e-9 * max(1.0, float(np.nanmax(np.abs(g), initial=0.0))), equal_nan=True), n
            checked += 1
    assert checked > 100
