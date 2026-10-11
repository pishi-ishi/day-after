# Day After: handover for the build

**From:** design sessions in Claude (claude.ai, 10–11 Oct 2026)
**To:** Claude Code on the owner's WSL2 machine
**Status:** design final, inputs gathered. **No application code exists yet.** This folder is the starting point of the `day-after` repository.

Day After is a local post-race (and pre-race) analysis tool for offshore yacht racing, modelled on Njord Analytics. It has four post-race report editions plus a pre-race "Day Before" crew briefing. Its first users are Llama II (Dehler 46, IRC, owner Jon Linton), the navigator (repo owner, GitHub `pishi-ishi`), the crew, and clients of 7 Seas Marine Electronics.

---

## 1. Read in this order

| # | File | What it gives you |
|---|---|---|
| 1 | `HANDOVER.md` (this file) | Decisions, environment, first tasks, gotchas, milestones |
| 2 | `docs/DESIGN.md` | Full product design: inputs, modules, editions, app, packaging |
| 3 | `docs/FILE_FORMATS.md` | Every input format, verified against real files, with samples |
| 4 | `docs/ACCEPTANCE.md` | Flinders Islet 2026 numbers the build must reproduce |
| 5 | `docs/DATA_GUIDE.md` | User-facing guide: what data to collect before and after a race, and where it comes from |
| 6 | `docs/BRAND.md` | Report look, Day After tokens, 7 Seas branding and logo |
| 7 | `reference/flinders_2026_scripts/` | The pandas/matplotlib scripts behind the hand-made Flinders report. They are a reference implementation of most algorithms, not production code (paths are hard-coded to the old session). |

The live design doc and the hand-made race report are Claude Docs. They mirror `docs/DESIGN.md` and `docs/ACCEPTANCE.md` and are not needed for the build.
- Design: https://claude.ai/code/artifact/7fcfc0d7-585e-4dc1-a760-90e149db0c06
- Flinders report: https://claude.ai/code/artifact/e8d77c96-7644-4ea6-8730-dacddccd8e6b (corrected on 11 Oct to official TCCs)

---

## 2. Decisions log (all answered by the owner)

| Topic | Decision |
|---|---|
| Shape | Cross-platform app: Python engine plus a **local browser UI** at `http://127.0.0.1:<port>`, no tkinter. One PyInstaller binary per OS (Windows, macOS, Linux). Output is self-contained interactive HTML reports that print to PDF. |
| Modules (v1) | Race overview · Plan vs reality · Fleet comparison · Performance & calibration · Season database |
| Forecast input | Read **GRIB files directly** (GRIB1 and GRIB2) as well as Expedition route tables |
| Editions | Navigator (full) · Skipper/owner (3–4 printed pages) · Crew (learning edition) · 7 Seas client (branded) |
| Crew edition | Limited to the **2–3 best models**. Teaches reading meteograms, fronts and change timing, and planning sail changes and tacks/gybes ahead. Sailing jargon is used freely; weather terms get a glossary. |
| Pre-race | **Yes: "Day Before" mode.** It builds the crew briefing before the race from route tables and GRIBs (meteograms, change window, sail-plan strip, shift strip) without the observed overlay. |
| Sail changes | Logged by the navigator as **Expedition events**; Day After reads them. The events storage format still needs checking (task T1). |
| Results | The owner supplies IRC results with **official TCCs** (the CYCA "HCAP" column) and corrected times. TCCs are fixed for the season. **Elapsed = corrected ÷ TCC.** Never take elapsed time from YB finish times (see §6). |
| Fleet data | From **YB Tracking** (all boats, 10-min fixes). No logs from other boats for now; two-boat Njord gain/loss is deferred until a rival shares a log. |
| 7 Seas edition | Logo and colours from the live **7seasmarine.me** (see `docs/BRAND.md`). |
| Video | **No** links to 7seas-telemetrics clips. |
| Repo | **Public** GitHub repo `pishi-ishi/day-after` with README. The owner creates the empty repo; never commit `data/`. |
| Build location | Claude Code on WSL2 (this handover). The earlier claude.ai session stopped before writing any app code. |

---

## 3. Environment notes for WSL2

- **Windows files** are under `/mnt/c/...`. Useful paths on this PC (user `user`):
  - Expedition data: `/mnt/c/ProgramData/Expedition/` with sub-folders `grib`, `database`, `tracking`, `sails`, `log`, `polars`, `polars_ORC_Certificates`, `marks-routes_me`, `racenotes`, `wxdata`, `calibration`, `config`, `archive`.
  - Navigation library: `/mnt/c/Users/user/Downloads/Offshore_Navigation_Expedition/` (ORC certificates and polars, GPX courses for the coming races, BOM station `.axf` files, the Flinders results PDF and screenshot, and the Expedition pre-race routings for Flinders).
  - Pre-race routings: `/mnt/c/Users/user/Downloads/llama2_offshore_program_2026/Expedition pre-race routings/`
  - 7seas-telemetrics checkout: `/mnt/c/Users/user/Downloads/7Seas_telemetrics/7seas-telemetrics/` (also `github.com/pishi-ishi/7seas-telemetrics`, public, MIT).
  - Website repo (brand source): `github.com/pishi-ishi/7seasmarine.me` (private). The original logo image may also be in `/mnt/c/Users/user/Documents/7seasmarine.me/`.
- **Packaging.** PyInstaller cannot cross-compile. A WSL2 build produces a Linux binary only. Build the Windows `.exe` either with a Windows Python venv (as 7seas-telemetrics' `build.ps1` does; the PC has Anaconda) or with a **GitHub Actions matrix** (`windows-latest`, `macos-latest`, `ubuntu-latest`) that attaches all three binaries to a release. The matrix is the recommended route.
- **Opening the browser from WSL2** for the local UI: try `wslview` first, then `cmd.exe /c start <url>`, then Python's `webbrowser`. On native Windows/macOS/Linux, `webbrowser.open` is enough.
- **Network.** YB (`cf.yb.tl`, `yb.tl`) and BOM are needed only at fetch time. Everything else works offline.

---

## 4. First tasks, in order

**T0 – Repository (owner + Claude Code).** The owner creates an empty public repo `pishi-ishi/day-after` on GitHub (no README, licence or .gitignore; this folder supplies them). Then:
```bash
git init && git add . && git status   # confirm data/ is NOT staged (.gitignore)
git commit -m "Design, handover and fixtures for Day After"
git branch -M main && git remote add origin https://github.com/pishi-ishi/day-after.git && git push -u origin main
```
`data/` holds the private race log, polars and route tables. It is git-ignored and must stay out of the public repo. Tests that need it skip when it is absent.

**T1 – Inspect Expedition's own folders (read-only)** and finish `docs/FILE_FORMATS.md` §§ 9–11. The claude.ai session could not get folder access, so these three are the open format questions:
1. `grib/`: list the files. For each GRIB2 message read Section 5's **data representation template number** (5.0 simple, 5.2/5.3 complex, 5.40 JPEG2000, 5.41 PNG, **5.42 CCSDS**) and Section 3's grid template; for GRIB1, the BDS packing flags. Also record the originating centres and the parameter set (U/V 10 m, gust, MSLP, 2 m temperature, precipitation, cloud). This **decides the decoder**:
   - Only 5.0/5.2/5.3/5.40/5.41 and GRIB1 simple packing → write the planned pure-Python+numpy decoder, using Pillow (already a dependency, ships OpenJPEG) for 5.40 and 5.41.
   - CCSDS (5.42) present (recent ECMWF open-data uses it) → either add a pure-Python AEC decoder or bundle `eccodes` (its wheels include the library, adding tens of MB). Prefer the pure route if the grids are small regional crops.
   - Keep a GRIB2 test vector per packing type in `fixtures/` (cropped messages are fine).
2. `database/` (and `racenotes/`, `log/`): find where **events** live (sail changes, notes, start/finish, marks rounded). Document the format (SQLite? CSV? Expedition binary?) and the sail-change text conventions the navigator uses. If the store is opaque, design for an Expedition export (CSV) plus Day After's own `events.csv` template, and note that in DATA_GUIDE.
3. `tracking/`: confirm what Expedition's YB download writes (`<key>-boatids.csv`, `<key>-expedition.csv`; the latter holds only the **latest** position per boat, so it is useless for tracks).
4. `sails/`: the sail chart format (`SailChart_Llama_S2H`). Optional: route tables already carry the sail chosen per step.
5. `marks-routes_me/`: compare with `data/courses/CYCA SOPS LOPS.dat` (format notes in FILE_FORMATS §7). GPX export is the fallback.

**T2 – Save the Flinders fleet file now.** The YB key `bwps2026` serves the whole Blue Water Pointscore series, so later races may replace the Flinders positions. Fetch `https://cf.yb.tl/BIN/bwps2026/AllPositions3` (27,443 bytes on 11 Oct) into `data/flinders_2026/yb_bwps2026_AllPositions3.bin`. A decoded copy at 1e-4° precision is already in `fixtures/flinders_2026/yb_fleet_tracks.csv` as a fallback.

**T3 onward – the milestones in §8.**

---

## 5. Architecture in one screen

```
dayafter/
  __main__.py, cli.py         serve (default) | build <race> | before <race> | fetch-yb <key> | selftest
  app/server.py               stdlib ThreadingHTTPServer + JSON API; serves app/static/*
  app/static/                 index.html, app.js, app.css (inputs checklist, folder browser,
                              drag-drop upload, settings, rivals picker, build progress, report links)
  ingest/                     expedition_log, routes (route table + summary), polar (2 layouts),
                              course (csv, gpx, expedition .dat, from route table), grib (GRIB1/2),
                              yb (AllPositions3 + RaceSetup + boatids), results, events, bom_axf, detect
  core/                       timeline (1 Hz arrays), calibration, truewind, progress (course
                              projection, mark passages, gates), geo, timeutil (tz, Excel serial)
  analysis/                   plan (splits vs routes, forecast vs observed, model scorecard,
                              change timing), fleet (corrected gaps, ranks, rounding effect),
                              performance (phases, polar %, targets, holes, by sail),
                              manoeuvres, findings (rule-based cautious text), briefing (Day Before / crew)
  season.py                   SQLite store next to the binary
  report/                     build.py + assets (report.css, report.js charts, coastlines, logos)
assets/coast/                 bundled coastline (Natural Earth 10 m SE Australia + OSM Sydney–Wollongong)
fixtures/                     public test vectors and expected numbers
data/                         private race data (git-ignored)
```

**Dependencies (keep the bundle small):** `numpy`, `Pillow` (GRIB JPEG2000/PNG unpacking and the icon), `tzdata` (zoneinfo on Windows). Use the **standard library** for everything else: `http.server`, `sqlite3`, `json`, `csv`, `xml.etree`, `zoneinfo`, `urllib`. No pandas, Flask or matplotlib in the app; they are fine in dev scripts and tests.

**Charts in reports:** write a small custom SVG/vanilla-JS chart module and inline it into each report, so reports stay self-contained and offline. Needed views: linked map (pan/zoom, tracks, routes, marks, time cursor), time-series lines with shared crosshair and brush selection that shows stats, scatter, bars, a polar diagram, a gap-vs-distance chart and sortable tables. Follow the dataviz rules in `docs/BRAND.md`: one y-axis per chart, legend for ≥2 series, our boat always blue, a fixed colour per model and rival, hover tooltips, a table view, and dark mode chosen deliberately.

---

## 6. Verified facts and gotchas (read before coding)

**Time**
- Expedition log `Utc` is **days since 1899-12-30, UTC** (Excel serial). Epoch seconds = `(days − 25569) × 86400`.
- Sydney is AEST (UTC+10) until 04 Oct 2026 02:00 and AEDT (UTC+11) after. Flinders (26 Sep) was +10; Sydney–Hobart (26 Dec) is +11. Use `zoneinfo("Australia/Sydney")` and bundle `tzdata`.
- Expedition route tables label the time column `AUS Eastern Standard Time`. That is the **Windows zone ID**, not a promise of standard time: the values are local wall-clock in that zone, DST included. Format `26-Sep-2026 10:00`.
- The Flinders log runs past the race (to 27 Sep 15:04 local). Bound every analysis by the race window: gun → official finish.

**Angles and units**
- Route-table directions are **magnetic** (`Twd°M`, `Set°M`, `Brg°M`). Convert to true with local variation: about 12.8° E at Sydney, rising to about 15° E at Hobart. Use a simple latitude-interpolated model or WMM, and record the value used.
- In route tables a TWA in parentheses, e.g. `(-173)`, marks a mark/turn row where the boat is not on a free optimal angle. Strip the parentheses for the number, keep a flag. *(Interpretation unverified.)*
- Log TWA sign: + starboard, − port.

**Instruments (Llama II, Flinders 2026): found in the data, must be detected automatically**
- **Boat speed reads low.** SOG/BSP was 1.31 southbound and 1.23 northbound. A least-squares fit `SOG⃗ = k·BSP·ĥ + c⃗` gives **k = 1.257** and a current of about **0.5 kt setting SE**. Fit it as complex least squares (`z = a·b + c`, with `a = k·e^{iδ}`) so a heading offset δ comes out too.
- **Upwind TWA logged about 15° wide** (57–59° logged vs about 41° recomputed from AWA/AWS and the corrected BSP). Downwind, logged and recomputed agree within 1 kt and 2°. Likely the instrument system's true-wind calculation is fed the uncalibrated BSP.
- **Duplicated (mis-mapped) channels:** `Heel`, `Trim`, `Leeway`, `MastAng`, `Rudder`, `RudderP/S`, `KeelAng`, `Foil P/S` and `Rud Ptch P/S` all carry the **same heel-like signal** (race median ≈ 0°, ±5–11° on each tack, spikes to ±180°). `J1`–`J4`, `Main`, `Forestay`, `RunnerP/S`, `D0/D1 P/S` and `Bobstay` share **one identical sparse series** (1,257 rows, 1.2–24.5). `WaterLev` equals `FuelLev`. Detect channels that duplicate another channel, or are constant or very sparse, and report them as a mapping problem. Use only the first channel of each duplicate group (Heel is plausibly real). *(The 10 Oct report said these sat at a constant −3.75. That was wrong and was corrected on 11 Oct.)*
- **Not logged:** Baro and AirTemp. Pressure is the best change marker, so the report should recommend logging it.
- Start-line pings are logged as `Port lat/lon` and `Stbd lat/lon`, plus `Mk Lat/Lon` for the active mark.

**Fleet / results**
- **YB finish times are 1–45 min later than the official elapsed time** (mean 7.4 min over 28 boats). Llama II: YB 11:47:45 vs official 11:44:00. Llama II passed 48 m from Expedition's finish point at 21:43:28 and finished officially at about 21:44:00. **Elapsed = corrected ÷ TCC, always.**
- The first hand-made report derived TCCs from YB (e.g. 1.130 for Llama II vs official 1.136). It was corrected on 11 Oct. Expected numbers in `fixtures/` use official TCCs.
- **YB key `bwps2026`** spans the series and includes pre- and post-race positions (e.g. 121 fixes for boat 2 vs 83 in the race window). Filter by the race window. Positions are **newest first** inside AllPositions3.
- YB `RaceSetup` (`https://cf.yb.tl/JSON/bwps2026/RaceSetup`) returned **503** on 11 Oct. Do not depend on it: take names from Expedition's `bwps2026-boatids.csv` (YB id → name) or a manual mapping, and fall back to fuzzy matching against the results.
- Name mismatches YB ↔ results: `Artaraxia`↔`Ataraxia`, `Wot's Next`↔`Wots Next`, `Back 2 Black`↔`BACK 2 BLACK`, `(DH)` suffixes. Normalise to lowercase alphanumerics, then use `difflib` (cutoff 0.75). See `fixtures/flinders_2026/yb_id_to_results_name.json`.
- The boat-ids file also lists spares and virtual trackers (`Spare 3`, `Virtual Tracker 9990502` in `bwps2026_4-boatids.csv`). Keep only boats that appear in the results.

**Course geometry**
- Out-and-back courses (Flinders: Cape Banks ⇄ Flinders Islet on the same line) break naive "nearest segment" projection. Track the current leg as state and advance only after passing a vertex. Use the closest approach to a rounding mark (within about 2 nm for 10-min YB fixes), or projection beyond the segment end for non-rounding waypoints. Progress is monotonic (first passage). The hand-made version used a two-stage projection (before/after rounding) and still distorted the 80 nm gate near Ben Buckler, so the general algorithm must not.
- Windy GPX courses for the coming races have numbered route points only (`1`…`10`). The turning mark (island) must be identified: mark it in the course settings or take the vertex farthest from the start.

**Coastline:** `assets/coast/ne10m_land_se_australia.geojson` (Natural Earth, public domain, lon 145.5–155, lat −44.5 to −31, covers every BWPS course and Sydney–Hobart) and `osm_coast_sydney_wollongong.geojson` (OSM detail lines, ODbL attribution required). NE is coarse at harbour scale (Port Jackson is filled in), so draw OSM lines over it when zoomed in near Sydney.

---

## 7. Algorithms to implement (specs; reference code in `reference/flinders_2026_scripts`)

1. **Expedition log → 1 Hz timeline:** merge the id→name maps from **all** header blocks (the Flinders log has four, at lines 1, 469, 10010 and 35385, as channels are added). Keep `boat == 0`. Bin to whole seconds, taking the last value per bin (angles must not be arithmetically averaged), and forward-fill gaps ≤ 3 s.
2. **Calibration:** BSP factor + current + heading offset (complex LSQ on steady-state rows, BSP & SOG > 2 kt, |ROT| small); port/starboard AWA symmetry upwind; **TWD tack test** (TWD before vs after each tack should match); logged vs recomputed TWA by point of sail; dummy-channel detection. Each check outputs status ok/warn/fail, a value and suggestion text.
3. **True wind recompute** from AWS, AWA and calibrated BSP: `ax,ay = −AWS·(cos AWA, sin AWA)`, `tx,ty = ax + BSP_c, ay`, `TWS = |t|`, `TWA = atan2(−ty, −tx)`, `TWD = HDG_true + TWA`. The code is in `llama.py::true_wind`.
4. **Course progress:** see §6. Output along-course distance s(t), leg index and mark-passage times. For our 1 Hz log, take the closest approach to each vertex.
5. **Gates:** times when s(t) first reaches every N nm (default 5), interpolated linearly. The finish gate uses the official finish (gun + elapsed).
6. **Corrected gaps:** `gap = (t_gate,boat × TCC_boat) − (t_gate,us × TCC_us)`, where t is elapsed since the gun. Negative means the boat is ahead on corrected time. Also corrected rank per gate.
7. **Rounding effect:** for the turning mark, correlate rounding time with corrected leg-after-rounding time (Flinders: r = −0.61).
8. **Plan vs reality:** our mark times vs each route table's mark rows (matched by name plus occurrence order) → minutes ahead/behind; route elapsed vs actual; race-morning summary CSVs as extra predictions.
9. **Forecast vs observed:** (a) the route table's forecast at time t (each model along its own route), and (b) GRIB sampled at our position and time (bilinear in space, linear in time; 10 m → masthead factor per boat, default 1.0, configurable). Use 10-minute means of observed wind. **Model scorecard:** TWS bias and MAE, circular TWD MAE, change-timing error, predicted vs actual elapsed.
10. **Change detection:** the largest sustained TWD swing (≥ 60° within ≤ 60 min, held ≥ 30 min) in observed and in each model. Report the time and place. Supporting signs: a pressure jump, a temperature drop, rain onset.
11. **Performance:** phases = legs between marks, split at the detected change and at "holes" (SOG < 3 kt for ≥ 10 min). Per phase: duration, distance, mean SOG, corrected STW, TWS mean and p95, TWD (circular), polar % (median, p25, p75). Polar % by TWS bucket (2 kt) × point of sail (upwind < 70°, reach 70–120°, downwind > 120°). Njord-style targets: per TWS bucket, the 75th–95th percentile VMG band → achieved BSP/TWA vs polar targets. By sail when events exist. The polar ends at 24 kt: clamp and mark results above it as indicative.
12. **Manoeuvres:** a tack is a TWA sign change with |TWA| < 90° on both sides; a gybe, the same with |TWA| > 90°. Require 30 s stable either side. Loss = VMG_entry × window − ∫VMG dt over [−20 s, +60 s], in metres and seconds. Rank by loss.
13. **Findings:** rule-based, cautious sentences (examples in the Flinders report): the largest gain or loss vs each route and where, best-verified model, holes, calibration warnings, the leg where rival gaps opened, rounding-time effect, weakest phase. Free-text navigator notes from the project file are inserted verbatim.
14. **Day Before / crew briefing:** per chosen model, a meteogram along the route (TWS red, gust, pressure black, air temperature green, rain blue: Expedition's colours); a change window (earliest–latest model change time vs ETA at the turning mark); a sail-plan strip from the route's `Sail` column; a shift/manoeuvre strip (TWA sign flips = tacks/gybes, hourly veer/back); "how to read this" callouts (max wind, pressure minimum and jump, temperature drop, rain start); glossary.

---

## 8. Milestones (each ends with a working binary and a test)

| # | Scope | Acceptance (details in docs/ACCEPTANCE.md) |
|---|---|---|
| M1 | Repo skeleton, CLI, Expedition log, polar (both layouts), course, route tables, calibration, progress; navigator edition with Overview + Plan vs reality | Mark times within 1 min; splits vs routes within 1 min; phases within 1 % / 1 min; flags k ≈ 1.26 (±0.03) and the upwind TWA error by itself |
| M2 | YB decode/fetch/cache, results import, name matching, gates, corrected gaps, ranks, rounding effect, Fleet tab | Finish gaps to the second (Calibre 12 −10:48, Kanreki −16:18, Ragtime −1:12, Western Morning +0:01); gate gaps within ±1.5 min of `expected/corrected_gap_to_llama_by_gate_min.csv` (80 nm gate excluded); r = −0.61 ± 0.03 |
| M3 | GRIB decoder (after T1), forecast at our position, model scorecard, change timing, crew edition, **Day Before** mode | Decoder passes per-packing test vectors; the Flinders crew edition and the Day Before briefing build from route tables alone; with race-morning GRIBs, observed-vs-forecast reproduces the report's story (models 30–60 % light; change about 17:05) |
| M4 | Performance (phases, targets, by sail), manoeuvres, Season SQLite | Polar-by-phase within 2 % of `expected/polar_by_phase.csv`; Flinders + Tollgate produce Season views |
| M5 | Local browser UI, skipper and 7 Seas editions, print CSS, packaging (Actions matrix), `--selftest` | The binary runs on Windows without Python and builds all editions for Flinders; README carries download links and SHA-256 |

---

## 9. Open items and unknowns

- Expedition GRIB packing, events store, tracking and sail-chart formats → **T1**.
- YB `RaceSetup` endpoint availability (503 on 11 Oct). Names come from the boat-ids CSV meanwhile.
- The YB race key per race: `bwps2026` held Flinders. Confirm on the CYCA tracker page for each race (`bwps2026_4-boatids.csv` suggests per-race keys may also exist).
- Magnetic variation model: a simple latitude table vs WMM coefficients (a small file).
- The route table's parenthesised TWA meaning (see §6).
- `docs/DATA_GUIDE.md` asks the owner to export route tables for every model on race morning. For Flinders only the 25 Sep 17:34 tables exist; the race-morning runs exist only as summary totals.

---

## 10. Conventions carried over from 7seas-telemetrics

MIT licence (`Copyright (c) 2026 ruzbeh`). The README has a **Download** section with a direct release link and the SHA-256 of each binary. `dist/` and `build/` are git-ignored and binaries ship only as release assets. `--selftest` runs end-to-end on fixtures. A windowed build logs to `%TEMP%\dayafter_log.txt`. The project file is JSON (`race.dayafter.json`). Worker thread for long jobs. Design tokens are defined once and reused in the app CSS and the reports.
