"""Time conversions used across Day After.

All internal times are epoch seconds (UTC, float). Expedition logs and events use the Excel serial
(days since 1899-12-30, UTC); Expedition route tables use local wall-clock in the zone named by the
time column header, which is a Windows time-zone ID (DST included despite "Standard" in the name).
"""
from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

import numpy as np

EXCEL_EPOCH_DAYS = 25569.0  # 1970-01-01 in days since 1899-12-30
UTC = dt.timezone.utc
DEFAULT_TZ = "Australia/Sydney"

# Windows time-zone IDs (as Expedition writes them) -> IANA zones.
WINDOWS_TZ = {
    "AUS Eastern Standard Time": "Australia/Sydney",
    "Tasmania Standard Time": "Australia/Hobart",
    "E. Australia Standard Time": "Australia/Brisbane",
    "Cen. Australia Standard Time": "Australia/Adelaide",
    "AUS Central Standard Time": "Australia/Darwin",
    "W. Australia Standard Time": "Australia/Perth",
    "Lord Howe Standard Time": "Australia/Lord_Howe",
    "New Zealand Standard Time": "Pacific/Auckland",
    "GMT Standard Time": "Europe/London",
    "Coordinated Universal Time": "UTC",
    "UTC": "UTC",
}


def excel_to_epoch(days):
    """Excel serial days (UTC) -> epoch seconds. Scalars give a float, arrays an array."""
    if np.ndim(days):
        return (np.asarray(days, dtype=float) - EXCEL_EPOCH_DAYS) * 86400.0
    return (float(days) - EXCEL_EPOCH_DAYS) * 86400.0


def epoch_to_excel(sec):
    return sec / 86400.0 + EXCEL_EPOCH_DAYS


def zone(name: str | None) -> ZoneInfo:
    return ZoneInfo(name or DEFAULT_TZ)


def tz_from_windows_id(header: str) -> str | None:
    """Map a Windows zone ID such as 'AUS Eastern Standard Time' to an IANA name, or None."""
    return WINDOWS_TZ.get(header.strip().strip('"'))


def local_to_epoch(local: dt.datetime, tz: str) -> float:
    """Naive local wall-clock -> epoch seconds. Non-existent DST times shift forward, as zoneinfo does."""
    return local.replace(tzinfo=zone(tz)).timestamp()


def parse_local(text: str, fmt: str, tz: str) -> float:
    return local_to_epoch(dt.datetime.strptime(text.strip(), fmt), tz)


def epoch_to_local(sec: float, tz: str) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(sec), zone(tz))


def fmt_local(sec: float | None, tz: str, fmt: str = "%H:%M") -> str:
    if sec is None or not np.isfinite(sec):
        return "–"
    return epoch_to_local(sec, tz).strftime(fmt)


def utc_offset_label(sec: float, tz: str) -> str:
    """'AEDT (UTC+11)' style label for the zone in force at that instant."""
    d = epoch_to_local(sec, tz)
    off = d.utcoffset().total_seconds() / 3600
    sign = "+" if off >= 0 else "-"
    hours = f"{abs(off):g}"
    return f"{d.tzname()} (UTC{sign}{hours})"


_DUR_HMS = re.compile(r"^\s*(-)?\s*(?:(\d+):)?(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)\s*$")
_DUR_HM = re.compile(r"^\s*(-)?\s*(\d+):(\d{1,2})(?::(\d{1,2}(?:\.\d+)?))?\s*$")
_DUR_WORDS = re.compile(r"^\s*(-)?\s*(?:(\d+)\s*d\s*)?(?:(\d+)\s*h\s*)?(?:(\d+)\s*m\s*)?(?:(\d+(?:\.\d+)?)\s*s)?\s*$")


def parse_duration(text: str) -> float | None:
    """Seconds from 'h:mm:ss', 'd:hh:mm:ss', '11h 04m 45s', '-01h 55m 10s', '-47m 52s'. None if blank."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    m = _DUR_HMS.match(s)
    if m:  # d:hh:mm:ss
        neg, d, h, mi, se = m.groups()
        v = int(d or 0) * 86400 + int(h) * 3600 + int(mi) * 60 + float(se)
        return -v if neg else v
    m = _DUR_HM.match(s)
    if m:  # h:mm[:ss]
        neg, h, mi, se = m.groups()
        v = int(h) * 3600 + int(mi) * 60 + float(se or 0)
        return -v if neg else v
    m = _DUR_WORDS.match(s)
    if m and any(m.groups()[1:]):
        neg, d, h, mi, se = m.groups()
        v = int(d or 0) * 86400 + int(h or 0) * 3600 + int(mi or 0) * 60 + float(se or 0)
        return -v if neg else v
    raise ValueError(f"unrecognised duration: {text!r}")


def fmt_duration(sec: float | None, signed: bool = False) -> str:
    """'11:44:00' (or '1:02:03:04' over a day). With signed=True a leading '+'/'−' is added."""
    if sec is None or not np.isfinite(sec):
        return "–"
    sign = ("−" if sec < 0 else "+") if signed else ("−" if sec < 0 else "")
    s = int(round(abs(sec)))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    body = f"{d}:{h:02d}:{m:02d}:{s:02d}" if d else f"{h}:{m:02d}:{s:02d}"
    return sign + body


def fmt_minutes(sec: float | None, signed: bool = True) -> str:
    """Whole minutes, e.g. '+23 min', '−4 min'."""
    if sec is None or not np.isfinite(sec):
        return "–"
    m = int(round(sec / 60.0))
    if not signed:
        return f"{abs(m)} min"
    return f"{'+' if m > 0 else '−' if m < 0 else '±'}{abs(m)} min"
