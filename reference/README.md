# Reference material

`flinders_2026_scripts/` holds the pandas/matplotlib scripts used on 10 Oct 2026 to make the hand-made Flinders Islet report. They show working versions of most algorithms Day After needs (log parsing, route tables, polar interpolation, true-wind recompute, course projection and gates, rounding time). They are **not** production code:

- Paths point at the old claude.ai session's scratch folder (`WORK = ...`). Repoint them to `data/` and `fixtures/` to run them.
- They use **derived** TCCs (`fleet_summary_estimated_tcc.psv`). The official TCCs in `fixtures/flinders_2026/results_irc.csv` supersede them.
- `common.py::load_yb` and `verify_tracks.py` read the delta-encoded text form of the YB tracks (`id|fin|n|checksum|t,lat,lon deltas` at 1e-4°). The same data is in `fixtures/flinders_2026/yb_fleet_tracks.csv`.

`flinders_2026_figures/` holds the six figures from that report (course map, zooms, vs plan, wind, rounding effect, gaps) as a visual target for the HTML report charts. The gap and rounding charts were drawn with derived TCCs.
