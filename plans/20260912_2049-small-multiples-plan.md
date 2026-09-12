# Small multiples: one panel per selected year

Status: **approved to build, 20260912.** Section 3's decision is taken: **option
B, the panels array**. The user also weighed the "do nothing" option in section 8
against the detail slider that already exists and chose to build. Nothing is
built yet; section 6 is the order of work.

## 1. Goal

Draw each selected year in its own small panel on a shared Jan-Dec x-axis and a
shared fixed y-axis, instead of overlaying every year on one plot. Occlusion goes
away by construction, because no two years share a panel.

The overlay stays. This is a second form the reader can switch to, not a
replacement, which is what "both" in section 2 commits us to.

## 2. What this rests on

`EDA/04-chart-forms.md`, which measured six candidate forms against the real
series. Read it before this. The load-bearing results:

- The failure that matters is **occlusion**, and it scales with the number of
  *pairs* on screen, not with any worsening of the lines. Expected crossings per
  day run 0.28 at two years to 111.00 at thirty, because pairs grow as N(N-1)/2
  while the per-pair swap rate stays flat near 25%.
- **No axis trick touches it.** Subtracting a day-of-year normal takes the same
  number off every year on a given day, so the swap rate is identical to three
  decimals. The anomaly buys resolution and buys exactly nothing here.
- **Two forms remove occlusion while still showing many years:** small multiples
  and the heatmap. The envelope removes it too, but only with one or two years
  drawn, which is a different question.
- Small multiples keeps the y-axis and the line, so a value can be read rather
  than inferred from a colour. At ten years a panel is 300 x 173 px, which is a
  real chart. At thirty it is 200 x 104 px carrying 365 points, 1.8 points per
  pixel: a sparkline whose shape reads and whose values do not.

**The decision the user made (20260912).** Asked whether the app is for comparing
a handful of chosen years or for surveying the whole record, the answer was
**both**. Section 4.1 of the analysis says that makes them non-exclusive and puts
small multiples first as the cheaper to abandon. So: small multiples now, the
heatmap after, and section 3 below is written so the second does not need the
first to be unpicked.

**What the analysis did not settle, and this plan inherits:** build cost. Nothing
in that document measured it. Its own section 5 says so.

## 3. The decision: what shape does `ChartView` take?

Today `src/chart/adapter.ts` describes one plot:

```ts
interface ChartView {
  xKind: 'time' | 'dayOfYear';
  xRange: [number, number];
  xWindow?: [number, number];
  yAxes: Axis[];
  series: Series[];
  lineOpacity?: number;
}
```

`src/chart/echarts.ts:240-349` turns that into exactly one `grid`, one `xAxis`, N
`yAxis` and N `series`, with `dataZoom` bound to `xAxisIndex: 0`. `src/main.ts:111`
is the only place a `ChartView` is built.

Small multiples needs `grid` and `xAxis` to become arrays, every series to name
its panel, and the zoom to span all of them. Three ways to say that.

**A constraint worth stating first.** `CLAUDE.md` requires each layer to sit
behind "an interface of at most four members". `ChartView` already has six and
`AppState` has five, so two of the four interfaces are over the limit before this
change adds anything. That is pre-existing and not caused by this work, but it
means option A makes a standing violation worse, and option B is the only one
that ends with `ChartView` inside the rule.

| | A. Add members | B. Panels array | C. Second adapter method |
|---|---|---|---|
| `ChartView` members after | 7 | **3** | 6, plus a new type |
| `ChartAdapter` members after | 3 | 3 | 4 (at the limit) |
| Files touched | `adapter.ts`, `echarts.ts` | `adapter.ts`, `echarts.ts`, `main.ts` | `adapter.ts`, `echarts.ts`, `main.ts` |
| Risk to the working overlay | low | **medium** - every caller moves | **lowest** - untouched |
| What the heatmap then costs | another member | a panel with a different mark | a third method |
| Single-panel path | unchanged | `panels: [one]` | unchanged |

**A. Add members to the flat `ChartView`.** `Series` gains `panel?: number`,
`ChartView` gains `panels?: { rows: number; cols: number }`. The adapter branches
on whether `panels` is present.
*For:* smallest diff, and the existing overlay path is literally unchanged when
`panels` is absent.
*Against:* takes `ChartView` to seven members and `Series` to nine. The heatmap
will then want a tenth thing, because a matrix is not a list of lines, so the
contract accretes a field per form. It also makes `ChartView` describe two
different things depending on which optional fields are set, which is the shape
of bug that is hard to type against.

**B. Restructure into a panels array.** ← recommended

```ts
interface Panel { yAxes: Axis[]; series: Series[]; title?: string }
interface ChartView { x: XSpec; panels: Panel[]; lineOpacity?: number }
```

where `XSpec` carries the `xKind`/`xRange`/`xWindow` triple that is already one
idea in three fields. A single-plot chart is `panels: [one]`.
*For:* `ChartView` goes to three members, back inside the rule, and the "exactly
one grid" assumption leaves the contract instead of being special-cased around.
The heatmap later becomes a panel whose mark is cells rather than lines, which is
a change inside `src/chart/` and not another contract change. Given "both", this
is the one option that does not charge us twice.
*Against:* the biggest single change of the three. `main.ts:111-118` moves, and
so does every read of `view.series` / `view.yAxes` / `view.xKind` in
`echarts.ts`. The overlay has to be re-verified in Chrome even though it should
be untouched in behaviour.

**C. A second adapter method.** `renderPanels(view: PanelView)` beside
`render(view: ChartView)`.
*For:* the working line chart is not touched at all, which is the lowest risk to
what already ships.
*Against:* two contracts to keep in step, and the shared zoom has to be wired
twice. `ChartAdapter` reaches four members, so the heatmap's third method breaks
the rule. Two forms that differ only in layout should not be two contracts.

**Decided 20260912: B.** Because the answer to section 4.1 was "both". A is
cheapest today and the most expensive across both forms; C protects the overlay
best and multiplies contracts. B is the only one that leaves the interface
compliant and the heatmap cheap.

A and C stay on record above rather than being deleted, per the project
convention. The cost B accepts is real and is not hidden: every caller of
`view.series`, `view.yAxes` and `view.xKind` moves, so step 1 must re-verify the
overlay in Chrome even though nothing about its behaviour should change.

## 4. Design, once the shape is chosen

- **One panel per selected year**, most recent first, matching the year strip's
  own order. The years you pick are the panels you get.
- **Grid:** `cols = ceil(sqrt(n))`, `rows = ceil(n / cols)`, the layout the
  analysis measured. Ten years is 4 x 3 with two empty slots, which is why a
  panel gets 8.3% of the area and not 10%.
- **Shared y-axis**, the same fixed per-variable range the overlay uses, from
  `meta.json` via `axisFor`. This is what makes panels comparable, and it is the
  existing rule rather than a new one.
- **Shared x-axis**, canonical Jan-Dec, and **one zoom across all panels**: a
  zoom into July is a zoom into July everywhere, or the panels stop being
  comparable.
- **Panel title is the year**, in that year's colour and dash from
  `src/model/style.ts`, so the existing encoding still identifies a panel.
- **Axis labels on the edges only** - left column keeps y labels, bottom row
  keeps x labels - or the labels cost more area than the data at ten panels.
- **Variables:** a panel draws every selected variable, exactly as the single
  plot does today. The UI allows one at a time, so in practice one line per
  panel; the plural case needs no special handling because `Panel` carries its
  own `yAxes`.
- **Detail and opacity sliders** keep working and apply to every panel.
- **Chips stay the selector.** They are the legend today; with the year written
  on each panel they are redundant as a legend but still the control, so they
  stay as they are.

## 5. Module impact

| Module | Change |
|---|---|
| `src/chart/adapter.ts` | The contract change chosen in section 3 |
| `src/chart/echarts.ts` | Build N grids, N x-axes, map each series to its panel, span `dataZoom` across all x-axis indices, edge-only labels |
| `src/main.ts` | Group the series it already builds into panels; pass the new view |
| `src/app/state.ts` | One field for which form is showing |
| `src/app/controls.ts` | The control that switches form |
| `src/model/*` | **None.** The model already emits one series per year; grouping is a view concern |
| `scripts/split_years.py`, `public/data/` | **None.** No data-contract change |

The last two rows are the point: unlike the anomaly, this form needs nothing new
from the data.

## 6. Steps

Each step ends green and is committed and pushed before the next begins.

1. The `ChartView` change from section 3, with the overlay still rendering
   exactly as before. `npm run build` clean, verified in Chrome.
2. N grids in the adapter, driven by a hardcoded two-panel view, to prove the
   layout before any state is wired to it.
3. Panel titles, edge-only axis labels, synced zoom.
4. `main.ts` groups real series into panels; the form switch in state and
   controls.
5. Chrome across the counts the analysis names: 1, 4, 10, 30, and 80 years.
   Confirm a panel at 30 is still legible as shape and that 80 is honestly bad,
   which is the boundary the heatmap exists to cover.
6. README and this plan's amendments section, in the same change as the code.

## 7. What is still missing from this plan

Stated plainly, because the convention is to say so before calling a plan ready.

**Settled here, as routine calls rather than open questions.** Each is reversible
and none needs a decision from the user before step 1.

- **Phone layout: one column, vertical scroll, below 600 px.** A 4 x 3 grid at
  400 px wide gives panels about 90 px across, which is not a chart. The year
  strip already branches on `(pointer: coarse)`; this branches on width instead,
  because it is about space and not about the input device.
- **Empty slots: leave them.** Ten years in a 4 x 3 grid leaves two holes.
  Stretching the last row would make two panels a different size from the other
  eight, and equal size is the whole reason the panels are comparable. This is
  also what the analysis measured, so the 8.3% figure stays true of what ships.
- **The form switch: a segmented control beside the detail slider**, two options
  now and three when the heatmap lands. Not a dropdown - with two or three
  choices a dropdown hides the alternative that makes the current one make sense.

**Genuinely still open.**

- **No cost estimate.** The analysis did not measure build cost and neither does
  this. Step 1 is the one that will tell us, which is why it is first and why it
  is scoped to "change the contract, change nothing visible".
- **Nothing here is measured in the browser.** Every panel-size figure is
  arithmetic on a 1200 x 520 plot, not a rendered page. Step 5 is the first time
  any of it is checked against a real screen, and the 30-year "legible as shape"
  claim is the one most likely to fail there.
- **Print and export are not considered** at all, and neither is what a panel
  grid does to the tooltip, which currently switches from axis to item mode past
  six series.

## 8. Alternatives kept on record

Per the project convention, the options not taken, with why.

- **Heatmap.** Second, not rejected. The only form that survives past thirty
  years to all eighty, and section 3 option B is chosen partly so it stays cheap.
- **Anomaly.** Cheapest real improvement and genuinely best at two to five years,
  and it composes with this one. Not first because it provably does nothing for
  occlusion, and because the sixth review pass found its cost had been
  understated: it needs a second precomputed range in `meta.json` and a mode flag
  in `AppState`, not just a subtraction.
- **Sequential ramp.** Accepts the tangle instead of fixing it. Worth having
  beside a form that fixes it, not instead of one.
- **Envelope.** Answers "was this year unusual", which nobody has asked yet.
- **Cumulative.** 2 of 13 variables, and its curves cross 3.4 times per pair
  after 1 April, which is more than was once claimed.
- **Doing nothing.** The detail slider already cuts crossings per pair from 94 a
  year to 21 at weekly, for 32% of the spread. If that trade is acceptable in
  practice, the case for building anything is weaker than the analysis implies.
  This is the option to take seriously before approving the plan.
