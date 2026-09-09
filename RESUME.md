# RESUME: handover

Updated 20260909 08:04 UTC. Read `CLAUDE.md` first, then this. Delete this file
when the open decision below is settled and nothing is left in flight.

## Where things stand

Nothing is in flight. `main` is clean, pushed, and deployed. There is no
half-finished branch and no uncommitted work.

- **Live:** <https://lucagattoni.github.io/Weather-Analysis/>, redeployed by
  `.github/workflows/pages.yml` on every push to `main`. Verified anonymously:
  the page and the JSON chunks all serve, http redirects to https.
- **Built:** the POC, then zoom and pan, then multi-year comparison on a shared
  Jan–Dec axis with the decade/shade/dash encoding, a two-knob year slider plus
  chips, a detail slider from 1 h to 7 days, and an opacity slider.
- **Analysis:** `EDA/` holds three documents with every figure and every number
  behind them. It is linked from the README and from the app footer.

## Read these before changing anything

| File | Why |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | The rules. Short. |
| [`plans/20260908_2031-weather-viewer-poc-plan.md`](plans/20260908_2031-weather-viewer-poc-plan.md) **§10** | Seven amendments to the POC plan. Sections 1–9 are as approved and some of their commands are stale. |
| [`plans/20260908_2230-multi-year-comparison-plan.md`](plans/20260908_2230-multi-year-comparison-plan.md) **§8, §12** | The three decisions taken, and the eight places the build differed from the plan. |
| [`EDA/01-data-review.md`](EDA/01-data-review.md) **§10** | The data-quality register. Read before trusting any statistic crossing September 1993. |

## The one open decision

The user asked which other chart form would best compare years. I measured four
against this data and recommended the first; **no choice has been made yet**, so
do not start building one.

| Form | What it buys, measured |
|---|---|
| **Anomaly** (recommended) | Subtracting the day-of-year normal halves the axis, 45 °C to 22 °C, so the same between-year difference fills twice the plot height. Cheapest to build: a build-time normal plus a subtraction in the model. |
| Heatmap, years down and day-of-year across | 80 × 365 cells at 3.5 × 7.5 px. No occlusion at all, and the only form that shows the +0.43 °C between the first and last 30 years, which is 1% of the current axis. |
| Envelope, percentile band with years on top | The 10–90 band is 6.0 °C wide; 2025 spent 80 of 365 days outside it. |
| Cumulative totals | Rain and sunshine only. Annual rainfall spans 555–1095 mm and the curves are 350 mm apart by 1 July, so they rarely cross. |

If the user picks one, the project convention is a plan in `plans/` reviewed and
approved before any code.

## Things that will bite

- **A green CI run is not proof the site shipped.** See the deploy bullet in
  `CLAUDE.md`; a sub-path build served at the root returns 200 for everything.
- **The app applies no correction for the September 1993 observation change**,
  which moves eleven of thirteen variables. That is deliberate and stated in the
  footer, but it means a line spanning 1993 crosses a discontinuity.
- **Sentinels are not missing data.** `clht` 999 is "no ceiling", `clamt` 9 is
  "sky obscured", `wddir` 0 is calm and not north. All three are excluded from a
  variable's range and from its aggregate, and drawn as gaps.
- **Aggregation is per variable.** Rain and sunshine sum, wind direction takes a
  circular mean, the other ten take a mean. It is a field in `meta.json`.
- **Resampling past a day pulls years together.** The spread across twenty years
  falls from 10.7 °C hourly to 6.4 °C weekly. Coarser steps buy traceable lines
  and cost some of the difference being looked for. Both halves are in the README.
- **The 1940s and the 2020s share a hue.** Nine decades, eight hues; decision A.
- Every change goes on a `YYYYMMDD_HHMM-<name>` branch in a git worktree, never
  in the primary checkout.

## Commands

```
npm install && npm run dev            # http://localhost:5173/
npm run build                         # tsc, then vite build
npm run preview                       # serves the build at /Weather-Analysis/
uv run scripts/split_years.py --csv data/dublin_airport-meteo-1946-2026-data.csv.gz --out public/data
uv run EDA/scripts/eda_report.py --section all
gh run list --workflow=pages.yml --limit 3
```

Both generators are deterministic: a re-run with unchanged input produces
byte-identical output, so a real change shows up as a git diff.
