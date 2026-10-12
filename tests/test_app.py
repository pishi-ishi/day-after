"""The browser app's server: token and Host checks, the folder scan, and the guard on Expedition's folder."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from dayafter.app import server


@pytest.fixture()
def app():
    server.Handler.token = "test-token"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _get(url, token="test-token", host=None):
    req = urllib.request.Request(url, headers={"X-DA-Token": token, **({"Host": host} if host else {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_token_and_host_are_checked(app, tmp_path):
    assert _get(f"{app}/api/browse?path={tmp_path}", token="wrong")[0] == 403
    assert _get(f"{app}/api/browse?path={tmp_path}", host="evil.example")[0] == 403
    assert _get(f"{app}/")[0] == 403  # the page itself needs ?t=
    status, body = _get(f"{app}/?t=test-token")
    assert status == 200 and b"test-token" in body and b"const DA" in body


def test_scan_and_upload(app, tmp_path):
    (tmp_path / "log-2026Oct16.csv").write_text("!Boat,Utc,BSP\n!boat,0,1\n!v1\n", encoding="utf-8")
    status, body = _get(f"{app}/api/scan?folder={tmp_path}")
    d = json.loads(body)
    assert status == 200 and d["checklist"]["after"][0]["n"] == 1 and not d["protected"]
    req = urllib.request.Request(f"{app}/api/upload?folder={tmp_path}&name=notes.md", data=b"Reef early.",
                                 headers={"X-DA-Token": "test-token"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        saved = json.loads(r.read())
    assert saved["kind"] == "notes" and (tmp_path / "added" / "notes.md").read_text(encoding="utf-8") == "Reef early."


def test_never_writes_into_expeditions_folder():
    assert server._protected("/mnt/c/ProgramData/Expedition/log")
    assert server._protected("C:\\ProgramData\\Expedition\\grib")
    assert not server._protected("/mnt/c/Users/user/Documents/races")
