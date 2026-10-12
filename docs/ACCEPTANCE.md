# Acceptance tests: Flinders Islet Race 2026 (Llama II)

The hand-made Flinders report is Day After's first acceptance test: the build must reproduce its numbers from the raw inputs, with no hand-tuning. Everything here was re-checked on 11 Oct 2026 against **official IRC TCCs**.

Inputs: `data/flinders_2026/` (private, git-ignored) and `fixtures/flinders_2026/` (public).
Expected outputs: `fixtures/flinders_2026/expected/`.

## Race facts

| Item | Value | Source |
|---|---|---|
| Race | Flinders Islet Race, Audi Centre Sydney Blue Water Pointscore 26/27 | CYCA |
| Date / gun | 26 Sep 2026, **10:00:00 AEST (UTC+10)** = 2026-09-26T00:00:00Z = epoch 1790380800 | SI |
| Course | Start (inside Sydney Heads) → LB → South Head → Dunbar → Ben Buckler → Cape Banks → Flinders Islet (rounded W→S→E) → Cape Banks → Ben Buckler → Dunbar → South Head → Finish; **88.02 nm** along the course polyline in `fixtures/flinders_2026/course.csv` (the Expedition route says 88.06–88.15 nm) | Expedition route tables |
| Our boat | Llama II, Dehler 46, IRC Div 2, **TCC 1.136** | CYCA results |
| Result | **15th of 28** finishers in IRC All (2 retired) | CYCA results |
| Corrected | **13:19:45** | CYCA results |
| Elapsed | **11:44:00** (= 47985 s ÷ 1.136 = 42240.3 s) | derived |
| Official finish | about **21:44:00** | derived |
| Log check | closest approach to Expedition's finish point: **48 m at 21:43:28** | log |
| Start crossing | **10:00:49** (49 s after gun) | log |

## M1: log, course, calibration, plan vs reality

**Mark passage times** (`expected/llama_mark_times.csv`, closest approach on the 1 Hz log; tolerance ±60 s):

| Mark | Time | Mark | Time |
|---|---|---|---|
| Start (crossing) | 10:00:49 | FI S (rounding) | 16:00:11 |
| LB | 10:29:23 | Cape Banks (ret) | 20:31:20 |
| South Head | 10:34:30 | Ben Buckler (ret) | 21:06:08 |
| Dunbar | 11:07:38 | Dunbar (ret) | 21:27:32 |
| Ben Buckler | 11:24:44 | South Head (ret) | 21:34:01 |
| Cape Banks | 12:21:17 | Finish waypoint | 21:43:28 |

**Splits vs routes** (`expected/splits_vs_routes.csv`; route tables from the 25 Sep 17:34 runs; Δ = actual − route in minutes, so positive means we were behind the route; tolerance ±1 min):

| Mark | Actual | GFS | Δ | ECMWF | Δ | ACCESS | Δ |
|---|---|---|---|---|---|---|---|
| LB | 10:29 | 10:26 | 3 | 11:00 | −31 | 10:31 | −2 |
| South Head | 10:34 | 10:29 | 6 | 11:05 | −30 | 10:33 | 2 |
| Dunbar | 11:07 | 10:45 | 23 | 11:16 | −8 | 10:44 | 24 |
| Ben Buckler | 11:24 | 11:14 | 11 | 11:40 | −15 | 11:09 | 16 |
| Cape Banks | 12:21 | 12:11 | 10 | 12:36 | −15 | 12:11 | 10 |
| FI S | 16:00 | 16:04 | −4 | 17:08 | −68 | 16:05 | −5 |
| Cape Banks (ret) | 20:31 | 19:24 | 67 | 20:38 | −7 | 19:40 | 51 |
| Ben Buckler (ret) | 21:06 | 20:06 | 60 | 21:18 | −12 | 20:24 | 42 |
| Dunbar (ret) | 21:27 | 20:23 | 65 | 21:34 | −6 | 20:40 | 48 |
| South Head (ret) | 21:34 | 20:30 | 64 | 21:41 | −7 | 20:47 | 47 |
| Finish | 21:43 | 20:35 | 68 | 21:47 | −4 | 20:53 | 50 |

*(In the CSV these are the `GFS_d`, `ECMWF_d` and `ACCESS_d` columns. Keep this one sign convention throughout the app and label it on every chart.)*

**Race-morning predicted finishes** (summary CSVs): 06:34 runs: ACCESS 21:04:45, GFS 21:57:10, ECMWF 22:11:14, AIGFS 22:41:37. 09:50 runs: ACCESS 21:39:15, GFS 21:58:58, ECMWF 22:08:36, AIGFS 22:20:03, ICON 23:34:25, AIFS 00:31:11 (next day). Our ~21:44 beat all of them except ACCESS (5–39 min faster).

**Calibration** (must be flagged automatically):

| Check | Expected | Tolerance |
|---|---|---|
| BSP factor k (SOG⃗ = k·BSP·ĥ + c⃗, race window, steady rows) | **1.257–1.259** | ±0.03 |
| Heading offset δ | +0.5° (HDG is already true) | ±2° |
| Current | **0.57 kt setting 125° T** (SE) | ±0.2 kt, ±25° |
| SOG/BSP by direction | 1.31 southbound, 1.23 northbound | ±0.03 |
| Upwind beat 16:05–17:00: median \|AWA\| | 28.0° | ±1° |
| logged \|TWA\| vs recomputed (k-corrected) | **58.1° vs 41.1°** → warn "TWA reads ~15–17° wide upwind" | ±2° |
| logged vs recomputed TWS on the beat | 11.3 vs 11.2 kt | ±0.5 |
| Duplicated channels | Heel = Trim = Leeway = MastAng = Rudder = KeelAng = Foil P/S…; J1–J4 = Main = Forestay = RunnerP = D0/D1 = Bobstay; WaterLev = FuelLev | all groups found |
| Missing | Baro, AirTemp | reported |

**Phases** (`expected/phases.csv`; tolerance ±1 min, ±2 % on speeds):

| Phase | From–to | min | Dist nm | SOG | STW corr | TWS | TWS p95 | TWD |
|---|---|---|---|---|---|---|---|---|
| Start → South Head | 10:00–10:34 | 34 | 3.53 | 6.29 | 5.15 | 6.9 | 9.1 | 26 |
| Hole at the Heads | 10:30–10:57 | 28 | 1.05 | 2.28 | 0.14 | 3.5 | 6.0 | 67 |
| South Head → Cape Banks | 10:34–12:21 | 107 | 12.58 | 7.07 | 6.04 | 12.1 | 19.9 | 12 |
| Cape Banks → Flinders Islet | 12:21–16:00 | 219 | 35.77 | 9.80 | 9.05 | 19.2 | 27.2 | 25 |
| Rounding → southerly arrives | 16:00–17:05 | 65 | 6.20 | 5.74 | 5.31 | 11.5 | 17.4 | 12 |
| Southerly → Cape Banks | 17:05–20:31 | 206 | 34.78 | 10.11 | 9.92 | 30.9 | 41.2 | 164 |
| Cape Banks → finish point | 20:31–21:43 | 72 | 11.88 | 9.88 | 9.80 | 30.0 | 39.7 | 159 |

The hole (10:30–10:57) must be found by the hole detector (SOG < 3 kt ≥ 10 min). The 17:05 change must be found by the change detector.

## M2: fleet

**Finish gaps on corrected time** (exact, from official results). Llama II 13:19:45 vs: Calibre 12 13:08:57 (**10:48 ahead**), Kanreki 13:03:27 (**16:18 ahead**), Ragtime 13:18:33 (**1:12 ahead**), Western Morning 13:19:46 (**1 s behind**), Wild Oats 13:18:07 (1:38 ahead), Disko Trooper 11:26:52 (1:52:53 ahead).

**Default rivals rule** (same division, nearest TCC, 3 boats) must return Calibre 12 (1.132), Kanreki (1.107) and Ragtime (1.095).

**Gate gaps** (`expected/corrected_gap_to_llama_by_gate_min.csv`, minutes, negative = boat ahead on corrected; official TCCs; YB fixes at 1e-4° from `yb_fleet_tracks.csv`). Tolerance ±1.5 min. **The 80 nm gate is excluded** (projection artefact in the reference).

| Gate nm | 5 | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 44.94 (islet) | 50 | 55 | 60 | 65 | 70 | 75 | 88.02 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Calibre 12 | 2.23 | 2.05 | 1.36 | 0.94 | 0.42 | −0.93 | −3.00 | −4.84 | −4.61 | −20.63 | −15.22 | −12.31 | −12.71 | −10.82 | −11.99 | −10.80 |
| Kanreki | −7.72 | −9.06 | −8.86 | −8.54 | −8.33 | −10.07 | −11.15 | −10.48 | −13.09 | −28.56 | −20.69 | −17.84 | −18.15 | −17.84 | −20.28 | −16.30 |
| Ragtime | −8.77 | −8.26 | 2.93 | 4.13 | 3.84 | 3.62 | 4.74 | 5.42 | 13.77 | −5.23 | −9.38 | −10.76 | −12.56 | −16.11 | −21.73 | −1.20 |

**Corrected rank of Llama II at gates:** 21 (5 nm), 21, 16, 17, 18, 18, 16, 17, **16 (islet)**, **21 (50 nm)**, 18, 11, 12, 14, 14, **15 (finish)**.

**Rounding effect:** rounding time at Flinders Islet vs corrected time from rounding to finish, all 28 finishers: **r = −0.605** (±0.03).

> **Build notes (12 Oct 2026).** Day After's fleet progress partitions the course at the angle bisectors of its corners and holds the turning mark until each boat's closest approach to it. It reproduces every gate gap in `expected/` within 1.5 min except at the turning-mark gate, and matches the rank list above exactly. Two findings change this page:
> - **The 80 nm gate is not an artefact.** Day After's values match the reference's at 80 nm (Ragtime −45, Kanreki −34, Calibre 12 −29 min), and the YB tracks show why: those boats were ahead on the water at 80 nm, then parked inside South Head (Ragtime 21:15–21:57, 0.6 nm in 42 min) while Llama II sailed straight through to finish at 21:44. The race on corrected time was decided in the last 2 nm. The selftest now checks the 80 nm gate too.
> - **At the turning-mark gate Day After uses the rounding** (closest approach of the YB fixes to the islet). The reference used a projection crossing that fires when a boat is abeam of the islet, 1–2 fixes earlier (Smuggler 14:29 at 1.5 nm off vs 14:40 at 0.36 nm; Minerva 15:09 at 1.2 nm vs 15:30 at 0.37 nm). The 12 boats affected differ there by up to 20 min; the ranks at that gate still match (16).
> - The rounding correlation is r = −0.594 (within tolerance). The podium (Disko Trooper, Borderline, Blue Planet) rounded at 16:34, 16:39 and 17:03, ranked 6th, 14th and 21st on corrected time at the islet, and sailed leg 2 1.60, 1.72 and 1.84 h faster than Llama II on corrected time.

**Elapsed times** (`expected/fleet_elapsed_official.csv`, corrected ÷ TCC) vs YB "finish": YB is late by 0.9–45.3 min (mean 7.4). The app must warn when they disagree by more than 2 min and always use the official value.

## M3: forecast and briefing

- Route tables alone (no GRIB) must produce: meteograms along each route (TWS, gust `Twg`, MSLP, AirT, Rain), sail-plan strips (`Sail` column: J1 → A1/2 → … → Poled J4 → J4), change times per model, and a change window covering the observed ~17:05 change.
- With GRIBs (after T1): observed-vs-forecast at our position shows every model **30–60 % light** on the leg-1 NNE (observed 21–25 kt 13:00–14:10 vs forecast 8–17 kt) and on the southerly (30–36 kt, 10-min mean, vs 20–30 kt).

> **Build notes (12 Oct 2026).** Day After reads every GRIB model at our own position (bilinear in space, linear in time, 10-min steps) and judges each on the forecast we had at the gun: the latest run among the files Expedition downloaded before 10:00 (the 08:34 download: ECMWF and AIFS 12Z, GFS, ICON and AIGFS 18Z on Fri 25 Sep). The decoder matches eccodes to 1e-9 on every field of every Flinders file. What the GRIBs show:
> - **Leg-1 NNE (13:00–14:10, observed 21–25 kt):** ECMWF 9–14 kt (**50 % light**), GFS 6–16 kt (**54 % light**). ICON, AIGFS and AIFS were 75–80 % light (4–7 kt).
> - **The southerly (18:00–20:30, observed 27–36 kt in 10-min means):** ECMWF 15–29 kt (21 % light), GFS 17–25 kt (28 %), ICON 14–28 kt (25 %), AIGFS 12–21 kt (45 %), AIFS 4–14 kt (72 %). So the southerly was 20–30 % light in the three main models, not 30–60 %; the 20–30 kt forecast range holds.
> - **Change timing at our position:** every model brought the change early: ECMWF 16:30 (35 min), ICON 16:20, AIFS 16:10, GFS 14:50 (2 h 15 min); AIGFS shows no change. Along their own routes (route tables) ECMWF was 14 min late and ACCESS 34 min late.
> - ACCESS and UM GRIBs are encrypted by Expedition (`grbenc01`): the report says so and judges ACCESS from its route table only.
> - The crew edition picks ACCESS, ECMWF and GFS (best verified along their routes, in that order) and its key moments are Cape Banks → Flinders Islet (19 kt measured; routings 10–15 kt, about 39 % light; GRIBs 4–9 kt), the change at 17:05 and the 30 kt southerly after it.

## M4: performance

`expected/polar_by_phase.csv` (STW corrected by k = 1.257; polar `llama2_polars_2026.txt`, clamped at its 24 kt row). Tolerance ±2 percentage points:

| Phase | n (1 Hz) | TWS | \|TWA\| | STWc | Target | % | p25 | p75 |
|---|---|---|---|---|---|---|---|---|
| Heads → Cape Banks | 3822 | 14.5 | 155 | 7.79 | 8.32 | 94.2 | 88 | 101 |
| Cape Banks → FI | 10457 | 19.2 | 163 | 8.92 | 8.98 | 101.2 | 93 | 110 |
| Post-rounding beat | 2567 | 11.9 | 59 (logged) / 41 (recomputed) | 6.03 | 8.19 | 73.3 | 67 | 81 |
| Southerly run | 8045 | 31.7 | 153 | 9.93 | 10.52 | 94.2* | 84 | 107 |
| Cape Banks → finish | 2482 | 32.1 | 154 | 10.06 | 10.48 | 96.0* | 85 | 110 |

\* above the polar's 24 kt row, so indicative only. The report quotes the post-rounding beat as **84 % of polar speed, 78 % of target VMG** using the recomputed TWA. The 73 % here uses the logged (wrong) TWA for the target. The app must use recomputed true wind when calibration flags the TWA error, and say so.

## M5: packaging

`dayafter --selftest` builds all editions for Flinders from `data/` and `fixtures/`, checks the numbers above, and exits non-zero on failure. It skips with a clear message when `data/` is absent (CI).
