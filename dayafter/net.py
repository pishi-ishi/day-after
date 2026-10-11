"""Downloads with retries, and saving that never replaces a good file with a worse one.

YB's CDN answers 503 now and then (five times in a row on 11 Oct 2026), so every fetch retries with
exponential backoff. Data that disappears (YB, BOM) is cached in the race folder on first success.
"""
from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from typing import Callable

from . import __version__

USER_AGENT = f"DayAfter/{__version__} (+https://github.com/pishi-ishi/day-after)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    pass


def http_get(url: str, *, retries: int = 7, backoff: float = 2.0, max_wait: float = 30.0, timeout: float = 60.0,
             log: Callable[[str], None] | None = None) -> bytes:
    """GET `url`, retrying on 5xx, 429, timeouts and connection errors. Raises FetchError at the end."""
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in RETRY_STATUS:
                raise FetchError(f"{url}: HTTP {e.code} {e.reason}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e
        if attempt < retries:
            wait = min(backoff ** attempt, max_wait)
            if log:
                log(f"  {url}: {last}; retrying in {wait:.0f} s ({attempt}/{retries - 1})")
            time.sleep(wait)
    raise FetchError(f"{url}: gave up after {retries} attempts ({last})")


def save_atomic(path: str, data: bytes, *, validate: Callable[[bytes], None] | None = None) -> str:
    """Write `data` to `path` via a temporary file. `validate` raises on bad data (nothing is written).

    If a different, valid file is already there and the new data is smaller, the old file is kept and
    the new one is saved next to it with a timestamp, so a truncated download never replaces good data.
    """
    if validate:
        validate(data)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.isfile(path):
        old = open(path, "rb").read()
        if old == data:
            return path
        old_ok = True
        if validate:
            try:
                validate(old)
            except Exception:
                old_ok = False
        if old_ok and len(data) < len(old):
            stem, ext = os.path.splitext(path)
            path = f"{stem}_{time.strftime('%Y%m%d-%H%M%S')}{ext}"
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    return path
