# Input file formats

Formats are marked **verified** (checked against real files from Llama II's 2026 season) or **to verify** (T1 in HANDOVER: needs a look in `/mnt/c/ProgramData/Expedition/`). Samples come from `data/` and `fixtures/`.

---

## 1. Expedition instrument log (`log-YYYYMonDD.csv`): verified

Sparse CSV written by Expedition 12.7.16 at about 1 Hz. Found in `C:\ProgramData\Expedition\log\`.

```
!Boat,Utc,BSP,AWA,AWS,TWA,TWS,TWD,RudderFwd,Leeway,Set,Drift,HDG,...      <- channel names
!boat,0,1,2,3,4,5,6,7,10,11,12,13,...                                       <- channel ids, same order
!v12.7.16                                                                    <- Expedition version
0,46290.827624,147,151.0,148,331.0,272,61.0,373,11.10                        <- data rows
```

- **Header blocks repeat** whenever the logged channel set changes. The Flinders log has four, at lines 1, 469, 10010 and 35385, with `dTargBsp`, `dTargTwa` and `dPolBsp` added later. Ids are global, so **merge** the name↔id maps from every block. There are 214 distinct channels.
- Data row: `boat, Utc, id, value, id, value, …`. Only channels that changed are written. `boat` 0 is own boat.
- `Utc` = **days since 1899-12-30 00:00 UTC** (Excel serial; 46290.8276 = 2026-09-25 19:51 UTC). Epoch s = (Utc − 25569) × 86400.
- Units: knots, degrees, `Lat`/`Lon` decimal degrees, HDG/COG/TWD **true**. The Flinders calibration fit gives a heading offset of only +0.5°, confirming true.

Common ids (from the Flinders header):

| Channel | id | Channel | id | Channel | id |
|---|---|---|---|---|---|
| BSP | 1 | HDG | 13 | Lat / Lon | 48 / 49 |
| AWA | 2 | AirTemp | 14 | COG / SOG | 50 / 51 |
| AWS | 3 | SeaTemp | 15 | Main | 69 |
| TWA | 4 | Baro | 16 | RPM 1 | 75 |
| TWS | 5 | Depth | 17 | dTargTwa | 104 |
| TWD | 6 | Heel / Trim | 18 / 19 | GPS time | 146 |
| dTargBsp | 8 | Rudder | 20 | Mk Lat / Mk Lon | 161 / 162 |
| Leeway | 10 | ROT | 32 | Port lat/lon | 163 / 164 |
| Set / Drift | 11 / 12 | TmToGun | 204 | Stbd lat/lon | 165 / 166 |
| TWDTwisted | 272 | dPolBsp | 279 | J1–J4 | 323–326 |
| TWDmin / TWDmax | 411 / 412 | | | | |

Llama II specifics (2026): Baro and AirTemp **absent**; Heel/Trim/Leeway/MastAng/Rudder/KeelAng/Foil channels are **duplicates** of one heel-like signal; J1–J4/Main/Forestay/Runner/D0/D1/Bobstay share one sparse series; WaterLev = FuelLev. The log continued after the finish, until 27 Sep 15:04 local.

## 2. Expedition optimal route table (`<MODEL>_<dd>_<hhmm>_<ddmonyyyy>.csv`): verified

The owner exports this from Expedition's routing table, one file per model run. Example: `GFS_25_1800_25sep2026.csv`. The name gives the model, the GRIB cycle day/hour and the date.

```
AUS Eastern Standard Time,Mark,Sail,Reef,Other,Twd°M,Tws,Twg,Twa,Targ,Bsp,Bsp%,Set°M,Drift,Weight,Brg°M,Dist nm,Awa,Aws,Mode,SigWave H,MeanWaveDir,MeanWavePer,PrimaryWaveDir,PrimaryWavePer,Swell dir,Swell H,Swell period,Wave Dir,Wave H,Wave period,MSLP,Rain,AirT,SST,Cloud,CAPE,LFTX,RH,AirDens,Latitude,Longitude
26-Sep-2026 10:00,Start,J1,,,322,4.1,7.9,-67,043,5.3,100.0,,,0.98,029,2.20,-28,7.8,Sail,,,,,,,,,,,,1024.01,0.00,25.4,,5.0,63.3,,,1.19,33 51.6390s,151 14.8560e
26-Sep-2026 10:29,South Head,,,,329,4.9,8.6,(-173),150,3.8,100.0,169,0.4,0.97,143,1.08,-101,2.5,Sail,...,33 49.8750s,151 16.8450e
...
26-Sep-2026 20:35,Finish,,,,161,23.4,29.3,,,,,129,0.4,1.01,,,,,Sail,...,33 50.4681s,151 16.4630e
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,          <- separator: a row of commas only
Name,G GFS High 17:34:41,,,...
Route distance,88.06nm
Optimal distance,93.17nm
Optimal route time,10h 35m 45s
Created,25-Sep-2026 17:34:41
Sail chart,SailChart_Llama_S2H
Polar,llama2_polars_2026
Polar % day,100
Polar % night,100
Model,GFS
Current,Copernicus
Wind %,100
Current %,130
Algorithm,Grid
Waves,No
Air density weight,Yes
Motor,No
```

- The time column header is the **Windows time-zone ID**. Values are local wall-clock (`%d-%b-%Y %H:%M`) in Australia/Sydney, DST included.
- **Directions are magnetic** (`Twd°M`, `Set°M`, `Brg°M`). Convert to true with local variation (12.8° E at Sydney in 2026).
- `Mark` is filled on rows where the route reaches a course mark. Names repeat on the return leg. Match by name plus occurrence order.
- `Sail` is the sail from the sail chart for that step (e.g. `J1`, `A1/2`, `OB J1`, `Poled J4`, `J4`); blank means unchanged.
- `Twa` is signed (+ stbd). A value in parentheses, e.g. `(-173)`, appears on mark rows. It probably means the boat is held on a mark-to-mark course rather than a free optimal angle *(to verify)*. Strip the parentheses and keep a flag.
- `Twg` is gust (kt), `MSLP` hPa, `Rain` mm/h, `AirT` °C, `Cloud` %, `Bsp%` the polar % used. `Targ` is probably the heading to steer (°M) *(to verify)*.
- `Latitude`/`Longitude` are degrees + decimal minutes + lowercase hemisphere: `33 51.6390s`, `151 14.8560e`.
- The meta block after the comma-only row holds `key,value` pairs.

## 3. Expedition "summary of all routes" (`summary of all routes_<ddmonyyyy>_<hhmm>.csv`): verified

```
Draw,Name,Colour,Route nm,Optimal nm,Elapsed time,Finish,Delta,Created
 G ,G ACCESS SY High 06:34:23,,88.15,91.01,11h 04m 45s,26-Sep-2026 21:04:45,-47m 52s,26-Sep-2026 06:34:23
 G ,G GFS High 06:34:12,,88.15,92.45,11h 57m 10s,26-Sep-2026 21:57:10,04m 32s,26-Sep-2026 06:34:12
 G ,G  High 06:38:43,,88.15,91.75,11h 52m 37s,26-Sep-2026 21:52:37,,26-Sep-2026 06:38:43
```

`Name` = `G <MODEL> High <hh:mm:ss>`. Models seen: `ACCESS SY`, `GFS`, `ECMWF`, `AIGFS`, `AIFS`, `ICON`, and blank (the active/reference route, which carries no `Delta`). `Delta` is elapsed relative to that reference. Elapsed is `11h 04m 45s` or `01h 55m 10s`; negative deltas have a leading `-`. Use these as extra predicted finishes when no full table exists for that run.

## 4. Polars: verified, two layouts

**A. Expedition polar** (`llama2_polars_2026.txt`): tab-separated. The first line starts with `!`. Each row is TWS followed by (TWA, BSP) pairs:
```
!Expedition polar
4	0	0	43.4	3.88	52	4.44	60	4.75	75	4.98	90	4.81	110	4.68	120	4.51	135	3.98	141.6	3.60	150	3.26	180	2.82
...
24	0	0	38.8	7.66	52	8.52	...	150	10.86	158.1	10.16	180	9.43
```
The pair after `0 0` is the **beat angle and beat speed**. The non-grid angle near 140–160° is the **run (gybe) angle and speed**. The 180° value equals the run VMG (ORC convention). Rows run from 4 to 24 kt. Above 24 kt **clamp to the 24 kt row** and mark the result "indicative".

**B. ORC certificate table** (`wings_2026.txt`, sister ship Dehler 46 *Wings*): tab-separated with TWS across the columns:
```
Twa/Tws	4	6	8	10	12	14	16	20	24
Upwind	46.0	43.4	41.4	39.8	38.9	38.3	38.0	37.9	38.8      <- beat angles
0	2.75	3.93	4.82	5.41	5.70	5.86	5.96	6.06	6.00          <- BEAT VMG (not BSP at 0°)
52	4.34	6.02	...
150	3.24	4.76	...
180	2.80	4.12	...                                             <- RUN VMG
Downwind	139.7	142.4	147.4	151.0	155.5	162.1	167.5	169.1	162.7   <- gybe angles
```
Convert to layout A: beat BSP = beat VMG ÷ cos(beat angle); run BSP = run VMG ÷ cos(180° − gybe angle); 180° BSP = run VMG.

Both feed one interpolator: bilinear in TWS × |TWA|, below 4 kt scaled linearly to 0, clamped above 24 kt. The reference is `reference/flinders_2026_scripts/polar.py`.

## 5. Course

**A. Day After `course.csv`** (template, verified with Flinders): `seq,name,lat,lon,role,note`. Role is one of `start | waypoint | turning_mark | finish`. Decimal degrees. See `fixtures/flinders_2026/course.csv`, where Flinders Islet is three rounding points, FI W → FI S → FI E.

**B. GPX route** (Windy exports in `data/courses/*.gpx`): `<rte><rtept lat lon><name>1</name>…`. Points are numbered only. The user names the turning mark in the UI, or Day After takes the vertex farthest from the start. Files are on hand for **Flinders Islet, Tollgate Islands, Bird Island and Cabbage Tree Island**.

**C. From a route table:** rows with a `Mark` name, using their lat/lon.

**D. Expedition marks/routes file** (`CYCA SOPS LOPS.dat`, also `C:\ProgramData\Expedition\marks-routes_me\`): MFC serialisation (`CMarkGrpOb`, `CMarkOb`, `CRouteOb`, `CMarkPtrOb` class tags). Verified so far: each mark stores **two little-endian float64 (lat, lon) in degrees before its name**. Names are MFC CStrings in UTF-16LE, prefixed `FF FE FF <len>`, then a second (notes) string. Routes reference marks by pointer. A best-effort parser (scan for name strings and take the two doubles preceding each record) recovered `Start −33.86065 151.2476`, `Finish −33.84114 151.27438`, `Cape Banks −34.00053 151.25702`, plus the Cabbage Tree, Bird Island and Flinders Island marks. **Prefer GPX/CSV export from Expedition**, and treat .dat parsing as optional.

## 6. YB Tracking: verified

**Full fleet tracks** (binary): `https://cf.yb.tl/BIN/<race-key>/AllPositions3`. Flinders key `bwps2026`: 27,443 bytes and 36 trackers on 11 Oct 2026. Big-endian layout:
```
u8  flags                 bit0 altitude, bit1 DTF, bit2 lap (only with DTF), bit3 percent-complete
u32 refTime               epoch seconds base (1720000000 for bwps2026)
repeat until end of buffer:
  u16 trackerId
  u16 nMoments
  nMoments × moment, NEWEST FIRST:
    if first byte & 0x80:  (delta record, 6 bytes + optional fields)
        u16 dt  = (u16 & 0x7FFF)    -> at  = prev.at  - dt
        i16 dLat                     -> lat = prev.lat + dLat
        i16 dLon                     -> lon = prev.lon + dLon
        [i16 alt] [i16 dDTF -> dtf = prev.dtf + dDTF] [u8 lap] [i16 pc/32000]
    else:                    (absolute record, 12 bytes + optional fields)
        u32 t   -> at = refTime + t
        i32 lat, i32 lon
        [i16 alt] [i32 dtf] [u8 lap] [i32 pc/21000000]
lat, lon in 1e-5 degrees
```
Test vector: `fixtures/flinders_2026/yb_allpositions3_head_team2.hex`. The first 741 bytes are flags 0, refTime 1720000000, then tracker 2 with 121 moments. The first moment is at = 1790460000, lat −33.87410, lon 151.23320; the last is at = 1790226684, lat −33.87438, lon 151.23318. Decoding the whole file consumes exactly 27,443 bytes.

**Names:** `https://cf.yb.tl/JSON/<key>/RaceSetup` (returned **503** on 11 Oct; treat as optional). Fallback: Expedition's tracking download `<key>-boatids.csv` (`id,name`, includes `Spare n` and `Virtual Tracker …` rows), then fuzzy match to results.

**Not useful for tracks:** `<key>-expedition.csv` from Expedition's tracking download has **only the latest fix per boat**: `id,lat,lon,yymmddHHMM` (e.g. `2,-33.87410,151.23320,2609262200`).

**Caveats:** the key spans the series, so filter to the race window. Fixes come every 10 min (5 min near the end for some boats). YB "finish" timing is unreliable (see HANDOVER §6).

## 7. Results: verified (Day After template)

`results.csv`: the owner copies it from the CYCA results page (`bwps.cycaracing.com/race/<year>/results/<race>?category=<id>`, a JavaScript page; a screenshot or PDF works as the source):
```
place,yacht,owner_skipper,state,division,double_handed,tcc,corrected,status
15,Llama II,Jon Linton,NSW,2,no,1.136,13:19:45,FINISHED
,Jupiter,Ian Smith,NSW,2,yes,1.007,,RETIRED - AT PORT (gear failure)
```
`tcc` = the page's **HCAP** column (the IRC TCC, fixed for the season). `corrected` is `h:mm:ss`, or `d:hh:mm:ss` for races over 24 h. Day After derives elapsed = corrected ÷ TCC and stores TCCs in the season DB, so later races can reuse them (then only corrected times, or elapsed times, are needed). Optional extra columns: `elapsed`, `phs`, `orc`.

## 8. BOM coastal observations (`IDN60701.<wmo>.axf`): verified

INI-like text sections `[notice]`, `[header]` and `[data]`. `[data]` is a CSV with a header row:
```
sort_order,wmo,name[80],history_product[80],local_date_time[80],local_date_time_full[80],aifstime_utc[80],lat,lon,...,gust_kt,air_temp,press,press_msl,...,wind_dir[80],wind_spd_kt
0,95768,"North Head","IDN60701","26/06:30am","20260926063000","20260925203000",-33.8,151.3,...,3,-9999.0,-9999.0,-9999.0,...,"NNW",1
```
Missing = `-9999`. `aifstime_utc` is `YYYYMMDDhhmmss` UTC. `wind_dir` is 16-point text. A file covers about the last 72 h at 30-min steps, so download it **within 3 days** of the race. Stations on the Flinders course: North Head 95768, Little Bay 94780, Wattamolla 95752, Bellambi 94749, Port Kembla Harbour 95745, Kiama 95749, Point Perpendicular 95940. URL pattern: `https://www.bom.gov.au/products/IDN60701/IDN60701.<wmo>.shtml` (the page links the `.axf`).

## 9. GRIB files: to verify (T1)

Location: `C:\ProgramData\Expedition\grib\`. Expected: Saildocs GRIB1 (simple packing) and Expedition-server GRIB2 per model (GFS, ECMWF, ACCESS-SY/G, ICON, AIGFS/AIFS). Record per file: edition, centre, grid (template 3.0 regular lat/lon?), **packing template** (5.0 / 5.2 / 5.3 / 5.40 / 5.41 / 5.42), parameters and levels, step count, file sizes. Decoder plan and decision rule: HANDOVER §4 T1.

Parameters to read (GRIB2 discipline/category/number → GRIB1 table 2):
U10 (0/2/2 → 33), V10 (0/2/3 → 34), gust (0/2/22 → 180 at NCEP), MSLP/PRMSL (0/3/1 → 2), 2 m temperature (0/0/0 → 11), precipitation rate or total (0/1/7, 0/1/8 → 59/61), total cloud (0/6/1 → 71). Wind level: type 103 (GRIB2) / 105 (GRIB1), 10 m.

## 10. Expedition events (sail changes, notes): to verify (T1)

The navigator logs sail changes in Expedition. Find the store (`database/`, `racenotes/` or inside `log/`) and document its format and the naming the navigator uses (e.g. `J1`, `A2`, `Reef 1`). Until then, Day After also accepts its own `events.csv`:
```
time_local,type,value,text
2026-09-26 11:10,sail,A1/2,hoist A1/2 at Dunbar
2026-09-26 16:02,sail,J1,drop kite, J1 up after rounding
2026-09-26 17:20,reef,1,first reef in southerly
```
`type` ∈ `sail | reef | note | mark | penalty | incident`.

## 11. Expedition sail chart: to verify (optional)

`C:\ProgramData\Expedition\sails\SailChart_Llama_S2H*`. The route table's `Sail` column already gives the planned sail per step, so parsing the chart is only needed to show the crossover chart itself.

## 12. Day After project file (`race.dayafter.json`): proposed

```json
{
  "race": {"name": "Flinders Islet Race 2026", "series": "BWPS 2026-27", "gun_local": "2026-09-26T10:00:00",
           "tz": "Australia/Sydney", "variation_deg_e": 12.8, "category": "IRC All"},
  "boat": {"name": "Llama II", "tcc": 1.136, "division": "2", "polar": "data/polars/llama2_polars_2026.txt",
           "masthead_wind_factor": 1.0},
  "inputs": {"log": "...", "routes": ["..."], "route_summaries": ["..."], "gribs": ["..."], "course": "...",
             "yb_key": "bwps2026", "yb_file": "...", "boatids": "...", "results": "...", "events": "...", "bom": ["..."]},
  "course": {"turning_mark": "FI S", "gate_step_nm": 5},
  "fleet": {"rivals": ["Calibre 12", "Kanreki", "Ragtime"], "rule": "same division, nearest TCC, 3"},
  "editions": ["navigator", "skipper", "crew", "client"],
  "crew_models": "auto",
  "notes": {"navigator": "", "skipper": ""}
}
```
