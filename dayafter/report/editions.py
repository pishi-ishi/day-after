"""All Day After editions from one analysis: the numbers are the same in each; depth and tone differ."""
from __future__ import annotations

import os

from ..analysis.race_analysis import RaceAnalysis

EDITIONS = ("navigator", "crew")


def write_editions(a: RaceAnalysis, editions=EDITIONS, out_dir: str | None = None, log=None) -> dict[str, str]:
    say = log or (lambda m: None)
    out_dir = out_dir or os.path.join(a.folder, "out")
    paths: dict[str, str] = {}
    for ed in editions:
        say(f"writing the {ed} edition")
        if ed == "navigator":
            from . import navigator
            paths[ed] = navigator.write(a, os.path.join(out_dir, navigator.filename(a)))
        elif ed == "crew":
            if not a.routes:
                say("crew edition skipped: it needs the route tables")
                continue
            from ..analysis.crew import build_crew_briefing
            from . import day_before
            b = build_crew_briefing(a)
            paths[ed] = day_before.write(b, os.path.join(out_dir, day_before.filename(b)))
        else:
            raise ValueError(f"unknown edition {ed!r} (have: {', '.join(EDITIONS)})")
    return paths
