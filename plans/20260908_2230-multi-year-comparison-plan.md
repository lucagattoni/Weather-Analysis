# Multi-year comparison — plan

Status: **draft for review, not approved** · written 20260908 22:30 UTC · branch `20260908_2230-multi-year-plan`

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
| 1 | Selecting years | A two-knob slider sets a start and end year. A chip list adds and removes individual years outside that range. |
| 2 | X axis | One shared Jan–Dec axis (`xKind: 'dayOfYear'`, the field already present and unused in `ChartAdapter`). |
| 3 | Day window | The existing day-range slider stays and applies to all overlaid years at once. Zooming to June–August shows that window for every selected year. |
| 4 | Colour | Hue from the decade; shade from the year's position in the decade divided by three; dash from that position modulo three. |
| 5 | Detail level | Rises with the year count: hourly to 3 years, daily mean to 12, monthly mean beyond, with a dropdown to override. |
| 6 | Legend | Always present for two or more series, showing the real line style. |

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

**Loading cost**, uncompressed: 2 years 0.7 MB, 5 years 2.1 MB, 10 years 4.4 MB,
20 years 9.1 MB. A further reason to aggregate rather than ship every hour.

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
- **Detail**: a new dropdown, Auto / Hourly / Daily mean / Monthly mean. Auto is the
  default and follows §2 decision 5. The resolved level is always visible.
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
| `src/model/series.ts` | `xKind: 'dayOfYear'`: map each year's hours onto a canonical year. New pure aggregation functions (mean, sum, circular mean) selected per variable. |
| `src/model/scales.ts` | Unchanged. The y-range stays the variable's global range. |
| `src/model/style.ts` (new) | The year-to-hue/shade/dash function and the validated ramps. Pure, no DOM, no library. |
| `src/chart/adapter.ts` | `Series` gains `dash` and `color`. `ChartView` gains the legend flag. |
| `src/chart/echarts.ts` | Applies dash and colour, renders the legend, direct labels at four or fewer series. |
| `src/app/state.ts` | Unchanged shape; `years[]` is already plural. Gains `detail`. |
| `src/app/controls.ts` | The year slider, the chip list and the detail dropdown. |
| `src/data/*` | **Unchanged.** |
| `scripts/split_years.py` | Emits `aggregate` per variable in `meta.json`. |

## 8. Open decisions — for the user

| # | Question | Options | Recommendation |
|---|---|---|---|
| A | 1946–2026 spans **nine decades**; the validated palette has **eight hues**, and generating a ninth is not allowed. | (i) The two partial decades share a hue: the 1940s has 4 years and the 2020s has 7, so 11 combinations of the 12 available, no collision. (ii) Hue cycles modulo 8, so the 1940s and 2020s collide, which is exactly the oldest-versus-newest comparison. (iii) Cap the selectable span at eight decades. | **(i)** — it costs one special case in the style function and never collides. |
| B | 29 February on a shared Jan–Dec axis. | (i) Canonical leap year: 366 slots, non-leap years show a one-day gap at 29 Feb. (ii) Canonical non-leap year: drop 29 Feb from leap years, losing 24 real readings per leap year. | **(i)** — it matches the existing rule that missing data is a gap and never invents or discards readings. |
| C | Does the day window survive a change to the year selection? | (i) Keep it: the window is in day-of-year, so it stays meaningful. (ii) Reset it. | **(i)** — the window no longer belongs to a particular year, so there is nothing to invalidate. |

## 9. Steps

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
- The three decisions in section 8 are unanswered.
- No estimate yet of whether monthly aggregation should be precomputed at build time
  rather than in the browser. At 81 years x 13 variables it is small, but it has not
  been measured, and the language boundary would put it at build time if it is slow.
