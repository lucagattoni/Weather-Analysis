# Temperature at Dublin Airport, 1946-2025: trends and anomalies

The second of three documents. It assumes the data-quality register in
[`01-data-review.md`](01-data-review.md) §10, in particular issue 6: temperature
steps across the September 1993 observation-practice change, and the step is
ambiguous between real warming and an instrument artefact. Resolving that
ambiguity turns out to be most of the work, and it changes three of the
headline answers.

Anomalies are against the **1961-1990** WMO reference period. 2026 is partial
and is excluded throughout, so "the record" means 1946-2025.

```
uv run EDA/scripts/eda_report.py --section temperature
```

## The short version

- **Dublin Airport has warmed by between 0.098 and 0.145 °C per decade**,
  roughly 0.8 to 1.2 °C across the record. The two figures are the same data
  read with and without a correction for the September 1993 break, and
  [§2.4](#24-does-the-artefact-reach-the-annual-mean) sets out why the corrected
  0.145 is the better of them.
- **The uncontaminated series agree with the corrected figure.** Daily maxima
  cross the break cleanly and warm at 0.157 °C per decade; daily minima
  corrected for their step warm at 0.137. Both sit near 0.145 and above 0.098.
- **Three findings a straightforward analysis would get backwards.** Daily
  minima appear not to warm at all, frost days appear to increase, and the
  diurnal temperature range appears to grow. All three are the same artefact,
  and all three reverse or vanish once it is accounted for.
- **The warming is a shift, not a spreading.** Every percentile of the daily
  distribution moves up by a similar amount; the standard deviation is
  essentially unchanged.
- 2023 is the warmest year on record and 2010 the coldest. Eight of the ten
  warmest years are 1989 or later; the exceptions are 1959 and 1949.

## 1. The annual series

![Annual mean temperature anomaly](figures/02-annual-anomaly.png)

The record runs cool through the 1950s and 1960s, rises through the 1980s and
1990s, flattens through the 2000s and 2010s, and rises sharply in the 2020s. The
2020s are the warmest decade by a clear margin.

| Decade | Mean (°C) | Anomaly vs 1961-1990 | Warmest year | Coldest year |
|---|---|---|---|---|
| 1940s (4 years) | 9.51 | -0.05 | 1949, 10.20 | 1947, 9.04 |
| 1950s | 9.35 | -0.20 | 1959, 10.24 | 1951, 8.76 |
| 1960s | 9.32 | -0.24 | 1961, 9.80 | 1963, 8.77 |
| 1970s | 9.61 | +0.05 | 1971, 10.06 | 1979, 8.92 |
| 1980s | 9.64 | +0.09 | 1989, 10.64 | 1986, 8.83 |
| 1990s | 9.85 | +0.29 | 1990, 10.47 | 1996, 9.00 |
| 2000s | 9.82 | +0.27 | 2006, 10.23 | 2001, 9.37 |
| 2010s | 9.67 | +0.11 | 2014, 10.09 | 2010, 8.45 |
| 2020s (6 years) | **10.33** | **+0.78** | 2023, 10.74 | 2020, 9.79 |

The 2010s dip is largely one year. 2010 is the coldest in the whole record, and
dropping it lifts the decade mean from 9.67 to 9.80 °C, level with the 1990s and
2000s. Whether a genuine pause appears at other stations is not something a
single record can say, and it was not checked.

Machine-readable: `EDA/stats/02-annual-anomaly.csv`, `EDA/stats/02-decades.csv`.

## 2. The 1993 break, and why it has to be handled first

This section exists because getting it wrong changes the sign of three answers.

### 2.1 The wrong way to ask

The obvious approach is to fit the whole record, then each side of the break,
and see whether they agree.

| Fit | Slope (°C/decade) | 95% CI | p |
|---|---|---|---|
| Whole record 1946-2025 | +0.098 | +0.049 to +0.147 | 0.0002 |
| Before the break 1946-1992 | +0.128 | +0.018 to +0.237 | 0.024 |
| After the break 1994-2025 | +0.201 | +0.002 to +0.399 | 0.048 |

![The three naive fits](figures/02-break-test.png)

All three are positive and significant, which looks reassuring. It is not
informative. A step and a trend are partly confounded: a jump halfway through a
record imitates a slope, and a slope imitates a jump. Comparing sub-period
slopes cannot separate them, and the fact that the whole-record slope is *lower*
than both sub-period slopes is a hint that something is going on that this
framing cannot name.

### 2.2 The right way

Fit the trend and the step together and let them compete for the same variance:

> temperature ~ intercept + trend × year + step × 1[year > 1993]

1993 itself is dropped, as a transition year with eight months before the break
and four after. Both p-values carry the same lag-1 autocorrelation correction
used everywhere else in these documents; without it the daily-minimum step reads
p = 2e-05 instead of the 0.001 below, which is more confidence than the evidence
supports.

| Series | Trend with the step in the model | Step at 1993 | 95% CI on the step | Step p |
|---|---|---|---|---|
| Annual mean | +0.145 °C/decade | -0.26 °C | -0.71 to +0.18 | 0.24 |
| Mean of daily maxima | +0.150 °C/decade | +0.04 °C | -0.44 to +0.51 | 0.87 |
| **Mean of daily minima** | **+0.137 °C/decade** | **-0.83 °C** | -1.32 to -0.35 | **0.001** |
| **Diurnal temperature range** | **+0.014 °C/decade** | **+0.87 °C** | +0.61 to +1.14 | **<1e-5** |

![Where the 1993 step lives](figures/02-step-diagnosis.png)

**The discontinuity is in the daily minimum and not the maximum.** The maximum
crosses September 1993 without a step worth mentioning. The minimum drops by
0.83 °C. The range between them jumps by 0.87 °C.

### 2.3 Is 1993 actually special, or would any year do?

A small p-value for a step at 1993 means nothing unless 1993 is unusual. Fitting
the same model at every candidate break year from 1955 to 2015 answers that.

| Series | Candidate years giving p < 0.05 | Best-fitting year | Rank of 1993 |
|---|---|---|---|
| Annual mean | 0 of 61 | 2015 | 2nd |
| Mean of daily maxima | 3 of 61 | 1962 | **57th** |
| Mean of daily minima | 10 of 61 | 1994 | **2nd** |
| Diurnal temperature range | 34 of 61 | 1994 | **3rd** |

Two things follow, and the second is a caution against the first.

- **1993 is genuinely the best-fitting break in the record** for the minimum and
  the range, out of sixty-one candidates, and it is one of the *worst* for the
  maximum at 57th. That specificity, landing on a date already known from the
  indicator flags to be an observation-practice change, is the real evidence.
- **The bare p-value is weaker than it looks.** For the diurnal range, a majority
  of all candidate years also clear 5%, because the series has genuine
  multi-decadal structure that a step term will always partly absorb. The case
  rests on the rank and the metadata correspondence, not on the size of the
  p-value.

### 2.4 Does the artefact reach the annual mean?

This is the question that decides the headline number, and the annual mean's own
step test cannot answer it: p = 0.24 is not evidence of absence when the trend
and step regressors are strongly collinear for a break two thirds of the way
through a record, and when averaging 24 hours dilutes a signal confined to some
of them while keeping all the noise.

Testing each fixed hour of the day separately is both more powerful and more
diagnostic.

![The step by hour of day](figures/02-hourly-step.png)

| Hours (UTC) | Step at 1993 | Significant at 5% |
|---|---|---|
| 20:00 to 04:00 | -0.41 to -0.78 °C | **9 of 9** |
| 08:00 to 14:00 | +0.09 to +0.25 °C | 0 of 7 |

**Nine of the twenty-four hours show an individually significant step, every one
of them negative, and they form a single unbroken block from 20:00 to 04:00.**
Roughly one hour would clear 5% by chance against the nine observed.

That count is not a formal test and is not offered as one: adjacent hours are
strongly correlated, so the twenty-four tests are nowhere near independent and
the arithmetic of a binomial does not apply. The evidence is the *pattern*
rather than the count, and it is the correlation between neighbouring hours that
makes a contiguous same-signed night block hard to get by accident.

Two conclusions follow.

- **The step is a night-time offset, not an artefact of tracking sharper
  minima.** Had a faster sensor merely been catching deeper pre-dawn dips, the
  daily minimum would move and fixed-hour means would not. Fixed-hour night
  means move, so something changed about night-time temperature itself, which
  points at the radiation screen or the siting rather than the response time.
- **The annual mean is affected.** The mean step across all 24 hours is
  **-0.262 °C**, which is the annual-mean step estimate to three decimals. The
  estimate is well determined; only its own significance test is underpowered.

**What this document does about it.** The headline trend is quoted from the
joint model at **+0.145 °C per decade**, and the naive +0.098 is stated beside
it throughout. That choice rests on the hourly evidence above, not on the
annual mean's own step test, which does not support it. A reader who rejects the
hourly argument should read +0.098 instead, and the two bracket the answer.

Two supporting checks point the same way. The daily maximum is uncontaminated on
every test here, and it warms at +0.157 °C per decade naively. The daily minimum
corrected for its step warms at +0.137. Both sit near the joint model's +0.145
and well above the naive annual figure of +0.098, which is what a downward
contamination of the mean would produce.

### 2.5 Why an instrument and not the climate

The evidence is circumstantial and the document states it as an inference.

- It is **instantaneous**, at a boundary already known to be an
  observation-practice change. Climate does not step in one month.
- It is **confined to the night**, with no daytime counterpart. No physical
  mechanism cools 20:00 to 04:00 by half a degree from one September while
  leaving noon untouched.
- It is **the best-fitting break year out of sixty-one** for the affected series
  and near the worst for the unaffected one.

The alternative, that Dublin's nights genuinely cooled 0.83 °C in one step in
September 1993 while its days did not, has no mechanism.

Machine-readable: `EDA/stats/02-break-test.csv`,
`EDA/stats/02-break-test-all-series.csv`,
`EDA/stats/02-placebo-break-scan.csv`, `EDA/stats/02-hourly-step.csv`.

## 3. Trends

Three estimates per series. Least squares gives the slope and an interval
widened for lag-1 autocorrelation; Mann-Kendall with Sen's slope is
non-parametric and robust; LOESS shows whether a straight line is the right
description at all. Where they agree the finding is solid.

| Series | OLS (°C/decade) | 95% CI | p | Sen | MK p | Agree |
|---|---|---|---|---|---|---|
| Annual mean | +0.098 | +0.049 to +0.147 | 0.0002 | +0.108 | <1e-4 | yes |
| Winter (DJF) | +0.124 | +0.009 to +0.239 | 0.035 | +0.129 | 0.009 | yes |
| Spring (MAM) | +0.094 | +0.021 to +0.168 | 0.013 | +0.106 | 0.013 | yes |
| Summer (JJA) | +0.109 | +0.045 to +0.173 | 0.001 | +0.107 | 0.002 | yes |
| Autumn (SON) | +0.059 | -0.009 to +0.128 | 0.089 | +0.049 | 0.156 | yes |
| Mean of daily maxima | +0.157 | +0.105 to +0.209 | <1e-4 | +0.168 | <1e-4 | yes |
| Mean of daily minima | -0.013 | -0.083 to +0.057 | 0.71 | -0.010 | 0.70 | yes |
| Diurnal range | +0.170 | +0.107 to +0.232 | <1e-5 | +0.173 | <1e-4 | yes |

**The last two rows of that table are wrong as descriptions of the climate**, and
they are left in because they are what the standard method produces. Corrected
for the 1993 step, daily minima warm at +0.137 °C per decade (p = 0.010) and
the diurnal range has no trend at all (+0.014 °C per decade, p = 0.63).

Once corrected, the picture is coherent and unremarkable: days and nights are
warming at almost the same rate, +0.150 and +0.137 °C per decade.

Three of the four seasons warm significantly. **Autumn does not** (p = 0.089),
and it is the one season where both tests agree there is no established trend.

![Temperature trend by season](figures/02-seasonal-trends.png)

Note that the seasonal panels use the naive fit, so their absolute values carry
the same caveat as the annual one. The comparison *between* seasons is unaffected,
since the step applies to all four equally.

Machine-readable: `EDA/stats/02-trends.csv`.

## 4. Is the distribution shifting or spreading?

A mean cannot distinguish the whole distribution sliding warmer from the tails
spreading while the middle stays put. The difference matters far more for
extremes than the change in the mean does. Percentiles of daily mean
temperature, 30 years at each end of the record:

| | mean | SD | p1 | p5 | p25 | p50 | p75 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|---|
| 1946-1975 | 9.42 | 4.36 | -0.32 | 2.09 | 6.19 | 9.56 | 12.93 | 16.08 | 17.87 |
| 1996-2025 | 9.86 | 4.43 | +0.11 | 2.47 | 6.60 | 9.96 | 13.40 | 16.60 | 18.61 |
| Change | +0.43 | +0.07 | +0.43 | +0.38 | +0.40 | +0.40 | +0.47 | +0.51 | +0.74 |

![Daily temperature distribution, two periods](figures/02-distribution-shift.png)

**This is a shift, not a spreading.** Every percentile from the 1st to the 95th
moves up by 0.38 to 0.51 °C, and the standard deviation grows by 0.07 °C, which
is nothing. The 99th percentile moves further, by 0.74 °C, which is a hint of
extra warming in the extreme upper tail, but one percentile is thin evidence and
this document does not build on it.

Machine-readable: `EDA/stats/02-distribution-shift.csv`.

## 5. Threshold day counts

![Threshold day counts](figures/02-thresholds.png)

These are counts of days whose **hourly** extremes cross a threshold. An hourly
series misses a brief peak between readings, so every count is a slight
underestimate of what a max/min thermometer would record. The bias is
one-directional and roughly constant, so trends survive it better than absolute
values do.

Two of the four counts are built on the daily minimum and therefore inherit its
1993 discontinuity. Testing each the same way:

| Count | Naive change, 1946-1975 to 1996-2025 | Trend with the step in the model | Step at 1993 | Step p |
|---|---|---|---|---|
| **Frost days (Tmin < 0)** | **22.9 → 30.7, rising** | **-2.32 days/decade, p = 0.034** | **+18.2 days** | **0.0006** |
| Ice days (Tmax < 0) | 0.4 → 0.5 | -0.03 days/decade, p = 0.77 | +0.23 | 0.68 |
| Warm days (Tmax ≥ 20) | 17.1 → 26.7 | +2.92 days/decade, p = 0.006 | -4.75 | 0.33 |
| Summer days (Tmax ≥ 25) | 0.2 → 1.1 | +0.25 days/decade, p = 0.090 | -0.17 | 0.80 |

**Frost days are the trap.** Read naively the record says Dublin gains eight
frost days a year while warming, which should stop any reader. It is entirely
the artefact: an artificial 0.83 °C drop in daily minima pushes borderline
nights below zero, and the fitted step of +18.2 days is highly significant. With
the step in the model, frost days **fall** by 2.32 per decade, which is what
warming predicts.

The two maximum-based counts have no significant step and can be read directly.
**Warm days above 20 °C rise by 2.9 per decade**, from about 17 a year in the
first thirty years to about 27 in the last thirty. Summer days above 25 °C are
too rare at this station to establish a trend (p = 0.090), at about one a year
now against one every five years then.

Machine-readable: `EDA/stats/02-thresholds.csv`,
`EDA/stats/02-break-test-thresholds.csv`.

## 6. Extremes and anomaly register

**Records.** The highest hourly reading is **29.1 °C on 2022-07-18**; the lowest
is **-11.5 °C on 2010-12-25**.

| Rank | Warmest years | Anomaly | Coldest years | Anomaly |
|---|---|---|---|---|
| 1 | 2023, 10.74 °C | +1.19 | 2010, 8.45 °C | -1.10 |
| 2 | 2025, 10.67 °C | +1.12 | 1951, 8.76 °C | -0.79 |
| 3 | 1989, 10.64 °C | +1.08 | 1963, 8.77 °C | -0.78 |
| 4 | 1990, 10.47 °C | +0.91 | 1986, 8.83 °C | -0.73 |
| 5 | 2022, 10.42 °C | +0.87 | 1962, 8.86 °C | -0.70 |

Warmest and coldest **months**, by anomaly against the 1961-1990 mean for that
calendar month:

| Rank | Warmest month | Anomaly | Coldest month | Anomaly |
|---|---|---|---|---|
| 1 | March 1957 | +3.02 | December 2010 | **-5.67** |
| 2 | April 2007 | +2.94 | February 1947 | -4.63 |
| 3 | February 1998 | +2.92 | January 1963 | -4.05 |
| 4 | November 2011 | +2.88 | December 1950 | -3.84 |
| 5 | December 2015 | +2.74 | February 1986 | -3.32 |

**December 2010 is the most extreme month in the record by a wide margin**, at
5.67 °C below its baseline and 1.0 °C further out than the next entry. It also
contains the record low and makes 2010 the coldest year. Note that a cold-side
monthly anomaly of that size sits in a period where the daily-minimum artefact
is active, but the monthly *mean* is not materially affected, since the annual
mean step is not significant.

The warm and cold lists are not symmetric in time. Four of the five warmest years
are from 1989 onward; four of the five coldest are from 1986 or earlier, with
2010 the exception.

Machine-readable: `EDA/stats/02-extremes.csv`.

## 7. What this document does not establish

- **Attribution.** Nothing here says why the station warmed. A single
  airport record cannot separate global forcing from regional circulation
  change or from local effects such as growth of the airport itself.
- **The cause of the 1993 step.** The evidence that it is instrumental is
  circumstantial. Met Éireann station metadata would settle it and has not been
  consulted.
- **Anything about the daily minimum before and after together.** The corrected
  trend of +0.138 °C per decade assumes the step is a single instantaneous
  offset. If the change was gradual, or if the sensor response changed again
  later, that number is wrong in a way this test cannot detect.
- **Extreme-value statistics.** Return periods for extreme heat or cold need a
  fitted extreme-value distribution, not the percentile counts used here.
- **Sub-daily behaviour.** Daily minima and maxima are hourly extremes, not
  thermometer extremes.

---

*Data: Met Éireann, Dublin Airport hourly observations, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Met Éireann does not
accept any liability for its use.*
