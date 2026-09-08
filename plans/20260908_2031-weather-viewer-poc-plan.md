# Weather viewer POC — plan

Status: **draft, awaiting review** · written 20260908 20:31 UTC · branch `20260908_2031-poc-plan`

## 1. Goal

A single-page app in TypeScript that runs in the browser (Chrome as reference) and shows **one variable for one year** of the Dublin Airport hourly series. Two controls: the year (autocomplete over the years present in the data) and the variable (dropdown). The y-scale is fixed per variable, so the same variable looks the same across years and years can be compared by eye. Minimal POC: no framework, no backend, no tests beyond a manual check.

## 2. The data (measured on 20260908)

Source: **Met Éireann**, the Irish national meteorological service. Dublin Airport synoptic station, hourly. The same dataset is listed on data.gov.ie as "Dublin Airport Hourly Data", licence **Creative Commons Attribution 4.0** — Met Éireann must be credited as the source (verified on data.gov.ie, 20260908).

| Item | Value |
|---|---|
| Files | `data/dublin_airport-meteo-1946-2026-data.csv` (63.6 MB, 12.1 MB gzipped) and `data/dublin_airport-meteo-1946-2026-info.txt` (column legend, station metadata). Both are **untracked in git** today. |
| Rows | 706,369 data rows, one per hour. Date format `dd-mon-yyyy HH:MM`, UTC. |
| Span | 1946-01-01 00:00 → 2026-08-01 00:00 |
| Regularity | Exactly one row per hour: 0 gaps, 0 duplicates, strictly chronological, no ragged rows. 80 complete years (1946–2025) plus a partial 2026 (5,089 hours, to 1 Aug). |
| Columns | 21: `date`, 15 variables, 5 indicator columns **all named `ind`** (duplicate header names; a generic "CSV to objects" parser would collapse them). |
| Missing values | Empty cells, negligible: vis 255, clht 24, clamt 24, vappr / rhum / wddir 1 each. |
| Sentinels | `clht` 999 = no cloud ceiling (not a height). `ind` = 111 in ~287k early rows (indicator not available). `wddir` 0 = calm, 360 = north. |

Variables and their global range over the whole series (this is what fixes the per-variable scale):

| Column | Meaning | Unit | Global min..max |
|---|---|---|---|
| rain | precipitation amount | mm per hour | 0 .. 26.5 |
| temp | air temperature | °C | -11.5 .. 29.1 |
| wetb | wet bulb temperature | °C | -11.5 .. 22.6 |
| dewpt | dew point temperature | °C | -17.7 .. 20.5 |
| vappr | vapour pressure | hPa | 2.2 .. 24.2 |
| rhum | relative humidity | % | 19 .. 100 |
| msl | mean sea level pressure | hPa | 944.1 .. 1048.7 |
| wdsp | mean wind speed | knot | 0 .. 46 |
| wddir | predominant wind direction | degree | 0 .. 360 |
| ww / w | present / past weather | SYNOP code | 0 .. 99, categorical |
| sun | sunshine duration | hours per hour | 0 .. 1 |
| vis | visibility | m | 5 .. 75,000 |
| clht | cloud ceiling height | 100s of ft | 0 .. 999 (999 = none) |
| clamt | cloud amount | okta | 0 .. 8, 9 = sky obscured |

Consequence of the perfect regularity: row index = hours since 1946-01-01 00:00 UTC, and every year is one contiguous block. Slicing per year needs no index and no date parsing at runtime.

## 3. Storage and lazy loading

The whole CSV is 63.6 MB (12 MB gzipped) and would be ~45 MB of typed arrays in memory. The app only ever needs one year, so the data should be split once, ahead of time, and fetched per year. Options considered:

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. One file per year** (recommended) | A script splits the CSV once into `public/data/years/<year>.json` (columnar: one array per variable, `null` = missing) plus `public/data/meta.json` (years, units, labels, global min/max). The app does one `fetch` per year. | ~640 KB per year (~100 KB gzipped), parsed in a few ms. Plain `fetch`, no library, works on any static host, readable in devtools. On a data refresh only the current year's file changes. | One-off preprocessing step; 81 generated files. |
| A′. Same, binary | `<year>.f32`: Float32 columns back to back, `NaN` = missing. | 513 KB per year, zero parse cost (`new Float32Array(buffer)`). | Opaque in devtools; needs a documented layout. |
| B. One binary file per variable + HTTP Range requests | `temp.f32` is 2.8 MB for all 80 years; a year is one byte range computed from the hour offset. | No per-year files; smallest transfer (34 KB per year per variable). Elegant given the regular grid. | Relies on the server honouring `Range` (Vite dev server and GitHub Pages do; `python -m http.server` does not). Harder to inspect. |
| C. Parquet / Arrow + DuckDB-WASM (or arrow-js, parquet-wasm) | SQL or Arrow tables in the browser over a columnar file. | Real analytics later (aggregates, joins, filters). | 10 MB+ of WASM to download, worker setup, Range support needed. Far beyond "show one year". |
| D. Load the whole CSV in the browser | PapaParse or d3-dsv in a Web Worker. | No preprocessing. | 12 MB download and seconds of parsing on every load; ~45 MB resident. |

Measured on 1990 (8,760 hours, 15 variables):

| Format | Size | gzipped |
|---|---|---|
| CSV slice, 21 columns | 741 KB | 155 KB |
| JSON columnar, 15 variables | 638 KB | 101 KB |
| Float32 binary, 15 variables | 513 KB | 105 KB |
| JSON, one variable (temp) | 39 KB | 10 KB |
| Float32, one variable (temp) | 34 KB | 12 KB |

Recommendation: **A**. It is the smallest thing that gives lazy loading. Moving to A′, to per-variable files, or to B later changes one script and one fetch function, not the app. C is worth revisiting only if this grows into an analysis tool. At runtime, keep a `Map<year, YearData>` of visited years so switching back is instant.

## 4. Architecture

Stack:

- Vite + vanilla TypeScript (`npm create vite@latest -- --template vanilla-ts`), no UI framework.
- Chart library: uPlot (see section 5).
- Preprocessing: one TypeScript script run directly by Node (Node 26 strips types natively, erasable syntax only), so the whole project stays in one language. Python (stdlib) is the fallback if you prefer; pandas is not installed locally.

Files:

```
index.html               controls + chart container
src/main.ts              wires the controls → fetch → draw
src/data.ts              fetchMeta(), fetchYear(year), in-memory cache
src/chart.ts             uPlot wrapper; y-range fixed from meta
src/variables.ts         label, unit, formatting, optional manual range per variable
scripts/split-years.ts   CSV → public/data/meta.json + public/data/years/<year>.json
public/data/             generated by the script (see open question 1)
README.md                how to run, how to regenerate data, Met Éireann attribution
```

Behaviour:

- Year control: `<input list="years">` + `<datalist>` (Chrome's native autocomplete), populated from `meta.json`. An unknown year is ignored.
- Variable control: `<select>`, populated from `meta.json`.
- Chart: one line, hourly points (8,760–8,784 per year), time x-axis in UTC always spanning 1 Jan → 31 Dec of the selected year. A partial year shows an empty remainder, so incompleteness is visible. Hover shows timestamp and value.
- Scale: y-range per variable = global [min, max] from `meta.json`, rounded outward to a round step (temp → -15..30 °C, msl → 940..1050 hPa). Same variable ⇒ same axis on every year; changing the variable ⇒ axis and unit change. A manual override per variable lives in `variables.ts` for cases where the automatic range is unhelpful.
- Missing cells and `clht` 999 → `null` → a gap in the line.
- Footer: "Data: Met Éireann, Dublin Airport hourly observations, CC BY 4.0".

## 5. Chart library

| Library | Size (approx.) | Fit for an 8,760-point hourly line | Notes |
|---|---|---|---|
| **uPlot** (recommended) | ~45 KB minified | Designed for exactly this: canvas, tens of thousands of points without decimation. | Fixed range via `scales.y.range: [min, max]`; time axis built in (unix seconds); TS types shipped. Low-level API, example-driven docs. |
| Chart.js | ~200 KB minified + date adapter | Fine with the decimation plugin. | Most familiar API; needs `chartjs-adapter-date-fns` for a time axis. |
| Plotly.js | 1–3.5 MB | Works, noticeably heavier. | Zoom, pan, export for free; overkill for one line. |
| ECharts | ~1 MB | Good, has data sampling. | Large API surface. |

## 6. Steps

1. Scaffold Vite vanilla-ts, add uPlot, commit.
2. `scripts/split-years.ts`: parse the CSV (drop the five `ind` columns), write `meta.json` and the per-year files; run it once; commit the script.
3. `data.ts` (fetch + cache), `chart.ts`, controls in `main.ts`.
4. Manual check in Chrome: years 1946, 1990, 2026 (partial); every variable; same axis across years for one variable; gaps for missing values.
5. README: run (`npm install && npm run dev`), regenerate data, attribution.

Expected size: 250–350 lines of TypeScript plus ~80 for the script.

## 7. Out of scope for the POC

Overlaying two years or two variables, zoom and pan, day/month ranges, daily or monthly aggregation, the indicator columns, SYNOP code legends, deployment, automated tests.

## 8. Open questions (need your answer before implementation)

1. **Data in git.** The raw CSV is untracked and 63.6 MB; GitHub warns above 50 MB per file. Also, per-repo rules the implementation happens in a git worktree, which only contains tracked files, so the data must be reachable from there. Options: (a) commit `data/*.csv.gz` (12 MB) and the info file; keep generated `public/data/` out of git and rebuild it with `npm run data` — **recommended**: one source of truth, reproducible, small; (b) additionally commit the generated per-year files (~52 MB of JSON, git-packed to roughly 8–10 MB) — only needed to deploy straight from the repo, e.g. GitHub Pages, without a build step; (c) keep all data out of git and point the script at a local path.
2. **Chart library:** uPlot (recommended) or Chart.js?
3. **Variables in the dropdown:** all 15, or the 13 numeric ones only, dropping the SYNOP codes `ww` and `w` (recommended: drop them, they are categorical codes and meaningless as a line)?
4. **Preprocessing language:** TypeScript run by Node (recommended, one language) or Python?
5. **Hosting for now:** local `npm run dev` only (assumed), with GitHub Pages as a possible later step?

Defaults I will apply unless you object: UTC on the axis; gaps for missing values; full Jan–Dec axis for a partial year; automatic global min/max scale rounded outward; npm as package manager.
