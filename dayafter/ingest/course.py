"""Race course: marks in order, with roles (start, waypoint, turning_mark, finish).

Sources, best first: Day After's course.csv, Expedition's marks.xml route, a GPX route, or the marks
an Expedition route table reaches. Windy GPX files number their points only, so the turning mark comes
from the race file, else the mark farthest from the start. Expedition's racenotes.xml islands are only
drawn on the map.
"""
from __future__ import annotations

import csv
import io
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np

from ..core import geo
from .routes import RouteTable, read_text

ROLES = ("start", "waypoint", "turning_mark", "finish")


@dataclass
class Mark:
    name: str
    lat: float
    lon: float
    role: str = "waypoint"
    pass_code: str | None = None  # Expedition marks.xml `pass` (0/1/2); meaning not yet verified
    note: str = ""


@dataclass
class Island:
    name: str
    lat: np.ndarray
    lon: np.ndarray


@dataclass
class Course:
    name: str
    marks: list[Mark]
    source: str
    warnings: list[str] = field(default_factory=list)

    @property
    def lat(self) -> np.ndarray:
        return np.array([m.lat for m in self.marks])

    @property
    def lon(self) -> np.ndarray:
        return np.array([m.lon for m in self.marks])

    def leg_lengths_nm(self) -> np.ndarray:
        return geo.haversine_nm(self.lat[:-1], self.lon[:-1], self.lat[1:], self.lon[1:])

    def length_nm(self) -> float:
        return float(self.leg_lengths_nm().sum()) if len(self.marks) > 1 else 0.0

    def turning_index(self) -> int | None:
        """The turning mark; when several are tagged (FI W, FI S, FI E) the one farthest from the start."""
        tagged = [i for i, m in enumerate(self.marks) if m.role == "turning_mark"]
        if not tagged:
            return None
        s = self.marks[0]
        return max(tagged, key=lambda i: float(geo.haversine_nm(s.lat, s.lon, self.marks[i].lat, self.marks[i].lon)))

    @property
    def turning_mark(self) -> Mark | None:
        i = self.turning_index()
        return None if i is None else self.marks[i]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


# ---------------------------------------------------------------------------------------------- readers

def read_course_csv(path: str) -> Course:
    rows = list(csv.DictReader(io.StringIO(read_text(path))))
    marks = []
    for r in sorted(rows, key=lambda r: int(r.get("seq") or 0)):
        role = (r.get("role") or "waypoint").strip() or "waypoint"
        if role not in ROLES:
            role = "waypoint"
        marks.append(Mark(name=r["name"].strip(), lat=float(r["lat"]), lon=float(r["lon"]), role=role,
                          note=(r.get("note") or "").strip()))
    return Course(name=os.path.splitext(os.path.basename(path))[0], marks=marks, source=path)


def read_gpx(path: str) -> Course:
    root = ET.fromstring(read_text(path).encode("utf-8"))
    ns = {"g": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    q = (lambda tag: f"g:{tag}") if ns else (lambda tag: tag)

    def points(parent, tag):
        out = []
        for p in parent.findall(q(tag), ns):
            nm = p.find(q("name"), ns)
            out.append(Mark(name=(nm.text or "").strip() if nm is not None else "", lat=float(p.get("lat")),
                            lon=float(p.get("lon"))))
        return out

    name = os.path.splitext(os.path.basename(path))[0]
    for rte in root.findall(q("rte"), ns):
        marks = points(rte, "rtept")
        if marks:
            nm = rte.find(q("name"), ns)
            return Course(name=(nm.text or name).strip() if nm is not None and nm.text else name, marks=marks, source=path)
    marks = points(root, "wpt")
    if not marks:
        for trk in root.findall(q("trk"), ns):
            for seg in trk.findall(q("trkseg"), ns):
                marks += points(seg, "trkpt")
    for i, m in enumerate(marks):
        m.name = m.name or str(i + 1)
    return Course(name=name, marks=marks, source=path)


def marks_xml_routes(path: str) -> tuple[list[str], str | None]:
    """Route names in Expedition's marks.xml, and the active route's name."""
    root = ET.fromstring(read_text(path).encode("utf-8"))
    names = {r.get("id"): r.get("name", "") for r in root.iter("route")}
    act = root.find("active")
    return list(names.values()), names.get(act.get("route_id")) if act is not None else None


def read_marks_xml(path: str, route: str | None = None) -> Course:
    """A route from Expedition's marks.xml: by name (case and punctuation ignored), else the active route."""
    root = ET.fromstring(read_text(path).encode("utf-8"))
    by_id = {m.get("id"): m for m in root.iter("mark") if m.get("lat") is not None and m.get("name") is not None}
    routes = list(root.iter("route"))
    chosen = None
    if route:
        chosen = next((r for r in routes if _norm(r.get("name", "")) == _norm(route)), None)
        if chosen is None:
            raise KeyError(f"route {route!r} not in {path}")
    else:
        act = root.find("active")
        rid = act.get("route_id") if act is not None else None
        chosen = next((r for r in routes if r.get("id") == rid), None)
        if chosen is None:
            raise KeyError(f"no active route in {path}")
    marks = []
    for ref in chosen:
        m = by_id.get(ref.get("id_mark"))
        if m is None:
            continue
        marks.append(Mark(name=m.get("name", "").strip(), lat=float(m.get("lat")), lon=float(m.get("lon")),
                          pass_code=ref.get("pass")))
    return Course(name=chosen.get("name", ""), marks=marks, source=f"{path}#{chosen.get('name')}")


def read_racenotes(path: str) -> list[Island]:
    root = ET.fromstring(read_text(path).encode("utf-8"))
    out = []
    for rn in root.iter("racenote"):
        pts = rn.findall("point")
        if len(pts) >= 3:
            out.append(Island(name=rn.get("name", ""), lat=np.array([float(p.get("lat")) for p in pts]),
                              lon=np.array([float(p.get("lon")) for p in pts])))
    return out


def course_from_route(route: RouteTable) -> Course:
    """The marks a route table reaches, at the positions where the route reaches them."""
    marks = [Mark(name=n, lat=float(route.lat[i]), lon=float(route.lon[i])) for i, n, _ in route.mark_rows()]
    return Course(name=f"{route.model} route marks", marks=marks, source=route.path)


# ---------------------------------------------------------------------------------------------- roles

def find_mark(course: Course, name: str) -> int | None:
    """Index of the mark called `name` (exact after normalising, else unique prefix/contains match)."""
    key = _norm(name)
    exact = [i for i, m in enumerate(course.marks) if _norm(m.name) == key]
    if exact:
        return exact[0]
    loose = [i for i, m in enumerate(course.marks) if key and (key in _norm(m.name) or _norm(m.name) in key)]
    return loose[0] if len(loose) == 1 else None


def assign_roles(course: Course, turning_mark: str | None = None) -> Course:
    """Set start/finish on the ends and pick the turning mark: named > already tagged > farthest from the start."""
    ms = course.marks
    if not ms:
        return course
    for m in ms:
        if m.role not in ROLES:
            m.role = "waypoint"
    if len(ms) >= 2:
        ms[0].role, ms[-1].role = "start", "finish"
    inner = range(1, len(ms) - 1) if len(ms) > 2 else range(len(ms))
    chosen = None
    if turning_mark:
        chosen = find_mark(course, turning_mark)
        if chosen is None:
            course.warnings.append(f"turning mark {turning_mark!r} is not on the course; picked one instead")
    if chosen is None and any(m.role == "turning_mark" for m in ms):
        return course
    if chosen is None and len(ms) > 2:
        d = [float(geo.haversine_nm(ms[0].lat, ms[0].lon, ms[i].lat, ms[i].lon)) for i in inner]
        chosen = list(inner)[int(np.argmax(d))]
    for m in ms:
        if m.role == "turning_mark":
            m.role = "waypoint"
    if chosen is not None:
        ms[chosen].role = "turning_mark"
    return course


def validate(course: Course, max_leg_nm: float = 400.0) -> Course:
    """Flag marks far from the rest (e.g. a Finish stored at +33.842 instead of −33.842)."""
    if len(course.marks) < 3:
        return course
    lat0, lon0 = float(np.median(course.lat)), float(np.median(course.lon))
    for m in course.marks:
        d = float(geo.haversine_nm(lat0, lon0, m.lat, m.lon))
        if d > max_leg_nm:
            course.warnings.append(f"mark {m.name!r} at {m.lat:.4f}, {m.lon:.4f} is {d:.0f} nm from the rest of the "
                                   "course; check its position (wrong hemisphere?)")
    return course
