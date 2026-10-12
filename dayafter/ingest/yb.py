"""YB Tracking: the AllPositions3 binary (all boats, all fixes), RaceSetup JSON and boat-id lists.

Layout (FILE_FORMATS §6), big-endian: u8 flags, u32 refTime, then per tracker u16 id, u16 count and
`count` moments, newest first. A moment whose first byte has bit 7 set is a delta record (u16 dt & 0x7FFF
back in time, i16 dLat, i16 dLon), otherwise an absolute record (u32 t after refTime, i32 lat, i32 lon).
Optional fields follow each record per the flags. Positions are in 1e-5 degrees.
"""
from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass

import numpy as np

from .. import net

BIN_URL = "https://cf.yb.tl/BIN/{key}/AllPositions3"
SETUP_URL = "https://cf.yb.tl/JSON/{key}/RaceSetup"

FLAG_ALT, FLAG_DTF, FLAG_LAP, FLAG_PC = 1, 2, 4, 8


@dataclass
class Track:
    tracker_id: int
    t: np.ndarray    # epoch s, oldest first (as in the file, repeated fixes included)
    lat: np.ndarray
    lon: np.ndarray
    dtf: np.ndarray | None = None

    def deduplicated(self) -> "Track":
        """The same track with repeated fixes (same time; YB repeats some) kept once."""
        keep = np.r_[True, np.diff(self.t) > 0]
        return Track(self.tracker_id, self.t[keep], self.lat[keep], self.lon[keep],
                     None if self.dtf is None else self.dtf[keep])


def decode_allpositions3(buf: bytes) -> dict[int, Track]:
    """Decode the whole file; raises ValueError unless every byte is consumed."""
    if len(buf) < 5:
        raise ValueError("AllPositions3: too short")
    flags = buf[0]
    (ref,) = struct.unpack_from(">I", buf, 1)
    has_alt, has_dtf, has_lap, has_pc = (bool(flags & f) for f in (FLAG_ALT, FLAG_DTF, FLAG_LAP, FLAG_PC))
    p = 5
    tracks: dict[int, Track] = {}
    try:
        while p < len(buf):
            tid, n = struct.unpack_from(">HH", buf, p)
            p += 4
            at = np.empty(n, dtype=np.int64)
            la = np.empty(n, dtype=np.int64)
            lo = np.empty(n, dtype=np.int64)
            dtf = np.zeros(n, dtype=np.int64) if has_dtf else None
            pa = pl = po = pd = 0
            for k in range(n):
                if buf[p] & 0x80:
                    dt, dla, dlo = struct.unpack_from(">Hhh", buf, p)
                    p += 6
                    pa, pl, po = pa - (dt & 0x7FFF), pl + dla, po + dlo
                    if has_alt:
                        p += 2
                    if has_dtf:
                        (dd,) = struct.unpack_from(">h", buf, p)
                        p += 2
                        pd += dd
                        if has_lap:
                            p += 1
                    if has_pc:
                        p += 2
                else:
                    t, pl, po = struct.unpack_from(">Iii", buf, p)
                    p += 12
                    pa = ref + t
                    if has_alt:
                        p += 2
                    if has_dtf:
                        (pd,) = struct.unpack_from(">i", buf, p)
                        p += 4
                        if has_lap:
                            p += 1
                    if has_pc:
                        p += 4
                at[k], la[k], lo[k] = pa, pl, po
                if dtf is not None:
                    dtf[k] = pd
            order = np.argsort(at, kind="stable")
            tracks[tid] = Track(tracker_id=tid, t=at[order].astype(float), lat=la[order] / 1e5, lon=lo[order] / 1e5,
                                dtf=None if dtf is None else dtf[order].astype(float))
    except struct.error as e:
        raise ValueError(f"AllPositions3: truncated at byte {p} of {len(buf)}") from e
    if p != len(buf):
        raise ValueError(f"AllPositions3: decoded {p} of {len(buf)} bytes")
    return tracks


def read_allpositions3(path: str) -> dict[int, Track]:
    with open(path, "rb") as f:
        return decode_allpositions3(f.read())


def parse_race_setup(raw: bytes) -> dict:
    """The useful parts of RaceSetup: title, zone, tracking window, gun and team names."""
    d = json.loads(raw.decode("latin-1"))
    tags = d.get("tags") or []
    gun = next((t.get("start") for t in tags if t.get("start")), None)
    teams = {int(t["id"]): {"name": (t.get("name") or "").strip(), "sail": t.get("sail", ""),
                            "model": t.get("model", ""), "finished_at": t.get("finishedAt")}
             for t in d.get("teams", []) if "id" in t}
    return {"key": d.get("url", ""), "title": d.get("title", ""), "tz": d.get("tz", ""),
            "tz_offset_s": d.get("tzOffset"), "start": d.get("start"), "stop": d.get("stop"), "gun": gun,
            "teams": teams, "associated": [(a.get("name", ""), a.get("url", "")) for a in d.get("associated2", [])]}


def read_race_setup(path: str) -> dict:
    with open(path, "rb") as f:
        return parse_race_setup(f.read())


def read_boatids(path: str) -> dict[int, str]:
    """Expedition's <KEY>-boatids.txt (or .csv): `id,name` per line."""
    out = {}
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            parts = line.strip().split(",", 1)
            if len(parts) == 2 and parts[0].strip().isdigit():
                out[int(parts[0])] = parts[1].strip()
    return out


def _validate_bin(data: bytes) -> None:
    decode_allpositions3(data)


def _validate_setup(data: bytes) -> None:
    parse_race_setup(data)


def fetch_race(key: str, out_folder: str, *, log=print) -> dict[str, str]:
    """Download AllPositions3 and RaceSetup for `key` into `out_folder`; returns the saved paths."""
    saved = {}
    data = net.http_get(BIN_URL.format(key=key), log=log)
    path = net.save_atomic(os.path.join(out_folder, f"yb_{key}_AllPositions3.bin"), data, validate=_validate_bin)
    tracks = decode_allpositions3(data)
    n_fix = sum(len(t.t) for t in tracks.values())
    log(f"saved {path} ({len(data):,} bytes, {len(tracks)} trackers, {n_fix:,} fixes)")
    if n_fix == 0:
        log("warning: YB has no positions for this key yet (race not started, or trackers not live). "
            "Fetch again after the finish.")
    saved["positions"] = path
    try:
        setup = net.http_get(SETUP_URL.format(key=key), log=log)
        path = net.save_atomic(os.path.join(out_folder, f"yb_{key}_RaceSetup.json"), setup, validate=_validate_setup)
        info = parse_race_setup(setup)
        log(f"saved {path} ('{info['title']}', {len(info['teams'])} teams)")
        saved["setup"] = path
    except (net.FetchError, ValueError) as e:
        log(f"RaceSetup not saved ({e}); boat names will come from the boat-ids file or the results")
    return saved


def read_tracks_csv(path: str) -> tuple[dict[int, Track], dict[int, str]]:
    """Decoded YB tracks as CSV (`yb_id,yb_name,time_utc,lat,lon`), e.g. fixtures/flinders_2026/yb_fleet_tracks.csv."""
    import csv
    import datetime as dt
    rows: dict[int, list] = {}
    names: dict[int, str] = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            i = int(r["yb_id"])
            names[i] = r.get("yb_name", "")
            t = dt.datetime.strptime(r["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
            rows.setdefault(i, []).append((t, float(r["lat"]), float(r["lon"])))
    out = {}
    for i, v in rows.items():
        a = np.array(sorted(v))
        out[i] = Track(tracker_id=i, t=a[:, 0], lat=a[:, 1], lon=a[:, 2]).deduplicated()
    return out, names
