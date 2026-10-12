"""The Day After app: a local web server (standard library only) that opens in the default browser.

Bound to 127.0.0.1 on a free port. Every API call carries a random per-session token, and the Host header must
name this server, so other web pages cannot drive it. It reads anything the user points it at, writes only into
the chosen race folder (race file, dropped files, downloads, `out/`) and never into Expedition's own folder.
"""
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import string
import sys
import threading
import time
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import __version__, resources
from ..ingest import detect, project as project_mod

PROTECTED = ("/mnt/c/programdata/expedition", "c:\\programdata\\expedition", "c:/programdata/expedition")
MAX_UPLOAD = 200 * 1024 * 1024

# what each mode needs: (Inputs field, label, level) with level required | recommended | optional
NEEDS = {
    "before": [("route_tables", "Expedition route tables (one per model)", "required"),
               ("route_summaries", "Summary of all routes", "optional"),
               ("course", "Course (GPX, course.csv or Expedition marks)", "recommended"),
               ("gribs", "GRIB files (models without a route table)", "optional"),
               ("project", "Race file (race.dayafter.json)", "optional")],
    "after": [("logs", "Expedition log (log-YYYYMonDD.csv)", "required"),
              ("polars", "Polar (or boat.polar in the race file)", "recommended"),
              ("results", "Results with TCC and corrected time", "recommended"),
              ("yb", "YB fleet tracks (fetch below)", "recommended"),
              ("route_tables", "Expedition route tables", "recommended"),
              ("expedition_db", "Expedition.db (events: gun, sails, reefs)", "optional"),
              ("gribs", "GRIB files from Expedition's grib folder", "optional"),
              ("bom", "BOM coastal observations (.axf)", "optional"),
              ("course", "Course (GPX, course.csv or Expedition marks)", "optional"),
              ("project", "Race file (race.dayafter.json)", "optional")],
}


def _protected(path: str) -> bool:
    """True inside Expedition's own data folder (C:\\ProgramData\\Expedition, or /mnt/c/... on WSL2)."""
    forms = {path.replace("\\", "/").lower(), os.path.abspath(path).replace("\\", "/").lower()}
    prefixes = [x.replace("\\", "/") for x in PROTECTED]
    return any(f.startswith(x) or f[2:].startswith(x) and f[1] == ":" for f in forms for x in prefixes)


def _roots() -> list[dict]:
    out = [{"name": "Home", "path": os.path.expanduser("~")}]
    if sys.platform.startswith("win"):
        for d in string.ascii_uppercase:
            if os.path.isdir(f"{d}:\\"):
                out.append({"name": f"{d}:", "path": f"{d}:\\"})
    else:
        if os.path.isdir("/mnt/c/Users"):
            out.append({"name": "Windows users (C:)", "path": "/mnt/c/Users"})
        out.append({"name": "/", "path": "/"})
    here = resources.bundle_root()
    if os.path.isdir(os.path.join(here, "data")):
        out.append({"name": "Day After data", "path": os.path.join(here, "data")})
    return out


def browse(path: str | None) -> dict:
    path = os.path.abspath(path or os.path.expanduser("~"))
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    dirs, nfiles = [], 0
    try:
        for e in sorted(os.scandir(path), key=lambda e: e.name.lower()):
            if e.name.startswith("."):
                continue
            if e.is_dir(follow_symlinks=False):
                dirs.append(e.name)
            else:
                nfiles += 1
    except PermissionError:
        pass
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else None, "dirs": dirs, "files": nfiles,
            "roots": _roots()}


def scan(folder: str) -> dict:
    inputs = detect.scan(folder)
    proj = project_mod.load(folder)
    have = {k: v for k, v in inputs.__dict__.items() if isinstance(v, list)}
    have["course"] = inputs.course_csv + inputs.gpx + inputs.marks_xml
    have["yb"] = inputs.yb_positions + inputs.yb_tracks_csv
    checklist = {}
    for mode, needs in NEEDS.items():
        rows = []
        for key, label, level in needs:
            files = have.get(key, [])
            if key == "polars" and not files and (proj.get("boat") or {}).get("polar"):
                files = [proj["boat"]["polar"]]
            rows.append({"key": key, "label": label, "level": level, "n": len(files),
                         "files": [os.path.relpath(f, folder) if os.path.isabs(f) else f for f in files[:8]]})
        checklist[mode] = rows
    results = []
    for p in inputs.results:
        try:
            from ..ingest.results import read_results
            results += [{"yacht": r.yacht, "division": r.division, "tcc": r.tcc, "place": r.place} for r in read_results(p)]
        except Exception:  # noqa: BLE001 - the checklist must render
            pass
    outs = []
    od = os.path.join(folder, "out")
    if os.path.isdir(od):
        for n in sorted(os.listdir(od)):
            if n.endswith(".html"):
                p = os.path.join(od, n)
                outs.append({"name": n, "path": p, "mtime": os.path.getmtime(p)})
    return {"folder": os.path.abspath(folder), "checklist": checklist, "project": {k: v for k, v in proj.items()
            if not k.startswith("_")}, "has_project": bool(proj.get("_path")), "results": results, "outputs": outs,
            "encrypted_gribs": len(inputs.gribs_encrypted), "protected": _protected(folder)}


# ---------------------------------------------------------------------------------------------- jobs

class Job:
    def __init__(self, kind: str):
        self.id = secrets.token_hex(6)
        self.kind = kind
        self.lines: list[str] = []
        self.state = "running"
        self.outputs: dict[str, str] = {}
        self.started = time.time()
        self.error = ""

    def log(self, msg: str) -> None:
        self.lines.append(msg)

    def as_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "state": self.state, "lines": self.lines[-200:],
                "outputs": self.outputs, "error": self.error, "seconds": round(time.time() - self.started, 1)}


JOBS: dict[str, Job] = {}


def _run(job: Job, fn) -> None:
    def target():
        try:
            fn(job)
            job.state = "done"
        except Exception as e:  # noqa: BLE001 - shown in the app
            job.error = f"{type(e).__name__}: {e}"
            job.log(traceback.format_exc(limit=3))
            job.state = "failed"
    threading.Thread(target=target, daemon=True).start()


def start_build(folder: str, mode: str, editions: list[str]) -> Job:
    job = Job(f"build-{mode}")

    def work(j: Job):
        if mode == "before":
            from ..analysis.briefing import build_briefing
            from ..report import day_before
            j.log("reading the route tables")
            b = build_briefing(folder)
            for w in b.warnings:
                j.log(f"warning: {w}")
            j.outputs["day before"] = day_before.write(b)
            j.log(f"wrote {j.outputs['day before']}")
            return
        from ..analysis.race_analysis import analyse
        from ..report import editions as editions_mod
        a = analyse(folder, log=j.log)
        for w in a.warnings:
            j.log(f"warning: {w}")
        eds = ["7seas" if e == "client" else e for e in editions] or list(editions_mod.DEFAULT_EDITIONS)
        j.outputs.update(editions_mod.write_editions(a, eds, log=j.log))
        for ed, p in j.outputs.items():
            j.log(f"wrote {ed}: {p}")

    JOBS[job.id] = job
    _run(job, work)
    return job


def start_fetch_yb(folder: str, key: str) -> Job:
    job = Job("fetch-yb")

    def work(j: Job):
        from ..ingest import yb
        out = os.path.join(folder, "fleet")
        os.makedirs(out, exist_ok=True)
        j.outputs.update(yb.fetch_race(key, out, log=j.log))

    JOBS[job.id] = job
    _run(job, work)
    return job


def preview(folder: str) -> dict:
    """Our track (every 30 s) and the routes, for the quick map."""
    import numpy as np
    from ..report import html as H
    inputs = detect.scan(folder)
    out: dict = {"track": None, "routes": []}
    lats, lons = [], []
    if inputs.logs:
        from ..ingest.expedition_log import read_logs
        lg = read_logs(inputs.logs)
        tl = lg.timeline(lg.t_first, lg.t_last)
        k = np.arange(0, len(tl), 30)
        la, lo = tl["Lat"][k], tl["Lon"][k]
        ok = np.isfinite(la) & np.isfinite(lo)
        out["track"] = {"t": tl.t[k][ok], "lat": la[ok], "lon": lo[ok]}
        lats += list(la[ok])
        lons += list(lo[ok])
    from ..ingest.routes import read_route_table
    for p in inputs.route_tables[:6]:
        try:
            r = read_route_table(p)
        except Exception:  # noqa: BLE001 - preview only
            continue
        out["routes"].append({"model": r.model, "t": r.t, "lat": r.lat, "lon": r.lon})
        lats += list(r.lat)
        lons += list(r.lon)
    if lats:
        land, coast = H.coastline((min(lats), max(lats)), (min(lons), max(lons)))
        out["land"], out["coast"] = land, coast
    return H.clean(out, 5)


# ---------------------------------------------------------------------------------------------- HTTP

def app_page(token: str) -> bytes:
    from ..report.html import read_asset
    with open(os.path.join(os.path.dirname(__file__), "app.html"), encoding="utf-8") as f:
        html = f.read()
    html = html.replace("/*CHARTS*/", read_asset("charts.js")).replace("/*REPORT_CSS*/", read_asset("report.css"))
    html = html.replace("__TOKEN__", token).replace("__VERSION__", __version__)
    return html.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = f"DayAfter/{__version__}"
    token = ""
    port = 0

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, status: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data, default=str).encode("utf-8"))

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _auth(self, q: dict) -> bool:
        tok = self.headers.get("X-DA-Token") or (q.get("t") or [""])[0]
        return self._host_ok() and secrets.compare_digest(tok, self.token)

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if not self._host_ok():
            return self._send(403, b"forbidden", "text/plain")
        if u.path == "/":
            if (q.get("t") or [""])[0] != self.token:
                return self._send(403, b"Open Day After from the link it printed when it started.", "text/plain")
            return self._send(200, app_page(self.token), "text/html; charset=utf-8")
        if not self._auth(q):
            return self._send(403, b"forbidden", "text/plain")
        arg = lambda k, d=None: (q.get(k) or [d])[0]
        try:
            if u.path == "/api/browse":
                return self._json(browse(arg("path")))
            if u.path == "/api/scan":
                return self._json(scan(arg("folder")))
            if u.path == "/api/preview":
                return self._json(preview(arg("folder")))
            if u.path.startswith("/api/job/"):
                job = JOBS.get(u.path.rsplit("/", 1)[-1])
                return self._json(job.as_dict() if job else {"state": "unknown"}, 200 if job else 404)
            if u.path == "/file":
                p = os.path.abspath(arg("path", ""))
                if not (p.endswith(".html") and os.path.basename(os.path.dirname(p)) == "out" and os.path.isfile(p)):
                    return self._send(404, b"not a report", "text/plain")
                with open(p, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
        except FileNotFoundError as e:
            return self._json({"error": f"not found: {e}"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        return self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if not self._auth(q):
            return self._send(403, b"forbidden", "text/plain")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            return self._json({"error": "file too large"}, 413)
        body = self.rfile.read(n) if n else b""
        arg = lambda k, d=None: (q.get(k) or [d])[0]
        try:
            if u.path == "/api/upload":
                folder, name = arg("folder"), os.path.basename(arg("name", ""))
                if not folder or not name or _protected(folder) or not os.path.isdir(folder):
                    return self._json({"error": "cannot write there"}, 400)
                dest = os.path.join(folder, "added", name)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest + ".part", "wb") as f:
                    f.write(body)
                os.replace(dest + ".part", dest)
                return self._json({"saved": dest, "kind": detect.classify(dest)})
            data = json.loads(body or b"{}")
            folder = data.get("folder")
            if not folder or not os.path.isdir(folder):
                return self._json({"error": "choose a race folder first"}, 400)
            if _protected(folder):
                return self._json({"error": "that is Expedition's own folder; copy the files into a race folder"}, 400)
            if u.path == "/api/project":
                proj = project_mod.load(folder)
                for section, values in (data.get("project") or {}).items():
                    if isinstance(values, dict):
                        proj.setdefault(section, {}).update(values)
                    else:
                        proj[section] = values
                return self._json({"saved": project_mod.save(folder, proj)})
            if u.path == "/api/build":
                job = start_build(folder, data.get("mode", "after"), data.get("editions") or [])
                return self._json(job.as_dict())
            if u.path == "/api/fetch-yb":
                key = (data.get("key") or "").strip()
                if not key or not all(c.isalnum() or c in "_-" for c in key):
                    return self._json({"error": "enter the YB race key (the last part of the tracker link)"}, 400)
                return self._json(start_fetch_yb(folder, key).as_dict())
        except Exception as e:  # noqa: BLE001
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        return self._send(404, b"not found", "text/plain")


def serve(port: int = 0, open_browser: bool = True, folder: str | None = None) -> None:
    token = secrets.token_urlsafe(18)
    Handler.token = token
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    Handler.port = httpd.server_address[1]
    url = f"http://127.0.0.1:{Handler.port}/?t={token}"
    if folder:
        url += "&folder=" + urllib.parse.quote(os.path.abspath(folder))
    print(f"Day After {__version__} is running at\n  {url}\nKeep this window open while you use it; press Ctrl+C to stop.", flush=True)
    if open_browser:
        from ..cli import open_url
        threading.Timer(0.5, lambda: open_url(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        httpd.server_close()


mimetypes.add_type("text/javascript", ".js")
