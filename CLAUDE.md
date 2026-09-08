# Weather-Analysis

Browser app in TypeScript that visualises the Met Éireann Dublin Airport hourly weather series (1946 onwards). Plan, decisions and module layout: `plans/20260908_2031-weather-viewer-poc-plan.md` (referenced below as "the plan").

## Scope and process

- Minimal POC, no over-engineering: build only what the approved plan says. The structure is prepared for the roadmap (plan §8); a roadmap feature is not built until asked.
- Do not assume: when a choice is the user's, present the options with honest pros and cons and a marked recommendation, then wait. The user has the last word.
- A plan is written, reviewed and approved before implementation. Plans live in `plans/` as `YYYYMMDD_HHMM-<name>.md` (UTC). When a decision lands in a plan, keep the original alternatives on record. Before calling a plan ready, state what is still missing.

## Architecture (plan §4)

- Modular by construction: four layers, data source → model → chart adapter → app state and controls, each behind an interface of at most four members. Any block must be replaceable without touching the others; dependencies point one way; only `src/main.ts` knows all four.
- The chart library is imported only inside `src/chart/`; everything else uses `ChartAdapter` and `ChartView`.
- App state is plural (`years[]`, `variables[]`) even while the UI allows one of each.
- Variables are data (`public/data/meta.json` plus a small registry), not code. Sentinels and missing values become gaps in the model, never in the chunks or the adapter.
- Contracts are enforced, not promised: `tsc --noEmit` runs in `npm run build`.
- The y-scale of a variable is fixed across years (global range from `meta.json`, rounded outward) so years are comparable; changing the variable changes the scale.

## Languages

- TypeScript only for now, at runtime and in build-time scripts (`scripts/*.ts`, run directly by Node 26: erasable syntax only, explicit `.ts` import extensions). One language in the browser, always.
- Language boundary (plan §4): build-time code does whole-series, run-once work and emits facts as static files under `public/data/`; runtime code does interaction-dependent work on the slice in memory and decides presentation. Python enters only for build-time work that needs pandas-class tooling, never at runtime.

## Runtime and hosting

- Runs directly in the browser, Chrome as reference. Static hosting only, local `npm run dev` now and GitHub Pages later: no backend, relative fetch paths, Vite `base` for deployment.

## Data

- Source: Met Éireann, Dublin Airport hourly observations, licence CC BY 4.0. Credit it in the app footer and in the README.
- Lazy-load one year at a time from `public/data/years/<year>.json`; never load the whole series. Chunks and `meta.json` are committed; their schema (plan §3) is the contract between the chunking script and the app.
- `data/*.csv.gz` and the info file are committed; the uncompressed CSV is git-ignored. Regenerate with `node scripts/split-years.ts --csv data/<file>.csv.gz --out public/data`; output must be deterministic so a re-run does not churn git.
