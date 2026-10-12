"""`dayafter selftest`: check this build against fixtures/ and, when present, the private data/ folder.

Each check returns a short detail string and raises AssertionError on failure or Skip when its inputs are
missing. The numbers come from docs/ACCEPTANCE.md (Flinders Islet Race 2026). Exit status 0 means no
failures; skipped checks (no data/ folder, e.g. in CI) do not fail the run.
"""
from __future__ import annotations

import os
import tempfile
import traceback

from . import resources


class Skip(Exception):
    pass


def _root(*parts: str) -> str:
    return os.path.join(resources.bundle_root(), *parts)


def _need(path: str) -> str:
    if not os.path.exists(path):
        raise Skip(f"{os.path.relpath(path, resources.bundle_root())} not present")
    return path


def _hm(t: float, tz: str = "Australia/Sydney") -> str:
    from .core.timeutil import fmt_local
    return fmt_local(t, tz, "%H:%M")


# --------------------------------------------------------------------------------------------- checks

def check_time_zones() -> str:
    import datetime as dt
    from .core import timeutil
    flinders = timeutil.local_to_epoch(dt.datetime(2026, 9, 26, 10, 0), "Australia/Sydney")
    assert flinders == 1790380800, flinders  # AEST, UTC+10 (ACCEPTANCE: gun epoch)
    tollgate = timeutil.local_to_epoch(dt.datetime(2026, 10, 16, 17, 0), "Australia/Sydney")
    assert tollgate == 1792130400, tollgate  # 06:00Z: Tollgate gun 17:00 AEDT (UTC+11)
    assert timeutil.excel_to_epoch(25569.0) == 0.0
    assert timeutil.parse_duration("13:19:45") == 47985
    return "AEST/AEDT, Excel serial and durations"


def check_yb_vector() -> str:
    from .ingest import yb
    hexfile = _need(_root("fixtures", "flinders_2026", "yb_allpositions3_head_team2.hex"))
    tr = yb.decode_allpositions3(bytes.fromhex(open(hexfile).read().strip()))[2]
    assert len(tr.t) == 121
    assert (int(tr.t[-1]), round(tr.lat[-1], 5), round(tr.lon[-1], 5)) == (1790460000, -33.87410, 151.23320)
    assert (int(tr.t[0]), round(tr.lat[0], 5), round(tr.lon[0], 5)) == (1790226684, -33.87438, 151.23318)
    return "tracker 2: 121 moments, first and last fix exact"


def check_yb_full_file() -> str:
    from .ingest import yb
    path = _need(_root("data", "flinders_2026", "yb_bwps2026_AllPositions3.bin"))
    data = open(path, "rb").read()
    tracks = yb.decode_allpositions3(data)  # raises unless every byte is consumed
    assert len(data) == 27443 and len(tracks) == 36, (len(data), len(tracks))
    return f"{len(data):,} bytes fully decoded, {len(tracks)} trackers"


def _briefing():
    from .analysis.briefing import build_briefing
    folder = _need(_root("data", "flinders_2026", "routes"))
    return build_briefing(os.path.dirname(folder))


def check_route_etas() -> str:
    b = _briefing()
    want = {"GFS": "16:04", "ECMWF": "17:08", "ACCESS": "16:05"}  # ACCEPTANCE splits at FI S
    got = {p.model: _hm(p.eta_turning, b.tz) for p in b.plans}
    assert got == want, got
    assert b.turning_name.endswith("S"), b.turning_name
    return ", ".join(f"{k} {v}" for k, v in got.items())


def check_change_window() -> str:
    import datetime as dt
    from .core import timeutil
    b = _briefing()
    observed = timeutil.local_to_epoch(dt.datetime(2026, 9, 26, 17, 5), b.tz)
    w = b.window
    assert w is not None and w["t0"] <= observed <= w["t1"], w
    return f"{_hm(w['t0'], b.tz)}–{_hm(w['t1'], b.tz)} covers the observed 17:05 change"


def check_sail_plan() -> str:
    b = _briefing()
    gfs = next(p for p in b.plans if p.model == "GFS")
    sails = [s["sail"] for s in gfs.sail_runs]
    assert sails[:2] == ["J1", "A1/2"] and sails[-2:] == ["Poled J4", "J4"], sails
    return " → ".join(sails)


def check_summary_finishes() -> str:
    b = _briefing()
    want = {("06:34", "ACCESS"): "21:04:45", ("06:34", "GFS"): "21:57:10", ("06:34", "ECMWF"): "22:11:14",
            ("06:34", "AIGFS"): "22:41:37", ("09:50", "ACCESS"): "21:39:15", ("09:49", "ICON"): "23:34:25"}
    from .core.timeutil import fmt_local
    got = {(fmt_local(r["run"], b.tz, "%H:%M"), r["model"]): fmt_local(r["finish"], b.tz, "%H:%M:%S")
           for r in b.finishes if r["source"] == "summary"}
    for k, v in want.items():
        assert got.get(k) == v, (k, got.get(k), v)
    return f"{len(want)} race-morning predicted finishes exact"


def check_report() -> str:
    import re
    from .report import day_before
    b = _briefing()
    with tempfile.TemporaryDirectory() as d:
        out = day_before.write(b, os.path.join(d, "briefing.html"))
        html = open(out, encoding="utf-8").read()
    urls = set(re.findall(r"https?://[^\"'<>\s)]+", html))
    allowed = {"http://www.w3.org/2000/svg", "https://github.com/pishi-ishi/day-after"}
    assert urls <= allowed, urls - allowed
    assert "<script src" not in html and "<link " not in html, "external resource"
    return f"self-contained, {len(html) // 1024} KB"


# --------------------------------------------------------------------------------------------- M1: Day After

_ANALYSIS = None


def _analysis():
    """The Flinders Day After analysis, computed once for all M1 checks."""
    global _ANALYSIS
    if _ANALYSIS is None:
        import json
        from .analysis.race_analysis import analyse
        _need(_root("data", "flinders_2026", "log-2026Sep26.csv"))
        fx = _root("fixtures", "flinders_2026")
        with open(os.path.join(fx, "race.dayafter.json"), encoding="utf-8") as f:
            project = json.load(f)
        _ANALYSIS = analyse(_root("data", "flinders_2026"), [fx], project)
    return _ANALYSIS


def _expected(name: str) -> list[dict]:
    import csv
    with open(_root("fixtures", "flinders_2026", "expected", name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _clock(a, hhmm: str) -> float:
    """'10:29:23' or '10:29' on race day -> epoch."""
    import datetime as dt
    from .core import timeutil
    parts = [int(x) for x in hhmm.split(":")]
    day = timeutil.epoch_to_local(a.gun, a.tz).date()
    return timeutil.local_to_epoch(dt.datetime(day.year, day.month, day.day, parts[0], parts[1],
                                               parts[2] if len(parts) > 2 else 0), a.tz)


def check_mark_times() -> str:
    a = _analysis()
    worst = abs(a.start - _clock(a, "10:00:49"))
    assert worst <= 60, f"start crossing off by {worst:.0f} s"
    names = {"FI S": "FI S", "Finish": "Finish"}
    for row in _expected("llama_mark_times.csv"):
        if row["mark"] == "Start":
            continue
        p = a.passage(names.get(row["mark"], row["mark"]))
        assert p is not None and p.t is not None, f"{row['mark']} not passed"
        err = abs(p.t - _clock(a, row["llama_local_time_AEST"]))
        assert err <= 60, f"{row['mark']} off by {err:.0f} s"
        worst = max(worst, err)
    return f"start and 12 marks, worst {worst:.0f} s"


def check_splits_vs_routes() -> str:
    a = _analysis()
    by_mark = {s.mark: s for s in a.splits}
    worst = 0
    for row in _expected("splits_vs_routes.csv"):
        s = by_mark[row["mark"]]
        for model in ("GFS", "ECMWF", "ACCESS"):
            got = round(s.delta[model] / 60.0)
            worst = max(worst, abs(got - int(row[f"{model}_d"])))
    assert worst <= 1, f"a split is {worst} min off"
    return f"11 marks × 3 models, worst {worst} min"


def check_calibration() -> str:
    from .analysis import calibration as cal
    a = _analysis()
    f = a.fit
    assert abs(f.k - 1.258) <= 0.03, f.k
    assert abs(f.delta - 0.5) <= 2, f.delta
    assert abs(f.current_kt - 0.57) <= 0.2 and abs(((f.current_set - 125 + 180) % 360) - 180) <= 25, (f.current_kt, f.current_set)
    ratios = next(c for c in a.checks if c.id == "current").data
    assert abs(ratios["southbound"] - 1.31) <= 0.03 and abs(ratios["northbound"] - 1.23) <= 0.03, ratios
    beat = a.tl.window(_clock(a, "16:05"), _clock(a, "17:00"))
    m = cal.np.isfinite(beat["AWA"]) & (beat["BSP"] > 0.5)
    c = cal.twa_compare(beat, m, 1.257)
    assert abs(c["awa"] - 28.0) <= 1, c
    assert abs(c["twa_logged"] - 58.1) <= 2 and abs(c["twa_recomputed"] - 41.1) <= 2, c
    assert abs(c["tws_logged"] - 11.3) <= 0.5 and abs(c["tws_recomputed"] - 11.2) <= 0.5, c
    ids = {x.id: x for x in a.checks}
    assert ids["speed"].status == "fail" and ids["twa_up"].status == "warn", "calibration not flagged"
    groups = ids["channels"].data["groups"]
    for members in (("Heel", "Trim", "Leeway", "MastAng", "KeelAng"), ("J1", "J4", "Main", "Forestay", "RunnerP", "Bobstay"),
                    ("FuelLev", "WaterLev")):
        assert any(set(members) <= set(g) for g in groups), f"duplicate group {members} not found"
    assert "Baro" in ids["missing"].value and "AirTemp" in ids["missing"].value
    return (f"k {f.k:.3f}, heading {f.delta:+.1f}°, current {f.current_kt:.2f} kt → {f.current_set:.0f}°, beat TWA "
            f"{c['twa_logged']:.1f}° logged vs {c['twa_recomputed']:.1f}° recomputed")


def check_phases() -> str:
    a = _analysis()
    rows = _expected("phases.csv")
    ours = a.phases
    assert len(ours) == len(rows), [p.name for p in ours]
    worst_t = worst_v = 0.0
    for row, p in zip(rows, ours):
        for got, want in ((p.t0, row["from"]), (p.t1, row["to"])):
            exp = _clock(a, want)
            err = 0.0 if exp - 60 <= got <= exp + 119 else min(abs(got - exp), abs(got - exp - 59))
            worst_t = max(worst_t, err)
        assert abs(p.minutes - float(row["min"])) <= 1.0, (p.name, p.minutes, row["min"])
        for got, want in ((p.sog, row["avgSOG"]), (p.stw_c, row["avgSTWcorr"])):
            want = float(want)
            worst_v = max(worst_v, abs(got - want) / max(abs(want), 1e-9) if abs(got - want) > 0.1 else 0.0)
        assert abs(p.tws - float(row["TWS"])) <= 0.3 and abs(p.tws_p95 - float(row["TWS95"])) <= 0.5, (p.name, p.tws, p.tws_p95)
    assert worst_t <= 60, f"a phase boundary is {worst_t:.0f} s off"
    assert worst_v <= 0.02, f"a phase speed is {worst_v * 100:.1f} % off"
    assert len(a.holes) == 1 and a.change is not None
    assert abs(a.change.onset - _clock(a, "17:05")) <= 90, "change not at 17:05"
    return f"{len(ours)} phases incl. the hole; boundaries within {worst_t:.0f} s, speeds within {worst_v * 100:.1f} %"


def check_finish() -> str:
    from .core import timeutil
    a = _analysis()
    assert a.result.place == 15 and sum(r.finished for r in a.results) == 28
    assert abs(a.elapsed - 42240.3) < 0.5 and timeutil.fmt_local(a.finish, a.tz, "%H:%M:%S") == "21:44:00"
    fp = a.finish_point
    assert fp is not None and abs(fp - _clock(a, "21:43:28")) <= 60
    return f"15th of 28, elapsed {timeutil.fmt_duration(a.elapsed)} (corrected ÷ TCC), official finish 21:44:00"


def check_navigator_report() -> str:
    import re
    from .report import navigator
    a = _analysis()
    html = navigator.render(a)
    urls = set(re.findall(r"https?://[^\"'<>\s)]+", html))
    assert urls <= {"http://www.w3.org/2000/svg", "https://github.com/pishi-ishi/day-after"}, urls
    assert "<script src" not in html and "NaN" not in html.split('id="da-data">')[1].split("</script>")[0]
    return f"self-contained, {len(html) // 1024} KB"


CHECKS = [
    ("time zones and durations", check_time_zones),
    ("YB decoder test vector", check_yb_vector),
    ("YB Flinders file", check_yb_full_file),
    ("route ETAs at the turning mark", check_route_etas),
    ("change window vs observed change", check_change_window),
    ("GFS sail plan", check_sail_plan),
    ("race-morning predicted finishes", check_summary_finishes),
    ("Day Before report", check_report),
    ("M1 mark times", check_mark_times),
    ("M1 splits vs routes", check_splits_vs_routes),
    ("M1 calibration", check_calibration),
    ("M1 phases, hole and change", check_phases),
    ("M1 finish and result", check_finish),
    ("M1 navigator report", check_navigator_report),
]


def run(verbose: bool = True) -> int:
    failed = skipped = 0
    for name, fn in CHECKS:
        try:
            detail = fn()
            status = "ok  "
        except Skip as e:
            detail, status = str(e), "skip"
            skipped += 1
        except Exception as e:  # noqa: BLE001 - every failure is reported, then the run fails
            detail = f"{type(e).__name__}: {e}"
            if verbose:
                detail += "\n" + "".join(traceback.format_exception(e)[-3:])
            status = "FAIL"
            failed += 1
        if verbose:
            print(f"[{status}] {name}: {detail}")
    if verbose:
        print(f"{len(CHECKS) - failed - skipped} passed, {skipped} skipped, {failed} failed")
    return 1 if failed else 0
