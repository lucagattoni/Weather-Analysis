# RESUME: handover

Updated 20260909 11:52 UTC. Read `CLAUDE.md` first, then this. Delete this file
when the open decision below is settled and nothing is left in flight.

## Where things stand

Nothing is in flight. `main` is clean, pushed, and deployed. There is no
half-finished branch and no uncommitted work.

- **Live:** <https://lucagattoni.github.io/Weather-Analysis/>, redeployed by
  `.github/workflows/pages.yml` on every push to `main`. Verified after the last
  deploy by fetching the site and comparing `sha256` of the served JS and CSS
  against the local `dist/`: identical, and `index.html` carries the new markup.
- **Built:** the POC, then zoom and pan, then multi-year comparison on a shared
  Jan–Dec axis with the decade/shade/dash encoding, a detail slider from 1 h to
  7 days, an opacity slider, and the year control described next.
- **Analysis:** `EDA/` holds three documents with every figure and every number
  behind them. It is linked from the README and from the app footer.

## The year control, rebuilt 20260909

The two-knob slider and the "chips only for years outside the range" model are
gone. Both bugs reported against them came from the same place: a range plus a
set of extras has two kinds of member, and a range cannot express "1990 to 2000
without 1995", so the years it contributed were not removable.

The selection is now a plain `Set<number>` and the strip is one tick per year,
most recent on the left. Tap a tick to add or remove that year, drag across for
a span, a chip removes one, `only <year>` leaves the most recent. The selection
can never be empty, and the app opens on the current year. The chips are also
the chart's legend, drawn with each year's real line and dash.

Full rationale, the alternatives weighed, and the gesture table:
`plans/20260908_2230-multi-year-comparison-plan.md` **§13**.

## Read these before changing anything

| File | Why |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | The rules. Short. |
| [`plans/20260908_2031-weather-viewer-poc-plan.md`](plans/20260908_2031-weather-viewer-poc-plan.md) **§10** | Seven amendments to the POC plan. Sections 1–9 are as approved and some of their commands are stale. |
| [`plans/20260908_2230-multi-year-comparison-plan.md`](plans/20260908_2230-multi-year-comparison-plan.md) **§8, §12, §13** | The decisions taken, the eight places the build differed, and the 20260909 revision of the year control. |
| [`EDA/01-data-review.md`](EDA/01-data-review.md) **§10** | The data-quality register. Read before trusting any statistic crossing September 1993. |

## The one open decision

The user asked which other chart form would best compare years. Four were
measured against this data and the first recommended; **no choice has been made
yet**, so do not start building one.

| Form | What it buys, measured |
|---|---|
| **Anomaly** (recommended) | Subtracting the day-of-year normal halves the axis, 45 °C to 22 °C, so the same between-year difference fills twice the plot height. Cheapest to build: a build-time normal plus a subtraction in the model. |
| Heatmap, years down and day-of-year across | 80 × 365 cells at 3.5 × 7.5 px. No occlusion at all, and the only form that shows the +0.43 °C between the first and last 30 years, which is 1% of the current axis. |
| Envelope, percentile band with years on top | The 10–90 band is 6.0 °C wide; 2025 spent 80 of 365 days outside it. |
| Cumulative totals | Rain and sunshine only. Annual rainfall spans 555–1095 mm and the curves are 350 mm apart by 1 July, so they rarely cross. |

If the user picks one, the project convention is a plan in `plans/` reviewed and
approved before any code.

## Not finished

An adversarial review of the 20260909 year-control change was launched and the
session ended before it reported. The change was merged on the user's explicit
instruction and verified by hand in Chrome (dev server, production preview at
the deploy sub-path, and the live site) with a clean console throughout, but no
second pair of eyes has been over it. Worth one Sonnet pass before building on
`src/app/controls.ts`.

## Things that will bite

- **A green CI run is not proof the site shipped.** See the deploy bullet in
  `CLAUDE.md`; a sub-path build served at the root returns 200 for everything.
  When fetching assets to check them, note that the paths inside `index.html`
  already start with `/Weather-Analysis/` — appending one to a base URL that
  ends the same way silently fetches the 404 page, at status 200.
- **An unregistered ECharts component makes its option do nothing, silently.**
  The chart title was configured correctly and simply never drew until
  `TitleComponent` was added to `echarts.use`. There is no warning.
- **The zoom slider's data shadow is drawn by data index, not by time**, so a
  part-year series fills it to December. It is switched off for that reason.
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
