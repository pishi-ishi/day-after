"""Shared test helpers. Synthetic inputs here are public; the Flinders data in data/ is private and optional."""
from __future__ import annotations

import datetime as dt
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")
DATA = os.path.join(ROOT, "data")
FLINDERS = os.path.join(DATA, "flinders_2026")

requires_data = pytest.mark.skipif(not os.path.isdir(os.path.join(FLINDERS, "routes")),
                                   reason="private data/ folder not present")

ROUTE_HEADER = ("AUS Eastern Standard Time,Mark,Sail,Reef,Other,Twd°M,Tws,Twg,Twa,Targ,Bsp,Bsp%,Set°M,Drift,Weight,"
                "Brg°M,Dist nm,Awa,Aws,Mode,SigWave H,MeanWaveDir,MeanWavePer,PrimaryWaveDir,PrimaryWavePer,Swell dir,"
                "Swell H,Swell period,Wave Dir,Wave H,Wave period,MSLP,Rain,AirT,SST,Cloud,CAPE,LFTX,RH,AirDens,"
                "Latitude,Longitude")


def ddm(v: float, pos: str, neg: str) -> str:
    h = pos if v >= 0 else neg
    v = abs(v)
    d = int(v)
    return f"{d} {(v - d) * 60:07.4f}{h}"


def route_table_text(rows: list[dict], model: str = "GFS", created: str = "15-Oct-2026 19:05:00") -> str:
    """A synthetic Expedition route table. rows: dicts with local `time` (datetime), lat, lon, twd_m, tws and
    optional twg, twa (str, may be parenthesised), mark, sail, mslp, rain, airt."""
    out = [ROUTE_HEADER]
    for r in rows:
        cells = [""] * 42
        cells[0] = r["time"].strftime("%d-%b-%Y %H:%M")
        cells[1] = r.get("mark", "")
        cells[2] = r.get("sail", "")
        cells[5] = f"{r['twd_m']:03.0f}"
        cells[6] = f"{r['tws']:.1f}"
        cells[7] = f"{r.get('twg', r['tws'] * 1.3):.1f}"
        cells[8] = r.get("twa", "")
        cells[19] = "Sail"
        cells[31] = f"{r.get('mslp', 1015.0):.2f}"
        cells[32] = f"{r.get('rain', 0.0):.2f}"
        cells[33] = f"{r['airt']:.1f}" if "airt" in r else ""
        cells[40] = ddm(r["lat"], "n", "s")
        cells[41] = ddm(r["lon"], "e", "w")
        out.append(",".join(cells))
    out.append("," * 41)
    out += [f"Name,G {model} High {created[-8:]}", f"Created,{created}", f"Model,{model}", "Route distance,250.00nm"]
    return "\n".join(out) + "\n"


def tollgate_like_rows(change_at: dt.datetime, start: dt.datetime = dt.datetime(2026, 10, 16, 14, 0)) -> list[dict]:
    """Sydney -> Tollgate Islands -> Sydney in 30-min steps, with a NE -> S change at `change_at` (local AEDT)."""
    pts = [(-33.8558, 151.2535, "Start"), (-34.6, 151.0, ""), (-35.1, 150.83, "Point Perpendicular"),
           (-35.755, 150.258, "TG South"), (-35.1, 150.85, ""), (-34.2, 151.2, ""), (-33.842, 151.274, "Finish")]
    rows = []
    n = 30
    for k in range(n + 1):
        f = k / n * (len(pts) - 1)
        a = min(int(f), len(pts) - 2)
        g = f - a
        lat = pts[a][0] + g * (pts[a + 1][0] - pts[a][0])
        lon = pts[a][1] + g * (pts[a + 1][1] - pts[a][1])
        t = start + dt.timedelta(minutes=30 * k)
        after = t >= change_at
        mark = pts[a][2] if g == 0 else (pts[-1][2] if k == n else "")
        rows.append({"time": t, "lat": lat, "lon": lon, "twd_m": 165.0 if after else 25.0,
                     "tws": 22.0 if after else 14.0, "twa": "-150" if not after else "45",
                     "mark": mark, "sail": "J4" if after else "A2", "mslp": 1012.0 + (4.0 if after else 0.0),
                     "airt": 16.0 if after else 21.0, "rain": 0.3 if after else 0.0})
    return rows
