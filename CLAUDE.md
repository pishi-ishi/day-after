# Notes for Claude Code

Read `HANDOVER.md` first, then `docs/DESIGN.md`, `docs/FILE_FORMATS.md` and `docs/ACCEPTANCE.md`. T0–T2 are done (see the progress note at the top of HANDOVER). The owner chose this order: first a thin **Day Before** slice (route tables + course → crew briefing HTML) plus `fetch-yb`/`fetch-bom`, ready for the Tollgate Islands Race on 16 Oct 2026; then milestones M1–M5 as in HANDOVER §8. All five were built by 12 Oct 2026 (progress notes at the top of HANDOVER).

Development: Python 3.12 in `.venv` (`uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e '.[dev]'`); run tests with `.venv/bin/python -m pytest` and the acceptance checks with `.venv/bin/python -m dayafter --selftest`. Binaries: `python packaging/make_icon.py && python packaging/build.py` (needs the `build` extra); releases come from tagging `vX.Y.Z`.

Ground rules:
- `data/` is private (race logs, polars, routings). It is git-ignored: never commit it, print it or paste it into issues. Tests that need it must skip cleanly when it is absent.
- The repository is **public**. Keep personal details to what is already in the docs.
- Elapsed time = corrected ÷ official TCC. Never derive elapsed from YB finish times.
- Route-table directions are magnetic; the log is true. Times: Excel-serial UTC in the log, Australia/Sydney wall-clock in route tables.
- Keep the app dependency-light: numpy and tzdata at run time (Pillow only at build time, for the icon); standard library for the server, SQLite, CSV and JSON. No pandas, matplotlib or eccodes inside `dayafter/` (they are dev-only cross-checks).
- Every analysis number shown in a report must be reproducible by `dayafter --selftest` against `fixtures/` (+ `data/` when present).
- Reports are single self-contained HTML files (inline CSS/JS/SVG, no CDN).
- On WSL2, Windows files are under `/mnt/c/`. Expedition's data folder is `/mnt/c/ProgramData/Expedition/`; read it but never write to it.
