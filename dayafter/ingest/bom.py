"""BOM coastal observations (`IDN60701.<wmo>.axf`, FILE_FORMATS §8).

INI-like text with [notice], [header] and [data] sections; [data] is CSV whose header names carry
sizes (`name[80]`). Missing values are -9999. Each file holds about the last 72 h at 30-min steps, so
it must be downloaded within three days after the race.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re

import numpy as np

from .. import net

URL = "https://reg.bom.gov.au/fwo/{product}/{product}.{wmo}.axf"  # www.bom.gov.au refuses scripts (403)
DEFAULT_PRODUCT = "IDN60701"  # NSW coastal observations

COMPASS16 = {d: i * 22.5 for i, d in enumerate(
    "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split())}


def _section(text: str, name: str) -> str:
    m = re.search(rf"^\[{name}\]\s*$(.*?)(?=^\[\w+\]\s*$|\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def _f(v: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return float("nan") if x <= -9999 else x


def parse_axf(text: str) -> dict:
    data = _section(text, "data").strip()
    if not data:
        raise ValueError("BOM file has no [data] section")
    reader = csv.reader(io.StringIO(data))
    header = [re.sub(r"\[\d+\]$", "", h.strip()) for h in next(reader)]
    rows = [dict(zip(header, r)) for r in reader if r and r[0].strip() and r[0].strip()[0].isdigit()]
    if not rows:
        raise ValueError("BOM file has no observations")
    t = np.array([dt.datetime.strptime(r["aifstime_utc"].strip('"'), "%Y%m%d%H%M%S")
                  .replace(tzinfo=dt.timezone.utc).timestamp() for r in rows])
    order = np.argsort(t)
    rows = [rows[i] for i in order]
    wdir = np.array([COMPASS16.get(r.get("wind_dir", "").strip('"').upper(), np.nan) for r in rows])
    first = rows[0]
    return {
        "wmo": first.get("wmo", "").strip('"'), "name": first.get("name", "").strip('"'),
        "lat": _f(first.get("lat")), "lon": _f(first.get("lon")), "t": t[order],
        "wind_dir": wdir, "wind_kt": np.array([_f(r.get("wind_spd_kt")) for r in rows]),
        "gust_kt": np.array([_f(r.get("gust_kt")) for r in rows]),
        "press_msl": np.array([_f(r.get("press_msl")) for r in rows]),
        "air_temp": np.array([_f(r.get("air_temp")) for r in rows]),
    }


def read_axf(path: str) -> dict:
    with open(path, encoding="latin-1") as f:
        return parse_axf(f.read())


def fetch_station(wmo: str, out_folder: str, *, product: str = DEFAULT_PRODUCT, log=print) -> str:
    """Download one station's file into `out_folder`, named after its last observation so a later
    download never replaces an earlier one (they cover different 72-hour windows)."""
    data = net.http_get(URL.format(product=product, wmo=wmo), log=log)
    obs = parse_axf(data.decode("latin-1"))
    last = dt.datetime.fromtimestamp(float(obs["t"][-1]), dt.timezone.utc).strftime("%Y%m%d-%H%MZ")
    path = net.save_atomic(os.path.join(out_folder, f"{product}.{wmo}_{last}.axf"), data,
                           validate=lambda b: parse_axf(b.decode("latin-1")))
    first = dt.datetime.fromtimestamp(float(obs["t"][0]), dt.timezone.utc).strftime("%d %b %H:%MZ")
    log(f"saved {path} ({obs['name']}, {len(obs['t'])} observations, {first} to {last})")
    return path
