"""Command line: `dayafter before <race folder>`, `dayafter fetch-yb`, `dayafter fetch-bom`, `dayafter selftest`."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import webbrowser

from . import __version__


def _is_wsl() -> bool:
    try:
        return "microsoft" in os.uname().release.lower()
    except AttributeError:  # Windows has no uname
        return False


def open_in_browser(path: str) -> None:
    """Open a local file: wslview or cmd.exe on WSL2, the default browser elsewhere."""
    path = os.path.abspath(path)
    if _is_wsl():
        if shutil.which("wslview"):
            subprocess.run(["wslview", path], check=False)
            return
        if shutil.which("wslpath") and shutil.which("cmd.exe"):
            win = subprocess.run(["wslpath", "-w", path], capture_output=True, text=True).stdout.strip()
            subprocess.run(["cmd.exe", "/c", "start", "", win], check=False, cwd="/mnt/c")
            return
    webbrowser.open("file://" + path)


def cmd_before(args) -> int:
    from .analysis.briefing import build_briefing
    from .report import day_before

    b = build_briefing(args.folder, models=args.models, turning_mark=args.turning_mark)
    out = day_before.write(b, args.out)
    print(f"Day Before briefing for {b.race_name}: {', '.join(p.model for p in b.plans)}")
    if b.window:
        from .core.timeutil import fmt_local
        print(f"  change window {fmt_local(b.window['t0'], b.tz)}–{fmt_local(b.window['t1'], b.tz)}: {b.window['verdict']}")
    for w in b.warnings:
        print(f"  warning: {w}")
    print(f"  wrote {out}")
    if args.open:
        open_in_browser(out)
    return 0


def cmd_build(args) -> int:
    import json
    from .analysis.race_analysis import analyse
    from .report import editions as editions_mod

    project = None
    if args.race_file:
        with open(args.race_file, encoding="utf-8") as f:
            project = json.load(f)
    a = analyse(args.folder, args.extra or [], project, log=lambda m: print(f"  {m}"))
    eds = [e.strip() for e in (args.editions or ",".join(editions_mod.EDITIONS)).split(",") if e.strip()]
    out_dir = None
    if args.out:
        out_dir = args.out if not args.out.lower().endswith(".html") else os.path.dirname(os.path.abspath(args.out))
    paths = editions_mod.write_editions(a, eds, out_dir, log=lambda m: print(f"  {m}"), season_path=args.season,
                                        use_season=not args.no_season)
    print(f"Day After for {a.race_name}: {a.boat}, {a.result.place if a.result and a.result.place else '?'}"
          f" of {sum(r.finished for r in a.results) or '?'}")
    for w in a.warnings:
        print(f"  warning: {w}")
    for ed, p in paths.items():
        print(f"  wrote {ed}: {p}")
    if args.open and paths:
        open_in_browser(next(iter(paths.values())))
    return 0


def cmd_fetch_yb(args) -> int:
    from .ingest import yb

    yb.fetch_race(args.key, args.out)
    return 0


def cmd_fetch_bom(args) -> int:
    from .ingest import bom

    failed = 0
    for wmo in args.stations:
        try:
            bom.fetch_station(wmo, args.out, product=args.product)
        except Exception as e:  # noqa: BLE001 - report every station, then fail at the end
            print(f"station {wmo}: {e}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def cmd_selftest(args) -> int:
    from .selftest import run

    return run(verbose=not args.quiet)


def cmd_serve(args) -> int:
    print("The browser app arrives with milestone M5. Until then:\n"
          "  dayafter before <race folder> [--open]     crew weather briefing from Expedition route tables\n"
          "  dayafter build <race folder> [--open]      the Day After report (navigator edition)\n"
          "  dayafter fetch-yb <race key> <folder>      save the YB fleet tracks (do it on race day)\n"
          "  dayafter fetch-bom <wmo ...> --out <folder> save BOM coastal observations (within 72 h)\n"
          "  dayafter selftest                         check the build against the Flinders 2026 numbers")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dayafter", description="Day After: post-race and pre-race analysis for offshore racing.")
    p.add_argument("--version", action="version", version=f"Day After {__version__}")
    sub = p.add_subparsers(dest="command")

    b = sub.add_parser("before", help="build the Day Before crew briefing from a race folder")
    b.add_argument("folder", help="race folder holding the Expedition route tables (searched recursively)")
    b.add_argument("--models", help="models to show, comma-separated (default: up to three, ECMWF, GFS, ACCESS first)")
    b.add_argument("--turning-mark", help="name of the turning mark (default: from race.dayafter.json, else farthest from the start)")
    b.add_argument("--out", help="output HTML file (default: <folder>/out/day_before_<race>.html)")
    b.add_argument("--open", action="store_true", help="open the briefing in the browser")
    b.set_defaults(func=cmd_before)

    d = sub.add_parser("build", help="build the Day After reports (all editions) from a race folder")
    d.add_argument("folder", help="race folder: Expedition log, course, route tables, results, events (searched recursively)")
    d.add_argument("--extra", action="append", help="another folder with inputs for this race (repeatable)")
    d.add_argument("--race-file", help="race.dayafter.json to use instead of the one in the folder")
    d.add_argument("--editions", help="editions to write, comma-separated (default: all: navigator,crew)")
    d.add_argument("--out", help="output folder (default: <folder>/out)")
    d.add_argument("--season", help="season database (default: season.sqlite next to the app, or $DAYAFTER_SEASON)")
    d.add_argument("--no-season", action="store_true", help="do not store this race in the season database")
    d.add_argument("--open", action="store_true", help="open the report in the browser")
    d.set_defaults(func=cmd_build)

    y = sub.add_parser("fetch-yb", help="download YB fleet tracks and race setup for a race key")
    y.add_argument("key", help="YB race key, the last part of the tracker link (e.g. bwps2026_2)")
    y.add_argument("out", nargs="?", default=".", help="folder to save into (default: current folder)")
    y.set_defaults(func=cmd_fetch_yb)

    o = sub.add_parser("fetch-bom", help="download BOM coastal observations (each file holds the last 72 h)")
    o.add_argument("stations", nargs="+", help="WMO station ids, e.g. 95768 (North Head)")
    o.add_argument("--out", default=".", help="folder to save into (default: current folder)")
    o.add_argument("--product", default="IDN60701", help="BOM product id (default IDN60701, NSW coastal)")
    o.set_defaults(func=cmd_fetch_bom)

    s = sub.add_parser("selftest", help="check the build against the Flinders 2026 acceptance numbers")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(func=cmd_selftest)

    v = sub.add_parser("serve", help="start the browser app (milestone M5)")
    v.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        return cmd_serve(args)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as e:
        print(f"dayafter: {e}", file=sys.stderr)
        return 2
