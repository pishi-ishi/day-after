"""Weather-model names: one canonical name per model, whatever Expedition or Saildocs calls it."""
from __future__ import annotations

import re

# Order of preference when the navigator has not chosen (the crew edition shows at most three).
PREFERRED = ["ECMWF", "GFS", "ACCESS", "ICON", "AIGFS", "AIFS", "UM"]

_RULES = [
    (re.compile(r"^ACCESS", re.I), "ACCESS"),
    (re.compile(r"^(EC[\s_-]*)?AIFS", re.I), "AIFS"),
    (re.compile(r"^AIGFS", re.I), "AIGFS"),
    (re.compile(r"^(ECMWF|IFS)", re.I), "ECMWF"),
    (re.compile(r"^GFS", re.I), "GFS"),
    (re.compile(r"^ICON", re.I), "ICON"),
    (re.compile(r"^(UM|UKMO|UK\s*MET)", re.I), "UM"),
]


def canonical_model(label: str | None) -> str:
    """'ACCESS SY' -> 'ACCESS', 'EC_AIFS' -> 'AIFS', '' -> 'Reference' (Expedition's active route)."""
    s = (label or "").strip()
    if not s:
        return "Reference"
    for rx, name in _RULES:
        if rx.match(s):
            return name
    return s.upper()


def rank(model: str) -> int:
    return PREFERRED.index(model) if model in PREFERRED else len(PREFERRED)
