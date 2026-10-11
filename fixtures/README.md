# Fixtures (public)

Test inputs and expected outputs that are safe to publish. Private inputs (the instrument log, polars and route tables) live in `data/` and are git-ignored.

## flinders_2026/

| File | What it is |
|---|---|
| `results_irc.csv` | CYCA IRC All results for the Flinders Islet Race 2026 with **official TCC (HCAP)**, transcribed from the results page on 11 Oct 2026 (28 finishers, 2 retired) |
| `course.csv` | Course polyline (Start … Flinders Islet W/S/E … Finish) from the Expedition route tables |
| `yb_boatids.csv` | YB tracker id → boat name (Expedition tracking download for key `bwps2026`) |
| `yb_expedition_latest_positions.csv` | Expedition's YB download: latest position only per tracker (`id,lat,lon,yymmddHHMM`); shows why it cannot be used for tracks |
| `yb_id_to_results_name.json` | Verified YB id → results name mapping (fuzzy match: `Artaraxia` → `Ataraxia`) |
| `yb_fleet_tracks.csv` | Decoded YB positions for the 28 finishers, 25 Sep 23:50Z to 26 Sep 16:00Z, **1e-4° precision** (decoded in the browser on 10 Oct; checksums verified) |
| `yb_allpositions3_head_team2.hex` | First 741 bytes of `cf.yb.tl/BIN/bwps2026/AllPositions3`: header + tracker 2 (121 moments). Decoder test vector; expected values in `docs/FILE_FORMATS.md` §6 |
| `expected/llama_mark_times.csv` | Llama II mark passage times from the 1 Hz log |
| `expected/splits_vs_routes.csv` | Mark times vs GFS/ECMWF/ACCESS route tables (Δ = actual − route, minutes) |
| `expected/phases.csv` | Race phases with distance, speeds and wind |
| `expected/polar_by_phase.csv` | Polar % by phase (BSP × 1.257, logged TWA) |
| `expected/fleet_elapsed_official.csv` | Per boat: official TCC, corrected, elapsed (= corrected ÷ TCC), YB elapsed, rounding time, elapsed at every 5 nm gate |
| `expected/corrected_gap_to_llama_by_gate_min.csv` | Corrected-time gap of every boat to Llama II at each gate, minutes (negative = boat ahead). Official TCCs. The 80 nm gate is a known projection artefact; exclude it. |

The expected numbers are derived from the private log and public tracker/results data. They hold no raw instrument data.
