import os
import struct

import pytest

from dayafter import net
from dayafter.ingest import bom, yb

from .conftest import FIXTURES, FLINDERS, requires_data


def encode(flags: int, ref: int, trackers: dict[int, list[tuple]]) -> bytes:
    """Encode AllPositions3 the way YB does: per tracker, fixes newest first, first absolute, then deltas.
    Each fix: (t, lat_e5, lon_e5, alt, dtf, lap, pc)."""
    out = struct.pack(">BI", flags, ref)
    for tid, fixes in trackers.items():
        fixes = sorted(fixes, key=lambda f: -f[0])
        out += struct.pack(">HH", tid, len(fixes))
        prev = None
        for f in fixes:
            t, la, lo, alt, dtf, lap, pc = f
            if prev is None:
                out += struct.pack(">Iii", t - ref, la, lo)
                if flags & 1: out += struct.pack(">h", alt)
                if flags & 2:
                    out += struct.pack(">i", dtf)
                    if flags & 4: out += struct.pack(">B", lap)
                if flags & 8: out += struct.pack(">i", pc)
            else:
                out += struct.pack(">Hhh", 0x8000 | (prev[0] - t), la - prev[1], lo - prev[2])
                if flags & 1: out += struct.pack(">h", alt)
                if flags & 2:
                    out += struct.pack(">h", dtf - prev[4])
                    if flags & 4: out += struct.pack(">B", lap)
                if flags & 8: out += struct.pack(">h", pc)
            prev = f
    return out


def test_yb_fixture_vector():
    raw = bytes.fromhex(open(os.path.join(FIXTURES, "flinders_2026", "yb_allpositions3_head_team2.hex"), encoding="ascii").read().strip())
    tr = yb.decode_allpositions3(raw)[2]
    assert len(tr.t) == 121
    assert (tr.t[-1], round(tr.lat[-1], 5), round(tr.lon[-1], 5)) == (1790460000, -33.8741, 151.2332)
    assert (tr.t[0], round(tr.lat[0], 5), round(tr.lon[0], 5)) == (1790226684, -33.87438, 151.23318)
    assert all(a <= b for a, b in zip(tr.t, tr.t[1:]))  # oldest first; YB repeats a few fixes verbatim
    d = tr.deduplicated()
    assert len(d.t) == 118 and all(a < b for a, b in zip(d.t, d.t[1:]))


@pytest.mark.parametrize("flags", [0, 1, 2, 3, 6, 15])
def test_yb_round_trip_with_optional_fields(flags):
    ref = 1720000000
    fixes = [(ref + 1000 + 600 * k, -3386000 - 50 * k, 15125000 + 30 * k, 3, 900000 - 1000 * k, 1, 20 * k)
             for k in range(5)]
    tracks = yb.decode_allpositions3(encode(flags, ref, {7: fixes, 9: fixes[:2]}))
    assert sorted(tracks) == [7, 9]
    t7 = tracks[7]
    assert list(t7.t) == [f[0] for f in fixes]
    assert [round(v, 5) for v in t7.lat] == [f[1] / 1e5 for f in fixes]
    if flags & 2:
        assert list(t7.dtf) == [f[4] for f in fixes]


def test_yb_rejects_truncated_or_trailing_bytes():
    good = encode(0, 1720000000, {1: [(1720000600, 1, 2, 0, 0, 0, 0), (1720001200, 3, 4, 0, 0, 0, 0)]})
    with pytest.raises(ValueError):
        yb.decode_allpositions3(good[:-1])
    with pytest.raises(ValueError):
        yb.decode_allpositions3(good + b"\x00")


def test_race_setup_and_boatids(tmp_path):
    setup = ('{"url":"bwps2026_2","title":"2. Tollgate Islands Race 2026","tz":"AEDT","tzOffset":39600,'
             '"start":1792022400,"stop":1793404800,"tags":[{"start":1792119600}],'
             '"teams":[{"id":2,"name":"Wot\'s Next","sail":"","model":""}],'
             '"associated2":[{"name":"1. Flinders Islet Race 2026","url":"Bwps2026"}]}').encode("latin-1")
    info = yb.parse_race_setup(setup)
    assert info["gun"] == 1792119600 and info["teams"][2]["name"] == "Wot's Next"
    assert info["associated"] == [("1. Flinders Islet Race 2026", "Bwps2026")]
    p = tmp_path / "BWPS2026-boatids.txt"
    p.write_text("1,Spare 1\n2,Wot's Next\nnot a row\n", encoding="utf-8")
    assert yb.read_boatids(str(p)) == {1: "Spare 1", 2: "Wot's Next"}


@requires_data
def test_flinders_allpositions3_file():
    tracks = yb.read_allpositions3(os.path.join(FLINDERS, "yb_bwps2026_AllPositions3.bin"))
    assert len(tracks) == 36


AXF = """[notice]
copyright ...
[header]
refresh_message="Issued at  9:52 pm EST Saturday 26 September 2026"
[data]
sort_order,wmo,name[80],history_product[80],local_date_time[80],local_date_time_full[80],aifstime_utc[80],lat,lon,apparent_t,cloud[80],gust_kt,air_temp,press,press_msl,wind_dir[80],wind_spd_kt
0,95768,"North Head","IDN60701","26/06:30am","20260926063000","20260925203000",-33.8,151.3,13.0,"-",3,-9999.0,-9999.0,1024.5,"NNW",1
1,95768,"North Head","IDN60701","26/06:00am","20260926060000","20260925200000",-33.8,151.3,13.0,"-",5,14.2,-9999.0,1024.4,"CALM",0
[$]
"""


def test_bom_axf():
    o = bom.parse_axf(AXF)
    assert o["name"] == "North Head" and o["wmo"] == "95768"
    assert list(o["t"]) == sorted(o["t"])  # oldest first
    assert o["wind_dir"][1] == 337.5 and o["press_msl"][1] == 1024.5
    assert o["air_temp"][1] != o["air_temp"][1]  # -9999 -> NaN (on the newer row)
    assert o["wind_dir"][0] != o["wind_dir"][0]  # CALM -> NaN


def test_save_atomic_never_replaces_good_with_worse(tmp_path):
    def validate(b):
        if not b.startswith(b"OK"):
            raise ValueError("bad")
    p = str(tmp_path / "f.bin")
    assert net.save_atomic(p, b"OK-long-and-good", validate=validate) == p
    with pytest.raises(ValueError):
        net.save_atomic(p, b"garbage", validate=validate)
    kept = net.save_atomic(p, b"OK-short", validate=validate)
    assert kept != p and open(p, "rb").read() == b"OK-long-and-good"
    assert net.save_atomic(p, b"OK-long-and-good", validate=validate) == p
