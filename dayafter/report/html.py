"""Shared pieces for self-contained HTML reports: page shell, safe JSON embedding, coastline data."""
from __future__ import annotations

import html
import json
import math
import os

import numpy as np

from .. import __version__, resources

COAST_FILES = ("ne10m_land_se_australia.geojson", "osm_coast_sydney_wollongong.geojson")


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def clean(v, nd: int = 2):
    """JSON-safe copy: floats rounded to `nd` places, NaN/inf -> None, numpy types -> Python."""
    if isinstance(v, dict):
        return {k: clean(x, nd) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x, nd) for x in v]
    if isinstance(v, np.ndarray):
        return [clean(x, nd) for x in v.tolist()]
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return round(v, nd) if math.isfinite(v) else None
    return v


def json_script(data, element_id: str = "da-data") -> str:
    s = json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    s = s.replace("</", "<\\/").replace("<!--", "<\\!--")
    return f'<script type="application/json" id="{element_id}">{s}</script>'


def read_asset(name: str) -> str:
    with open(resources.report_asset(name), encoding="utf-8") as f:
        return f.read()


def coastline(lat_range: tuple[float, float], lon_range: tuple[float, float], margin: float = 0.6):
    """Land rings (Natural Earth) and coastline lines (OpenStreetMap) near the course, as [[lon, lat], ...]."""
    la0, la1 = lat_range[0] - margin, lat_range[1] + margin
    lo0, lo1 = lon_range[0] - margin, lon_range[1] + margin

    def near(coords) -> bool:
        return any(la0 <= c[1] <= la1 and lo0 <= c[0] <= lo1 for c in coords)

    land, coast = [], []
    for name in COAST_FILES:
        path = resources.asset_path("coast", name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            gj = json.load(f)
        for feat in gj.get("features", []):
            geom = feat.get("geometry") or {}
            kind, coords = geom.get("type"), geom.get("coordinates") or []
            if kind == "Polygon":
                rings = coords
            elif kind == "MultiPolygon":
                rings = [r for poly in coords for r in poly]
            elif kind == "LineString":
                rings = [coords]
            elif kind == "MultiLineString":
                rings = coords
            else:
                continue
            target = land if kind.endswith("Polygon") else coast
            for r in rings:
                if r and near(r):
                    target.append([[round(c[0], 4), round(c[1], 4)] for c in r])
    return land, coast


_THEME_BOOT = ("<script>try{var t=localStorage.getItem('da-theme');"
               "if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}</script>")


def page(title: str, body: str, data: dict, scripts: tuple[str, ...], description: str = "") -> str:
    css = read_asset("report.css")
    js = "\n".join(read_asset(s) for s in scripts)
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<meta name=\"generator\" content=\"Day After {esc(__version__)}\">\n"
        f"<meta name=\"description\" content=\"{esc(description)}\">\n"
        f"<title>{esc(title)}</title>\n{_THEME_BOOT}\n<style>\n{css}\n</style>\n</head>\n<body>\n"
        f"{body}\n{json_script(data)}\n<script>\n{js}\n</script>\n</body>\n</html>\n"
    )


# ---------------------------------------------------------------------------------------------- page parts

def table(headers: list[str], rows: list[list[str]], num_cols: set[int] = frozenset(), row_class=None,
           stack: bool = False) -> str:
    """An HTML table. `stack=True` turns rows into label/value cards on phones (data-label per cell)."""
    th = "".join(f'<th class="num">{esc(h)}</th>' if i in num_cols else f"<th>{esc(h)}</th>" for i, h in enumerate(headers))
    body = []
    for k, r in enumerate(rows):
        cls = f' class="{row_class(k)}"' if row_class and row_class(k) else ""
        tds = "".join((f'<td class="num" data-label="{esc(headers[i])}">{c}</td>' if i in num_cols
                       else f'<td data-label="{esc(headers[i])}">{c}</td>') for i, c in enumerate(r))
        body.append(f"<tr{cls}>{tds}</tr>")
    tcls = ' class="stack"' if stack else ""
    return f'<div class="table-wrap"><table{tcls}><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def figure(fid: str, caption: str, table_html: str = "", table_label: str = "Table view") -> str:
    tv = f'<details class="table-view"><summary>{esc(table_label)}</summary>{table_html}</details>' if table_html else ""
    return (f'<figure class="chart" id="{fid}"><div class="legend"></div><div class="chart-body"></div>'
            f'<figcaption>{caption}</figcaption>{tv}</figure>')


def num(v, dp=1) -> str:
    return "–" if v is None or not np.isfinite(v) else f"{v:.{dp}f}"


def model_key(model: str) -> str:
    var = {"GFS": "--m-gfs", "ECMWF": "--m-ecmwf", "ACCESS": "--m-access"}.get(model, "--m-other")
    return f'<span class="swatch-line" style="border-top-color: var({var})"></span>'


def model_cell(model: str) -> str:
    """Colour key and model name that stay on one line, also in the phone card layout."""
    return f'<span class="nowrap">{model_key(model)} {esc(model)}</span>'
