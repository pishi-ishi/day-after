"""Official results (`results.csv`, FILE_FORMATS §7). Elapsed time is corrected ÷ TCC, always."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from ..core import timeutil
from .routes import read_text


@dataclass
class Result:
    place: int | None
    yacht: str
    owner: str
    division: str
    double_handed: bool
    tcc: float | None
    corrected: float | None   # seconds
    status: str

    @property
    def elapsed(self) -> float | None:
        if self.corrected is None or not self.tcc:
            return None
        return self.corrected / self.tcc

    @property
    def finished(self) -> bool:
        return self.corrected is not None and self.status.upper().startswith("FIN")


def norm_name(s: str) -> str:
    """Lowercase alphanumerics, without a trailing (DH): how boat names are compared across sources."""
    s = re.sub(r"\(\s*dh\s*\)", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def read_results(path: str) -> list[Result]:
    out = []
    for r in csv.DictReader(io.StringIO(read_text(path))):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        if not r.get("yacht"):
            continue
        tcc = r.get("tcc", "")
        out.append(Result(
            place=int(r["place"]) if r.get("place", "").isdigit() else None, yacht=r["yacht"],
            owner=r.get("owner_skipper", ""), division=r.get("division", ""),
            double_handed=r.get("double_handed", "").lower() in ("yes", "y", "true", "1"),
            tcc=float(tcc) if tcc else None, corrected=timeutil.parse_duration(r.get("corrected", "")),
            status=r.get("status", "") or ("FINISHED" if r.get("corrected") else ""),
        ))
    return out


def find(results: list[Result], name: str) -> Result | None:
    key = norm_name(name)
    return next((r for r in results if norm_name(r.yacht) == key), None)
