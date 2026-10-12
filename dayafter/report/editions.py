"""All Day After editions from one analysis: the numbers are the same in each; depth and tone differ."""
from __future__ import annotations

import os

from ..analysis.race_analysis import RaceAnalysis

EDITIONS = ("navigator", "crew")


def write_editions(a: RaceAnalysis, editions=EDITIONS, out_dir: str | None = None, log=None,
                   season_path: str | None = None, use_season: bool = True) -> dict[str, str]:
    """Write the editions; unless `use_season` is False, first store the race in the season database and give the
    navigator edition the season views."""
    say = log or (lambda m: None)
    out_dir = out_dir or os.path.join(a.folder, "out")
    paths: dict[str, str] = {}
    season = None
    if use_season:
        from .. import season as season_mod
        try:
            rid = season_mod.store(a, a.performance, season_path)
            season = season_mod.load(season_path)
            n = len(season["races"])
            say(f"season database: {rid} stored ({n} race{'s' if n != 1 else ''} in {season_path or season_mod.default_path()})")
        except Exception as e:  # noqa: BLE001 - the reports matter more than the database
            say(f"season database not updated: {e}")
    for ed in editions:
        say(f"writing the {ed} edition")
        if ed == "navigator":
            from . import navigator
            paths[ed] = navigator.write(a, os.path.join(out_dir, navigator.filename(a)), season)
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
