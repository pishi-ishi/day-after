import numpy as np
import pytest

from dayafter.analysis import weather as W

T0 = 1792130400.0  # 16 Oct 2026 17:00 AEDT


def series(dirs, speeds=None, step=600.0):
    t = T0 + step * np.arange(len(dirs))
    return t, np.asarray(dirs, float), np.asarray(speeds if speeds is not None else [15.0] * len(dirs), float)


def test_sharp_change_is_found_at_the_right_time():
    t, d, s = series([20] * 12 + [170] * 12, [12] * 12 + [24] * 12)
    c = W.detect_change(t, d, s)
    assert c is not None
    assert abs(c.t - (T0 + 11.5 * 600)) <= 600       # between the last NNE and the first S row
    assert c.twd_from == pytest.approx(20, abs=1) and c.twd_to == pytest.approx(170, abs=1)
    assert c.swing == pytest.approx(150, abs=1) and c.kind == "veer"
    assert c.tws_after > c.tws_before


def test_backing_change_through_north():
    t, d, s = series([60] * 10 + [300] * 10)
    c = W.detect_change(t, d, s)
    assert c is not None and c.swing == pytest.approx(-120, abs=1) and c.kind == "back"


def test_slow_drift_is_not_a_change():
    t, d, s = series(np.arange(0, 240, 6) % 360)       # 36 degrees an hour for 6+ hours
    assert W.detect_change(t, d, s) is None


def test_light_air_flip_that_does_not_hold_is_ignored():
    dirs = [30] * 8 + [270, 90, 260] + [35] * 8          # variable patch, then back to the old breeze
    t, d, s = series(dirs, [10] * 8 + [3, 3, 3] + [10] * 8)
    assert W.detect_change(t, d, s) is None


def test_sparse_route_rows_still_resolve():
    t = T0 + np.array([0, 40, 95, 150, 200, 260]) * 60.0  # irregular route-table spacing
    d = np.array([15, 18, 25, 160, 165, 168], float)
    c = W.detect_change(t, d, np.full(6, 12.0))
    assert c is not None and T0 + 95 * 60 <= c.t <= T0 + 150 * 60


def test_supporting_signs():
    t, d, s = series([20] * 12 + [170] * 12)
    c = W.detect_change(t, d, s)
    p = np.r_[np.linspace(1014, 1010, 12), np.linspace(1011, 1016, 12)]
    a = np.r_[[22.0] * 12, [17.0] * 12]
    r = np.r_[[0.0] * 11, [0.4] * 13]
    sg = W.supporting_signs(c, t, p, a, r)
    assert sg["pressure_min"]["hpa"] == pytest.approx(1010) and sg["pressure_rise_3h"] >= 4
    assert sg["temp_drop"] == pytest.approx(5.0)
    assert sg["rain_onset"] == pytest.approx(t[11])


def test_hourly_shifts_and_compass():
    t, d, s = series([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60])
    shifts = W.hourly_shifts(W.wind_grid(t, d, s), min_shift=15)
    assert shifts and all(x["kind"] == "veer" for x in shifts)
    assert W.compass(0) == "N" and W.compass(169) == "S" and W.compass(337.5) == "NNW"
    assert W.compass(348.7) == "NNW" and W.compass(348.8) == "N" and W.compass(float("nan")) == "–"
