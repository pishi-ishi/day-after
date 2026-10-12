import os

from dayafter.ingest import course as C

from .conftest import FIXTURES

GPX = """<?xml version="1.0"?>
<gpx version="1.1" creator="Windy" xmlns="http://www.topografix.com/GPX/1/1">
<rte><name>Test course</name>
<rtept lat="-33.8558" lon="151.2535"><name>1</name></rtept>
<rtept lat="-34.6" lon="151.0"><name>2</name></rtept>
<rtept lat="-35.755" lon="150.258"><name>3</name></rtept>
<rtept lat="-34.6" lon="151.05"><name>4</name></rtept>
<rtept lat="-33.842" lon="151.274"><name>5</name></rtept>
</rte></gpx>"""

MARKS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<marksdb version="1.0" creator="Expedition - https://www.ExpeditionMarine.com">
  <active route_id="2" mark_index="0" />
  <marks>
    <mark id="1" name="Start" group="G" lat="-33.860650" lon="151.247600" />
    <mark id="2" name="Turn" group="G" lat="-35.755000" lon="150.258000" />
    <mark id="3" name="Finish" group="G" lat="-33.842000" lon="151.274000" />
    <mark id="4" name="Finish" group="Bad" lat="33.842000" lon="151.274000" />
  </marks>
  <routes>
    <route id="1" name="Wrong finish"><mark id_mark="1" pass="2" /><mark id_mark="2" pass="1" /><mark id_mark="4" pass="2" /></route>
    <route id="2" name="Tollgate_Islands_Windy"><mark id_mark="1" pass="2" /><mark id_mark="2" pass="1" /><mark id_mark="3" pass="1" /></route>
  </routes>
</marksdb>"""


def test_course_csv_turning_mark_group():
    c = C.read_course_csv(os.path.join(FIXTURES, "flinders_2026", "course.csv"))
    C.assign_roles(c)
    assert c.marks[0].role == "start" and c.marks[-1].role == "finish"
    assert c.turning_mark.name == "FI S"  # FI W/S/E are all tagged; the one farthest from the start wins
    assert 88.0 < c.length_nm() < 88.2   # ACCEPTANCE: 88.02 nm along the polyline (+ the islet triangle)


def test_gpx_numbered_points(tmp_path):
    p = tmp_path / "t.gpx"
    p.write_text(GPX, encoding="utf-8")
    c = C.assign_roles(C.read_gpx(str(p)))
    assert [m.name for m in c.marks] == ["1", "2", "3", "4", "5"]
    assert c.turning_mark.name == "3"
    c = C.assign_roles(C.read_gpx(str(p)), turning_mark="2")
    assert c.turning_mark.name == "2"


def test_marks_xml_active_route_and_validation(tmp_path):
    p = tmp_path / "marks.xml"
    p.write_text(MARKS_XML, encoding="utf-8")
    names, active = C.marks_xml_routes(str(p))
    assert active == "Tollgate_Islands_Windy" and "Wrong finish" in names
    c = C.assign_roles(C.read_marks_xml(str(p)))
    assert [m.name for m in c.marks] == ["Start", "Turn", "Finish"] and c.turning_mark.name == "Turn"
    assert c.marks[1].pass_code == "1"
    bad = C.validate(C.read_marks_xml(str(p), "wrong finish"))
    assert any("wrong hemisphere" in w for w in bad.warnings)


def test_unknown_turning_mark_warns(tmp_path):
    p = tmp_path / "t.gpx"
    p.write_text(GPX, encoding="utf-8")
    c = C.assign_roles(C.read_gpx(str(p)), turning_mark="Lord Howe")
    assert c.turning_mark.name == "3" and c.warnings
