# Day After: design

*Final design, 11 Oct 2026. Supersedes the 10 Oct design doc; changes since then are in "Decisions" at the end.*

Day After is a **local, cross-platform post-race analysis tool** for offshore yacht racing, styled on Njord Analytics. You point it at a race folder and it builds self-contained, interactive HTML reports in four editions, then adds the race to a season database. A **Day Before** mode builds the crew weather briefing before the race from the same inputs, minus the boat log.

Its first acceptance test is to reproduce the hand-made **Flinders Islet 2026** analysis of Llama II automatically (`docs/ACCEPTANCE.md`).

## At a glance

```
 INPUTS (race folder)                       ENGINE (Python + numpy)                         OUTPUTS
 ─────────────────────                      ──────────────────────────                      ──────────────────────────
 Expedition log (1 Hz) ─┐                   ingest → 1 Hz timeline, course, routes,         Day Before: crew briefing (HTML)
 Polar + sail chart     │                            GRIBs, fleet, results, events          Day After:  navigator  (full, interactive)
 Course (GPX/CSV/marks) │                   core   → calibration, true wind, progress,                  skipper/owner (3–4 printed pages)
 Route tables + summary ├──► local app ───►          mark passages, gates                              crew (learning edition)
 GRIB files             │   (browser UI at   analysis → plan vs reality, forecast vs obs,               7 Seas client (branded)
 YB fleet tracks        │    localhost)               fleet (corrected time), performance,  Season database (SQLite)
 Results (TCC, corr.)   │                            manoeuvres, findings, briefing
 Events (sail changes)  │                   report → HTML + inline SVG charts + coastline
 BOM station obs        ┘
```

One analysis run feeds every edition. The editions differ in depth and tone, never in the numbers.

## What Day After takes from Njord, and what it adds

| Njord Analytics feature | Day After v1 | Notes |
|---|---|---|
| Automatic race and leg detection | Yes | Start from the gun, legs from course marks, phases from wind-regime changes and "holes" |
| Map with speed and tactical modes (track width = TWS, colour = shifts) | Yes | Offline vector coastline; optional online map tiles when viewing |
| Line charts linked to the map, selection statistics | Yes | Brush a stretch of track → mean, min, max, standard deviation |
| Targets by TWS bucket (75th–95th percentile) and polar diagram | Yes | Uses the Expedition polar; exports updated targets for Expedition |
| Manoeuvres (tacks/gybes, ±20 s windows, ranked by loss) | Yes | Distance and time lost per manoeuvre |
| Calibration (BSP vs SOG, heading vs COG, AWA port vs starboard) | Yes, plus TWA consistency, TWD tack test, duplicate/dummy channel detection | These checks found the ×1.26 speed error, the 15° upwind TWA error and the mis-mapped channels on Llama II |
| Two-boat gain/loss (forward, sideways, VMG) | Later | Needs a rival's instrument log; none available now |
| Fleet race report (ranks per leg) | Yes, from **YB** | Njord supports TracTrac/GeoRacing, not YB |
| Sails and comments | Yes, from Expedition events | Sail changes on the timeline and map |
| Performance database | Yes | SQLite file next to the app |
| **Added:** plan vs reality against Expedition optimal routes | Yes | Split times at each mark; minutes ahead/behind each route |
| **Added:** forecast vs observed from GRIBs | Yes | Each model sampled at our own position and time |
| **Added:** IRC corrected-time gaps every 5 nm, ranks at marks, rounding-time effect | Yes | |
| **Added:** audience editions and a crew learning edition | Yes | Including a pre-race **Day Before** briefing |

## Two modes

| Mode | When | Needs | Produces |
|---|---|---|---|
| **Day Before** | Race eve / race morning | Course, route tables (one per model), optional GRIBs, polar | Crew briefing: meteograms per model along the route, change window vs ETA at the turning mark, sail-plan strip, shift/manoeuvre strip, glossary |
| **Day After** | After the race | All of the above + the boat log, YB fleet, results, events, BOM obs | Navigator, skipper/owner, crew and client editions; season DB update |

## Inputs and how each one is read

The minimum for Day After is a log and a polar. Every extra input adds a module, and a missing one only greys out its section. Formats are in `docs/FILE_FORMATS.md`.

| Input | Format | How Day After reads it | Needed for |
|---|---|---|---|
| Boat log | Expedition sparse CSV (later: NMEA 0183, GPX, Vakaros VKX reusing 7seas-telemetrics' `vkx.py`) | 1 Hz timeline in UTC; channel maps merged across header blocks; duplicate/dummy channels flagged | Everything after the race |
| Polar | Expedition polar `.txt`, or ORC certificate table | Bilinear in TWS × \|TWA\|; clamped above the top TWS row | Performance, targets |
| Course | `course.csv`, GPX route, route-table marks, Expedition marks `.dat` (best effort) | Marks, roles, turning mark, along-course distance | Splits, gates, fleet |
| Optimal routes | Expedition route-table CSV per model + "summary of all routes" CSV | Times, positions, forecast wind/gust/pressure/temperature/rain, sail per step; °M → °T | Plan vs reality, briefing |
| GRIB forecasts | GRIB1 and GRIB2 from Expedition's `grib` folder | Wind, gust, pressure, temperature, rain at our position and time (bilinear in space, linear in time); 10 m → masthead factor per boat | Forecast vs observed, model scorecard, briefing |
| Fleet tracks | YB `AllPositions3` (online by race key, or a saved file) + boat ids | 10-min positions per boat, filtered to the race window | Fleet comparison |
| Results | `results.csv` with official TCC (HCAP) and corrected time | Elapsed = corrected ÷ TCC; TCCs remembered for the season | Fleet comparison |
| Events | Expedition events (format to confirm) or `events.csv` | Sail changes, reefs, notes | Timeline, performance by sail, crew edition |
| Observations | BOM `.axf` coastal station files | Station wind, gust and pressure on the forecast charts | Forecast vs observed |
| Notes | `notes.md` | Inserted verbatim | All editions |

## Report modules (tabs)

Each tab opens with three to five headline numbers, Njord-style, followed by its map and charts.

| Module | What it answers | Main views |
|---|---|---|
| Race overview | Result, key times, distance, and the moments that decided it | KPI tiles; course map with legs coloured; timeline of events, holes and sail changes; 3 decisive moments |
| Plan vs reality | Where we gained or lost against each optimal route, and whether the forecast was right | Track over routes; minutes ahead/behind at each mark; forecast vs observed wind and pressure per model; change-timing table; **model scorecard** (bias and error per model for this race) |
| Fleet comparison | How we did against similar-rated rivals, and where the race was won | Corrected-time gap every 5 nm; corrected rank at each mark; rounding time vs leg time (all boats); rival tracks on the map; leg table |
| Performance & calibration | How close to polar we sailed, by phase and condition, and whether the instruments can be trusted | Polar % by phase and TWS bucket; targets view; polar diagram; manoeuvres ranked by loss; calibration checks with suggested corrections |
| Season | Whether this race was typical, and what is trending | Targets and polar % across races; calibration history; which model verified best on this coast; head-to-head with regular rivals |

## Editions

| Edition | Reader | Length | What it holds | Tone |
|---|---|---|---|---|
| Navigator | Navigator | Full, interactive | All modules and views, data caveats, calibration detail, raw tables and exports | Technical |
| Skipper/owner | Skipper, owner, tactician | 3–4 printed pages | Overview, plan vs reality, fleet comparison, 3–5 decisions and recommendations; follows the leadership weather-briefing style | Tactical, plain |
| Crew | Whole crew | 3–4 printed pages + interactive meteograms | The 2–3 best-verified models, how to read them, and what they meant on deck | Sailing jargon used freely; weather terms explained |
| 7 Seas client | Other boats, as a paid 7 Seas Marine service | Skipper edition + navigator appendix | 7 Seas logo and colours, cover page and contact; only that client's own data plus public tracker and results data | Professional |

### The crew edition (and the Day Before briefing)

It teaches everyone to read the forecast the way the nav station does, so that sail changes and manoeuvres can be planned ahead. It assumes good sailors: boat-handling language is used freely, and only weather terms are explained.

- **Two or three models, no more.** After the race: the models that verified best against our log (Flinders: ECMWF for change timing, ACCESS for leg-1 breeze, GFS as the central plan). Before the race: the models the navigator selects (default ECMWF, GFS, ACCESS). The navigator can override.
- **One meteogram per model, drawn along our track/route**, in Expedition's colours (red TWS, black pressure, green air temperature, blue rain) so what the crew learns transfers to the nav screen. After the race, the observed wind is overlaid.
- **"How to read this" callouts** on the meteogram: where the breeze builds; where pressure bottoms and then jumps; where the temperature drops and the rain starts. Together these are the signature of a front or southerly change.
- **Change timing as a window**: the earliest-to-latest model arrival is shaded, with our ETA at the turning mark drawn across it. It answers "are we likely to round before or after the change?"
- **Sail-plan strip**: the routing's planned sail for each hour (e.g. A1/2 to J1 at the rounding, then J4 and a reef as TWS passes 25 kt), and after the race what we actually flew (from events).
- **Shift and manoeuvre strip**: forecast veers and backs, which tack or gybe they favour, and when the laylines move. Each item is a heads-up the crew can prepare for.
- **What actually happened** (after the race only): forecast vs observed for the race's two or three key moments, in a few lines each.
- **Weather glossary**: about 15 terms, one line each: GRIB, 10 m wind, gust factor, pressure gradient, trough, ridge, front, southerly buster, coastal trapping, veer and back, sea breeze, meteogram, ensemble, model run.

## Season database

Every analysed race goes into one SQLite file next to the app. It moves with the app, and the season views draw on it. Raw logs stay where they are; the database stores derived numbers and file paths, so it stays small and fully rebuildable.

| Stored per race | Used for |
|---|---|
| Race, course, conditions summary, result, TCC | Season results table; comparing like-for-like races |
| Polar % and target angles by TWS bucket, point of sail and sail | Season targets; an updated nav polar for Expedition |
| Calibration results (speed factor, heading offset, AWA/TWA checks, channel mapping) | Whether a fix held and whether a sensor is drifting |
| Model verification (bias and error in wind speed, direction and change timing) | Which model to trust first on this coast and in which weather type |
| Fleet: rivals' TCCs, elapsed and corrected times, gaps, rounding times | Season head-to-head with the same rivals; TCC lookup for later races |
| Manoeuvres with their losses | Trends in tack and gybe quality by condition |

## App, packaging and look

- **Shape.** Python 3.12 engine; a local web server (standard-library `http.server`) opens the app in the default browser at `http://127.0.0.1:<port>`. The same code runs on Windows, macOS and Linux. **One PyInstaller binary per OS**, built by a GitHub Actions matrix and attached to releases. Offline except for YB, BOM and optional map tiles.
- **App window (in the browser).** Left: a race-folder picker (server-side folder browser), the inputs checklist (found / missing / override), drag-and-drop to add files, the YB race key, and the rivals picker. Middle: a quick map and timeline preview. Right: mode (Day Before / Day After), editions and **Build**, with progress while it runs. Uses the 7seas-telemetrics dark, crimson-accent tokens (`docs/BRAND.md`).
- **Reports.** One self-contained `.html` per edition: data embedded, chart and map code inlined. It opens in any browser, travels as an email attachment and prints to PDF via a print stylesheet. Njord-like look: light and clean, our boat always blue, a fixed colour per model and rival. The 7 Seas edition uses 7 Seas branding.
- **Engine** (`dayafter/`): `ingest/` (one parser per input), `core/` (timeline, calibration, true wind, progress), `analysis/` (plan, forecast, fleet, performance, manoeuvres, findings, briefing), `season.py`, `report/`, `app/`.
- **Dependencies.** numpy, Pillow (GRIB JPEG2000/PNG, icon), tzdata. Standard library for the rest; no pandas. GRIB decoding is pure Python unless T1 finds CCSDS packing (see HANDOVER).
- **Project file and command line.** Each race folder gets a `race.dayafter.json` (inputs, rivals, settings, notes). CLI: `dayafter` (app), `dayafter build <folder>`, `dayafter before <folder>`, `dayafter fetch-yb <key> <out>`, `dayafter --selftest`.
- **Distribution.** Public GitHub repo `pishi-ishi/day-after`. Binaries are release assets with SHA-256 in the README, as with 7seas-telemetrics.

## Build plan

Five milestones, each ending with a working binary and a test against Flinders 2026. Scope and acceptance criteria are in `HANDOVER.md` §8 and `docs/ACCEPTANCE.md`.

1. Core + plan vs reality (log, polar, course, routes, calibration, progress; navigator Overview + Plan tabs)
2. Fleet (YB, results, gates, corrected gaps, ranks, rounding effect)
3. Forecast from GRIBs, crew edition and Day Before mode
4. Performance, manoeuvres and the season database
5. Local browser UI, skipper and 7 Seas editions, print CSS, packaging and `--selftest`

## Decisions (open questions closed on 11 Oct 2026)

| Question | Decision |
|---|---|
| Windows only, or all OS / browser? | All OS: Python engine + local browser UI, one binary per OS (replaces the tkinter plan) |
| GRIB decoder | Look at Expedition's `grib` folder first (HANDOVER T1). Pure Python + numpy + Pillow unless CCSDS packing is found |
| Sail changes | The navigator logs them as Expedition events; Day After reads them (store format to confirm in T1) |
| Results input | The owner supplies results with official TCC (HCAP) and corrected time; elapsed = corrected ÷ TCC; TCCs fixed for the season. The BWPS page is not scraped. |
| Pre-race crew version | Yes: the Day Before mode |
| Crew wording | Sailing jargon freely; weather terms explained |
| 7 Seas client edition | Logo and colours from the live 7seasmarine.me |
| Two-boat comparison | Not now (no rival logs); fleet comparison from YB tracks. Two-boat gain/loss stays on the roadmap. |
| Video links | No |
| Repo | Public `pishi-ishi/day-after` with README; built with Claude Code on WSL2 from this handover |
