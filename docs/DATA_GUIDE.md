# Day After data guide: what to collect, and where it comes from

This guide is for the navigator. Follow it for every race: **Tollgate Islands, Bird Island, Cabbage Tree Island and Sydney–Hobart** this season. Day After runs twice per race:

- **Day Before**: a crew weather briefing built from the routings (no instrument data needed).
- **Day After**: the post-race report in four editions (navigator, skipper/owner, crew, 7 Seas client).

Keep **one folder per race**. Day After finds files by type, so names only need to be recognisable:

```
2026-27 season/
  season/                       <- once per season
    llama2_polars_2026.txt
    boats.csv                   (optional: TCCs of boats you race against; Day After also learns them from results)
  2026-10-xx Tollgate Islands/
    course/      Tollgate_Islands_Windy.gpx  (or course.csv)
    routes/      ECMWF_<dd>_<hhmm>_<date>.csv, GFS_..., ACCESS_..., summary of all routes_<date>_<hhmm>.csv
    gribs/       the GRIB files the routings used
    log/         log-2026Oct..csv  + Expedition.db (holds the events)
    fleet/       yb_<key>_AllPositions3.bin, <KEY>-boatids.txt
    results/     results.csv  (+ screenshot or PDF of the results page)
    obs/         IDN60701.<station>.axf files
    notes.md     what you saw, decisions, crew feedback
```

---

## Once per season

| What | Where it comes from | Notes |
|---|---|---|
| Polar | Your ORC certificate, converted for Expedition (`llama2_polars_2026.txt`) | Both Expedition and ORC-table layouts are accepted |
| Boat settings | You | Name, IRC TCC (1.136 for 2026–27), division, masthead-vs-10 m wind factor (start at 1.0) |
| Instrument calibration | Do it before the next race | Flinders showed boat speed reading ~20 % low (factor ×1.26) and upwind TWA ~15° wide. Day After keeps flagging it until fixed. |
| Expedition logging | Expedition → Instruments / Log settings | Turn on **Baro** and **AirTemp** (pressure is the best front/change marker). Check the channel mapping: at Flinders, Heel/Trim/Leeway/MastAng/Rudder all carried the same signal. |

---

## Before the race: for the Day Before crew briefing

Do this on race eve and again on race morning (the race-morning run is what the boat actually sails on).

1. **Course.** Load the SI marks or the GPX course into Expedition, and save the course into `course/`: GPX from Windy or Expedition, or `course.csv` (`seq,name,lat,lon,role`). Note the **turning mark** (the island). Windy GPX files have numbered points only, so name the turning mark in Day After.
2. **GRIBs.** Download the models in Expedition as usual. Copy the files you used from `C:\ProgramData\Expedition\grib\` into `gribs/` **straight away**: Expedition does not keep that folder reliably (newer downloads there have turned into empty files). ACCESS (`EX_ACCESS_Sydney_…`) and UM (`….gre`) files are encrypted by Expedition, so Day After cannot read them; copy them anyway, but for ACCESS the route table (step 3) is the only source Day After can use.
3. **Routings, one per model.** Run Expedition's optimal routing for each model you trust (ECMWF first, then GFS and ACCESS; the crew edition shows at most three). For **each** routing, **export the routing table to CSV**, as was done for Flinders (`GFS_25_1800_25sep2026.csv`), and name it `<MODEL>_<GRIB day>_<GRIB hour>_<date>.csv`. Also save the **"summary of all routes"** CSV. *Flinders had full tables only for the race-eve runs. The race-morning runs existed only as totals, so export the race-morning tables too.*
4. **Run Day After → Day Before** (`dayafter before "<race folder>" --open`; see the README). It builds the crew briefing: one meteogram per model along the route, the window when the change could arrive vs your ETA at the turning mark, the planned sail changes (from the routing's sail column) and the expected tacks, gybes and shifts. Send the HTML file to the crew (it opens offline on phones and laptops).

## During the race

- **Logging on** before the 10-minute gun until after the finish (Expedition logs at 1 Hz).
- **Ping both ends of the start line** in Expedition.
- **Log every sail change and reef as an Expedition event** (navigator). Expedition stores events in `C:\ProgramData\Expedition\database\Expedition.db`, which Day After reads directly. Use the same names as the sail chart (`J1`, `J2`, `A1/2`, `A2`, `J4`, `Poled J4`, `Reef 1`, …).
- Add a short event for anything notable: wind change, squall, gear issue, a rival's move.

## After the race: for the Day After report

**Do the YB and BOM steps first:** that data disappears.

| # | What | Where to find it | When | Needed for |
|---|---|---|---|---|
| 1 | **Fleet tracks (all boats)** | Day After downloads them from YB with the **race key**: the last part of the tracker link, e.g. `yb.tl/bwps2026` → `bwps2026`. **Each race has its own key** (Tollgate Islands: `bwps2026_2`; see the race notes below). Command: `dayafter fetch-yb <key> <race folder>/fleet/`. Manual backup: open `https://cf.yb.tl/BIN/<key>/AllPositions3` in a browser; it downloads a file named `AllPositions3`. Save it into `fleet/` as `yb_<key>_AllPositions3.bin`. YB sometimes refuses requests for a few minutes (HTTP 503); Day After retries, and in a browser just reload. | **Same day** | Fleet comparison |
| 2 | **Boat names for the trackers** | Day After takes them from YB's race setup. Backup: Expedition's YB tracking download writes `<KEY>-boatids.txt` (e.g. `BWPS2026-boatids.txt`) into `C:\ProgramData\Expedition\tracking\`. Copy it to `fleet/`. (Expedition's other tracking files, `<KEY>-expedition.txt` and `<KEY>-YB.json`, hold only the positions Expedition polled while it was running, so they are not enough on their own.) | Same day | Fleet comparison |
| 3 | **BOM coastal observations** | `https://www.bom.gov.au/products/IDN60701/IDN60701.<station>.shtml` → download the `.axf` file, or run `dayafter fetch-bom <station ids> <race folder>/obs/`. Download **after** the race: the Flinders files were saved on race morning and stop before the start. Stations on the southern courses: North Head 95768, Little Bay 94780, Wattamolla 95752, Bellambi 94749, Port Kembla Harbour 95745, Kiama 95749, Point Perpendicular 95940 (your `Observation_Links.xlsx`); further south for Tollgate: Jervis Bay Airfield 94751, Ulladulla 94938, Moruya Airport 95937, Montague Island 94939, Narooma 95935 (checked on BOM's coastal list, 11 Oct 2026). | **Within 72 h** (each file holds only the last 3 days) | Forecast vs observed |
| 4 | **Instrument log** | `C:\ProgramData\Expedition\log\log-YYYYMonDD.csv`. Multi-day races (Sydney–Hobart) have one file per day; copy them all. | Any time | Everything |
| 5 | **Sail-change events** | Copy `C:\ProgramData\Expedition\database\Expedition.db` into `log/`. Day After reads the sail changes, reefs, notes and the gun from it. Without Expedition, fill in `events.csv`: `time_local,type,value,text`. | Within a few days, while memory is fresh | Sail timeline, performance by sail, crew edition |
| 6 | **Results** | CYCA results page for your category, e.g. `bwps.cycaracing.com/race/2026/results/<race>?category=1130` (IRC All). Copy into `results/results.csv` (template below). Copy the **HCAP** column as `tcc`. Keep a screenshot or PDF of the page. | When results are final | Fleet comparison, corrected time |
| 7 | **Routings actually sailed on** | The race-morning route tables and summary (from "Before the race") | Already saved | Plan vs reality |
| 8 | **GRIBs** | The race-morning GRIB files from `C:\ProgramData\Expedition\grib\`, plus any downloaded during the race | Before Expedition purges them (copy on race morning) | Forecast at your own position, model scorecard |
| 9 | **Notes** | `notes.md`: key decisions, what you saw on deck, crew feedback. Day After prints them verbatim in the report. | Day after | All editions |

Then run **Day After → Build**. Choose rivals (default: same division, nearest TCC, three boats) and the editions to build.

### Results template (`results.csv`)

```
place,yacht,owner_skipper,state,division,double_handed,tcc,corrected,status
1,Disko Trooper,Jules Hall,NSW,2,yes,0.996,11:26:52,FINISHED
15,Llama II,Jon Linton,NSW,2,no,1.136,13:19:45,FINISHED
,Jupiter,Ian Smith,NSW,2,yes,1.007,,RETIRED - AT PORT (gear failure)
```
- `corrected` is `h:mm:ss`, or `d:hh:mm:ss` for races over 24 h (Sydney–Hobart).
- Elapsed time is computed as corrected ÷ TCC. **Do not use YB finish times**: at Flinders they ran 1–45 min late.
- TCCs are fixed for the season, so for later races you can leave `tcc` blank for boats Day After already knows.

### Where does the other boats' data come from?

There is no "download" button on the YB race page. The full tracks for every boat sit in YB's data file `https://cf.yb.tl/BIN/<race-key>/AllPositions3`. Day After reads that file directly: it fetches it with the race key, or opens the copy you saved. It holds 10-minute positions for every tracker in the race. YB's race setup (`https://cf.yb.tl/JSON/<race-key>/RaceSetup`) gives the boat names and the gun time. Expedition's own YB download is a backup for the **boat names** (`<KEY>-boatids.txt`) but holds only the positions Expedition polled while it was running. Logs from other boats (for Njord-style two-boat gain/loss) are optional; none are available at the moment.

---

## Race notes for the rest of the season

| Race | Course file on hand | Things to watch |
|---|---|---|
| Tollgate Islands | Expedition route `Tollgate_Islands_Windy` in `marks.xml` (rounding marks `TG SE`, `TG South`, `TG SW`, `TG NW`, around 35.75° S off Batemans Bay); `Tollgate_Islands_Windy.gpx` has numbered points only | YB key **`bwps2026_2`**; gun **Fri 16 Oct 2026 14:00 AEDT (UTC+11)**. BOM stations further south: Point Perpendicular 95940, Jervis Bay Airfield 94751, Ulladulla 94938, Moruya Airport 95937, Montague Island 94939. Check the local magnetic variation on the chart (Day After assumes about 13.2° E there unless `variation_deg_e` is set) |
| Bird Island | `Bird_island_Windy.gpx` (north of Sydney) | YB key `Bwps2026_3`. Northern BOM stations (e.g. Norah Head). In Expedition, the `Finish` mark of the `Bird Island` route is stored at lat **+33.842** (wrong hemisphere): fix it before routing |
| Cabbage Tree Island | `Cabbage_Tree_Island_Windy.gpx` (off Port Stephens, about 32.7° S) | YB key `Bwps2026_4`. Northern stations; long night leg |
| Sydney–Hobart | Use the SI course | Multi-day logs, **AEDT (UTC+11)**, variation rising to about 15° E, results in `d:hh:mm:ss`, a different YB key. Expect GRIB files of several days. |

*BOM station names above are suggestions; pick the ones along each course and add them to `Observation_Links.xlsx`.*

## Privacy

The race folder (logs, polars, routings) stays on your computer. The public `day-after` repository never contains it (`data/` is git-ignored). The 7 Seas client edition includes only that client's own data plus public tracker and results data.
