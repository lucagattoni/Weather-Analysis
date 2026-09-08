# Weather viewer POC — plan

Status: **v3, all decisions taken, ready to implement on the go-ahead** · written 20260908 20:31 UTC · updated 20260908 21:08 UTC · branch `20260908_2031-poc-plan`

Decisions taken on 20260908 are recorded in section 9. The alternatives stay in the tables so the choice remains visible. Section 4 ends with the language boundary (TypeScript only for now).

## 1. Goal

A single-page app in TypeScript that runs in the browser (Chrome as reference) and shows **one variable for one year** of the Dublin Airport hourly series. Two controls: the year (autocomplete over the years present in the data) and the variable (dropdown). The y-scale is fixed per variable, so the same variable looks the same across years and years can be compared by eye.

Minimal POC in features, but **modular in structure**: the app must be extendable later (pan/zoom, range selection, overlaying two years or two variables, other views, other data sources) without rewriting what exists. Section 4 defines the module boundaries; section 8 maps each future feature to the module it lands in.

## 2. The data (measured on 20260908)

Source: **Met Éireann**, the Irish national meteorological service. Dublin Airport synoptic station, hourly. The same dataset is listed on data.gov.ie as "Dublin Airport Hourly Data", licence **Creative Commons Attribution 4.0** — Met Éireann must be credited as the source (verified on data.gov.ie, 20260908).

| Item | Value |
|---|---|
| Files | `data/dublin_airport-meteo-1946-2026-data.csv` (63.6 MB, 12.1 MB gzipped) and `data/dublin_airport-meteo-1946-2026-info.txt` (column legend, station metadata). Both are **untracked in git** today; decision 1 commits the CSV gzipped and the info file. |
| Rows | 706,369 data rows, one per hour. Date format `dd-mon-yyyy HH:MM`, UTC. |
| Span | 1946-01-01 00:00 → 2026-08-01 00:00 |
| Regularity | Exactly one row per hour: 0 gaps, 0 duplicates, strictly chronological, no ragged rows. 80 complete years (1946–2025) plus a partial 2026 (5,089 hours, to 1 Aug). |
| Columns | 21: `date`, 15 variables, 5 indicator columns **all named `ind`** (duplicate header names; a generic "CSV to objects" parser would collapse them). |
| Missing values | Empty cells, negligible: vis 255, clht 24, clamt 24, vappr / rhum / wddir 1 each. |
| Sentinels | `clht` 999 = no cloud ceiling (not a height). `ind` = 111 in ~287k early rows (indicator not available). `wddir` 0 = calm, 360 = north. |

Variables and their global range over the whole series (this is what fixes the per-variable scale). The 13 numeric ones are the ones the app exposes (decision 3); `ww` and `w` are kept here for the record.

| Column | Meaning | Unit | Global min..max | In the app |
|---|---|---|---|---|
| rain | precipitation amount | mm per hour | 0 .. 26.5 | yes |
| temp | air temperature | °C | -11.5 .. 29.1 | yes |
| wetb | wet bulb temperature | °C | -11.5 .. 22.6 | yes |
| dewpt | dew point temperature | °C | -17.7 .. 20.5 | yes |
| vappr | vapour pressure | hPa | 2.2 .. 24.2 | yes |
| rhum | relative humidity | % | 19 .. 100 | yes |
| msl | mean sea level pressure | hPa | 944.1 .. 1048.7 | yes |
| wdsp | mean wind speed | knot | 0 .. 46 | yes |
| wddir | predominant wind direction | degree | 0 .. 360 | yes |
| sun | sunshine duration | hours per hour | 0 .. 1 | yes |
| vis | visibility | m | 5 .. 75,000 | yes |
| clht | cloud ceiling height | 100s of ft | 0 .. 999 (999 = none) | yes |
| clamt | cloud amount | okta | 0 .. 8, 9 = sky obscured | yes |
| ww / w | present / past weather | SYNOP code | 0 .. 99, categorical | no |

Consequence of the perfect regularity: row index = hours since 1946-01-01 00:00 UTC, and every year is one contiguous block. Slicing per year needs no index and no date parsing at runtime; a chunk only needs its start timestamp and its hour count.

## 3. Storage and lazy loading

The whole CSV is 63.6 MB (12 MB gzipped) and would be ~45 MB of typed arrays in memory. The app only ever needs one year, so the data is split once, ahead of time, and fetched per year. Options considered:

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. One file per year — chosen** | A script splits the CSV once into `public/data/years/<year>.json` (columnar: one array per variable, `null` = missing) plus `public/data/meta.json` (years, units, labels, global min/max). The app does one `fetch` per year. | ~600 KB per year (~100 KB gzipped), parsed in a few ms. Plain `fetch`, no library, works on any static host, readable in devtools. On a data refresh only the current year's file changes. | One-off preprocessing step; 81 generated files. |
| A′. Same, binary | `<year>.f32`: Float32 columns back to back, `NaN` = missing. | 513 KB per year, zero parse cost (`new Float32Array(buffer)`). | Opaque in devtools; needs a documented layout. |
| B. One binary file per variable + HTTP Range requests | `temp.f32` is 2.8 MB for all 80 years; a year is one byte range computed from the hour offset. | No per-year files; smallest transfer (34 KB per year per variable). Elegant given the regular grid. | Relies on the server honouring `Range` (Vite dev server and GitHub Pages do; `python -m http.server` does not). Harder to inspect. |
| C. Parquet / Arrow + DuckDB-WASM (or arrow-js, parquet-wasm) | SQL or Arrow tables in the browser over a columnar file. | Real analytics later (aggregates, joins, filters). | 10 MB+ of WASM to download, worker setup, Range support needed. Far beyond "show one year". |
| D. Load the whole CSV in the browser | PapaParse or d3-dsv in a Web Worker. | No preprocessing. | 12 MB download and seconds of parsing on every load; ~45 MB resident. |

Measured on 1990 (8,760 hours, 15 variables; the 13-variable chunks will be slightly smaller):

| Format | Size | gzipped |
|---|---|---|
| CSV slice, 21 columns | 741 KB | 155 KB |
| JSON columnar, 15 variables | 638 KB | 101 KB |
| Float32 binary, 15 variables | 513 KB | 105 KB |
| JSON, one variable (temp) | 39 KB | 10 KB |
| Float32, one variable (temp) | 34 KB | 12 KB |

Option A is the smallest thing that gives lazy loading. Moving to A′, to per-variable files, or to B later changes the preprocessing script and the one `DataSource` implementation (section 4), not the app. C is worth revisiting only if this grows into an analysis tool.

Chunk schema (decision 1: chunks are committed to git):

```
public/data/meta.json
{ "station": { "name": "DUBLIN AIRPORT", "height_m": 71, "lat": 53.428, "lon": -6.241 },
  "source":  { "provider": "Met Éireann", "licence": "CC BY 4.0" },
  "years":   [ { "year": 1946, "start": "1946-01-01T00:00:00Z", "hours": 8760 }, … ],
  "variables": [ { "key": "temp", "label": "Air temperature", "unit": "°C",
                   "min": -11.5, "max": 29.1, "decimals": 1 }, … ] }

public/data/years/1990.json
{ "year": 1990, "start": "1990-01-01T00:00:00Z", "hours": 8760,
  "columns": { "temp": [7.8, 7.2, …], "rain": […], … } }      // null = missing
```

Chunks hold the 13 numeric variables, values as in the source (`clht` 999 stays 999; the model layer turns sentinels into gaps, so the chunk stays a faithful copy of the data). No per-row timestamps: the grid is regular, `start + i × 3600 s` reconstructs them. The script writes deterministic output (sorted keys, fixed number formatting) so a re-run does not churn git. Working tree cost: ~50 MB over 81 files; git packs them with zlib, so the repository grows by roughly the gzipped size (estimate, to be confirmed at the first commit). The original CSV is committed gzipped (`data/dublin_airport-meteo-1946-2026-data.csv.gz`, 12.1 MB) with the info file; the uncompressed CSV is git-ignored, and the script reads the gzipped file directly.

## 4. Architecture

Stack:

- Vite + vanilla TypeScript (`npm create vite@latest -- --template vanilla-ts`), no UI framework. One language at runtime: the browser runs TypeScript only.
- Chart library: Apache ECharts 6 behind an adapter (section 5), imported from `echarts/core` with only the needed components; `useUTC: true` so the time axis shows UTC.
- Preprocessing: `scripts/split-years.ts`, TypeScript run directly by Node 26 (native type stripping: erasable syntax only, explicit `.ts` import extensions), no dependencies beyond Node's `fs`, `zlib` and `readline`. It streams the gzipped CSV. Offline tooling, run once per data refresh; not part of the runtime. Python is not used for now (see the language boundary at the end of this section).

Principles (modular without a framework):

- **Four layers, each a directory with one small interface.** Data source → model (pure transforms) → chart adapter → app (state + controls). Dependencies point one way; only `main.ts` knows all four.
- **The state is already plural.** `AppState = { years: number[]; variables: VarKey[]; xRange?: [number, number] }`. The POC controls put exactly one year and one variable in it; the model and the adapter already handle N series. Overlays later are a controls change, not a model change.
- **The chart library touches one file.** Everything the app needs from a chart is a `ChartView` (series, axes, ranges). Swapping the library means writing one new adapter. Honest caveat: interaction UX (zoom, pan) differs per library, so the adapter limits the blast radius of a wrong choice; it does not make the choice free. Pick the library for the roadmap (section 5).
- **Variables are data, not code.** Label, unit, decimals, global range, sentinel and optional manual range override live in `meta.json` plus a small registry; adding a variable is a metadata change.
- **Sentinels and gaps are handled in the model**, never in the chunks or the adapter.
- **No plugin system, no dependency injection, no event bus.** Modules and interfaces are the extension mechanism; the interfaces stay at three or four members.

Replaceable blocks, and what keeps the rest working when one is swapped:

| Block | Replace it with | Contract that protects the rest |
|---|---|---|
| Data source (`data/json-year-source.ts`) | Range-request source, DuckDB-WASM, a live API, an in-memory synthetic source | `DataSource` interface; the model only ever sees `Meta` and `YearData` |
| Chart library (`chart/echarts.ts`) | Any of the libraries in section 5 | `ChartAdapter` + `ChartView`; the app never imports the library directly |
| Model transforms (`model/*.ts`) | New transforms (aggregation, overlays) added beside the existing ones | Pure functions from `YearData` to `Series[]`; no I/O, no DOM |
| Controls (`app/controls.ts`) | Multi-select, range slider, URL-driven state | They only write `AppState`; nothing reads the DOM elsewhere |
| Preprocessing (`scripts/split-years.ts`) | A Python/pandas version (language boundary below), another chunking (A′, B) | The chunk schema in section 3 and `meta.json` |

The guarantees are enforced, not promised: `tsc --noEmit` runs in `npm run build`, so a replacement that does not honour an interface fails to compile; each interface has at most four members, so a second implementation is cheap; and the second implementation of `DataSource` exists from day one as a ~20-line synthetic in-memory source used during development, which is what proves the seam is real rather than assumed.

Interfaces (sketch, the final shape may differ in detail):

```ts
// src/data/source.ts
interface DataSource { meta(): Promise<Meta>; year(year: number): Promise<YearData>; }

// src/chart/adapter.ts — the only contract with a chart library
interface Series   { id: string; label: string; unit: string; scale: string; x: Float64Array; y: Float64Array; } // NaN = gap
interface Axis     { scale: string; label: string; range: [number, number]; side: 'left' | 'right'; }
interface ChartView { xKind: 'time' | 'dayOfYear'; xRange: [number, number]; yAxes: Axis[]; series: Series[]; }
interface ChartAdapter { render(view: ChartView): void; destroy(): void; }
```

Files:

```
index.html                    controls + chart container
src/main.ts                   composition root: state → source → model → adapter
src/app/state.ts              AppState + change notification
src/app/controls.ts           year <input list> + variable <select> → state
src/data/types.ts             Meta, YearData, VarKey
src/data/source.ts            DataSource interface
src/data/json-year-source.ts  per-year JSON implementation + Map cache
src/model/series.ts           (years × variables) → Series[]; sentinels → gaps; later overlays, ranges, aggregates
src/model/scales.ts           fixed y-range per variable: global min/max rounded outward, manual overrides
src/chart/adapter.ts          ChartAdapter, ChartView, Series, Axis
src/chart/echarts.ts          the one library-specific file (ECharts adapter)
scripts/split-years.ts        CSV.gz → public/data/meta.json + public/data/years/<year>.json (Node 26, no dependencies)
data/*.csv.gz, data/*-info.txt original data, committed; the uncompressed CSV is git-ignored
public/data/                  committed chunks
README.md                     run, regenerate data, Met Éireann attribution
```

Behaviour of the POC:

- Year control: `<input list="years">` + `<datalist>` (Chrome's native autocomplete), populated from `meta.json`. An unknown year is ignored.
- Variable control: `<select>`, populated from `meta.json`, 13 entries.
- Chart: one line, hourly points (8,760–8,784 per year), time x-axis in UTC always spanning 1 Jan → 31 Dec of the selected year. A partial year shows an empty remainder, so incompleteness is visible. Hover shows timestamp and value.
- Scale: y-range per variable = global [min, max] from `meta.json`, rounded outward to a round step (temp → -15..30 °C, msl → 940..1050 hPa). Same variable ⇒ same axis on every year; changing the variable ⇒ axis and unit change. A manual override per variable is possible in the registry.
- Missing cells and `clht` 999 → gap in the line.
- Fetches use relative paths and Vite's `base`, so the later GitHub Pages deployment is a config change (decision 5).
- Loading and error states: a one-line status under the controls (loading a year, failed to load, unknown year). No spinner library.
- Footer: "Data: Met Éireann, Dublin Airport hourly observations, CC BY 4.0".

### Language boundary

Rule: the split between build-time and runtime code is by **when the logic runs**, not by subject.

| Question about a piece of logic | Where it goes |
|---|---|
| Needs the whole series or many years, runs once per data refresh | Build time: a script producing static files under `public/data/` |
| Depends on parameters chosen at runtime | Runtime: TypeScript on the slice already in memory |
| Both, and the parameter space is small | Build time, precompute every case (for example normals for one reference period) |
| Both, and the parameter space is large | Neither today; a backend or DuckDB-WASM later, behind `DataSource` |

Current decision (20260908): **TypeScript only, at build time and at runtime.** The chunking script is TypeScript run by Node. Python enters only when a build-time task needs pandas/NumPy-class tooling (heavy aggregation, statistics), and it never runs at runtime for this app: a backend breaks "runs directly in the browser" and the GitHub Pages plan, and Pyodide costs a multi-megabyte download before the first chart. Build-time code emits facts about the data (ranges, counts); runtime code decides presentation (rounding, gaps).

Drift control between build-time and runtime code, whatever the language: the chunk schema and `meta.json` (section 3) are the contract, mirrored by a TypeScript type; the script checks the data invariants when it runs (one row per hour, no gaps, 13 columns, value ranges); the JSON data source validates the shape at load and fails with a clear message. A fixture test on one real chunk comes with the first automated tests.

## 5. Chart library: ECharts (decided 20260908)

Criteria, from the roadmap: pan/zoom, range selection, overlaying two years (several series on a common "day of year" x-axis) and two variables (two y-axes), performance at 8,760 × N points, bundle size, TypeScript types, and how much custom code each future feature costs. Versions and sizes verified on npm and bundlephobia on 20260908; "not measured" marks figures not checked.

| Library | Version · size (min / gzip) | Zoom and pan | Range selection | Overlay years · two y-axes | Performance at 8,760 × N | Types · docs | Custom code for the roadmap |
|---|---|---|---|---|---|---|---|
| **uPlot** | 1.6.32 · 51 KB / 22 KB | Drag-to-zoom on x and double-click reset built in; wheel zoom and pan via an ~80-line plugin copied from the official demos (not on npm) | Programmatic `setScale`; no slider, an overview mini-chart has to be built | Native multi-series · native multiple scales and axes | Excellent; built for 100k+ points without decimation | Shipped · README, demos, commented `.d.ts`; sparse prose | Moderate: wheel/pan plugin, overview chart, legend toggles (~100–150 lines) |
| **Apache ECharts (chosen)** | 6.1.0 · 1.11 MB / 368 KB full package; smaller with `echarts/core` and only the needed components (not measured; will be measured at scaffold time) | `dataZoom` inside: wheel, pinch, drag, built in | `dataZoom` slider and brush built in | Native · native multiple y-axes, legend toggling | Good; `sampling: 'lttb'` for 100k+ points | Shipped (`EChartsOption`) · extensive docs and examples | Minimal: configuration. Also heatmap, calendar, polar, scatter, box plot series if the app grows beyond lines |
| Chart.js | 4.5.1 · 201 KB / 68 KB, plus `chartjs-plugin-zoom` 2.2.0 and a date adapter (not measured) | Official zoom plugin: wheel, pinch, drag, pan | Programmatic min/max; no slider | Native · native multiple y-axes | Fine with the decimation plugin | Shipped · good docs, very popular | Low to moderate; the time axis needs an adapter package (date-fns or luxon) |
| Plotly.js | 4.1.0 · basic bundle 1.14 MB / 376 KB; full bundle with WebGL traces larger (not measured) | Modebar zoom and pan built in | Range slider and range selector built in | Native · `yaxis2` | SVG traces slow beyond ~10–20k points; `scattergl` needs the bigger bundle | Types in the v4 `dist` package per npm metadata, none in the basic bundle · extensive docs | Minimal; familiar if you use Plotly in Python |

Also considered, not shortlisted: D3 (everything hand-written), Observable Plot (no built-in zoom/pan), Vega-Lite (declarative, needs the full Vega runtime), Lightweight Charts (finance-oriented time scale).

**Decision: ECharts.** Every item on the roadmap is a configuration option rather than code, the types are shipped, the project is active, and it keeps the door open to non-line views (heatmap of hour × day, wind rose) that a weather analysis app tends to grow into. Its real costs: the largest working bundle of the shortlist after Plotly (irrelevant for a local app and acceptable for GitHub Pages), a large option-object API that the type checker cannot validate deeply, and slower rendering than uPlot when tens of thousands of points are on screen (mitigated by sampling).

**Alternative: uPlot** if bundle size and raw speed matter more than built-in features — for example if the roadmap includes overlaying many years at once (80 × 8,760 = 700k points). Cost: the interaction features are written by us, and the library stays line-oriented.

In the v1 plan uPlot was recommended; the roadmap (pan/zoom, range, overlays, more views) changes the weighting.

## 6. Steps

1. Extend `.gitignore` (the current one is a Python template): `node_modules/`, `dist/`, `.DS_Store`, `data/*.csv`. Scaffold Vite vanilla-ts, add ECharts (`echarts/core` plus line chart, grid, tooltip, legend, dataZoom, canvas renderer), commit with the lockfile. Record the measured bundle size in the README.
2. Commit `data/*.csv.gz` (gzip of the original, 12.1 MB) and the info file. `scripts/split-years.ts`: stream the gzipped CSV, drop the five `ind` columns and `ww`/`w`, check the invariants, write `meta.json` and the 81 year chunks deterministically; run it once; commit script and chunks.
3. Data layer (`DataSource` + JSON implementation + cache), model (`series`, `scales`), chart adapter, state and controls, composition in `main.ts`.
4. Manual check in Chrome: years 1946, 1990, 2026 (partial); every variable; same axis across years for one variable; gaps for missing values and `clht` 999.
5. README: run (`npm install && npm run dev`), data refresh procedure (replace the `.csv.gz`, run `node scripts/split-years.ts --csv data/<file>.csv.gz --out public/data`, commit the changed chunks), attribution, module map.

Expected size: 300–400 lines of TypeScript for the app plus ~120 for the script.

## 7. Out of scope for the POC

Overlaying two years or two variables, zoom and pan, day/month ranges, daily or monthly aggregation, the indicator columns, SYNOP code legends, deployment, automated tests. The structure is prepared for them (section 8); the features are not built.

## 8. Extension roadmap — where each future feature lands

| Future feature | Module that changes | What stays untouched |
|---|---|---|
| Pan / zoom | `chart/echarts.ts` (enable `dataZoom`), `app/state.ts` (`xRange`) | data, model |
| Range selection (sub-period of a year) | `app/controls.ts` (range input), `model/series.ts` (slice) | data, adapter |
| Overlay two years | `app/controls.ts` (multi-select), `model/series.ts` (`xKind: 'dayOfYear'`, one series per year) | data, adapter |
| Overlay two variables | `app/controls.ts`, `model/scales.ts` (second axis, `side: 'right'`) | data, adapter |
| Daily / monthly aggregation | `model/series.ts` (aggregate before building series) | data, adapter, controls |
| Another data source (Range requests, DuckDB, live API) | new `data/<source>.ts` implementing `DataSource` | model, adapter, app |
| Another chart library | new `chart/<library>.ts` implementing `ChartAdapter` | data, model, app |
| Heavy whole-series analysis (normals, records, anomalies) | a build-time script writing new static files (Python when pandas-class tooling pays off, per the language boundary); `DataSource` gains a method to read them | model, adapter, controls |
| GitHub Pages | `vite.config.ts` `base`, a deploy workflow | everything else |
| Sharable state (URL hash `#years=1990&vars=temp`) | `app/state.ts` | everything else |

## 9. Decisions (20260908)

| # | Question | Decision | Alternatives kept on record |
|---|---|---|---|
| 1 | Data in git | **Commit the per-year chunks** (`public/data/`) **and the original CSV gzipped** (`data/*.csv.gz`, 12.1 MB) with the info file; the uncompressed CSV is git-ignored. | Chunks only, raw CSV kept out of git; raw CSV committed and chunks rebuilt at build time instead of committed; all data out of git. |
| 2 | Chart library | **ECharts** (section 5). | uPlot, Chart.js, Plotly.js as tabled. |
| 3 | Variables | **The 13 numeric ones.** `ww` and `w` are excluded from the dropdown and from the chunks (regenerating with them is one command). | All 15. |
| 4 | Preprocessing | **TypeScript run by Node 26** (`scripts/split-years.ts`): TypeScript only for now, at build time and at runtime. | Python 3 stdlib script (the v2 choice); Python enters later under the language-boundary rule. |
| 5 | Hosting | **Local `npm run dev` now, GitHub Pages later**; relative paths and Vite `base` prepared for it. | — |
| 6 | Architecture | **Modular**: four layers with small interfaces, plural state, chart library behind an adapter (section 4). | A flat single-file POC (rejected: the roadmap is explicit). |
| 7 | Language boundary | **Rule recorded in section 4; TypeScript only for now.** | Python for build-time whole-series work when it pays off; never at runtime for this app. |

Nothing is open. Implementation starts on the explicit go-ahead, on a fresh branch from `main` once this plan is merged.

Defaults I will apply unless you object: UTC on the axis; gaps for missing values; full Jan–Dec axis for a partial year; automatic global min/max scale rounded outward; npm as package manager.
