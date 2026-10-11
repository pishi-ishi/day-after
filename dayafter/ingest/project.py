"""The race file `race.dayafter.json` (FILE_FORMATS §12): settings that cannot be read from the inputs.

Every key is optional. Unknown keys are kept, so newer files survive older versions of Day After.
"""
from __future__ import annotations

import copy
import json
import os
from typing import Any

FILENAME = "race.dayafter.json"

DEFAULTS: dict[str, Any] = {
    "race": {"name": "", "series": "", "gun_local": "", "tz": "Australia/Sydney", "variation_deg_e": None,
             "category": ""},
    "boat": {"name": "Llama II", "tcc": None, "division": "", "polar": "", "masthead_wind_factor": 1.0},
    "inputs": {},
    "course": {"turning_mark": "", "marks_route": "", "gate_step_nm": 5},
    "fleet": {"yb_key": "", "rivals": [], "rule": "same division, nearest TCC, 3"},
    "editions": ["navigator", "skipper", "crew", "client"],
    "crew_models": "auto",
    "notes": {"navigator": "", "skipper": ""},
}


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(folder: str) -> dict[str, Any]:
    """The race file in `folder` merged over the defaults (defaults alone when there is none)."""
    path = os.path.join(folder, FILENAME)
    data: dict[str, Any] = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    proj = _merge(DEFAULTS, data)
    proj["_path"] = path if os.path.isfile(path) else None
    return proj


def save(folder: str, project: dict[str, Any]) -> str:
    path = os.path.join(folder, FILENAME)
    data = {k: v for k, v in project.items() if not k.startswith("_")}
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return path
