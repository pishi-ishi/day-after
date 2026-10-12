"""Race events: Expedition's SQLite `Expedition.db` (FILE_FORMATS §10) or Day After's `events.csv`."""
from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3
from dataclasses import dataclass

from ..core import timeutil
from .routes import read_text

NO_SAIL = 32767  # Expedition: no sail / unchanged


@dataclass
class Event:
    t: float
    kind: str          # gun | finish | line | sail | reef | note | mob | sart | mark | penalty | incident | other
    text: str = ""
    sail: str = ""
    reef: int | None = None
    lat: float | None = None
    lon: float | None = None
    auto: bool = False
    source: str = ""


_KIND = {"gun": "gun", "finish": "finish", "mob": "mob", "sart": "sart", "line port": "line", "line starboard": "line",
         "sails up": "sail", "race leg": "mark", "tech problem": "incident", "photo": "note", "misc": "note",
         "other": "other", "test start": "note", "test end": "note", "set route": "note"}


def read_expedition_db(path: str) -> list[Event]:
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        types = {i: n for i, n in con.execute("select ID, NAME from EVENT_TYPE")}
        sails = {i: n for i, n in con.execute("select ID, NAME from SAIL")}
        rows = con.execute("select TIME, LAT, LON, FORESAIL_ID, STAYSAIL_ID, STAYSAIL2_ID, MAINSAIL_ID, REEF, TYPE_ID, "
                           "AUTO, NOTE from EVENT order by TIME").fetchall()
    finally:
        con.close()
    out = []
    for tm, lat, lon, fore, stay, stay2, main, reef, type_id, auto, note in rows:
        tname = (types.get(type_id) or "Other").strip()
        kind = _KIND.get(tname.lower(), "other")
        names = [sails[s] for s in (fore, stay, stay2, main) if s not in (None, NO_SAIL) and s in sails]
        text = (note or "").strip()
        if kind in ("other", "note") and reef not in (None, NO_SAIL) and reef:
            kind = "reef"  # a reef entry also names the mainsail; it is a reef, not a sail change
        elif kind in ("other", "note") and names:
            kind = "sail"
        if tname.lower().startswith("line"):
            text = text or tname
        out.append(Event(t=timeutil.excel_to_epoch(tm), kind=kind, text=text or tname, sail=" + ".join(names),
                         reef=int(reef) if reef not in (None, NO_SAIL) else None, lat=lat, lon=lon, auto=bool(auto),
                         source="Expedition.db"))
    return out


def read_events_csv(path: str, tz: str) -> list[Event]:
    out = []
    for r in csv.DictReader(io.StringIO(read_text(path))):
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items()}
        if not r.get("time_local"):
            continue
        t = timeutil.local_to_epoch(dt.datetime.fromisoformat(r["time_local"]), tz)
        kind = (r.get("type") or "note").lower()
        val = r.get("value", "")
        out.append(Event(t=t, kind=kind, text=r.get("text", ""), sail=val if kind == "sail" else "",
                         reef=int(val) if kind == "reef" and val.isdigit() else None, source="events.csv"))
    return out


def in_window(events: list[Event], t0: float, t1: float) -> list[Event]:
    return [e for e in events if t0 <= e.t <= t1]
