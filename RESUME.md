# RESUME: implementing the weather viewer POC

Updated 20260908 21:13 UTC. Read `CLAUDE.md` and the plan first, then this file. Remove this file when the POC lands.

## State

- Plan v3 is approved and on `main`: `plans/20260908_2031-weather-viewer-poc-plan.md`. The development guidelines are in `CLAUDE.md`. Both were reviewed in the planning session on 20260908.
- No application code exists yet. The repo holds `.gitignore` (a Python template), `LICENSE`, `CLAUDE.md`, `plans/` and this file.
- The source data is **untracked** in the primary checkout's `data/` directory: `dublin_airport-meteo-1946-2026-data.csv` (63.6 MB) and `dublin_airport-meteo-1946-2026-info.txt`. A worktree does not contain them. Never run `git clean` in the primary checkout. Step 2 below gzips the CSV into the worktree and commits it.
- The data analysis in plan §2 (one row per hour, no gaps, 2026 partial with 5,089 hours, five `ind` columns, value ranges) was measured with a throwaway script that is not in the repo; the chunking script must re-check those invariants when it runs.

## Confirm with the user before step 2

Two readings of the user's decisions were assumed, not explicitly confirmed:

1. "TypeScript only for now" includes the chunking script (`scripts/split-years.ts`, run by Node 26), not only the browser code.
2. "Gzipped original one" means `data/*.csv.gz` is committed alongside the chunks and the info file, with the uncompressed CSV git-ignored.

If the user already confirmed them in a later session, delete this section.

## Next steps, in order (plan §6)

Process: create a worktree on a new branch from `main` named `$(date -u +%Y%m%d_%H%M)-poc-implementation`; commit and push after each step; update this file at each step.

1. Extend `.gitignore` with `node_modules/`, `dist/`, `.DS_Store`, `data/*.csv`. Scaffold with `npm create vite@latest . -- --template vanilla-ts`, add ECharts (`npm install echarts`), import from `echarts/core` with only line chart, grid, tooltip, legend, dataZoom and the canvas renderer. Check that `npm run build` type-checks (the template's build script is expected to run `tsc` before `vite build`; verify). Record the measured bundle size in the README. Commit with the lockfile.
2. Copy the info file and a gzip of the CSV into the worktree's `data/`, commit them. Write `scripts/split-years.ts` (Node 26, no dependencies: `fs`, `zlib`, `readline`): stream the gzipped CSV, drop the five `ind` columns and `ww`/`w`, check the invariants, write `public/data/meta.json` and `public/data/years/<year>.json` deterministically per the schema in plan §3. Run it, verify 81 chunk files, 2026 with 5,089 hours, and `meta.json` ranges equal to the plan §2 table. Commit script and chunks.
3. Implement the layers per the file list in plan §4: `src/data` (types, `DataSource`, JSON source with cache, a ~20-line synthetic in-memory source), `src/model` (series with sentinels to gaps, fixed scales rounded outward), `src/chart` (adapter types, ECharts adapter with `useUTC: true`), `src/app` (plural state, year datalist, variable select, one-line status), `src/main.ts`.
4. Manual check in Chrome: years 1946, 1990, 2026; all 13 variables; same axis across years for one variable; gaps for missing values and `clht` 999; the partial year shows an empty remainder.
5. README: run, data refresh procedure, Met Éireann CC BY 4.0 attribution, module map. Then merge to `main`, remove the worktree, delete the branch, and delete this file.

## Commands

```
npm install && npm run dev
node scripts/split-years.ts --csv data/dublin_airport-meteo-1946-2026-data.csv.gz --out public/data
npm run build
```
