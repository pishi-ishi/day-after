# Look and branding

Day After uses three visual systems:

1. **App UI** (the browser window at localhost): the dark 7seas-telemetrics look.
2. **Reports** (navigator, skipper, crew, Day Before): light, clean, Njord-like, and built on the validated data-viz palette below.
3. **7 Seas client edition**: the report system re-skinned with 7 Seas Marine Electronics branding.

Define tokens once as CSS custom properties and reuse them across app and reports.

---

## 1. App UI tokens (from 7seas-telemetrics `sevenseas/gui.py`)

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#000000` | Page |
| `--panel` | `#121212` | Panels |
| `--panel-2` | `#1C1C1C` | Inputs, cards |
| `--panel-3` | `#242424` | Hover, raised |
| `--text` | `#FAFAFA` | Primary text |
| `--muted` | `#A7A7A7` | Secondary text |
| `--dim` | `#6F6F6F` | Disabled, hints |
| `--accent` | `#DC143C` | Crimson accent, primary buttons |
| `--accent-hover` | `#F04060` | |
| `--ok` | `#22C55E` | Input found / check passed |
| `--warn` | `#F5B544` | Input missing (optional) / warning |
| `--err` | `#EF4444` | Input missing (required) / error |

The app icon follows the 7seas-telemetrics icon (two masts, two sails, hull baseline; see its `make_icon.py`) with the wordmark "day after".

## 2. Report system (light; dark mode chosen separately)

**Surfaces and ink**

| Role | Light | Dark |
|---|---|---|
| Chart surface | `#fcfcfb` | `#1a1a19` |
| Page | `#f9f9f7` | `#0d0d0d` |
| Primary ink | `#0b0b0b` | `#f0efec` |
| Secondary ink | `#52514e` | `#c3c2b7` |
| Muted (axes, labels) | `#898781` | `#898781` |
| Gridline | `#e1e0d9` | `#2c2c2a` |
| Land (map) | `#ebe9e3` | `#2a2a28` |
| Coastline | `#b4b1a8` | `#5a5955` |

**Fixed entity colours** (colour follows the entity, never its rank):

| Entity | Light | Dark | Secondary encoding |
|---|---|---|---|
| **Our boat** (always) | `#2a78d6` blue | `#3987e5` | solid, thicker line |
| GFS | `#eb6834` orange | `#d95926` | dashed `6 3`, circle markers |
| ECMWF | `#1baf7a` aqua | `#199e70` | dashed `2 2`, square markers |
| ACCESS | `#eda100` yellow | `#c98500` | dash-dot, triangle markers |
| Rival 1 | `#e87ba4` magenta | `#d55181` | direct label |
| Rival 2 | `#008300` green | `#008300` | direct label |
| Rival 3 | `#6250d6` violet | `#9085e9` | direct label |
| Other model / 4th rival | `#e34948` red | `#e66767` | direct label |
| Everyone else (fleet context) | muted ink at 35 % | | no label |

**Status** (never reused for series; always with icon + label): good `#0ca30c`, warning `#fab219`, serious `#ec835a`, critical `#d03b3b`.

**Expedition meteogram colours** (crew edition and Day Before, so the crew learns the nav-screen look): TWS **red**, pressure **black**, air temperature **green**, rain **blue**. Draw them as **stacked panels on one shared time axis**, one quantity per panel. Never use a dual y-axis.

**Chart rules** (from the data-viz method these colours were validated with):
- One y-axis per chart. Two measures → two panels.
- Legend whenever there are ≥2 series; direct labels when there are ≤4. Never rely on colour alone (dash patterns and markers above).
- Thin marks: 2 px lines, ≥8 px markers, recessive grid.
- Hover by default: crosshair + tooltip on lines, per-mark tooltip on dots and bars. Map and time charts share one time cursor.
- A table view for every chart (the navigator edition shows them; the others link to them).
- Text uses ink tokens, never series colours.
- Yellow sits below 3:1 contrast on the light surface, so ACCESS lines always carry a direct label.
- Scatter/map with >3 coloured series: fade the rest to the muted fleet colour.
- Typeface: system sans (`system-ui, -apple-system, "Segoe UI", sans-serif`), tabular figures in tables and axes.
- Print: A4 portrait, one module per page group, charts static, hover layer hidden, URLs printed.

## 3. 7 Seas Marine Electronics (client edition)

**Source:** the live site **7seasmarine.me** (checked 11 Oct 2026). It is still the older site builder version. The redesign in `github.com/pishi-ishi/7seasmarine.me` uses a different palette (navy `#0b1f33`/`#123a5c`, teal `#1b9aaa`, amber `#e8792f`); switch to it if that site goes live.

**Logo:** `assets/7seas_logo.svg`, a vector redraw of the site logo: two masts, two sails, a hull baseline, and the wordmark "Seven Seas Marine Electronics". It uses `currentColor`, so it works black-on-light and white-on-dark. The original raster (300×248 PNG) is served at `https://7seasmarine.me/gallery_gen/599a33c4ba6496e2213cb32c7732d878_300x248_fit.png`, and may also be in `C:\Users\user\Documents\7seasmarine.me\`. If exactness matters, compare the redraw with it and replace the SVG.

**Colours (live site CSS):**

| Token | Hex | Use in the client edition |
|---|---|---|
| `--7s-ink` | `#000000` | Logo, headings |
| `--7s-navy` | `#2e3a51` | Cover band, section headers, footer |
| `--7s-sky` | `#e6f8ff` | Page/cover background tint |
| `--7s-aqua` | `#bef7f6` | Highlights, KPI tile backgrounds |
| `--7s-sand` | `#d0c7ba` | Rules, table header tint |
| `--7s-white` | `#ffffff` | |

Data series keep the report palette above. Brand colours frame the page and never encode data.

**Type:** the site uses Montserrat (headings) and Open Sans (body). Reports must work offline, so use `Montserrat, "Segoe UI", system-ui, sans-serif` and `"Open Sans", system-ui, sans-serif`. Embedding WOFF2 subsets (SIL OFL) is optional.

**Cover page and footer:** logo, "Post-race analysis: <race>, <boat>", date, "Prepared by 7Seas Marine Electronics · 66B Prince St, Mosman NSW 2088 · 7seasmarine.me · info@7seasmarine.me". The footer on every page repeats the name and the page number.

## 4. Coastline and map attributions

- `assets/coast/ne10m_land_se_australia.geojson`: Natural Earth 10 m land (public domain), clipped to lon 145.5–155°, lat −44.5 to −31°, Douglas-Peucker 0.004°. Covers every BWPS course and Sydney–Hobart.
- `assets/coast/osm_coast_sydney_wollongong.geojson`: OpenStreetMap `natural=coastline` (ODbL). Credit "© OpenStreetMap contributors" on every map that shows it.
- Optional online tiles (as in 7seas-telemetrics `maptiles.py`): OSM standard and Esri World Imagery, with their attributions, used only when the viewer is online.
