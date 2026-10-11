import datetime as dt
import json
import os
import re

import pytest

from dayafter import selftest
from dayafter.analysis.briefing import build_briefing
from dayafter.cli import main
from dayafter.core.timeutil import fmt_local
from dayafter.report import day_before

from .conftest import requires_data, route_table_text, tollgate_like_rows


@pytest.fixture
def race(tmp_path):
    """A Tollgate-like race folder: three models whose change arrives at different times."""
    routes = tmp_path / "routes"
    routes.mkdir()
    for model, hh in (("ECMWF", 21), ("GFS", 19), ("ACCESS", 23)):
        rows = tollgate_like_rows(change_at=dt.datetime(2026, 10, 16, hh, 0))
        (routes / f"{model}_15_1900_15oct2026.csv").write_text(route_table_text(rows, model=model), encoding="utf-8")
    (tmp_path / "notes.md").write_text("Reef early if the change beats us to the islands.", encoding="utf-8")
    return tmp_path


def test_briefing_on_synthetic_race(race):
    b = build_briefing(str(race))
    assert [p.model for p in b.plans] == ["ECMWF", "GFS", "ACCESS"]
    assert b.gun_source == "first row of the route tables" and fmt_local(b.gun, b.tz, "%H:%M %Z") == "14:00 AEDT"
    assert b.turning_name == "TG South"
    eta = {p.model: fmt_local(p.eta_turning, b.tz, "%H:%M") for p in b.plans}
    assert eta == {"ECMWF": "21:30", "GFS": "21:30", "ACCESS": "21:30"}
    change = {p.model: fmt_local(p.change.t, b.tz, "%H:%M") for p in b.plans}
    assert change["GFS"] < change["ECMWF"] < change["ACCESS"]
    assert b.window["before"] == ["ACCESS"] and set(b.window["after"]) == {"ECMWF", "GFS"}
    assert "disagree" in b.window["verdict"]
    assert b.plans[0].sail_runs[0]["sail"] == "A2" and b.plans[0].sail_runs[-1]["sail"] == "J4"
    assert "Reef early" in b.notes


def test_models_option_and_race_file(race):
    (race / "race.dayafter.json").write_text(json.dumps({
        "race": {"name": "Tollgate Islands Race 2026", "gun_local": "2026-10-16T14:00:00"},
        "course": {"turning_mark": "Point Perpendicular"}, "crew_models": ["GFS", "ACCESS"]}))
    b = build_briefing(str(race))
    assert b.race_name == "Tollgate Islands Race 2026" and b.gun_source == "race file"
    assert [p.model for p in b.plans] == ["GFS", "ACCESS"] and b.turning_name == "Point Perpendicular"
    b = build_briefing(str(race), models="ecmwf", turning_mark="TG South")
    assert [p.model for p in b.plans] == ["ECMWF"] and b.turning_name == "TG South"


def test_report_is_self_contained(race):
    b = build_briefing(str(race))
    out = day_before.write(b)
    assert out.endswith(".html") and os.sep + "out" + os.sep in out
    html = open(out, encoding="utf-8").read()
    assert set(re.findall(r"https?://[^\"'<>\s)]+", html)) <= {"http://www.w3.org/2000/svg", "https://github.com/pishi-ishi/day-after"}
    data = json.loads(re.search(r'<script type="application/json" id="da-data">(.*?)</script>', html, re.S).group(1))
    assert [m["model"] for m in data["models"]] == ["ECMWF", "GFS", "ACCESS"] and data["turning"] == "TG South"
    assert "NaN" not in html.split('id="da-data">')[1].split("</script>")[0]
    assert "Reef early" in html and "Weather words" in html


def test_cli_before(race, capsys):
    assert main(["before", str(race), "--models", "GFS,ACCESS"]) == 0
    out = capsys.readouterr().out
    assert "GFS, ACCESS" in out and "wrote" in out


def test_cli_reports_missing_route_tables(tmp_path, capsys):
    assert main(["before", str(tmp_path)]) == 2
    assert "no Expedition route tables" in capsys.readouterr().err


@requires_data
@pytest.mark.parametrize("check", [c for _, c in selftest.CHECKS], ids=[n for n, _ in selftest.CHECKS])
def test_flinders_acceptance(check):
    check()


def test_gpx_course_when_the_routing_names_few_marks(tmp_path):
    """Route tables that name only start and finish fall back to the GPX course; numbered points read well."""
    routes = tmp_path / "routes"
    routes.mkdir()
    rows = tollgate_like_rows(change_at=dt.datetime(2026, 10, 16, 23, 0))
    for r in rows:
        r["mark"] = ""
    rows[0]["mark"], rows[-1]["mark"] = "Start", "Finish"
    (routes / "ECMWF_15_1900_15oct2026.csv").write_text(route_table_text(rows, model="ECMWF"), encoding="utf-8")
    (tmp_path / "course.gpx").write_text(
        '<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><rte>'
        '<rtept lat="-33.8558" lon="151.2535"><name>1</name></rtept><rtept lat="-35.1" lon="150.83"><name>2</name></rtept>'
        '<rtept lat="-35.755" lon="150.258"><name>3</name></rtept><rtept lat="-33.842" lon="151.274"><name>4</name></rtept>'
        '</rte></gpx>')
    b = build_briefing(str(tmp_path))
    assert b.course.source.endswith("course.gpx")
    assert b.turning_label == "the turning mark (point 3)"
    assert fmt_local(b.plans[0].eta_turning, b.tz, "%H:%M") == "21:30"
    assert any("point 3" in c["text"] for c in b.plans[0].callouts)
