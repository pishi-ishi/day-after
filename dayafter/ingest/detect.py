"""Find a race's input files by what they are, not where they sit.

The DATA_GUIDE folder layout (course/, routes/, gribs/ …) is a suggestion: every file under the race
folder is classified by name pattern and a sniff of its first bytes. Day After's own output folder
(`out/`) and hidden folders are skipped.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .routes import looks_like_route_summary, looks_like_route_table

SKIP_DIRS = {"out", "__pycache__", ".git", ".venv", "node_modules"}


@dataclass
class Inputs:
    folder: str
    route_tables: list[str] = field(default_factory=list)
    route_summaries: list[str] = field(default_factory=list)
    course_csv: list[str] = field(default_factory=list)
    gpx: list[str] = field(default_factory=list)
    marks_xml: list[str] = field(default_factory=list)
    racenotes: list[str] = field(default_factory=list)
    project: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    expedition_db: list[str] = field(default_factory=list)
    events_csv: list[str] = field(default_factory=list)
    yb_positions: list[str] = field(default_factory=list)
    yb_setup: list[str] = field(default_factory=list)
    boatids: list[str] = field(default_factory=list)
    results: list[str] = field(default_factory=list)
    bom: list[str] = field(default_factory=list)
    gribs: list[str] = field(default_factory=list)
    gribs_encrypted: list[str] = field(default_factory=list)
    polars: list[str] = field(default_factory=list)
    sail_charts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.__dict__.items() if isinstance(v, list) and v}


def _head(path: str, n: int = 4096) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _first_line(head: bytes) -> str:
    text = head.decode("utf-8-sig", errors="replace")
    return text.splitlines()[0] if text else ""


def classify(path: str) -> str | None:
    """The input kind of one file (an `Inputs` field name), or None if it is not an input."""
    name = os.path.basename(path)
    low = name.lower()
    ext = os.path.splitext(low)[1]
    head = _head(path)
    if not head:
        return None
    if head.startswith(b"grbenc01"):
        return "gribs_encrypted"
    if head.startswith(b"GRIB") or ext in (".grb", ".grb2", ".grib", ".grib2"):
        return "gribs" if head.startswith(b"GRIB") else None
    if head.startswith(b"SQLite format 3"):
        return "expedition_db"
    if low == "race.dayafter.json":
        return "project"
    if "allpositions3" in low:
        return "yb_positions"
    if "racesetup" in low and ext == ".json":
        return "yb_setup"
    if re.search(r"-boatids\.(txt|csv)$", low):
        return "boatids"
    if ext == ".axf" or b"[header]" in head[:2000] and b"[data]" in head:
        return "bom"
    if ext == ".gpx":
        return "gpx"
    if ext == ".md" and "note" in low:
        return "notes"
    if ext == ".xml":
        if b"<marksdb" in head:
            return "marks_xml"
        if b"<racenotes" in head:
            return "racenotes"
        return None
    if ext in (".csv", ".txt"):
        first = _first_line(head)
        if first.startswith("!Boat"):
            return "logs"
        if looks_like_route_table(first):
            return "route_tables"
        if looks_like_route_summary(first):
            return "route_summaries"
        flat = first.replace(" ", "").lower()
        if flat.startswith("seq,name,lat,lon"):
            return "course_csv"
        if flat.startswith("place,yacht"):
            return "results"
        if flat.startswith("time_local,type,value"):
            return "events_csv"
        if first.startswith("!Expedition polar") or flat.startswith("twa/tws"):
            return "polars"
        if "sailchart" in low:
            return "sail_charts"
    return None


def scan(folder: str) -> Inputs:
    inputs = Inputs(folder=os.path.abspath(folder))
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.startswith(".") or f.endswith((".part", ":Zone.Identifier")):
                continue
            path = os.path.join(root, f)
            kind = classify(path)
            if kind:
                getattr(inputs, kind).append(path)
    return inputs
