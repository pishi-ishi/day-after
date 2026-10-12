"""Manoeuvre detection and loss on a synthetic tack, and the season database round trip (no private data)."""
from types import SimpleNamespace

import numpy as np

from dayafter import season
from dayafter.analysis import performance


def _fake_analysis(n=600):
    t = np.arange(n, dtype=float) + 1_790_000_000
    tl = SimpleNamespace(t=t)
    return SimpleNamespace(tl=tl, start=t[0], finish=t[-1], events=[])


def test_tack_detected_with_its_loss():
    a = _fake_analysis()
    n = len(a.tl.t)
    twa = np.where(np.arange(n) < 300, 42.0, -42.0)
    stw = np.full(n, 7.0)
    stw[290:330] = np.linspace(4.0, 7.0, 40)  # slow through the tack, back up in 40 s
    tws = np.full(n, 14.0)
    ms = performance.manoeuvres(a, twa, tws, stw)
    assert len(ms) == 1
    m = ms[0]
    assert m.kind == "tack" and abs(m.t - a.tl.t[300]) <= 5
    vmg = 7.0 * np.cos(np.radians(42))
    lost_kt_s = float(np.sum((7.0 - stw[285:345]) * np.cos(np.radians(42))))
    assert abs(m.loss_m - lost_kt_s * 1852 / 3600) < 1.0
    assert abs(m.loss_s - m.loss_m / (vmg * 1852 / 3600)) < 0.01


def test_gybe_and_a_course_change():
    a = _fake_analysis(900)
    n = len(a.tl.t)
    twa = np.where(np.arange(n) < 300, 150.0, -150.0)
    twa[600:] = -100.0  # then a bear-up to a reach on the same gybe: not a manoeuvre
    stw = np.full(n, 9.0)
    ms = performance.manoeuvres(a, twa, np.full(n, 20.0), stw)
    assert [m.kind for m in ms] == ["gybe"] and abs(ms[0].loss_m) < 1


def test_season_round_trip(tmp_path):
    check = SimpleNamespace(id="speed", status="warn", value="× 1.258", data={"k": 1.258})
    res = SimpleNamespace(place=15, corrected=47985.0, tcc=1.136, finished=True, division="2")
    phase = SimpleNamespace(kind="leg", tws=19.0, minutes=60.0, tws_p95=27.0)
    a = SimpleNamespace(gun=1_790_380_800.0, tz="Australia/Sydney", race_name="Test Race", boat="Llama II",
                        folder="/tmp/x", fleet=None, result=res, results=[res], elapsed=42240.0, k=1.258,
                        phases=[phase], checks=[check], forecasts=[], forecast=None)
    perf = SimpleNamespace(phases=[SimpleNamespace(n=100, pct=95.0)], twa_source="logged",
                           buckets=[{"tws0": 18.0, "tws1": 20.0, "pos": "downwind", "n": 600, "pct": 99.0, "p25": 92.0,
                                     "p75": 106.0, "indicative": False}],
                           targets=[], by_sail=[], manoeuvres=[])
    db = str(tmp_path / "season.sqlite")
    rid = season.store(a, perf, db)
    rid2 = season.store(a, perf, db)
    assert rid == rid2 == "2026-09-26 Test Race"
    s = season.load(db)
    assert len(s["races"]) == 1 and s["races"][0]["polar_pct"] == 95.0
    assert s["perf"] == [{"race_id": rid, "pos": "downwind", "n": 600, "pct": 99.0}]
    assert s["calibration"][0]["check_id"] == "speed"
    assert season.load(str(tmp_path / "missing.sqlite")) == {"races": []}
