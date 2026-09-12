# EDA: Dublin Airport hourly weather, 1946-2026

Exploratory analysis of the Met Éireann Dublin Airport hourly series that this
repository visualises. Three documents on the series itself, written to be read
in order, plus one that measures chart forms against it, plus the code and data
that produce every number and figure in all four.

## The documents

| | Document | What it answers |
|---|---|---|
| 1 | **[Complete data review](01-data-review.md)** | What is in the file, and where it cannot be trusted |
| 2 | **[Temperature](02-temperature.md)** | Long-term warming, by year, season and decade, and the extremes |
| 3 | **[Precipitation](03-precipitation.md)** | The same questions asked of rainfall |
| 4 | **[Which chart form to build next](04-chart-forms.md)** | Six candidate charts measured against the series, to settle an open decision |

**Read document 1 first, or at least its
[data-quality register](01-data-review.md#10-data-quality-register).** The station
changed how it observes in September 1993, and the change moves eleven of the
thirteen variables. Documents 2 and 3 both depend on that register, and several
of their conclusions reverse if it is ignored.

## What the analysis found

- **The file is sound.** 706,369 hourly rows from 1946-01-01 to 2026-08-01 with
  no duplicate timestamps, no missing timestamps, and 306 null cells. Recomputing
  Met Éireann's published 1991-2020 normals from these rows reproduces the annual
  rainfall total to within 0.03%.
- **Temperature is rising at 0.098 to 0.145 °C per decade**, roughly 0.8 to
  1.2 °C across the record, with 2023 the warmest year and 2010 the coldest. The
  range is the same data read with and without a correction for the 1993 break.
- **Rainfall shows no detectable trend in anything.** Twelve measures tested,
  none significant, both the parametric and non-parametric tests agreeing on
  every one.
- **Overlaid year lines fail on ordering, and it is the pair count that grows,
  not the rate.** Any two years change places on about a quarter of all days at
  every year count from two to thirty, but the pairs on screen grow as N(N-1)/2,
  so expected crossings go from 0.3 a day at two years to 111 at thirty.
  Subtracting a day-of-year normal is proven not to change that, to three decimal
  places, because it takes the same number off every year. Document 4 measures
  six candidate replacements on that basis, and finds that temperature has the
  second lowest swap rate of seven variables, so it flattered the line chart.
- **A September 1993 discontinuity in the daily minimum temperature reverses
  three answers** that a straightforward analysis gets backwards: daily minima
  appear not to warm, frost days appear to increase, and the diurnal
  temperature range appears to grow. All three are the same artefact.

## Layout

```
EDA/
  01-data-review.md      the three documents on the series
  02-temperature.md
  03-precipitation.md
  04-chart-forms.md      the chart-form comparison
  figures/*.png          every chart, embedded by the documents
  stats/*.csv            every number the documents quote
  scripts/
    eda_common.py        loading, cleaning, the aggregation ladder, trend fitting
    eda_climate.py       the temperature and precipitation analyses
    eda_forms.py         the chart-form comparison
    eda_report.py        entry point
    eda_report.py.lock   pinned dependencies
```

## Regenerating

Requires [uv](https://docs.astral.sh/uv/); dependencies are declared inline in
`eda_report.py` and pinned in the sibling `.lock`, so nothing needs installing
first. Run from the repository root:

```
uv run EDA/scripts/eda_report.py --section all
```

`--section` also takes `review`, `temperature`, `precipitation` or `forms`
individually,
and `--csv` points at a different source file. The default is the committed
`data/dublin_airport-meteo-1946-2026-data.csv.gz`, which pandas decompresses by
extension, so there is nothing to unpack first.

A full run takes about 15 seconds. The first one takes longer while uv resolves
the pinned dependencies and matplotlib builds its font cache.

**Output is deterministic.** Same input, byte-identical figures and tables, so a
re-run does not churn git and a number that changes shows up as a real diff.

## How the documents stay honest

The scripts write every figure to `figures/` and every quoted number to
`stats/`. The prose is written by hand around them and is never generated. That
split is deliberate: generating the prose too would remove any chance of drift
but would make the narrative painful to edit, and these are documents meant to
be read. The safeguard is that a number changing in `stats/` shows up in the git
diff, so prose and data cannot disagree silently.

Every document names the command that regenerates its inputs and links the CSV
behind each table.

## Method

Every trend is estimated three ways, because the disagreements are informative:

- **Least squares**, with the confidence interval widened for lag-1
  autocorrelation. An annual weather series is not a set of independent draws,
  so the naive interval is too narrow and reports significance that is not there.
- **Mann-Kendall with Sen's slope**, non-parametric and robust to the skew and
  heavy tails that make least squares unreliable on rainfall.
- **LOESS**, at two spans, to show whether a straight line is the right
  description at all.

Any trend spanning September 1993 is additionally fitted with a joint
trend-plus-step model, which is the only one of these that can separate a
discontinuity from a slope. Anomalies are against the 1961-1990 WMO reference
period. 2026 is partial and is excluded from every annual statistic.

## Data

Met Éireann, Dublin Airport hourly observations, licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Met Éireann does not
accept any liability for its use. Indicator codes are interpreted using Met
Éireann's
[KeyHourly.txt](https://www.met.ie/cms/assets/uploads/2018/05/KeyHourly.txt);
the value 111, which covers 40% of the file, appears nowhere in it and is
discussed in [document 1 §4.1](01-data-review.md#41-an-undocumented-indicator-value-covers-40-of-the-file).
