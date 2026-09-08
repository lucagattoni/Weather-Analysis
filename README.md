# Dublin Airport hourly weather

A single-page browser app that plots one variable for one year of the Met Éireann
Dublin Airport hourly observation series, 1946 to 2026. The y-scale is fixed per
variable, so the same variable looks the same on every year and years can be
compared by eye.

Data: **Met Éireann**, Dublin Airport hourly observations, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Run it

```
npm install
npm run dev          # http://localhost:5173/
npm run build        # runs tsc, then vite build
```

`npm run build` type-checks before it bundles, so the interfaces below are
enforced rather than promised. Production bundle: **554 kB, 187 kB gzipped**
(the full ECharts package is 1.11 MB, 368 kB gzipped; only the line chart, grid,
tooltip, legend, dataZoom and canvas renderer are registered).

## What it does

- **Year** is an autocomplete over the 81 years present. An unknown year is
  ignored and says so.
- **Variable** is a dropdown over the 13 numeric variables. The two SYNOP code
  columns (`ww`, `w`) are categorical and excluded.
- The x-axis always spans a whole calendar year in UTC, so 2026 (partial, to
  1 August) shows an empty remainder rather than stretching to fill the width.
- Missing readings and sentinels break the line rather than plotting as zero.
- The status line reports how many hours were drawn and how many are gaps.

## How the data is prepared

The source CSV is 63.6 MB, so it is split once, ahead of time, into one JSON
chunk per year that the app fetches lazily. Chunks are committed.

```
uv run scripts/split_years.py \
  --csv data/dublin_airport-meteo-1946-2026-data.csv.gz \
  --out public/data
```

To refresh the data: replace `data/*.csv.gz` (keep it gzipped with `gzip -9 -n`,
so the archive itself is reproducible), re-run the command above, and commit the
chunks that changed. The script is deterministic, so an unchanged year produces a
byte-identical file and does not appear in the diff.

The script drops the five duplicate `ind` columns and the SYNOP codes, checks the
source invariants on every run, and fails loudly rather than writing a bad chunk.
It is the one piece of Python in the project: it is build-time work, run once per
refresh, and nothing it does reaches the browser.

### What the source data actually looks like

Measured over all 706,369 rows:

| Property | Value |
|---|---|
| Rows | 706,369, exactly one per hour, no gaps and no duplicates |
| Span | 1946-01-01 00:00 to 2026-08-01 00:00 UTC |
| Years | 81: 60 normal, 20 leap, plus 2026 partial at 5,089 hours |
| Missing readings | 306 cells in total, 0.003% |

Three things about the source are easy to get wrong:

- **Missing values are a single space, not an empty field.** `Number(" ")` is `0`
  in JavaScript, so a naive parse records 255 missing visibility readings as 0 m
  rather than as gaps.
- **`clht` 999 means "no cloud ceiling", not a height of 99,900 ft.** It is 26.5%
  of all rows. The real ceiling never exceeds 440, so the sentinel is excluded
  when computing the axis range and shown as a gap in the line.
- **`clamt` 9 means "sky obscured"**, not 9 oktas. One row in the whole series.

Sentinels stay verbatim in the chunks, which are a faithful copy of the source.
Turning them into gaps happens in the model layer, at runtime.

One known characteristic of the source, left as is: dew point exceeds air
temperature in 2,554 rows and wet bulb exceeds it in 11, always by 0.1 to 0.7 °C
and spread evenly across all 80 years. That is independent rounding of separately
derived quantities, not instrument failure.

## Module map

Four layers. Dependencies point one way, and only `src/main.ts` knows all four.

| Path | Responsibility | Replace it with |
|---|---|---|
| `src/data/source.ts` | `DataSource`: `meta()` and `year()` | Range requests, DuckDB-WASM, a live API |
| `src/data/json-year-source.ts` | Fetches and caches one chunk per year | any of the above |
| `src/data/synthetic-source.ts` | A second `DataSource`, in memory | — |
| `src/model/series.ts` | Chunks to drawable series; sentinels to gaps | aggregation, overlays |
| `src/model/scales.ts` | Fixed y-range per variable, rounded outward | manual ranges per variable |
| `src/chart/adapter.ts` | `ChartAdapter` and `ChartView`, the whole contract | — |
| `src/chart/echarts.ts` | The only file that imports a chart library | any charting library |
| `src/app/state.ts` | `AppState`, already plural in years and variables | URL-driven state |
| `src/app/controls.ts` | The only file that reads the DOM | multi-select, range slider |
| `scripts/split_years.py` | Build-time chunking, Python and pandas via uv | another chunk format |

`src/data/synthetic-source.ts` is what keeps the data seam honest: it is a second
implementation of `DataSource` that exists from day one, so swapping the line in
`src/main.ts` runs the whole app with no chunks on disk.

## Layout

```
data/                  source CSV (gzipped, committed) and the station info file
public/data/meta.json  station, years, and per-variable label, unit, range, decimals
public/data/years/     81 chunks, one per year, ~455 KB each
scripts/               build-time preprocessing
src/                   the app, TypeScript only
plans/                 the approved plan and its amendments
```

## Scope

This is a POC. Zoom and pan, range selection, overlaying two years or two
variables, aggregation, tests and deployment are deliberately not built. Section 8
of the plan maps each of them to the one module it would land in.
