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
    tollgate = timeutil.local_to_epoch(dt.datetime(2026, 10, 16, 14, 0), "Australia/Sydney")
    assert tollgate == 1792119600, tollgate  # 03:00Z: AEDT, UTC+11 (YB RaceSetup bwps2026_2)
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


CHECKS = [
    ("time zones and durations", check_time_zones),
    ("YB decoder test vector", check_yb_vector),
    ("YB Flinders file", check_yb_full_file),
    ("route ETAs at the turning mark", check_route_etas),
    ("change window vs observed change", check_change_window),
    ("GFS sail plan", check_sail_plan),
    ("race-morning predicted finishes", check_summary_finishes),
    ("Day Before report", check_report),
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
