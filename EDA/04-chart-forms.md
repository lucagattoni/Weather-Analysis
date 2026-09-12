# 04. Which chart form to build next

This document exists to settle one open question: **what should the next chart in
the app be?** Six candidates are measured here against the real series, so the
choice rests on numbers rather than on which one sounds best.

**No choice has been made.** The recommendation in section 4 is a recommendation.
The decision is the user's, and the project convention is that a plan in `plans/`
is written and approved before any of this is built.

Every number below comes from a CSV in `EDA/stats/`. Regenerate all of it with:

```
uv run EDA/scripts/eda_report.py --section forms
```

![The same ten years drawn four ways](figures/04-forms.png)

**Where the six come from.** Four were put to the user as the next chart. Two
more, **small multiples** and **a sequential colour ramp above roughly 24 years**,
were already on record in
`plans/20260908_2230-multi-year-comparison-plan.md` §10 and §12 as things
considered and deferred during the multi-year build. Leaving them out would have
offered a choice narrower than the one the project had already framed, and small
multiples in particular turns out to matter.

---

## 1. What actually fails, and what does not

The app overlays one line per year on a shared January-to-December axis, on a
y-scale fixed to the variable's full range so that changing the year never
rescales the plot. Past a handful of years the result is unreadable. Being
precise about **why** is what separates the six candidates, because they fix
different things and only some fix the thing that is broken.

Four quantities, all on daily mean temperature, from
`EDA/stats/04-occlusion.csv` and `EDA/stats/04-axis-cost.csv`:

| Quantity | What it means | At ten years |
|---|---|---|
| Separation | median gap between the highest and lowest year on a given day | 7.22 °C |
| Spread | median standard deviation across years on a given day | 2.36 °C |
| Roughness | median day-to-day movement within one year | 1.20 °C |
| Swap rate | share of days on which a given pair of years changes which is on top | 25.8% |

Separation is a range, a maximum minus a minimum, and every window here is a
superset of the one before it, so it can only climb as years are added. That
climb is arithmetic and not a finding, which is why spread sits beside it: a
standard deviation across years has no such property. It rises from 1.51 °C at
two years to 2.43 °C at twenty and then stops; at thirty it is 2.40 °C.

**Resolution is a real problem.** The app's fixed axis spans 45 °C, so a ten-year
selection's 7.22 °C of separation fills 16.0% of the plot height. An axis fitted
to what is actually drawn spans 24.67 °C and lifts that to 29.3%.

**Roughness is not the problem.** At 1.20 °C it is below the separation at every
year count tested, two included, so the lines are not lost in their own noise.

### Ordering is the problem, but not because the rate rises

The swap rate is flat. It is 28.0% at two years and 25.5% at thirty, slightly
*higher* at two. Taken alone that refutes the obvious story, because the app
plainly works at two or three years: if a quarter of days swapping were
disqualifying, it would disqualify two years as well.

What grows is not the rate but the number of pairs that can swap, and pairs grow
as N(N-1)/2. From `EDA/stats/04-occlusion.csv`:

| Years | Pairs on screen | Swap rate | Expected crossings per day |
|---|---|---|---|
| 2 | 1 | 28.0% | 0.28 |
| 5 | 10 | 25.6% | 2.56 |
| 10 | 45 | 25.8% | 11.63 |
| 20 | 190 | 25.2% | 47.83 |
| 30 | 435 | 25.5% | 111.00 |

That is the shape of the failure. Two lines crossing every fourth day is a chart;
thirty lines producing a hundred crossings a day is a texture. **The per-pair rate
never had to worsen for the form to fail, and no rescaling of the axis reduces a
single one of those crossings.**

### Subtracting a normal cannot help, and that is provable

Subtracting a day-of-year normal takes **the same number off every year on a
given day**, so it cannot change which year is above which. The swap rate is
computed twice in `EDA/stats/04-occlusion.csv`, once on raw values and once on
anomalies, so the claim is held to the data rather than asserted:

| Years | Swap rate, raw | Swap rate, anomaly |
|---|---|---|
| 2 | 28.022% | 28.022% |
| 10 | 25.844% | 25.844% |
| 30 | 25.517% | 25.517% |

Identical to three decimals, as it must be. **The anomaly buys resolution and
buys exactly nothing in occlusion.** That is not an argument against it; it is an
argument about which problem it solves.

### The app's own detail slider is a partial answer already

Every measurement above is at one point per day, and the app can resample to one
per week. Judging the line chart only at daily would test it at a resolution its
own README tells people not to use for a wide selection. From
`EDA/stats/04-resolution.csv`, ten years:

| Step | Points per year | Spread | Swap rate | Crossings per pair per year |
|---|---|---|---|---|
| 1 day | 365 | 2.36 °C | 25.8% | 94.3 |
| 2 days | 183 | 2.10 °C | 32.4% | 59.3 |
| 4 days | 92 | 1.81 °C | 38.9% | 35.8 |
| 1 week | 53 | 1.62 °C | 39.7% | 21.0 |
| 4 weeks | 14 | 0.99 °C | 39.8% | 5.6 |

The rate and the count point opposite ways, and both are true. Coarser steps make
each remaining point *more* likely to swap, because averaging pulls the years
toward each other, but there are far fewer points, so the absolute tangle falls
by a factor of four from daily to weekly. The cost is in the spread column: it
falls 31% over the same range. **The slider trades tangle for the difference you
came to see.** It helps, it is already built, and it does not remove the problem.

### It is not a fact about temperature, or about one decade

Six twenty-year windows spread across the record, three straddling September 1993
(`EDA/stats/04-anchor-sweep.csv`), hold the swap rate between 24.6% and 25.5%.
The anchor does not carry the finding.

Nor does the variable. From `EDA/stats/04-variables.csv`, ten years, daily:

| Variable | Aggregate | Swap rate | Tied days |
|---|---|---|---|
| Mean sea level pressure | mean | 18.4% | 0.0% |
| Air temperature | mean | 25.8% | 0.1% |
| Mean wind speed | mean | 33.3% | 0.4% |
| Relative humidity | mean | 35.0% | 0.1% |
| Precipitation amount | sum | 36.3% | 18.5% |
| Visibility | mean | 36.3% | 0.2% |
| Sunshine duration | sum | 42.9% | 2.4% |

Temperature, which everything else here is measured on, has the second *lowest*
swap rate of the seven. Every other variable tangles at least as much, so
choosing temperature flattered the line chart rather than the alternatives. Rain
is the odd one out for a different reason: 18.5% of its day-pairs are exactly
tied, both years recording nothing, so "which is on top" is often undefined.

---

## 2. The six candidates, measured

### Anomaly: subtract the day-of-year normal

Each year plotted as its distance from the 1991-2020 normal for that day. From
`EDA/stats/04-separation.csv`:

| Years | Separation | Raw axis needed | % of axis | Anomaly axis | % of axis |
|---|---|---|---|---|---|
| 2 | 2.13 °C | 23.06 °C | 9.2% | 14.44 °C | 14.7% |
| 3 | 3.79 °C | 23.06 °C | 16.4% | 14.44 °C | 26.2% |
| 5 | 5.31 °C | 24.50 °C | 21.7% | 15.30 °C | 34.7% |
| 10 | 7.22 °C | 24.67 °C | 29.3% | 15.64 °C | 46.2% |
| 20 | 8.85 °C | 30.09 °C | 29.4% | 21.27 °C | 41.6% |
| 30 | 9.65 °C | 30.09 °C | 32.1% | 21.27 °C | 45.4% |

Against the app's own fixed 45 °C axis the gain is larger: 16.0% to 46.2% at ten
years, which is 2.9 times the plot height for the same difference.

![Separation as a share of the axis each form needs](figures/04-separation.png)

**Buys:** the largest resolution gain here, at every year count, and by a wide
margin the cheapest to build: a build-time day-of-year normal in `meta.json` and
a subtraction in the model. No new chart type, no adapter change, and zoom,
detail and opacity keep working untouched.
**Costs:** nothing at all in occlusion, proven above. The top-right panel of the
figure is ten anomaly lines and it is as tangled as the raw panel beside it. It
also puts the reader one subtraction from the observation: a line at +3 °C no
longer says what the temperature was.
**Best at:** two to five years, where few enough pairs exist for the lines to be
told apart and height is the whole difficulty.

### Small multiples: one small panel per year

The same line chart repeated, one year per panel, on a shared axis. From
`EDA/stats/04-small-multiples.csv`, on a 1200 × 520 px plot:

| Years | Grid | Panel size | Share of the area each year gets |
|---|---|---|---|
| 4 | 2 × 2 | 600 × 260 px | 25.0% |
| 10 | 4 × 3 | 300 × 173 px | 10.0% |
| 30 | 6 × 5 | 200 × 104 px | 3.3% |
| 80 | 9 × 9 | 133 × 58 px | 1.3% |

**Buys:** occlusion is gone by construction, exactly as for the heatmap, because
no two years share a panel. It keeps the y-axis, so values stay readable, and it
reuses the existing line chart rather than needing a new one, which makes it the
cheaper of the two forms that actually solve the problem.
**Costs:** comparing two years becomes looking from one panel to another instead
of at one line against another, which is what an overlay is for. Panel area falls
as 1/N, and at thirty years each panel is 200 × 104 px carrying 365 daily points,
which is 1.8 points per pixel: a sparkline, not a chart you read values off.
**Best at:** five to about thirty years.

### Heatmap: years down, day of year across

One row per year, one column per day, colour carrying the value. From
`EDA/stats/04-heatmap-cells.csv`, same plot size:

| Years | Cells | Cell size |
|---|---|---|
| 10 | 3,650 | 3.3 × 52.0 px |
| 30 | 10,950 | 3.3 × 17.3 px |
| 80 | 29,200 | 3.3 × 6.5 px |

**Buys:** occlusion is gone by construction. It is the only candidate that stays
legible across the whole archive: at all 80 years each row is still 6.5 px tall
and the full width, where a small-multiple panel has shrunk to 133 × 58 px.

**What it does not buy, and this was claimed here before it was measured.** An
earlier draft of this document said the heatmap was the only form that makes the
+0.43 °C shift across eighty years visible. **That is false, and
`EDA/stats/04-heatmap-signal.csv` is the measurement that killed it.** Colour has
to compete with the noise in the cells, and the shift loses:

| Cell | Cells per year | Trend ÷ cell noise | One year ÷ row noise |
|---|---|---|---|
| 1 day | 365 | 0.17 | 3.62 |
| 1 week | 53 | 0.25 | 1.93 |
| 1 month | 13 | 0.34 | 1.40 |
| 1 season | 5 | 0.42 | 1.14 |

The left column is the eighty-year shift against the spread of cell values: 0.17
to 0.42, never close to 1, so the trend is not visible as colour at any cell size
tested. Aggregating helps a little and then stops, because coarser cells lose
resolution as fast as they gain signal.

The right column is a different question with a different answer: a single year's
deviation against the noise of its own row, which the eye averages along. At one
cell per day that ratio is **3.6**, so an individual warm or cold year does read
as a row, and finer cells are better for it, not worse. The honest claim is
therefore: **a heatmap makes an unusual year findable anywhere in eighty years of
record; it does not make the slow trend visible.** The slow trend is what
document 2's fitted trends are for.

![The same eighty years at two cell sizes](figures/04-heatmap-detail.png)

**Costs:** a new chart type. Not as costly as that sounds, since the POC plan
(`plans/20260908_2031-weather-viewer-poc-plan.md` §5) chose ECharts partly
because it supports heatmaps natively, but still a new adapter path, a colour
scale, and a legend that no longer means what the chip list means. Reading a
value off a colour is far less precise than off an axis. Zoom and opacity do not
obviously survive: zoom acts on time and a heatmap's x-axis is a canonical day of
year, and opacity exists to let overlapping lines show through, which cells never
do.
**Best at:** thirty years and up, and uniquely at all eighty.

### Sequential ramp: keep the overlay, change the colours

Not a new chart, an encoding change: replace the decade hue with one ramp running
oldest to newest, so a tangle of lines reads as a gradient from old to recent.
Already endorsed for this purpose in
`plans/20260908_2230-multi-year-comparison-plan.md` §4 above roughly 24 years.

**Buys:** the cheapest change on this list, smaller even than the anomaly: it
touches `src/model/style.ts` and nothing else. It does not need the lines to be
individually followable, which is exactly the property the measurements above say
is unavailable, so it is the only candidate that accepts the tangle instead of
fighting it.
**Costs:** it removes nothing. Every crossing in the table above is still there,
and individual years become *less* identifiable, not more, since adjacent years
become near-identical colours. It answers "is there drift over time" and nothing
else.
**Best at:** twenty years and up, as a cheap improvement to a form that will
still be hard to read.

### Envelope: a percentile band with years on top

A 10th-to-90th percentile band over 1991-2020, selected years drawn over it.
From `EDA/stats/04-band-width.csv` and `EDA/stats/04-envelope-escape.csv`:

| Quantity | Value |
|---|---|
| Band width, median across the year | 5.83 °C |
| Band width, narrowest and widest day | 2.88 °C, 10.10 °C |
| Days outside the band, 2025 | 96 of 365 (26.3%) |
| Days outside the band, 2018 | 93 of 365 (25.5%) |
| Days outside the band, 2010 | 119 of 365 (32.6%) |
| Days outside the band, 1963 | 101 of 365 (27.7%) |

A typical year spends a quarter to a third of its days outside the band, so the
form has something to show rather than a rarity.

**Buys:** it solves occlusion by replacing most of the lines with a band, and
answers a question none of the others answer: *was this year unusual?*
**Costs:** one or two years on top before the tangle returns, so it does not
scale. It needs a reference period chosen and stated, and that choice moves every
count in the table.
**Best at:** one or two years against the climate, not years against each other.

### Cumulative totals: running sum through the year

Only meaningful for the two variables the app sums; a running total of a mean is
not a quantity. From `EDA/stats/04-cumulative.csv`:

| Variable | Window | Annual range | Spread by 1 July | Swaps per pair after 1 April |
|---|---|---|---|---|
| Rain | 2016-2025 | 662-1002 mm | 144 mm | 3.5 |
| Rain | whole series | 555-1095 mm | 350 mm | 3.5 |
| Sun | 2016-2025 | 1319-1648 h | 288 h | 3.4 |
| Sun | whole series | 1240-1740 h | 364 h | 3.4 |

**Buys:** integrating removes day-to-day roughness entirely, so curves are smooth
and a year's standing is readable at any point. Rainfall totals differ by a
factor of **2.0** across the archive; sunshine by **1.4**.
**Costs:** 2 of 13 variables. And the curves cross more than was previously
claimed here: **3.4 times per pair after 1 April**, averaged over the four rows,
so "they rarely cross" is wrong.
**Best at:** "how wet is this year so far", for rain and sunshine only.

---

## 3. Side by side

Three kinds of cell, kept apart, because a table giving a measured number and an
opinion the same weight hides which is which.

- **Bold** is measured and the CSV is named in section 2.
- *Judgement* is my assessment with nothing measured behind it.
- Plain text is a structural fact, true by what the form is. "A heatmap cannot
  show an exact value" needs no CSV.

| | Anomaly | Small multiples | Heatmap | Sequential ramp | Envelope | Cumulative |
|---|---|---|---|---|---|---|
| Fixes resolution | **yes, 2.9×** | *judgement: yes* | not applicable | no | *judgement: yes* | *judgement: yes* |
| Fixes occlusion | **no, measured identical** | yes, by construction | yes, by construction | no | *judgement: yes* | **partly, 3.4 swaps** |
| Years it works at | *judgement: 2-5* | **5-30, from panel size** | **30-80, from cell size** | *judgement: 20+* | *judgement: 1-2 over a band* | not measured |
| Variables covered | all 13 | all 13 | all 13 | all 13 | all 13 | **2 of 13** |
| Exact values readable | yes | yes | no | yes | yes | yes |
| Reuses the line chart | yes | yes | no | yes | yes | no |
| Keeps zoom and opacity | yes | *judgement: yes* | *judgement: neither* | yes | yes | *judgement: zoom only* |
| Build cost | *judgement: lowest* | *judgement: low* | *judgement: highest* | *judgement: lowest* | *judgement: medium* | *judgement: medium* |
| Answers | how did these few years differ | what did each year look like | which years were unusual, and when | is there drift over time | was this year unusual | how much so far |

Build cost is the row to be most sceptical of. Nothing here measures it and the
recommendation leans on it.

---

## 4. Recommendation

**Build small multiples.** ← recommended

The measured failure is occlusion, and it grows with the number of pairs on
screen rather than with any worsening of the lines themselves. Two candidates
remove it outright, and between them small multiples is the cheaper: it reuses
the existing line chart and adapter rather than adding a chart type, it keeps the
y-axis so values stay readable, and at the year counts the app is actually built
for it has the room. At ten years each panel is 300 × 173 px, which is a real
chart. The year strip that was just rebuilt maps onto it directly: the years you
pick are the panels you get.

**Build the heatmap second, or first if the goal is the whole archive.** It is
the only candidate that survives past thirty years, where small-multiple panels
have fallen to 133 × 58 px, and the only way to find an unusual year anywhere in
eighty years at a glance, which it does at 3.6 times the row noise. It costs the
most, and one of the two reasons previously given for it turned out to be false.

**Take the anomaly whenever the budget is smallest.** It is the cheapest real
improvement, it is genuinely the best form at two to five years, and it composes
with either of the above. Choose it with open eyes: it will not make a ten-year
selection readable and section 1 proves that to three decimal places.

**Not recommended now.** The sequential ramp accepts the tangle rather than
fixing it, and is worth having only alongside a form that does. The envelope
answers a different question and should wait until someone wants to ask it. The
cumulative form covers 2 of 13 variables and its curves cross more than was
thought.

### Two recommendations were overturned by measurement, including mine

An earlier session recommended the anomaly, on the grounds that it halves the
axis and is cheapest. Both are confirmed. What was missing is that the axis was
never the binding constraint.

An earlier draft of **this** document then recommended the heatmap, partly
because it was "the only form on which a +0.43 °C shift across eighty years is
visible at all". Measuring that claim rather than asserting it showed the shift
is 0.17 to 0.42 times the cell noise and is not visible at any cell size. The
heatmap keeps a real and different advantage, finding an unusual year across the
whole record, but it no longer outranks the cheaper form that solves the same
binding problem.

Three figures from the earlier session's summary also failed re-measurement and
are corrected above: cumulative curves cross 3.4 times per pair after 1 April
rather than rarely, 2025 spends 96 days outside the band rather than 80, and the
+0.43 °C is suppressed by the 1993 step rather than inflated by it.

### What +0.43 °C actually is

Not a reason to build anything, on the evidence above, but it is quoted in this
project and the reasoning was wrong here before, so it is worth stating once.

The station changed how it observes in September 1993
(`EDA/01-data-review.md` §10), and it would be easy to assume that inflates the
figure. It does not. Document 2 fits trend and step together and puts the step at
**-0.262 °C**, a cooling offset (`EDA/stats/02-break-test.csv`), which holds the
whole-series number **down**. From `EDA/stats/04-warming-signal.csv`:

| Window | Measured | Centres apart | Trend alone | Difference |
|---|---|---|---|---|
| 1946-1975 against 1996-2025 | +0.43 °C | 50 years | +0.73 °C | -0.29 °C |
| 1994-2008 against 2011-2025 | +0.22 °C | 17 years | +0.25 °C | -0.03 °C |

Using document 2's fitted +0.145 °C per decade, the whole-series comparison falls
0.29 °C short of trend, which is the step almost exactly; the comparison that
never crosses 1993 falls short by 0.03 °C, which is nothing. The smaller +0.22 °C
is not a cleaner measurement of the same thing, it is a shorter window, and
comparing them as though they measured the same quantity was the error. One
honest qualifier: on the annual mean alone the step is not significant, p = 0.24,
interval -0.706 to +0.182, which does not exclude a warming step. The sign comes
from document 2's hour-by-hour decomposition, not from that test.

---

## 5. What this document does not decide

- **The colour scale**, if the heatmap is chosen. Diverging around a normal is
  the obvious choice and the cell-noise measurement above is the constraint on it.
- **What happens to the year strip** under a heatmap of all eighty years, which
  needs no year selection at all, and under small multiples, which needs one.
- **Whether forms coexist** behind a switch or replace one another.
- **Build cost**, which nothing here measures and which the recommendation uses.
- **Anything about the 1993 discontinuity beyond stating it.** No correction is
  applied anywhere in this project, deliberately.

## 6. Provenance

| File | Holds |
|---|---|
| `EDA/stats/04-separation.csv` | separation, spread and axis span, raw and anomaly, by year count |
| `EDA/stats/04-axis-cost.csv` | what the app's fixed axis costs against a fitted one |
| `EDA/stats/04-occlusion.csv` | spread, roughness, pair counts and the swap rate, raw and anomaly |
| `EDA/stats/04-anchor-sweep.csv` | the same measures from six windows across the record |
| `EDA/stats/04-resolution.csv` | what the detail slider does to spread and to crossings |
| `EDA/stats/04-variables.csv` | the swap rate for seven variables, and tied days |
| `EDA/stats/04-small-multiples.csv` | panel size and area share by year count |
| `EDA/stats/04-heatmap-cells.csv` | cell counts and cell size at a real plot size |
| `EDA/stats/04-heatmap-signal.csv` | whether the trend, and whether one year, beats the cell noise |
| `EDA/stats/04-warming-signal.csv` | first-to-last difference, the gap it spans, and what the trend implies |
| `EDA/stats/02-break-test.csv` | document 2's joint trend-plus-step fit, read at runtime, not copied |
| `EDA/stats/04-band-width.csv` | the 10-90 band's width |
| `EDA/stats/04-envelope-escape.csv` | days a year spends outside the band |
| `EDA/stats/04-cumulative.csv` | annual totals, mid-year spread, crossing counts |
| `EDA/figures/04-forms.png` | the same ten years in four of the forms |
| `EDA/figures/04-separation.png` | separation as a share of the axis, by year count |
| `EDA/figures/04-heatmap-detail.png` | eighty years of anomaly at two cell sizes |

All of it is regenerated by `uv run EDA/scripts/eda_report.py --section forms`,
and the output is deterministic: two runs produce byte-identical files, so a
number that moves shows up as a git diff rather than as drift between the prose
and the data.
