# RESUME: handover

Updated 20260912 08:46 UTC. Read `CLAUDE.md` first, then this.

## Where things stand

Nothing is in flight. `main` is clean, pushed and deployed. There is no
half-finished work, no stray worktree and no stray branch.

- **Live:** <https://lucagattoni.github.io/Weather-Analysis/>, redeployed by
  `.github/workflows/pages.yml` on every push to `main`. Verified after the last
  deploy by fetching the site and comparing `sha256` of the served JS and CSS
  against the local `dist/`: identical.
- **Built:** the POC, zoom and pan, multi-year comparison on a shared Jan-Dec
  axis with the decade/shade/dash encoding, a detail slider from 1 h to 7 days,
  an opacity slider, and the year strip described below.
- **Analysed:** `EDA/` holds four documents. Three cover the series; the fourth
  measures four candidate chart forms so the next one can be chosen.

## The decision waiting for you

**Which chart to build next.** The evidence is on disk and finished:
[`EDA/04-chart-forms.md`](EDA/04-chart-forms.md). It measures the four candidates
against the real series, marks a recommendation, and states explicitly that no
choice has been made.

The short version, with the detail and the caveats in the document:

- Overlaid year lines fail on **ordering**, and it is the number of pairs that
  grows rather than the rate: a quarter of days swap at every year count, but
  pairs grow as N(N-1)/2, so expected crossings run from 0.3 a day at two years
  to 111 at thirty.
- Subtracting a day-of-year normal **cannot** change that, because it takes the
  same number off every year on a given day. The document proves it rather than
  asserting it: the swap rate is computed on raw values and on anomalies in one
  table and the columns are identical to three decimals.
- The recommendation is **small multiples**, the cheaper of the two forms that
  remove occlusion outright, with the **heatmap** second and uniquely able to
  carry all eighty years. It is a recommendation, not a decision.

Several figures did not survive re-measurement, including two the analysis itself
had asserted before measuring them. The document records each correction. Do not
quote the old four-form table that used to live in this file.

When a form is chosen, the project convention is a plan in `plans/`, reviewed and
approved, before any code.

## Read these before changing anything

| File | Why |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | The rules. Short. |
| [`EDA/04-chart-forms.md`](EDA/04-chart-forms.md) | The open decision and every number behind it |
| [`plans/20260908_2031-weather-viewer-poc-plan.md`](plans/20260908_2031-weather-viewer-poc-plan.md) **§10** | Seven amendments to the POC plan. Sections 1-9 are as approved and some of their commands are stale. |
| [`plans/20260908_2230-multi-year-comparison-plan.md`](plans/20260908_2230-multi-year-comparison-plan.md) **§8, §12, §13** | The decisions taken, the eight places the build differed, and the 20260909 revision of the year control |
| [`EDA/01-data-review.md`](EDA/01-data-review.md) **§10** | The data-quality register. Read before trusting any statistic crossing September 1993. |

## The year control, rebuilt and reviewed 20260909

The two-knob slider and the "chips only for years outside the range" model are
gone. Both bugs reported against them came from one cause: a range plus a set of
extras has two kinds of member, and a range cannot express "1990 to 2000 without
1995", so the years it contributed were not removable.

The selection is now a plain `Set<number>`; the strip is one tick per year, most
recent on the left. Tap a tick to add or remove, drag across for a span, a chip
removes one, `only <year>` leaves the most recent. The selection can never be
empty and the app opens on the current year. The chips are also the chart's
legend, drawn with each year's real line and dash. Rationale and the alternatives
weighed: `plans/20260908_2230-multi-year-comparison-plan.md` §13.

**It has been adversarially reviewed.** Three reviewers found eleven real issues;
all are fixed, verified in Chrome and deployed. The largest were a zoom window
that came back inverted when it started on 29 February, a phone that could not
scroll the page if the swipe began on the strip, a chip that lost its styling
whenever exactly one year was selected, which is the state the app opens in, and
a shift-arrow sweep that could grow but never shrink.

**The drag is not available on touch.** On a narrow screen the strip is wider
than its track and a horizontal swipe scrolls it, which is how a finger reaches
1946; the browser cancels the pointer when it takes the pan. Tapping adds and
removes everywhere, and the hint under the strip is written from
`(pointer: coarse)` so it only promises the gesture the device has.

## Known wrong and deliberately left

Six commit subjects, `5753811` to `921d08e`, carry timestamps that were composed
rather than read from the clock, and run one to three hours ahead of the commits
they label. The real times are 08:35 to 08:58 UTC on 20260909;
`git log --pretty='%h %cI'` is the record to trust. The history is public and
deployed, so it was not force-pushed. Nothing else takes its dates from those
strings.

## Things that will bite

- **A green CI run is not proof the site shipped.** See the deploy bullet in
  `CLAUDE.md`; a sub-path build served at the root returns 200 for everything.
  When fetching assets to check them, note that the paths inside `index.html`
  already start with `/Weather-Analysis/` - appending one to a base URL that ends
  the same way silently fetches the 404 page, at status 200.
- **An unregistered ECharts component makes its option do nothing, silently.**
  The chart title was configured correctly and never drew until `TitleComponent`
  was added to `echarts.use`. There is no warning. `LegendComponent` and
  `TitleComponent` are both deregistered now, because the chips are the legend
  and the title is HTML.
- **The zoom slider's data shadow is drawn by data index, not by time**, so a
  part-year series fills it to December. It is switched off for that reason.
- **The app applies no correction for the September 1993 observation change**,
  which moves eleven of thirteen variables. Deliberate, and stated in the footer.
- **Sentinels are not missing data.** `clht` 999 is "no ceiling", `clamt` 9 is
  "sky obscured", `wddir` 0 is calm and not north. All three are excluded from a
  variable's range and from its aggregate, and drawn as gaps.
- **Aggregation is per variable.** Rain and sunshine sum, wind direction takes a
  circular mean, the other ten take a mean. It is a field in `meta.json`.
- **Resampling past a day pulls years together.** The spread across twenty years
  falls from 10.7 °C hourly to 6.4 °C weekly. Coarser steps buy traceable lines
  and cost some of the difference being looked for. Both halves are in the README.
- **The 1940s and the 2020s share a hue.** Nine decades, eight hues; decision A.
