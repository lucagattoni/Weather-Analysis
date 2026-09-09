# Multi-year comparison — plan

Status: **approved 20260908, ready to implement** · written 20260908 22:30 UTC · branch `20260908_2230-multi-year-plan`

Builds on the POC (plan `20260908_2031-weather-viewer-poc-plan.md`, implemented and
merged 20260908). Read that plan's section 10 first: it records what the built app
actually does. This document covers one roadmap item from its section 8, "overlay
two years", widened to N years.

## 1. Goal

Compare the same variable across several years at once. Every selected year is drawn
on one shared 1 January to 31 December axis, so the years lie on top of each other and
can be read against a single fixed y-scale.

## 2. Decisions already taken (with the user, 20260908)

| # | Question | Decision |
|---|---|---|
| 1 | Selecting years | A two-knob slider sets a start and end year. A chip list adds and removes individual years outside that range. **Superseded 20260909, see §13.** |
| 2 | X axis | One shared Jan–Dec axis (`xKind: 'dayOfYear'`, the field already present and unused in `ChartAdapter`). |
| 3 | Day window | The existing day-range slider stays and applies to all overlaid years at once. Zooming to June–August shows that window for every selected year. |
| 4 | Colour | Hue from the decade; shade from the year's position in the decade divided by three; dash from that position modulo three. |
| 5 | Detail level | **No automatic detail.** Hourly stays the default at any year count. A manual slider resamples from 1 h to 6 h. Revised by the user 20260908 after the first draft; the automatic ladder is rejected and kept on record below. |
| 6 | Legend | Always present for two or more series, showing the real line style. |

Rejected and kept on record — **the automatic detail ladder** (hourly to 3 years,
daily to 12, monthly beyond). The user's reasoning: the chart should not silently
change what it is showing, and hourly detail stays wanted even at 20 years. Monthly
means also discard the daily texture that makes an hourly weather series worth
plotting. Section 3 records what the manual range does and does not achieve.

Alternatives considered and rejected, kept on record: a token input with autocomplete
(Tom Select or Choices.js, ~16 kB gzipped) — rejected because the domain is 81 fixed
ordered values, so autocomplete solves a problem this dataset does not have, and
removal would be a smaller, different gesture than adding; a toggle grid of all 81
years — viable, rejected in favour of the slider, which sweeps a decade in one gesture;
a hard cap of 8 years; small multiples above a threshold; a single sequential ramp
across the whole selection (still the right answer above ~24 years, see §4).

## 3. The measurements this design rests on

All measured on the committed chunks, 20260908.

**Overlaying raw hourly lines does not work past a few years.** On the fixed
temperature axis (-15..30 °C), the median vertical gap between the highest and lowest
selected year, against a single year's median within-day swing of 6.4 °C:

| Years | Hourly gap | Daily-mean gap | Monthly-mean gap | Hourly points per pixel |
|---|---|---|---|---|
| 2 | 2.6 °C | 2.2 °C | 0.6 °C | 13.8 |
| 3 | 4.6 °C | 3.9 °C | 1.0 °C | 20.7 |
| 5 | 6.5 °C | 5.5 °C | 2.0 °C | 34.5 |
| 10 | 8.8 °C | 7.2 °C | 3.1 °C | 69.0 |
| 20 | 10.7 °C | 8.9 °C | 4.0 °C | 138.0 |
| 40 | 12.0 °C | 10.2 °C | 4.8 °C | 275.9 |

At two years the between-year gap (2.6 °C) is *smaller* than one year's daily swing
(6.4 °C): the lines sit inside each other's noise. A single year is already 6.9 hourly
points per pixel at full width, so the line is a band before a second year is added.
Aggregation is what creates separation; colour only says which line you are pointing at.

**What the 1 h to 6 h slider buys**, measured on 2006–2025:

| Step | Samples/day | Points per year | Points per pixel, per series | Within-day swing | 20-year gap |
|---|---|---|---|---|---|
| 1 h | 24 | 8,760 | 6.90 | 6.4 °C | 10.7 °C |
| 2 h | 12 | 4,380 | 3.45 | 5.8 °C | 10.6 °C |
| 3 h | 8 | 2,920 | 2.30 | 5.4 °C | 10.5 °C |
| 4 h | 6 | 2,190 | 1.72 | 4.9 °C | 10.4 °C |
| 6 h | 4 | 1,460 | 1.15 | 4.2 °C | 10.2 °C |

Two conclusions. **6 h is where dash patterns become legible**: a dash cycle needs
roughly 1.5 points per pixel or fewer, and 6 h lands at 1.15 where 1 h is 6.90. It also
takes 20 years from 175,200 points to 29,200. **Resampling does not separate the
years**: the 20-year gap moves only from 10.7 °C to 10.2 °C. It smooths each line, it
does not move the lines apart. At 20 years the chart shows the shape of the cloud and
the trend, not individual followable years. That is intended, not a defect.

Only 1, 2, 3, 4 and 6 divide 24 evenly, so the slider snaps to those five positions; a
5 h bucket would straddle midnight and drift through the day.

**Loading cost**, uncompressed: 2 years 0.7 MB, 5 years 2.1 MB, 10 years 4.4 MB,
20 years 9.1 MB. Resampling happens in the browser after the chunk is loaded, so it
reduces points drawn, not bytes fetched.

## 4. Colour, shade and dash

Reproduces the user's worked example exactly (2020 light solid, 2021 light dashed,
2022 light dotted, 2023 mid solid, 2024 mid dashed, 2025 mid dotted, 2026 dark solid):

```
hue   = fixed 8-slot categorical order, indexed by decade
shade = floor((year - decadeStart) / 3)     ->  light, mid, dark, darkest
dash  = (year - decadeStart) % 3            ->  solid, dashed, dotted
```

Derived from the year alone, never from its position in the selection. Widening the
range therefore never repaints a line that was already on screen, which is the
"colour follows the entity, never its rank" rule.

Capacity: 4 shades x 3 dashes = **12 combinations per decade**, covering 10 years with
2 spare.

**Validated with the palette validator, not by eye** (`scripts/validate_palette.js`,
ordinal mode). Light and dark need different steps, not a flip:

| Mode | Surface | Blue ramp, light to dark | Result |
|---|---|---|---|
| Dark | `#1a1a19` | `#cde2fb` `#86b6ef` `#3987e5` `#184f95` | all checks pass |
| Light | `#fcfcfb` | `#6da7ec` `#3987e5` `#256abf` `#104281` | all checks pass |

Rejected by measurement: 10 shades of one hue (adjacent lightness gap 0.047 against a
0.06 floor; normal-vision ΔE 4.7 against a floor of 15). On a light surface a ramp
starting at `#9ec5f4` fails contrast at 1.74:1 against a 2:1 floor, which is why the
light ramp starts three steps darker.

**Dashes do not render at hourly resolution.** An hourly line reverses direction
several times per pixel, which shreds a dash cycle into noise. This is why shade and
dash both encode the same within-decade position: shade carries it at hourly detail,
dash takes over once aggregated. They reinforce rather than compete.

Above roughly 24 years the honest encoding is a single sequential ramp oldest to
newest, so the chart reads as a trend rather than a lookup table. Out of scope here.

## 5. Aggregation is per variable, not one function

A plain mean is wrong for three of the thirteen variables. Measured on 2025:

| Variable | Aggregate | Why |
|---|---|---|
| `wddir` | Circular mean | The naive mean disagrees by more than 30° on 50 of 365 days, worst case 179°. A day reading 340, 330, 300, 290, 280, 270 degrees averages naively to 175° (due south), against a circular mean of 355° (due north). |
| `rain` | Sum | Mean gives 0.09 mm/h, which means nothing to a reader; the sum gives 2.21 mm/day and 805 mm/year. |
| `sun` | Sum | Mean gives 0.19 h/h; the sum gives 4.5 h/day and 1648 h/year. |
| the other ten | Mean | |

This becomes an `aggregate` field per variable in `meta.json`, emitted by
`scripts/split_years.py`, because the existing rule is that variables are data and not
code. A sentinel is excluded before aggregating, and a bucket with no readings is a gap.

## 6. UI

One control row, as today, plus the year selection beneath it.

- **Years**: a two-knob range slider over 1946–2026, showing the current span. Beside
  it, a chip list of years outside the range, each chip removable, and a control to add
  one. Selecting a single year collapses to today's behaviour.
- **Variable**: unchanged.
- **Detail**: a slider with five positions, 1 h / 2 h / 3 h / 4 h / 6 h, labelled with
  both the step and the samples per day. Default 1 h, and it never moves on its own.
- **Legend**: always present for two or more series, rendering the real hue, shade and
  dash so identity is never colour-alone. Clicking an entry hides that year temporarily
  without deselecting it, which ECharts provides. With four or fewer series the lines
  are also directly labelled at their right-hand end.
- **Reset zoom**: unchanged, still governs the day window.
- The status line reports the year count, the resolved detail level and the gap count.

## 7. Module impact

Dependencies still point one way. The chart library stays inside `src/chart/`.

| File | Change |
|---|---|
| `src/model/series.ts` | `xKind: 'dayOfYear'`: map each year's hours onto a canonical year. A pure `resample(step)` using the per-variable aggregate from §5 (mean, sum, circular mean). |
| `src/model/scales.ts` | Unchanged. The y-range stays the variable's global range. |
| `src/model/style.ts` (new) | The year-to-hue/shade/dash function and the validated ramps. Pure, no DOM, no library. |
| `src/chart/adapter.ts` | `Series` gains `dash` and `color`. `ChartView` gains the legend flag. |
| `src/chart/echarts.ts` | Applies dash and colour, renders the legend, direct labels at four or fewer series. |
| `src/app/state.ts` | Unchanged shape; `years[]` is already plural. Gains `stepHours`. |
| `src/app/controls.ts` | The year slider, the chip list and the detail dropdown. |
| `src/data/*` | **Unchanged.** |
| `scripts/split_years.py` | Emits `aggregate` per variable in `meta.json`. |

## 8. Decisions taken 20260908

| # | Question | Chosen | Alternatives kept on record |
|---|---|---|---|
| A | 1946–2026 spans **nine decades**; the validated palette has **eight hues**, and generating a ninth is not allowed. | **Hue cycles modulo 8.** `hue = ((decade - 1940) / 10) mod 8`. The simplest rule and no special cases. Its cost, flagged before the choice and accepted: the 1940s and the 2020s land on the same hue, so a selection spanning both shows two decades in one colour. That is only reachable across the full 81-year span, which is past legibility for any encoding. | (i) The two partial decades share a hue — the 1940s has 4 years and the 2020s 7, so 11 of the 12 combinations, no collision; this was the recommendation. (iii) Cap the selectable span at eight decades. |
| B | 29 February on a shared Jan–Dec axis. | **Canonical leap year**: 366 slots, and a non-leap year shows a one-day gap at 29 February. Matches the existing rule that absent data is a gap, and never invents or discards a reading. | (ii) Canonical non-leap year, dropping 29 February from leap years and losing 24 real readings each time. |
| C | Does the day window survive a change to the year selection? | **Keep it.** Once the axis is day-of-year the window belongs to no particular year, so there is nothing to invalidate. | (ii) Reset it on every change. |

## 9. Steps

0. **Ships first, on its own, against today's single-year app**: the per-variable `aggregate` in `meta.json`, the pure `resample` function, and the 1 h–6 h slider. It is useful and testable without any of the multi-year work below.
1. `scripts/split_years.py`: add `aggregate` per variable, regenerate `meta.json`, confirm the chunks are byte-identical apart from that field.
2. `src/model/style.ts` and the aggregation functions, with the ramps for all eight hues generated and each run through the validator in both modes.
3. `xKind: 'dayOfYear'` in the model; adapter carries dash, colour and the legend.
4. Controls: year slider, chip list, detail dropdown.
5. Manual check in Chrome, then README and this plan's amendments section.

## 10. Out of scope

A sequential ramp above 24 years; the historical envelope behind the selected years;
small multiples; a heatmap view; overlaying two *variables*; sharing state in the URL.
Section 8 of the POC plan still maps each of these to one module.

## 11. What is still missing from this plan

- The eight hues' ramps are only worked out for blue. The other seven need generating
  from the same reference ramps and validating in both modes, which is step 2 above.
  Every generated ramp must pass the ordinal validator in both modes before it ships;
  if a hue cannot make four steps, it takes three and the fourth slot is unused.
- Whether the slider should later extend past 6 h. Nothing in the design prevents it;
  12 h and 24 h are measured in section 3 and are a one-line change to the step list.
  Left at 6 h because that is what was asked for.

## 12. Built 20260908 — what differed

Implemented on branch `20260908_2254-multi-year`. Sections 1 to 11 are left as
approved. What changed while building:

| # | Plan said | Built | Why |
|---|---|---|---|
| M1 | §7: `src/model/style.ts` holds "the year-to-hue/shade/dash function and the validated ramps" | Same, and the 64 colours are **generated** by a script against the validator rather than hand-picked | Only the blue ramp existed. The other seven were generated in OKLCH at fixed lightness targets and each checked programmatically. |
| M2 | §4: shades taken from the reference blue ramp's lightness | Ramps constrained to OKLab lightness **0.50–0.80** (light mode 0.50–0.72) | Measured: outside that window at least one of the eight hues drops below the 0.10 chroma floor and reads grey, or sinks into the surface. Two dark ramps additionally needed their dark end lifted 0.005 to clear 2:1. |
| M3 | §6: legend "always present for two or more series" | Also: legend icons are lines not blocks, and the legend ignores the opacity slider | A filled block hides the dash, and a legend that fades with the chart stops being the relief that a sub-3:1 line depends on. |
| M4 | §6: "with four or fewer series the lines are also directly labelled" | Labels carry the series colour and collide-hide | Three labels stacked at the same y is worse than none. |
| M5 | not specified | The tooltip switches from axis to item past six series, and drops the year on the shared axis | An axis tooltip would list all 36 years; and on the shared axis the year belongs to the series, not the x position. |
| M6 | not specified | The x-axis labels omit the year in day-of-year mode | Otherwise the canonical year 2024 appears on the axis for every selected year, which is a lie about the data. |
| M7 | §2 decision 5 as revised: a 1–6 h detail slider | The slider runs **1 h to 24 h**, one point per hour down to one per day | User request, 20260908, after seeing the overlay. Daily is the only step that removes the within-day swing completely: it falls from 6.4 °C at hourly to 4.2 °C at six-hourly, 1.9 °C at twelve and nothing at twenty-four. Still fully manual and still defaulting to hourly. |
| M7b | §2 decision 5 | The slider runs **1 h to 7 days**: 1, 2, 3, 4, 6, 8, 12 h then 1, 2, 4, 7 days | User request, 20260908, after seeing daily. Multi-day steps are what make a 30-year overlay readable: at one point a week each line is 52 points, 0.04 per pixel, against 6.90 at hourly. Correcting an earlier claim in this plan: past a day, resampling **does** move the years together, from a 10.7 °C spread at hourly to 6.4 °C at weekly, because averaging pulls each year toward the climatological mean. The 1–6 h measurement that said otherwise was right only over that range. A short final bucket is dropped for summed variables. |
| M8 | not specified | Legend and axis text take their colour from the page's own CSS tokens | ECharts paints text at a fixed dark grey, which was invisible on the dark surface. The legend was present but unreadable, and `icon: 'line'` is not a valid ECharts icon so the swatch was not drawn at all. Removing the icon lets ECharts draw the series' own line, which is what carries the dash. |

### Verified

- The style rule reproduces the worked example exactly: 2020–2022 one shade
  solid/dashed/dotted, 2023 a darker shade restarting at solid.
- Decision A holds: the 1940s and 2020s collide as chosen, the other eight decades
  are distinct.
- Decision B holds: 2024 gives 8,784 points, 2025 gives 8,761, and the extra one is
  a gap at 29 February. Both land inside the canonical year.
- All 16 ramps pass the ordinal checks; all 8 hues pass the categorical checks at
  every one of the 4 shade levels, in both modes.
- In Chrome: a 6-year range, adding and removing 1963 as a chip, three years with
  direct labels, zoom and pan across all selected years at once, and a 36-year
  selection which renders in about 12 seconds. Console clean throughout.

### Still not built

The sequential ramp above 24 years, the historical envelope, small multiples, a
heatmap view, overlaying two variables, and URL state. Section 10 stands.

## 13. Revised 20260909 — the year control, after using it

Sections 1 to 12 are left as approved and as built. Decision 1 (a two-knob range
slider, with a chip list only for years outside the range) was reported by the
user as two bugs, and both came from the same place.

**What was wrong.** A selection held as a range plus a set of extras has two
kinds of member, and only one of them was a chip. So a single selected year had
no chip at all, and adding a second year drew a chip for that one only, leaving
the first with nothing to remove it by. This was not an oversight in the build:
a range cannot express "1990 to 2000 without 1995", so the years it contributed
genuinely were not removable, and a chip for them would have been a lie. The two
knobs were the second bug — at a one-year selection they sit exactly on top of
each other, and which one a drag picks up is undefined.

**What replaced it.** The selection is a plain set of years. Every selected year
is a chip and every chip removes. The slider is replaced by a strip of one tick
per year, most recent on the left:

| Gesture | Effect |
|---|---|
| tap a tick | adds that year, or removes it if it is already shown |
| drag across ticks | adds every year swept, previewed live on the strip |
| a chip | removes that year |
| `only <year>` | drops every year but the most recent one selected |
| arrows / space / shift-arrow | move the cursor / toggle / sweep a span |

The selection can never be empty (user, 20260909): there would be nothing to look
at and nothing to say where you were. The gesture that would empty it does
nothing, in the drag preview as well as on release, and the last remaining chip
is drawn as a plain legend entry with no remove control. That is also why the
bulk control leaves one year rather than clearing: it names the year it keeps.
The app opens on the current year, which is partial until December.

No gesture needs a modifier key or a hover, because a phone has neither. Where
the strip does not fit it keeps a usable tick width and scrolls inside its track,
and its ticks grow taller for a coarse pointer.

**Corrected 20260909, after review.** The drag is not universal, and the claim
above that every gesture works with a finger was wrong. On a narrow screen the
strip overflows its track and `touch-action: pan-x` gives a horizontal swipe to
scrolling, which is how a finger reaches 1946; the browser cancels the pointer
when it takes the pan, so the sweep never runs. The trade is deliberate — the
old years have to be reachable — and tapping is the touch route to a multi-year
selection. The hint under the strip is now written from `(pointer: coarse)` so
it only ever promises the gesture the device actually has.

**Alternatives weighed and rejected, kept on record.** Two separate From and To
sliders, which the user suggested: it fixes the overlapping knobs but not the
chips, because the selection would still be a range. Keeping the two knobs and
hit-testing whichever is nearer the pointer: same objection. A tap that replaces
the selection with one year, with shift-click to add: one gesture fewer for
browsing, rejected because shift-click and the Add menu it would have kept are
both unavailable to a finger. A wrapped decade grid for narrow screens: better
per-target size than a scrolling strip, rejected because it needs a second
layout and a second set of row labels.

**Carried with it.** Decision 6, the legend, is now the chip list: HTML above the
plot rather than drawn in the canvas, one row instead of a legend and a set of
chips naming the same years. Each chip draws the year's real line and dash, which
was the point of M3. The variable name left the y axis, where rotated it took a
46px gutter, and joined the year summary in one horizontal title above the chart.
`TitleComponent` and `LegendComponent` are no longer registered.

**A trap worth recording.** A component that is not registered makes its option
silently do nothing: the title was configured correctly and simply never drawn
until `TitleComponent` was added to `echarts.use`. There is no warning.
