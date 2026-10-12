import numpy as np

from dayafter.analysis import fleet as FL
from dayafter.ingest.course import Course, Mark, assign_roles
from dayafter.ingest.results import Result

T0 = 1790380800.0


def out_and_back() -> Course:
    """Start → corner (Cape) → turning mark 20 nm south → corner → finish: legs on the same line both ways."""
    ms = [Mark("Start", -33.85, 151.28), Mark("Cape", -34.00, 151.26), Mark("Turn", -34.30, 151.10),
          Mark("Cape (ret)", -34.00, 151.26), Mark("Finish", -33.85, 151.28)]
    c = Course("test", ms, "")
    return assign_roles(c, "Turn")


def boat_path(c: Course, offset_deg: float = 0.0, speed_kt: float = 8.0, step_s: float = 600.0):
    """A boat sailing the course polyline at constant speed, `offset_deg` of longitude east of it."""
    xy, cx, cy, cum = FL.course_geometry(c)
    total = cum[-1]
    n = int(total / speed_kt * 3600 / step_s) + 2
    s = np.minimum(np.arange(n) * speed_kt * step_s / 3600.0, total)
    x, y = np.interp(s, cum, cx), np.interp(s, cum, cy)
    lat, lon = xy.latlon(x, y)
    return T0 + np.arange(n) * step_s, lat, lon + offset_deg, s


def test_progress_follows_the_course_and_never_decreases():
    c = out_and_back()
    t, lat, lon, s_true = boat_path(c)
    rt = FL.rounding_time(t, lat, lon, c.turning_mark)
    s = FL.progress(t, lat, lon, c, None, rt, c.turning_index())
    assert np.all(np.diff(s) >= 0)
    off = t != rt  # at the rounding fix progress is the mark itself, up to half a fix interval from the boat
    assert np.max(np.abs(s - s_true)[off]) < 0.2  # on the line, progress is the distance sailed


def test_wide_of_a_corner_still_advances():
    """1.5 nm outside the corners: projecting on the nearest polyline point would stall at each vertex."""
    c = out_and_back()
    t, lat, lon, s_true = boat_path(c, offset_deg=0.03)
    rt = FL.rounding_time(t, lat, lon, c.turning_mark)
    s = FL.progress(t, lat, lon, c, None, rt, c.turning_index())
    steps = np.diff(s)[(np.diff(s_true) > 0.5) & (t[1:] != rt) & (t[:-1] != rt)]
    assert steps.min() > 0.6, steps.min()  # every fix advances (8 kt = 1.33 nm per fix)
    assert abs(s[-1] - s_true[-1]) < 1.0


def test_abeam_of_the_turning_mark_is_not_a_rounding():
    c = out_and_back()
    t, lat, lon, _ = boat_path(c)
    rt = FL.rounding_time(t, lat, lon, c.turning_mark)
    s = FL.progress(t, lat, lon, c, None, rt, c.turning_index())
    turn_s = FL.course_geometry(c)[3][c.turning_index()]
    assert np.all(s[t < rt] < turn_s) and s[t == rt][0] == turn_s


def test_gate_times_interpolate_and_use_the_official_finish():
    t = T0 + np.array([0, 600, 1200, 1800.0])
    s = np.array([0.0, 1.0, 3.0, 4.0])
    g = FL.gate_times(t, s, np.array([2.0, 5.0]), T0, 4000.0, 5.0)
    assert g[0] == 900.0 and g[1] == 4000.0


def test_name_matching_and_default_rivals():
    res = [Result(1, "Ataraxia", "", "2", False, 1.0, 40000, "FINISHED"),
           Result(2, "Wots Next", "", "1", False, 1.172, 48354, "FINISHED"),
           Result(3, "Llama II", "", "2", False, 1.136, 47985, "FINISHED"),
           Result(4, "Calibre 12", "", "2", False, 1.132, 47337, "FINISHED"),
           Result(None, "Jupiter", "", "2", True, 1.007, None, "RETIRED")]
    m = FL.match_names({41: "Artaraxia", 2: "Wot's Next", 9: "Spare 3", 50: "Llama II (DH)"}, res)
    assert m[41].yacht == "Ataraxia" and m[2].yacht == "Wots Next" and m[50].yacht == "Llama II" and 9 not in m
    assert FL.default_rivals(res[2], res) == ["Calibre 12", "Ataraxia"]


def test_no_rounding_found_means_no_turning_constraint():
    """A boat that never came within 5 nm of the turning mark must not be teleported to it."""
    c = out_and_back()
    t, lat, lon, s_true = boat_path(c)
    s = FL.progress(t[:10], lat[:10], lon[:10], c, None, None, c.turning_index())
    assert s[0] < 0.5 and np.max(np.abs(s - s_true[:10])) < 0.2
