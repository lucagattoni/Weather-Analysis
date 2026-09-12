# RESUME: handover

Updated 20260912 21:12 UTC. Read `CLAUDE.md` first, then this.

## Where things stand

`main` is clean, pushed and deployed. No half-finished work, no stray worktree,
no stray branch.

- **Live:** <https://lucagattoni.github.io/Weather-Analysis/>, redeployed by
  `.github/workflows/pages.yml` on every push to `main`.
- **Built:** the POC, zoom and pan, multi-year comparison on a shared Jan-Dec
  axis with the decade/shade/dash encoding, a detail slider from 1 h to 7 days,
  an opacity slider, and the year strip described below.
- **Analysed:** `EDA/` holds four documents. Three cover the series; the fourth
  measures **six** candidate chart forms and is the evidence the next build rests
  on.
- **Decided and planned:** see the next two sections.

## The decision, and what is next

**The chart question is settled.** Asked whether the app is for comparing a
handful of chosen years or for surveying the whole record - the question
`EDA/04-chart-forms.md` section 4.1 says flips the recommendation - the answer
was **both**. That makes the two forms non-exclusive, so **small multiples is
built first** as the cheaper to abandon, and the **heatmap** follows.

**The plan is written and approved:**
[`plans/20260912_2049-small-multiples-plan.md`](plans/20260912_2049-small-multiples-plan.md).
Its one real decision is taken: `ChartView` becomes **option B, a panels array**,
`{x, panels[], lineOpacity}`. Three members where it carries six today, against a
project rule of four. A single plot is `panels` of length one.

That choice is about the heatmap more than about panels. Adding a panel field to
the flat contract is a smaller diff today, but a matrix is not a list of lines,
so the heatmap would want another field and the contract would accrete one per
form. A panels array lets the heatmap arrive as a panel whose mark is cells,
inside `src/chart/`, changing no contract. Options A and C stay on record in
section 3.

**Next action: implement section 6 of that plan, step 1 first.** Step 1 is
deliberately "change the contract, change nothing a user can see", because nobody
has costed this work and step 1 is what will tell us. Start it in a fresh
session; it is a different shape of task from the review that produced the plan.

The exact next command, from the repo root:

```
NAME=$(date -u "+%Y%m%d_%H%M")-small-multiples
git fetch && git pull --ff-only
git worktree add "../Weather-Analysis.worktrees/$NAME" -b "$NAME"
```

Then, in that worktree: reshape `ChartView` in `src/chart/adapter.ts` to
`{x, panels[], lineOpacity}`, follow it through `src/chart/echarts.ts` and the
single construction site at `src/main.ts:111`, and finish with `npm run build`
clean and the overlay verified unchanged in Chrome. No user-visible change in
step 1 is the point of step 1.

## The review loop is open, and honestly so

`EDA/04-chart-forms.md` has had **eight** adversarial passes. Findings: 8, 9, 7,
6, 15, 8, 7, 9. Passes 5 to 8 ran two or three reviewers with separate lenses, so
those counts are not comparable to the single-lens passes before them.

**No pass has come back clean.** Two things are now true at once and both matter
to whoever runs the ninth.

**The document's own defects are thinning.** Pass 7's prose reviewer checked every
number, table and quotation and found none wrong; pass 8's found one pre-existing
error. Prose-versus-CSV checking has reached its floor.

**The fixing is now a large source of the findings.** Four of pass 8's five
prose-side findings were damage from passes 6 and 7 - including a sentence that
mistranscribed the very CSV column it was written to vindicate, and a commit
message claiming a fix that had only half landed. That part of the loop does not
converge by running more passes, because each pass seeds the next one's findings.
What breaks it is mechanising the check, which is where the effort has gone.

Each pass has also opened a category its predecessors were not looking at, which
is the argument for a ninth:

| Pass | The category it opened |
|---|---|
| 5 | Build cost, never audited beyond small multiples |
| 5 | Numbers the prose *derives* from cells, which the checker never saw |
| 6 | **The figures.** Four passes cited the lead figure; none had opened it |
| 7 | Bucketing: a cell labelled "one season" was one day long |
| 8 | **The measurement itself**: a number that matched its CSV exactly and was computed wrongly |

### What pass 8 changed, because it moved a headline number

`table_heatmap_signal` asks whether one year stands out as a row, and the document
calls its denominator "the noise of its own row". The code divided by the standard
deviation of the **whole heatmap**. Those differ by exactly the quantity being
detected: variance splits as pooled^2 = within^2 + between^2, and the between-year
term is the signal, so the signal sat in its own denominator.

The bias grows as cells coarsen, because within-row noise falls while the
between-year term does not:

| Cell | was | is | understated |
|---|---|---|---|
| 1 day | 1.587 | 1.616 | 1.8% |
| 1 week | 1.379 | 1.430 | 3.7% |
| 1 month | 1.308 | 1.439 | 10.0% |
| 1 season | 1.158 | 1.420 | 22.6% |

**The recommendation does not move** - the headline goes 1.59 to 1.62. One claim
did not survive: "finer cells are still better for spotting a year" was an
artefact of the wrong term. Corrected, the column is nearly flat, so cell size is
close to free on that axis.

This is the one seven passes could not have found. It matched its CSV perfectly;
the CSV was wrong. Only reading the generator as a statistician reaches it.

## Before editing the document or `eda_forms.py`, run

```
uv run EDA/scripts/check_forms_numbers.py
```

272 claims, and it exits non-zero if the prose and the CSVs have drifted apart.
It exists because seven passes found numbers left stale by corrections applied in
one place and not another, five separate times.

**What it cannot reach, and this matters:** it reads CSVs and the markdown, never
`src/` and never a figure's axes. Every claim the document makes about the app is
checked by hand or not at all. The lead figure was drawing its heatmap panel into
3.5% of its width for four passes and nothing here noticed.

## Read these before changing anything

| File | Why |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | The rules. Short. |
| [`plans/20260912_2049-small-multiples-plan.md`](plans/20260912_2049-small-multiples-plan.md) | **What to build next**, and section 7 for what it does not yet settle |
| [`EDA/04-chart-forms.md`](EDA/04-chart-forms.md) | Every number behind the decision |
| [`plans/20260908_2031-weather-viewer-poc-plan.md`](plans/20260908_2031-weather-viewer-poc-plan.md) **section 10** | Seven amendments to the POC plan. Sections 1-9 are as approved and some commands are stale. |
| [`plans/20260908_2230-multi-year-comparison-plan.md`](plans/20260908_2230-multi-year-comparison-plan.md) **sections 8, 12, 13** | Decisions taken, the eight places the build differed, and the 20260909 year-control revision |
| [`EDA/01-data-review.md`](EDA/01-data-review.md) **section 10** | The data-quality register. Read before trusting any statistic crossing September 1993. |

## The year control, rebuilt and reviewed 20260909

The two-knob slider and the "chips only for years outside the range" model are
gone. Both bugs reported against them came from one cause: a range plus a set of
extras has two kinds of member, and a range cannot express "1990 to 2000 without
1995", so the years it contributed were not removable.

The selection is now a plain `Set<number>`; the strip is one tick per year, most
recent on the left. Tap a tick to add or remove, drag across for a span, a chip
removes one, `only <year>` leaves the most recent. The selection can never be
empty and the app opens on the current year. The chips are also the chart's
legend, drawn with each year's real line and dash. Rationale and alternatives:
`plans/20260908_2230-multi-year-comparison-plan.md` section 13.

**It has been adversarially reviewed.** Three reviewers found eleven real issues;
all fixed, verified in Chrome and deployed. The largest were a zoom window that
came back inverted when it started on 29 February, a phone that could not scroll
the page if the swipe began on the strip, a chip that lost its styling whenever
exactly one year was selected - which is the state the app opens in - and a
shift-arrow sweep that could grow but never shrink.

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

`EDA/figures/01-rain-granularity.png` has its footnote overlapping the x-axis
label. Found by pass 7 and not fixed: it belongs to document 01, and fixing it
means regenerating that section, which was not this branch's job.

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
- **`ChartView` has six members and `AppState` five, against a rule of four.**
  Pre-existing, and the reason the plan chose option B. Do not add a seventh.
- **The zoom slider's data shadow is drawn by data index, not by time**, so a
  part-year series fills it to December. It is switched off for that reason.
- **The app applies no correction for the September 1993 observation change**,
  which moves eleven of thirteen variables. Deliberate, and stated in the footer.
- **Sentinels are not missing data.** `clht` 999 is "no ceiling", `clamt` 9 is
  "sky obscured", `wddir` 0 is calm and not north. All three are excluded from a
  variable's range and from its aggregate, and drawn as gaps.
- **Wind direction is circular**, and that is not only a display question. A
  day-of-year normal or a percentile band on degrees needs circular statistics
  nothing in this project implements, which is why three of the six chart forms
  cover 12 of 13 variables rather than all 13.
- **Aggregation is per variable.** Rain and sunshine sum, wind direction takes a
  circular mean, the other ten take a mean. It is a field in `meta.json`.
- **Resampling past a day pulls years together.** Coarser steps buy traceable
  lines and cost some of the difference being looked for: weekly detail cuts
  crossings per pair from 94 a year to 21 and costs 32% of the spread. Both
  halves are in the README.
- **A partial year is not a year.** `eda_common.LAST_COMPLETE_YEAR` is 2025 and
  2026 holds 212 days. Filter complete years at **both** ends; bounding only the
  start is what put a 212-day row in the lead figure.
- **The 1940s and the 2020s share a hue.** Nine decades, eight hues; decision A.
