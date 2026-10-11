import datetime as dt
import math

import numpy as np
import pytest

from dayafter.core import geo, magvar, timeutil
from dayafter.core.wxmodel import canonical_model


def test_excel_serial_round_trip():
    assert timeutil.excel_to_epoch(25569.0) == 0.0
    t = timeutil.excel_to_epoch(46290.827624)  # Flinders log sample: 2026-09-25 19:51 UTC
    assert dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M") == "2026-09-25 19:51"
    arr = timeutil.excel_to_epoch(np.array([25569.0, 25570.0]))
    assert list(arr) == [0.0, 86400.0]


@pytest.mark.parametrize("local, epoch", [
    (dt.datetime(2026, 9, 26, 10, 0), 1790380800),    # Flinders gun, AEST (UTC+10)
    (dt.datetime(2026, 10, 16, 14, 0), 1792119600),   # Tollgate gun, AEDT (UTC+11) after 4 Oct
    (dt.datetime(2026, 12, 26, 13, 0), 1798250400),   # Sydney-Hobart gun, AEDT
])
def test_sydney_wall_clock(local, epoch):
    assert timeutil.local_to_epoch(local, "Australia/Sydney") == epoch


def test_route_table_zone_header():
    assert timeutil.tz_from_windows_id("AUS Eastern Standard Time") == "Australia/Sydney"
    assert timeutil.tz_from_windows_id("Tasmania Standard Time") == "Australia/Hobart"
    assert timeutil.tz_from_windows_id("Mars Standard Time") is None


@pytest.mark.parametrize("text, sec", [
    ("13:19:45", 47985), ("1:02:03:04", 93784), ("11h 04m 45s", 39885), ("-47m 52s", -2872),
    ("-01h 55m 10s", -6910), ("04m 32s", 272), ("", None), ("2:30", 9000),
])
def test_parse_duration(text, sec):
    assert timeutil.parse_duration(text) == sec


def test_format_helpers():
    assert timeutil.fmt_duration(42240.3) == "11:44:00"
    assert timeutil.fmt_duration(-90061) == "−1:01:01:01"
    assert timeutil.fmt_minutes(-240) == "−4 min"
    assert timeutil.utc_offset_label(1792119600, "Australia/Sydney") == "AEDT (UTC+11)"


def test_ddm_and_distance():
    assert geo.parse_ddm("33 51.6390s") == pytest.approx(-33.86065)
    assert geo.parse_ddm("151 14.8560e") == pytest.approx(151.2476)
    with pytest.raises(ValueError):
        geo.parse_ddm("33.86S")
    # one minute of latitude is one nautical mile
    assert geo.haversine_nm(-34.0, 151.0, -34.0 + 1 / 60, 151.0) == pytest.approx(1.0, rel=2e-3)


def test_angles():
    assert geo.angdiff(10, 350) == 20          # veer through north
    assert geo.angdiff(350, 10) == -20         # back through north
    assert geo.circmean([350, 10]) == pytest.approx(0.0, abs=1e-9) or geo.circmean([350, 10]) == pytest.approx(360.0)
    assert math.isnan(geo.circmean([0, 180]))  # opposite vectors cancel
    assert geo.circmean([90, 270], [3, 1]) == pytest.approx(90.0)
    t = np.array([0.0, 100.0])
    assert geo.interp_direction(np.array([50.0]), t, np.array([350.0, 10.0]))[0] == pytest.approx(0.0, abs=1e-6) or \
        geo.interp_direction(np.array([50.0]), t, np.array([350.0, 10.0]))[0] == pytest.approx(360.0, abs=1e-6)


def test_magnetic_variation():
    assert magvar.variation_deg_e(-33.85) == pytest.approx(12.8)
    assert magvar.variation_deg_e(-42.9) == pytest.approx(15.0)
    assert 12.8 < magvar.variation_deg_e(-35.75) < 13.5
    assert magvar.variation_deg_e(-33.85, override=12.5) == 12.5
    assert list(magvar.variation_deg_e(np.array([-33.85, -33.85]), override=11.0)) == [11.0, 11.0]


@pytest.mark.parametrize("label, model", [
    ("ACCESS SY", "ACCESS"), ("ACCESS_1", "ACCESS"), ("EC_AIFS", "AIFS"), ("AIFS", "AIFS"), ("AIGFS", "AIGFS"),
    ("ECMWF", "ECMWF"), ("GFS", "GFS"), ("ICON", "ICON"), ("UM_Global", "UM"), ("", "Reference"),
])
def test_model_names(label, model):
    assert canonical_model(label) == model
