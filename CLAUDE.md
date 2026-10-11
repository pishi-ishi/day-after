# Notes for Claude Code

Read `HANDOVER.md` first, then `docs/DESIGN.md`, `docs/FILE_FORMATS.md` and `docs/ACCEPTANCE.md`. Nothing has been built yet; start with HANDOVER §4 (tasks T0–T2) and then milestone M1.

Ground rules:
- `data/` is private (race logs, polars, routings). It is git-ignored: never commit it, print it or paste it into issues. Tests that need it must skip cleanly when it is absent.
- The repository is **public**. Keep personal details to what is already in the docs.
- Elapsed time = corrected ÷ official TCC. Never derive elapsed from YB finish times.
- Route-table directions are magnetic; the log is true. Times: Excel-serial UTC in the log, Australia/Sydney wall-clock in route tables.
- Keep the app dependency-light: numpy, Pillow, tzdata; standard library for the server, SQLite, CSV and JSON. No pandas or matplotlib inside `dayafter/`.
- Every analysis number shown in a report must be reproducible by `dayafter --selftest` against `fixtures/` (+ `data/` when present).
- Reports are single self-contained HTML files (inline CSS/JS/SVG, no CDN).
- On WSL2, Windows files are under `/mnt/c/`. Expedition's data folder is `/mnt/c/ProgramData/Expedition/`; read it but never write to it.
