"""Locate bundled files in a source checkout and inside a PyInstaller binary alike."""
from __future__ import annotations

import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))


def bundle_root() -> str:
    """The folder holding `assets/`: the repository root, or PyInstaller's unpack folder."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(PACKAGE_DIR)


def asset_path(*parts: str) -> str:
    """A file under the top-level `assets/` folder (coastlines, logo)."""
    return os.path.join(bundle_root(), "assets", *parts)


def report_asset(name: str) -> str:
    """A file under `dayafter/report/assets/` (CSS and JavaScript inlined into reports)."""
    return os.path.join(PACKAGE_DIR, "report", "assets", name)


def data_root() -> str:
    """The private `data/` folder for `--selftest`: $DAYAFTER_DATA, else `data/` in the checkout, next to the
    binary, or in the current folder (the first that exists)."""
    env = os.environ.get("DAYAFTER_DATA")
    if env:
        return env
    cands = [os.path.join(bundle_root(), "data")]
    if getattr(sys, "frozen", False):
        cands.append(os.path.join(os.path.dirname(sys.executable), "data"))
    cands.append(os.path.join(os.getcwd(), "data"))
    return next((c for c in cands if os.path.isdir(c)), cands[0])
