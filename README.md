# Day After

**Post-race (and pre-race) analysis for offshore yacht racing, on your own computer.**

Day After reads your Expedition instrument log, the optimal routes and GRIB forecasts you sailed with, the YB tracker positions of the whole fleet and the official results. From them it builds self-contained, interactive HTML reports in the style of Njord Analytics:

- **Plan vs reality**: your track and mark times against each model's optimal route, and forecast vs observed wind.
- **Fleet comparison**: corrected-time gaps to similar-rated rivals every 5 nm, ranks at the marks, and who the weather favoured.
- **Performance & calibration**: polar %, targets, manoeuvres, and checks that catch bad boat-speed and wind calibration.
- **Season**: a local database that tracks targets, calibration, model accuracy and rivals across races.

Reports come in four editions (navigator, skipper/owner, crew and a branded 7 Seas Marine client edition). A **Day Before** mode turns the routings into a crew weather briefing: meteograms, the window when a change could arrive vs your ETA at the turning mark, the planned sail changes and the expected tacks and gybes.

> **Status (12 Oct 2026): all five milestones are built.** The Day Before briefing, the four post-race editions, the browser app, the season database and `--selftest` work from source and as one-file binaries; see [`HANDOVER.md`](HANDOVER.md) for the build notes.

## Download

One file per operating system, no install, no Python needed. Get it from the [latest release](https://github.com/pishi-ishi/day-after/releases/latest):

| OS | File |
|---|---|
| Windows 10/11 64-bit | `dayafter-windows-x64.exe` |
| macOS (Apple silicon) | `dayafter-macos-arm64` |
| Linux 64-bit | `dayafter-linux-x64` |

Each release lists the SHA-256 of every file in its notes and in `SHA256SUMS.txt`. Check a download with `certutil -hashfile dayafter-windows-x64.exe SHA256` (Windows), `shasum -a 256 dayafter-macos-arm64` (macOS) or `sha256sum dayafter-linux-x64` (Linux).

Run it and Day After opens in your web browser at `http://127.0.0.1:<port>`: choose the race folder, check the inputs list, and press **Build**. Keep the console window open while you use it; close it to quit. On macOS, run `chmod +x dayafter-macos-arm64` once and allow it under System Settings → Privacy & Security (the binary is not notarised). `dayafter --selftest` checks the binary; with your private `data/` folder next to it (or `DAYAFTER_DATA` pointing at it) it also rebuilds every Flinders Islet 2026 number.

## How a race works

1. **Before the race**: export a routing table per model from Expedition and run **Day Before** for the crew briefing.
2. **After the race**: collect the log, the YB race key, the results and the BOM observations (see [`docs/DATA_GUIDE.md`](docs/DATA_GUIDE.md)), point Day After at the race folder and press **Build**.

## Use it now (from source)

Until the binaries are released, run Day After from a checkout with Python 3.12 (on Windows, use WSL2):

```bash
git clone https://github.com/pishi-ishi/day-after && cd day-after
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e .
.venv/bin/dayafter            # the app, in your browser
.venv/bin/dayafter --help     # the command line
```

**Day Before (race eve and race morning).** Export one routing table per model from Expedition, plus the "summary of all routes", into the race folder (any layout works; Day After finds files by content), then:

```bash
.venv/bin/dayafter before "/mnt/c/.../Tollgate_Islands_2026(llama_II)" --open
```

It writes `out/day_before_<race>.html` in that folder: one file that opens offline on phones and laptops, ready to send to the crew. Options: `--models ECMWF,GFS,ACCESS` (at most three are shown; the default picks ECMWF, GFS, ACCESS when present) and `--turning-mark "TG South"`. Settings that cannot be read from the files go in an optional `race.dayafter.json` in the race folder:

```json
{
  "race": {"name": "Tollgate Islands Race 2026", "gun_local": "2026-10-16T17:00:00", "tz": "Australia/Sydney"},
  "boat": {"name": "Llama II"},
  "course": {"turning_mark": "TG South"},
  "crew_models": ["ECMWF", "GFS", "ACCESS"]
}
```

**After the race (same day, then within 72 h).** Save the fleet tracks and the coastal observations before they disappear:

```bash
.venv/bin/dayafter fetch-yb bwps2026_2 "<race folder>/fleet"
.venv/bin/dayafter fetch-bom 95768 94780 95752 94749 95745 95749 95940 94751 94938 95937 94939 --out "<race folder>/obs"
```

**Day After.** With the log, results, YB tracks, route tables and (optionally) GRIBs, BOM files and `Expedition.db` in the race folder:

```bash
.venv/bin/dayafter build "<race folder>" --open
```

It writes one HTML file per edition into `out/`: the **navigator** edition (overview, phases, plan vs reality with the GRIB model scorecard, fleet, performance against the polar, calibration, season) and the **crew** edition (the briefing's meteograms for the three best-verified models with what we actually measured on top, and the race's key moments). `--editions navigator` limits the set. Each build also stores the race in the season database (`season.sqlite` next to the app; `--season <file>` or `--no-season` to change that).

`dayafter selftest` checks a build against the Flinders Islet 2026 numbers in [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md).

## Documentation

| File | Contents |
|---|---|
| [`docs/DATA_GUIDE.md`](docs/DATA_GUIDE.md) | What data to collect before and after a race, and where to find it |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Product design: inputs, modules, editions, app, packaging |
| [`docs/FILE_FORMATS.md`](docs/FILE_FORMATS.md) | Every input format (Expedition log, route tables, polars, YB, results, BOM, GRIB) |
| [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) | The Flinders Islet 2026 numbers the build must reproduce |
| [`docs/BRAND.md`](docs/BRAND.md) | App and report look, 7 Seas branding |
| [`HANDOVER.md`](HANDOVER.md) | Build handover: decisions, environment, tasks, gotchas, milestones |

## Repository layout

```
dayafter/            application package: ingest/, core/, analysis/, report/, app/, season.py, cli.py
packaging/           icon and PyInstaller build script (used by .github/workflows/release.yml)
tests/               pytest suite (tests that need data/ skip)
assets/              logo, bundled coastlines
fixtures/            public test vectors and expected results (Flinders Islet 2026)
reference/           scripts and figures behind the hand-made Flinders report
docs/                design and guides
data/                private race data: never committed (git-ignored)
```

## Sister project

[7seas-telemetrics](https://github.com/pishi-ishi/7seas-telemetrics) overlays sailing telemetry on race video. Day After follows its packaging and look.

## Licence

MIT, see [`LICENSE`](LICENSE). Coastline data: Natural Earth (public domain) and © OpenStreetMap contributors (ODbL).
