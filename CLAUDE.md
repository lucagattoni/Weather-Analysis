# Weather-Analysis

Browser app in TypeScript that visualises the Met Éireann Dublin Airport hourly weather series (1946 onwards). Plan, decisions and module layout: `plans/20260908_2031-weather-viewer-poc-plan.md` (referenced below as "the plan").

## Scope and process

- Minimal POC, no over-engineering: build only what the approved plan says. The structure is prepared for the roadmap (plan §8); a roadmap feature is not built until asked.
- Do not assume: when a choice is the user's, present the options with honest pros and cons and a marked recommendation, then wait. The user has the last word.
- Every change happens on a branch named `YYYYMMDD_HHMM-<name>` (UTC) in a git worktree, never in the primary checkout. Commit and push after each step that works, not at the end.
- Multi-step work in progress keeps a `RESUME.md` at the repo root (state, exact next command); read it first if it exists, keep it current, delete it when the work lands.
- A plan is written, reviewed and approved before implementation. Plans live in `plans/` as `YYYYMMDD_HHMM-<name>.md` (UTC). When a decision lands in a plan, keep the original alternatives on record. Before calling a plan ready, state what is still missing.

## Architecture (plan §4)

- Modular by construction: four layers, data source → model → chart adapter → app state and controls, each behind an interface of at most four members. Any block must be replaceable without touching the others; dependencies point one way; only `src/main.ts` knows all four.
- The chart library is imported only inside `src/chart/`; everything else uses `ChartAdapter` and `ChartView`.
- App state is plural (`years[]`, `variables[]`) even while the UI allows one of each.
- Variables are data (`public/data/meta.json` plus a small registry), not code. Sentinels and missing values become gaps in the model, never in the chunks or the adapter.
- Contracts are enforced, not promised: `tsc --noEmit` runs in `npm run build`.
- The y-scale of a variable is fixed across years (global range from `meta.json`, rounded outward) so years are comparable; changing the variable changes the scale. A sentinel is excluded from that range: it is a real observation but not a measurement on the scale (`clht` 999 = no ceiling), so including it would leave the axis mostly empty.

## Languages

- TypeScript in the browser, always: everything under `src/` (erasable syntax only, explicit `.ts` import extensions).
- Python for build-time preprocessing and offline analysis only, run by `uv run` with dependencies pinned in the sibling `.lock`. Preprocessing that feeds the app lives in `scripts/*.py`; analysis that feeds only the EDA documents lives in `EDA/scripts/*.py`. Decided 20260908; supersedes plan decision 4.
- Language boundary (plan §4): build-time code does whole-series, run-once work and emits facts as static files under `public/data/`; runtime code does interaction-dependent work on the slice in memory and decides presentation. Python never runs at runtime.

## Runtime and hosting

- Runs directly in the browser, Chrome as reference. Static hosting only: no backend, and every fetch built from `import.meta.env.BASE_URL`.
- Live at <https://lucagattoni.github.io/Weather-Analysis/>, deployed by `.github/workflows/pages.yml` on every push to `main`. The sub-path appears only in `vite.config.ts`.
- **Checking a deploy: HTTP 200 is not proof.** A sub-path build served at the root answers every data request with `index.html`, at 200. Assert content type and byte size, never status alone. This bit once: `vite preview` runs with `command === 'serve'`, so a `base` keyed only on `build` made preview rehearse the wrong site, and `meta.json` and `1990.json` both "passed" at 3,184 bytes each, which is the size of `index.html`.

## Data

- Source: Met Éireann, Dublin Airport hourly observations, licence CC BY 4.0. Credit it in the app footer and in the README.
- Lazy-load one year at a time from `public/data/years/<year>.json`; never load the whole series. Chunks and `meta.json` are committed; their schema (plan §3) is the contract between the chunking script and the app.
- `data/*.csv.gz` and the info file are committed; the uncompressed CSV is git-ignored. Regenerate with `uv run scripts/split_years.py --csv data/<file>.csv.gz --out public/data`; output must be deterministic so a re-run does not churn git.

## Analysis (`EDA/`)

- Exploratory analysis of the source series lives in `EDA/`, self-contained: `EDA/scripts/` generates `EDA/figures/` and `EDA/stats/`, which the numbered markdown documents embed. Regenerate with `uv run EDA/scripts/eda_report.py --section {review|temperature|precipitation|all}`; output must be deterministic.
- Prose is written by hand, never generated; every number a document quotes must exist in an `EDA/stats/*.csv` so drift shows up as a git diff.
- Read `EDA/01-data-review.md` §10 before trusting any statistic that crosses September 1993: the station changed observation practice there and it moves eleven of thirteen variables.
