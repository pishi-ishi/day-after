# Day After

**Post-race (and pre-race) analysis for offshore yacht racing, on your own computer.**

Day After reads your Expedition instrument log, the optimal routes and GRIB forecasts you sailed with, the YB tracker positions of the whole fleet and the official results. From them it builds self-contained, interactive HTML reports in the style of Njord Analytics:

- **Plan vs reality**: your track and mark times against each model's optimal route, and forecast vs observed wind.
- **Fleet comparison**: corrected-time gaps to similar-rated rivals every 5 nm, ranks at the marks, and who the weather favoured.
- **Performance & calibration**: polar %, targets, manoeuvres, and checks that catch bad boat-speed and wind calibration.
- **Season**: a local database that tracks targets, calibration, model accuracy and rivals across races.

Reports come in four editions (navigator, skipper/owner, crew and a branded 7 Seas Marine client edition). A **Day Before** mode turns the routings into a crew weather briefing: meteograms, the window when a change could arrive vs your ETA at the turning mark, the planned sail changes and the expected tacks and gybes.

> **Status: the Day Before crew briefing works (run it from source, below).** The post-race report, the browser app and the downloadable binaries are being built; see [`HANDOVER.md`](HANDOVER.md) for the plan and [`docs/DESIGN.md`](docs/DESIGN.md) for the design.

## Planned download

One file per operating system, no install, no Python needed. Releases will go on the [releases page](https://github.com/pishi-ishi/day-after/releases) with SHA-256 checksums here:

| OS | File |
|---|---|
| Windows 10/11 64-bit | `day-after.exe` |
| macOS | `day-after-macos` |
| Linux | `day-after-linux` |

Run it and Day After opens in your web browser at `http://127.0.0.1:<port>`. Close the console window to quit.

## How a race works

1. **Before the race**: export a routing table per model from Expedition and run **Day Before** for the crew briefing.
2. **After the race**: collect the log, the YB race key, the results and the BOM observations (see [`docs/DATA_GUIDE.md`](docs/DATA_GUIDE.md)), point Day After at the race folder and press **Build**.

## Use it now (from source)

Until the binaries are released, run Day After from a checkout with Python 3.12 (on Windows, use WSL2):

```bash
git clone https://github.com/pishi-ishi/day-after && cd day-after
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e .
.venv/bin/dayafter --help
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
dayafter/            application package (to be built)
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
