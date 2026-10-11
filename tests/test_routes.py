import datetime as dt
import os

import numpy as np
import pytest

from dayafter.core.timeutil import fmt_local
from dayafter.ingest.routes import read_route_summary, read_route_table

from .conftest import FLINDERS, requires_data, route_table_text, tollgate_like_rows


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_synthetic_route_table(tmp_path):
    rows = tollgate_like_rows(change_at=dt.datetime(2026, 10, 16, 23, 0))
    rows[1]["twa"] = "(-173)"
    path = _write(tmp_path, "ECMWF_15_1900_15oct2026.csv", route_table_text(rows, model="ECMWF"))
    r = read_route_table(path)
    assert r.model == "ECMWF" and r.grib_cycle == "15_1900"
    assert r.tz == "Australia/Sydney"
    assert fmt_local(r.start, r.tz, "%d %b %H:%M %Z") == "16 Oct 17:00 AEDT"
    assert len(r) == len(rows)
    # magnetic -> true with the latitude table (about 12.8-13.3 degrees east on this course)
    assert 12.7 < r.get("twd")[0] - 25.0 < 13.4
    assert r.twa_paren[1] and r.get("twa")[1] == -173
    assert r.mark_rows()[0][1] == "Start"
    assert not r.has("cape")
    assert r.created is not None and fmt_local(r.created, r.tz, "%H:%M") == "19:05"


def test_variation_override(tmp_path):
    rows = tollgate_like_rows(change_at=dt.datetime(2026, 10, 16, 23, 0))
    path = _write(tmp_path, "GFS_15_1900_15oct2026.csv", route_table_text(rows))
    r = read_route_table(path, variation_override=10.0)
    assert r.get("twd")[0] == pytest.approx(35.0)


def test_route_summary(tmp_path):
    text = ("Draw,Name,Colour,Route nm,Optimal nm,Elapsed time,Finish,Delta,Created\n"
            " G ,G ACCESS SY High 06:34:23,,88.15,91.01,11h 04m 45s,26-Sep-2026 21:04:45,-47m 52s,26-Sep-2026 06:34:23\n"
            " G ,G  High 06:38:43,,88.15,91.75,11h 52m 37s,26-Sep-2026 21:52:37,,26-Sep-2026 06:38:43\n")
    s = read_route_summary(_write(tmp_path, "summary of all routes_26sep2026_0600.csv", text))
    a, ref = s.rows
    assert (a.model, a.label, a.run, a.elapsed, a.delta) == ("ACCESS", "ACCESS SY", "06:34:23", 39885, -2872)
    assert fmt_local(a.finish, s.tz, "%H:%M:%S") == "21:04:45"
    assert ref.is_reference and ref.delta is None


@requires_data
def test_flinders_route_tables():
    r = read_route_table(os.path.join(FLINDERS, "routes", "GFS_25_1800_25sep2026.csv"))
    assert r.model == "GFS" and len(r) == 20
    assert r.get("brg_mag")[0] == 29 and r.get("brg")[0] == pytest.approx(41.8, abs=0.05)  # 029°M = 041.8°T
    names = [n for _, n, _ in r.mark_rows()]
    assert names[0] == "Start" and names[-1] == "Finish" and names.count("Cape Banks") == 2
    assert np.all(np.diff(r.t) >= 0)
