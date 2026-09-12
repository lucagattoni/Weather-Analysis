"""Measure how well four chart forms separate years, for `EDA/04-chart-forms.md`.

Run through the report entry point:

    uv run EDA/scripts/eda_report.py --section forms

The app draws overlaid lines on a fixed y-scale. That works for two or three
years and stops working well before twenty, because the between-year difference
is small next to a single year's own swing. Four forms were proposed as the next
chart and two more were already deferred in the multi-year plan; this module
measures all six against the real series so the choice is made on numbers rather
than on which one sounds best.

The governing measure is **separation**: the median vertical distance between
the highest and lowest selected year, as a fraction of the axis the form needs.
A form that halves the axis without shrinking the differences doubles what a
pixel is worth. Every number the document quotes is written to `EDA/stats/`.

One caveat runs through all of it. The station changed how it observes in
September 1993 and that moves eleven of the thirteen variables
(`EDA/01-data-review.md` section 10). Any measurement spanning that date carries
the step as well as the climate, so the two long-window numbers below are
reported for the post-1993 era as well as for the whole series, and the document
quotes both.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from eda_common import (
    GRID,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    NORMALS,
    SERIES,
    clean,
    daily,
    load_raw,
    save_fig,
    save_table,
)

# The window the app's own README uses when it talks about comparing years, and
# the one the figures draw. Ten years is past the point where overlaid hourly
# lines stop being readable, which is the problem these forms exist to solve.
DEMO_YEARS = (2016, 2025)

# A representative wide plot. Used only to turn a count of cells into a cell
# size, so the heatmap's claim is about pixels and not about arithmetic.
# Days per column in the four-way figure's monthly heatmap.
BUCKET_DAYS = 30


def bucket_index(doy: pd.Series, step: int) -> pd.Series:
    """Day of year to cell index, with the short final cell merged backwards.

    `(doy - 1) // step` leaves a remainder cell wherever step does not divide
    365: five days at a month, and a single day at a week and at a season. A
    one-day cell labelled "one season" is not a season. It is averaged over
    ninety times fewer days than the cells beside it, so it is far noisier, and
    it was carrying real weight: it doubled the season row's cell noise and
    moved trend-over-cell-noise from 0.53 to 0.42 at that step. Clamping the
    index folds those days into the last full cell instead.
    """
    return np.minimum((doy - 1) // step, 365 // step - 1)
PLOT_WIDTH_PX = 1200
PLOT_HEIGHT_PX = 520

# Where the app's fixed temperature axis sits, from `public/data/meta.json`
# rounded outward the way `src/model/scales.ts` rounds it.
APP_TEMP_AXIS = (-15.0, 30.0)

def doc02_joint_fit() -> tuple[float, float]:
    """Document 2's joint trend-plus-step fit, read from its own table.

    The trend once a step at 1993 is in the model, and the step itself. The step
    is NEGATIVE, so it holds the whole-series difference down rather than
    propping it up. It is not significant on the annual mean on its own
    (p = 0.242); document 2 section 2.4 makes the case from the hour-by-hour
    decomposition instead.

    Read rather than copied. Two literals here would be right today and silently
    stale the next time document 2 is regenerated against another year of data,
    which is the same class of bug as hardcoding the number of years in the
    archive. Missing or unparseable is an error, not a default.
    """
    table = pd.read_csv(STATS / "02-break-test.csv", index_col=0)
    rows = [i for i in table.index if "Joint" in str(i)]
    if not rows:
        raise ValueError("02-break-test.csv has no joint trend-plus-step row")
    row = table.loc[rows[0]]
    trend = float(row["OLS slope (degC/decade)"])
    match = re.search(r"step\s+(-?\d+\.\d+)\s*degC", str(row["verdict"]))
    if not match:
        raise ValueError(f"cannot read the 1993 step from: {row['verdict']!r}")
    return trend, float(match.group(1))


def _day_of_year(index: pd.DatetimeIndex) -> np.ndarray:
    """Day of year with 29 February folded onto 28 February.

    The app puts every year on one canonical leap year, so a non-leap year's
    1 March and a leap year's 1 March are the same x. Folding rather than
    dropping keeps all 365 or 366 readings and costs one shared slot.
    """
    doy = np.asarray(index.dayofyear)
    leap = np.asarray(index.is_leap_year)
    # `>= 60`, not `> 60`. In a leap year 29 February is day 60 and 1 March is
    # day 61; shifting only the days after 29 February left 29 February sitting
    # on day 60, which is 1 March in every other year, so the two were averaged
    # together. Shifting from day 60 puts 29 February on 28 February, which is
    # what this function claims to do, and lands 1 March on 1 March.
    return np.where(leap & (doy >= 60), doy - 1, doy)


def _daily_temp(clean_df: pd.DataFrame) -> pd.DataFrame:
    day = daily(clean_df, "temp")
    day = day.loc[day["mean"].notna()].copy()
    day["doy"] = _day_of_year(day.index)
    return day


def _matrix(day: pd.DataFrame, lo: int, hi: int, column: str = "mean") -> pd.DataFrame:
    """Years down, day-of-year across, for the years in [lo, hi]."""
    window = day.loc[(day["year"] >= lo) & (day["year"] <= hi)]
    return window.pivot_table(index="year", columns="doy", values=column, aggfunc="mean")


def _separation(matrix: pd.DataFrame) -> tuple[float, float]:
    """Median and mean of (max - min) across years, per day of year.

    This is the quantity every form is trying to make visible: on a given day,
    how far apart are the years being compared.
    """
    spread = matrix.max(axis=0) - matrix.min(axis=0)
    spread = spread.dropna()
    return float(spread.median()), float(spread.mean())


def _axis_span(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    return float(finite.max() - finite.min())


def table_separation(day: pd.DataFrame) -> pd.DataFrame:
    """Separation and required axis for raw daily values against anomalies.

    The anomaly is the daily value minus the 1991-2020 normal for that day of
    year, so it removes the seasonal cycle, which is the single largest thing on
    the raw axis and the one thing every year has in common.
    """
    normals = (
        day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
        .groupby("doy")["mean"]
        .mean()
    )
    day = day.copy()
    day["anomaly"] = day["mean"] - day["doy"].map(normals)

    rows = []
    for count in (2, 3, 5, 10, 20, 30):
        hi = DEMO_YEARS[1]
        lo = hi - count + 1
        raw = _matrix(day, lo, hi, "mean")
        ano = _matrix(day, lo, hi, "anomaly")
        raw_sep, _ = _separation(raw)
        ano_sep, _ = _separation(ano)
        raw_axis = _axis_span(raw.to_numpy())
        ano_axis = _axis_span(ano.to_numpy())
        rows.append({
            "years": count,
            "window": f"{lo}-{hi}",
            "raw_separation_c": raw_sep,
            "raw_axis_span_c": raw_axis,
            "raw_separation_pct_of_axis": 100.0 * raw_sep / raw_axis,
            "anomaly_separation_c": ano_sep,
            "anomaly_axis_span_c": ano_axis,
            "anomaly_separation_pct_of_axis": 100.0 * ano_sep / ano_axis,
        })
    out = pd.DataFrame(rows).set_index("years")
    return out


def table_app_axis(day: pd.DataFrame) -> pd.DataFrame:
    """What the app's own fixed axis costs, against an axis fitted to the data.

    The app fixes the temperature axis at the variable's global range so that
    changing the year never rescales the plot. That is the right call for
    comparability and it is also why a ten-year overlay uses so little of the
    plot height.
    """
    lo, hi = DEMO_YEARS
    raw = _matrix(day, lo, hi, "mean")
    used = _axis_span(raw.to_numpy())
    app_span = APP_TEMP_AXIS[1] - APP_TEMP_AXIS[0]
    sep, _ = _separation(raw)
    normals = (
        day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
        .groupby("doy")["mean"]
        .mean()
    )
    ano = _matrix(day.assign(anomaly=day["mean"] - day["doy"].map(normals)),
                  lo, hi, "anomaly")
    ano_span = _axis_span(ano.to_numpy())
    rows = [
        {"axis": "app fixed (meta.json, rounded)", "span_c": app_span,
         "separation_c": sep, "separation_pct_of_axis": 100.0 * sep / app_span},
        {"axis": "fitted to the ten years drawn", "span_c": used,
         "separation_c": sep, "separation_pct_of_axis": 100.0 * sep / used},
        {"axis": "anomaly, fitted", "span_c": ano_span,
         "separation_c": _separation(ano)[0],
         "separation_pct_of_axis": 100.0 * _separation(ano)[0] / ano_span},
    ]
    return pd.DataFrame(rows).set_index("axis")


def table_warming(day: pd.DataFrame) -> pd.DataFrame:
    """The long-term signal a heatmap is uniquely able to show, and its caveat.

    Reported twice: across the whole series, where the September 1993 change of
    practice is inside the window, and across the post-1993 era only, where it
    is not. The document quotes both and says which is which. If the two
    disagree badly, the whole-series number is measuring the instrument.
    """
    trend_per_decade, _step = doc02_joint_fit()
    annual_mean = day.groupby("year")["mean"].mean()
    complete = day.groupby("year")["mean"].count() >= 350
    annual_mean = annual_mean.loc[complete]

    rows = []
    for label, series, block in (
        ("whole series, first and last 30", annual_mean, 30),
        ("post-1993 only, first and last 15",
         annual_mean.loc[annual_mean.index >= 1994], 15),
    ):
        span = len(series)
        third = min(block, span // 2)
        early = series.iloc[:third]
        late = series.iloc[-third:]
        # The two windows are not the same distance apart, so their differences
        # are not comparable as they stand. Reporting the gap between the window
        # centres, and what this project's fitted trend alone would predict over
        # that gap, is what makes them comparable.
        gap_years = float(late.index.to_series().mean() - early.index.to_series().mean())
        rows.append({
            "window": label,
            "years_used": span,
            "early_period": f"{int(early.index.min())}-{int(early.index.max())}",
            "late_period": f"{int(late.index.min())}-{int(late.index.max())}",
            "early_mean_c": float(early.mean()),
            "late_mean_c": float(late.mean()),
            "difference_c": float(late.mean() - early.mean()),
            "pct_of_app_axis": 100.0 * float(late.mean() - early.mean())
            / (APP_TEMP_AXIS[1] - APP_TEMP_AXIS[0]),
            "years_between_window_centres": gap_years,
            "trend_implied_c": trend_per_decade * gap_years / 10.0,
            "measured_minus_trend_implied_c": float(late.mean() - early.mean())
            - trend_per_decade * gap_years / 10.0,
        })
    return pd.DataFrame(rows).set_index("window")


def _swap_rate(matrix: pd.DataFrame, ties: str = "drop") -> float:
    """Share of days on which a pair of years swaps which one is on top.

    Averaged over every pair. A line the eye can follow keeps its place; one
    that changes places with its neighbours on a quarter of all days cannot be
    followed by position, only by colour.

    `ties` decides what to do with days the two years record identically, which
    for temperature is a rounding coincidence and for rain is two dry days.
    Both readings are defensible and they differ by several points where ties
    are common, so both are reported rather than one chosen silently:

      drop   remove tied days and compare what is left, so a tie is invisible
      hold   a tie leaves the leader unchanged, so it cannot be a swap
    """
    swaps = []
    years = list(matrix.index)
    for i, a in enumerate(years):
        for b in years[i + 1:]:
            diff = (matrix.loc[a] - matrix.loc[b]).to_numpy()
            diff = diff[np.isfinite(diff)]
            sign = np.sign(diff)
            if ties == "drop":
                sign = sign[sign != 0]
            else:
                # Carry the last non-zero sign forward across the ties.
                carried, last = [], 0.0
                for v in sign:
                    if v != 0:
                        last = v
                    carried.append(last)
                sign = np.array([v for v in carried if v != 0])
            if sign.size >= 2:
                swaps.append(float((np.diff(sign) != 0).mean()))
    return 100.0 * float(np.mean(swaps)) if swaps else float("nan")


def table_occlusion(day: pd.DataFrame) -> pd.DataFrame:
    """Why more vertical resolution does not, on its own, make lines readable.

    Two quantities decide whether overlaid lines can be followed:

      separation  how far apart the years are on a given day
      roughness   how far a single year moves from one day to the next

    When roughness is larger than separation the lines cross each other
    constantly, and stretching the axis stretches the crossings with them. This
    is the measurement that separates "the difference is too small to see" from
    "the lines cannot be told apart", which are different problems with
    different answers.
    """
    normals = (
        day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
        .groupby("doy")["mean"]
        .mean()
    )
    work = day.assign(anomaly=day["mean"] - day["doy"].map(normals))

    rows = []
    for count in (2, 3, 5, 10, 20, 30):
        hi = DEMO_YEARS[1]
        lo = hi - count + 1
        matrix = _matrix(day, lo, hi, "mean")
        anomaly = _matrix(work, lo, hi, "anomaly")
        sep, _ = _separation(matrix)
        # Day-over-day movement within each year, then the median across years.
        roughness = float(np.nanmedian([
            np.nanmedian(np.abs(np.diff(matrix.loc[year].to_numpy())))
            for year in matrix.index
        ]))
        # How often the ordering of two years swaps from one day to the next,
        # averaged over every pair. A line you can follow rarely swaps.
        rows.append({
            "years": count,
            "window": f"{lo}-{hi}",
            "separation_c": sep,
            # Separation is the range across years, and every window here is a
            # superset of the one before it, so it can only climb as years are
            # added: that climb is arithmetic, not a finding. The standard
            # deviation across years on the same day does not have that
            # property, and is the honest measure of how spread out they are.
            "cross_year_sd_c": float(_matrix(day, lo, hi, "mean")
                                     .std(axis=0, ddof=1).median()),
            "roughness_c": roughness,
            "roughness_over_separation": roughness / sep if sep else float("nan"),
            # A flat rate per PAIR is not a flat amount of tangle: the number
            # of pairs on screen grows as N(N-1)/2, so the crossings a reader
            # has to disentangle grow with it even though the rate does not.
            "pairs_on_screen": count * (count - 1) // 2,
            "expected_crossings_per_point": (count * (count - 1) // 2)
            * _swap_rate(matrix) / 100.0,
            "pct_days_pair_swaps_raw": _swap_rate(matrix),
            # Subtracting a day-of-year normal takes the same number off every
            # year on a given day, so it cannot change which year is above
            # which. This column exists to hold that claim to the data rather
            # than to assert it: it must equal the one before it.
            "pct_days_pair_swaps_anomaly": _swap_rate(anomaly),
        })
    return pd.DataFrame(rows).set_index("years")


def table_anchor_sweep(day: pd.DataFrame) -> pd.DataFrame:
    """The same measurements from several end-years, not just from 2025.

    Every other table is anchored at 2025 and extends backwards, which is a
    choice, and a conclusion that only holds for the most recent decade would be
    a weak basis for a build decision. Three of these windows deliberately
    straddle September 1993, so the observation change is inside them.
    """
    rows = []
    windows = [
        ("2006-2025", 2006, 2025),
        ("1986-2005", 1986, 2005),
        ("1983-2002", 1983, 2002),
        ("1978-1997", 1978, 1997),
        ("1966-1985", 1966, 1985),
        ("1946-1965", 1946, 1965),
    ]
    for label, lo, hi in windows:
        matrix = _matrix(day, lo, hi, "mean")
        sep, _ = _separation(matrix)
        roughness = float(np.nanmedian([
            np.nanmedian(np.abs(np.diff(matrix.loc[year].to_numpy())))
            for year in matrix.index
        ]))
        rows.append({
            "window": label,
            "years": int(len(matrix.index)),
            "crosses_1993": lo <= 1993 <= hi,
            "separation_c": sep,
            "roughness_c": roughness,
            "cross_year_sd_c": float(matrix.std(axis=0, ddof=1).median()),
            "pct_days_pair_swaps": _swap_rate(matrix),
        })
    return pd.DataFrame(rows).set_index("window")


def table_resolution(day: pd.DataFrame) -> pd.DataFrame:
    """Does the app's own detail slider already fix this?

    Every other measurement here is at one point per day. The app can resample
    down to one point per week, and its README calls daily to weekly the useful
    range for a wide selection, so daily is the fine end of what it recommends
    rather than something it warns against. Measuring only there still judges
    the line chart at one end of its range. If coarser steps drop the swap rate
    far enough, the slider is already most of the answer and the argument for a
    new chart form is correspondingly weaker.
    """
    lo, hi = DEMO_YEARS[1] - 9, DEMO_YEARS[1]
    rows = []
    # The app's slider stops at one point per week (`STEP_HOURS` in
    # src/model/resample.ts tops out at 168 hours). Four weeks is past what it
    # can do and is marked as such, so the table cannot be read as if the app
    # offered it.
    for label, step in (("1 day", 1), ("2 days", 2), ("4 days", 4),
                        ("1 week", 7), ("4 weeks (beyond the slider)", 28)):
        work = day.loc[(day["year"] >= lo) & (day["year"] <= hi)].copy()
        work["bucket"] = bucket_index(work["doy"], step)
        matrix = work.pivot_table(index="year", columns="bucket", values="mean",
                                  aggfunc="mean")
        sep, _ = _separation(matrix)
        rate = _swap_rate(matrix)
        points = int(matrix.shape[1])
        rows.append({
            "step": label,
            "points_per_year": points,
            "separation_c": sep,
            "cross_year_sd_c": float(matrix.std(axis=0, ddof=1).median()),
            "pct_points_pair_swaps": rate,
            # The rate and the count point opposite ways, and both are real: a
            # coarser line swaps on a larger share of its points but has far
            # fewer points, so there is less tangle on screen in absolute terms.
            "crossings_per_pair_per_year": rate / 100.0 * points,
        })
    return pd.DataFrame(rows).set_index("step")


def table_variables(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Is the swap rate a fact about temperature, or about the series?

    The recommendation generalises to an app with thirteen variables, so it
    should not rest on one of them. Rain and sunshine are summed rather than
    averaged and a great many of their days are exactly equal at zero, which
    makes "which year is on top" ill-defined; they are reported anyway, with
    the share of tied points, so the reader can see why they behave differently.
    """
    lo, hi = DEMO_YEARS[1] - 9, DEMO_YEARS[1]
    rows = []
    for key in ("temp", "rhum", "msl", "wdsp", "vis", "rain", "sun"):
        var_day = daily(clean_df, key)
        var_day = var_day.loc[var_day["mean"].notna()].copy()
        if var_day.empty:
            continue
        var_day["doy"] = _day_of_year(var_day.index)
        matrix = _matrix(var_day, lo, hi, "mean")
        if matrix.empty or len(matrix.index) < 2:
            continue
        ties = []
        years = list(matrix.index)
        for i, a in enumerate(years):
            for b in years[i + 1:]:
                diff = (matrix.loc[a] - matrix.loc[b]).to_numpy()
                diff = diff[np.isfinite(diff)]
                if diff.size:
                    ties.append(float((diff == 0).mean()))
        rows.append({
            "variable": key,
            "aggregate": "sum" if key in ("rain", "sun") else "mean",
            "separation": _separation(matrix)[0],
            "cross_year_sd": float(matrix.std(axis=0, ddof=1).median()),
            "pct_days_pair_swaps": _swap_rate(matrix),
            "pct_days_pair_swaps_ties_hold": _swap_rate(matrix, ties="hold"),
            "pct_days_tied": 100.0 * float(np.mean(ties)) if ties else float("nan"),
        })
    return pd.DataFrame(rows).set_index("variable")


def table_heatmap_signal(day: pd.DataFrame) -> pd.DataFrame:
    """Can a heatmap actually show the long-run shift, and at what cell size?

    The heatmap is recommended partly because a +0.43 C shift across eighty
    years is invisible on a line chart. That is only an argument for it if the
    shift is visible in the colour, and colour has to compete with the noise in
    the cells: a day's anomaly swings several degrees, so at one cell per day a
    0.43 C difference is a small fraction of the range the scale must cover.
    Aggregating the cells cuts the noise without touching the signal.

    The ratio below is the first-to-last-thirty-years difference over the
    standard deviation of the cell values. Below about 1 it is hopeless, and a
    reader sees speckle; well above it the shift reads as a change in colour.
    """
    normals = (
        day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
        .groupby("doy")["mean"]
        .mean()
    )
    work = day.assign(anomaly=day["mean"] - day["doy"].map(normals))
    complete = work.groupby("year")["mean"].count()
    complete = complete.loc[complete >= 350].index
    work = work.loc[work["year"].isin(complete)]

    rows = []
    for label, step in (("1 day", 1), ("1 week", 7), ("1 month", 30),
                        ("1 season", 91)):
        buckets = work.copy()
        buckets["bucket"] = bucket_index(buckets["doy"], step)
        matrix = buckets.pivot_table(index="year", columns="bucket",
                                     values="anomaly", aggfunc="mean")
        early = matrix.loc[matrix.index[:30]].to_numpy()
        late = matrix.loc[matrix.index[-30:]].to_numpy()
        signal = float(np.nanmean(late) - np.nanmean(early))
        noise = float(np.nanstd(matrix.to_numpy()))
        # A single cell is not the only thing a reader sees. The eye averages
        # along a row, so an unusual year can be legible as a row even where the
        # slow trend across rows is not. These are two questions with different
        # answers and the document has to give both.
        #
        # Dividing the cell noise by the root of the cell count would assume the
        # cells in a row are independent, and they are not: one warm day is
        # followed by another. This project already has a convention for that,
        # `fit_trend` in eda_common, and it is used here rather than invented:
        # n_eff = n (1 - r1) / (1 + r1), with r1 the lag-1 autocorrelation along
        # the row. At one cell per day r1 is around 0.7 and the effective count
        # is a fifth of the nominal one, which matters a great deal to the
        # answer.
        year_means = np.nanmean(matrix.to_numpy(), axis=1)
        r1s = []
        for row in matrix.to_numpy():
            row = row[np.isfinite(row)]
            if row.size > 3:
                r1s.append(float(np.corrcoef(row[:-1], row[1:])[0, 1]))
        r1 = float(np.nanmedian(r1s)) if r1s else 0.0
        r1 = min(max(r1, 0.0), 0.99)
        n = matrix.shape[1]
        n_eff = max(n * (1.0 - r1) / (1.0 + r1), 3.0)
        row_noise = noise / np.sqrt(n_eff)
        rows.append({
            "cell": label,
            "cells_per_year": int(n),
            "trend_signal_c": signal,
            "cell_noise_sd_c": noise,
            "trend_over_cell_noise": signal / noise if noise else float("nan"),
            "year_to_year_sd_c": float(np.nanstd(year_means)),
            "lag1_along_row": r1,
            "effective_cells_per_row": n_eff,
            "row_noise_sd_c": float(row_noise),
            "year_over_row_noise": float(np.nanstd(year_means) / row_noise),
        })
    return pd.DataFrame(rows).set_index("cell")


def fig_heatmap_detail(day: pd.DataFrame) -> None:
    """The same eighty years of anomaly at one cell per day and one per month."""
    normals = (
        day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
        .groupby("doy")["mean"]
        .mean()
    )
    work = day.assign(anomaly=day["mean"] - day["doy"].map(normals))
    complete = work.groupby("year")["mean"].count()
    complete = complete.loc[complete >= 350].index
    work = work.loc[work["year"].isin(complete)]

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.6))
    for ax, (label, step) in zip(axes, (("one cell per day", 1),
                                        ("one cell per month", 30))):
        buckets = work.copy()
        buckets["bucket"] = bucket_index(buckets["doy"], step)
        matrix = buckets.pivot_table(index="year", columns="bucket",
                                     values="anomaly", aggfunc="mean")
        limit = float(np.nanpercentile(np.abs(matrix.to_numpy()), 99))
        im = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="RdBu_r",
                       vmin=-limit, vmax=limit,
                       extent=(0, matrix.shape[1],
                               float(matrix.index.max()) + 0.5,
                               float(matrix.index.min()) - 0.5))
        ax.set_title(f"{label} ({matrix.shape[1]} per year)", color=INK, fontsize=10)
        ax.set_ylabel("year", color=INK_SECONDARY)
        ax.set_xticks([])
        fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="°C from normal")
    fig.tight_layout()
    save_fig(fig, FIGURES / "04-heatmap-detail.png")


def table_small_multiples(day: pd.DataFrame) -> pd.DataFrame:
    """One small panel per year, which the roadmap already named.

    It removes occlusion exactly as the heatmap does, because no two years share
    a panel. It is not free reuse of the existing line chart: ChartView carries
    one x-range, one list of y-axes and one list of series, so N panels need a
    multi-grid shape for that contract or N synchronised instances. What it
    spends instead is panel area, and comparing two years becomes a matter of
    looking from one panel to another rather than at one line against another.
    """
    rows = []
    for count in (4, 10, 30, 80):
        cols = int(np.ceil(np.sqrt(count)))
        panel_rows = int(np.ceil(count / cols))
        rows.append({
            "years": count,
            "grid": f"{cols} x {panel_rows}",
            "panel_width_px": PLOT_WIDTH_PX / cols,
            "panel_height_px": PLOT_HEIGHT_PX / panel_rows,
            # The panel's real share of the plot, which is 1/slots and not
            # 1/count: a grid that does not divide evenly leaves empty slots
            # and every panel is smaller than 1/N would suggest.
            "panel_area_share_pct": 100.0 / (cols * panel_rows),
        })
    return pd.DataFrame(rows).set_index("years")


def table_heatmap_cells(day: pd.DataFrame) -> pd.DataFrame:
    """Cell size for a heatmap of years by day of year, at a real plot size."""
    # Count the complete years rather than subtracting the first year from the
    # last. The archive ends in a partial 2026, so `max - min` happens to give
    # 80 today only because the missing "+1" cancels that partial year; append
    # one more year of data and it would quietly be wrong again, which is the
    # bug this line already had once. The column count is 365 because the
    # leap-day fold shares 28 and 29 February.
    columns = int(day["doy"].max())
    per_year = day.groupby("year")["mean"].count()
    full = int((per_year >= 350).sum())
    rows = []
    for count in (10, 30, full):
        hi = DEMO_YEARS[1]
        lo = hi - count + 1
        rows.append({
            "years": count,
            "columns": columns,
            "cells": count * columns,
            "cell_width_px": PLOT_WIDTH_PX / columns,
            "cell_height_px": PLOT_HEIGHT_PX / count,
            "window": f"{lo}-{hi}",
        })
    return pd.DataFrame(rows).set_index("years")


def table_envelope(day: pd.DataFrame) -> pd.DataFrame:
    """Band width and how much of a year escapes it.

    The envelope draws a percentile band over a reference period and puts the
    selected years on top. It is only useful if a typical year spends a visible
    part of the year outside the band; if it does not, every line sits inside a
    grey stripe and nothing is distinguishable.
    """
    ref = day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
    grouped = ref.groupby("doy")["mean"]
    band = pd.DataFrame({
        "p10": grouped.quantile(0.10),
        "p50": grouped.quantile(0.50),
        "p90": grouped.quantile(0.90),
    })
    band["width"] = band["p90"] - band["p10"]

    rows = []
    for year in (1963, 1995, 2010, 2018, 2025):
        # groupby, not set_index: _day_of_year folds 29 February onto 28
        # February, so a leap year hands this two rows at doy 59 and the
        # shared slot has to be averaged the way every other path averages it.
        this = day.loc[day["year"] == year].groupby("doy")["mean"].mean()
        joined = band.join(this.rename("value"), how="inner").dropna(subset=["value"])
        if joined.empty:
            continue
        outside = ((joined["value"] < joined["p10"]) | (joined["value"] > joined["p90"])).sum()
        rows.append({
            "year": year,
            "days_compared": int(len(joined)),
            "days_outside_10_90": int(outside),
            "pct_outside": 100.0 * outside / len(joined),
        })
    # The band's own width is `table_band_width`; this table is only the escapes.
    return pd.DataFrame(rows).set_index("year")


def table_band_width(day: pd.DataFrame) -> pd.DataFrame:
    ref = day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
    grouped = ref.groupby("doy")["mean"]
    width = (grouped.quantile(0.90) - grouped.quantile(0.10)).dropna()
    return pd.DataFrame([{
        "reference_period": f"{NORMALS[0]}-{NORMALS[1]}",
        "band": "10th to 90th percentile",
        "median_width_c": float(width.median()),
        "min_width_c": float(width.min()),
        "max_width_c": float(width.max()),
    }]).set_index("reference_period")


def table_cumulative(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Annual totals and mid-year separation for the two summed variables.

    Cumulative curves only make sense for a variable that accumulates. Rain and
    sunshine are the two the app sums; the other eleven are averaged, and a
    running total of a mean is not a quantity.

    Measured over the ten-year window the other forms use and over the whole
    series, because a claim about how far apart the curves get depends entirely
    on how many years are on the plot.
    """
    rows = []
    for key, unit in (("rain", "mm"), ("sun", "h")):
        day = daily(clean_df, key)
        day = day.loc[day["mean"].notna()].copy()
        day["doy"] = _day_of_year(day.index)
        complete_years = day.groupby("year")["mean"].count() >= 350
        complete_years = set(complete_years.loc[complete_years].index)

        windows = (
            (f"{DEMO_YEARS[0]}-{DEMO_YEARS[1]}", DEMO_YEARS[0], DEMO_YEARS[1]),
            ("whole series", int(day["year"].min()), int(day["year"].max())),
        )
        for label, lo, hi in windows:
            window = day.loc[(day["year"] >= lo) & (day["year"] <= hi)
                             & day["year"].isin(complete_years)]
            totals = window.groupby("year")["mean"].sum()
            matrix = window.pivot_table(index="year", columns="doy", values="mean",
                                        aggfunc="sum").fillna(0.0)
            running = matrix.cumsum(axis=1)
            mid = running.get(182)
            rows.append({
                "variable": key,
                "unit": unit,
                "window": label,
                "complete_years": int(len(totals)),
                "annual_min": float(totals.min()),
                "annual_max": float(totals.max()),
                "annual_spread": float(totals.max() - totals.min()),
                "spread_at_1_july": float(mid.max() - mid.min())
                if mid is not None else float("nan"),
                "crossings_per_pair_year": _mean_crossings(running),
                "crossings_per_pair_after_1_apr": _mean_crossings(running, start_doy=91),
            })
    return pd.DataFrame(rows).set_index(["variable", "window"])


def _mean_crossings(running: pd.DataFrame, start_doy: int = 1) -> float:
    """How often two cumulative curves swap order, averaged over every pair.

    A form whose lines never cross is easy to read and says little; one whose
    lines cross constantly is the occlusion problem again in another shape.
    `start_doy` exists because in January the running totals are a few
    millimetres apart and swap on almost any wet day, which says nothing about
    whether the form works for the year as a whole.
    """
    columns = [c for c in running.columns if c >= start_doy]
    running = running[columns]
    years = list(running.index)
    counts = []
    for i, a in enumerate(years):
        for b in years[i + 1:]:
            diff = (running.loc[a] - running.loc[b]).to_numpy()
            sign = np.sign(diff)
            sign = sign[sign != 0]
            if sign.size < 2:
                counts.append(0)
                continue
            counts.append(int((np.diff(sign) != 0).sum()))
    return float(np.mean(counts)) if counts else float("nan")


def fig_forms(day: pd.DataFrame) -> None:
    """The same ten years drawn four ways, which is the argument in one image."""
    lo, hi = DEMO_YEARS
    normals = (
        day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
        .groupby("doy")["mean"]
        .mean()
    )
    work = day.copy()
    work["anomaly"] = work["mean"] - work["doy"].map(normals)
    raw = _matrix(work, lo, hi, "mean")
    ano = _matrix(work, lo, hi, "anomaly")

    fig, axes = plt.subplots(2, 2, figsize=(12.4, 7.4))
    months = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    ax = axes[0][0]
    for i, year in enumerate(raw.index):
        ax.plot(raw.columns, raw.loc[year], lw=0.7, color=SERIES[i % len(SERIES)], alpha=0.85)
    ax.set_ylim(*APP_TEMP_AXIS)
    ax.set_title(f"Overlaid lines, the app's fixed axis ({lo}-{hi})", color=INK, fontsize=10)
    ax.set_ylabel("°C", color=INK_SECONDARY)

    ax = axes[0][1]
    for i, year in enumerate(ano.index):
        ax.plot(ano.columns, ano.loc[year], lw=0.7, color=SERIES[i % len(SERIES)], alpha=0.85)
    ax.axhline(0.0, color=INK_MUTED, lw=0.8)
    ax.set_title("Anomaly against the 1991-2020 day-of-year normal", color=INK, fontsize=10)
    ax.set_ylabel("°C from normal", color=INK_SECONDARY)

    ax = axes[1][0]
    # Anomaly, not raw, and the whole archive rather than the last thirty years.
    # On raw values an auto-scaled diverging map spends its whole range on the
    # seasonal cycle, so the panel shows summer and winter and says nothing
    # about the difference between years, which is the only thing the heatmap is
    # being recommended for. The scale is symmetric so that zero is the middle
    # colour and a warm year and a cold one are equally far from it.
    # Complete years only, at BOTH ends. Bounding just the start let the partial
    # 2026 in as an eighty-first row built from as little as one day per cell,
    # and titled the panel 1946-2026 while 04-heatmap-cells.csv called the same
    # window 1946-2025.
    complete = work.groupby("year")["mean"].count()
    complete = complete.loc[complete >= 350].index
    wide = work.loc[work["year"].isin(complete)].copy()
    wide["bucket"] = bucket_index(wide["doy"], BUCKET_DAYS)
    wide = wide.pivot_table(index="year", columns="bucket", values="anomaly",
                            aggfunc="mean")
    limit = float(np.nanpercentile(np.abs(wide.to_numpy()), 99))
    # The x extent is in days, not bucket indices. Every panel in this figure
    # shares a day-of-year axis and the formatting loop below sets xlim to
    # (1, 366) for all four; an extent of (0, n_buckets) put this panel's whole
    # eighty years inside the first 3.5% of its width and left the rest blank.
    im = ax.imshow(wide.to_numpy(), aspect="auto", cmap="RdBu_r",
                   vmin=-limit, vmax=limit,
                   extent=(1, 1 + BUCKET_DAYS * wide.shape[1],
                           float(wide.index.max()) + 0.5,
                           float(wide.index.min()) - 0.5))
    ax.set_title("Heatmap of the monthly anomaly, "
                 f"{int(wide.index.min())}-{int(wide.index.max())}",
                 color=INK, fontsize=10)
    ax.set_ylabel("year", color=INK_SECONDARY)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="°C from normal")

    ax = axes[1][1]
    ref = day.loc[(day["year"] >= NORMALS[0]) & (day["year"] <= NORMALS[1])]
    grouped = ref.groupby("doy")["mean"]
    p10, p50, p90 = (grouped.quantile(q) for q in (0.10, 0.50, 0.90))
    ax.fill_between(p10.index, p10, p90, color=GRID, label="1991-2020, 10th-90th")
    ax.plot(p50.index, p50, lw=0.9, color=INK_MUTED, label="median")
    for i, year in enumerate((2018, 2025)):
        this = work.loc[work["year"] == year].set_index("doy")["mean"]
        ax.plot(this.index, this, lw=0.8, color=SERIES[i], label=str(year))
    ax.set_title("Envelope, two years on the reference band", color=INK, fontsize=10)
    ax.set_ylabel("°C", color=INK_SECONDARY)
    ax.legend(frameon=False, fontsize=7, loc="upper left")

    for row in axes:
        for ax in row:
            ax.set_xlim(1, 366)
            ax.set_xticks(months)
            ax.set_xticklabels(labels, fontsize=7)
    fig.tight_layout()
    save_fig(fig, FIGURES / "04-forms.png")


def fig_separation(sep: pd.DataFrame) -> None:
    """What a pixel is worth, form by form, as the year count grows."""
    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    ax.plot(sep.index, sep["raw_separation_pct_of_axis"], marker="o", lw=1.4,
            color=SERIES[0], label="overlaid lines, fitted axis")
    ax.plot(sep.index, sep["anomaly_separation_pct_of_axis"], marker="o", lw=1.4,
            color=SERIES[1], label="anomaly")
    ax.set_xlabel("years compared", color=INK_SECONDARY)
    ax.set_ylabel("median between-year gap,\n% of the axis it needs", color=INK_SECONDARY)
    ax.set_title("How much of the plot height the difference between years fills",
                 color=INK, fontsize=10)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    save_fig(fig, FIGURES / "04-separation.png")


FIGURES = Path(__file__).resolve().parents[1] / "figures"
STATS = Path(__file__).resolve().parents[1] / "stats"


def run_forms(csv_path: Path) -> None:
    raw = load_raw(csv_path)
    clean_df = clean(raw)
    day = _daily_temp(clean_df)

    sep = table_separation(day)
    save_table(sep, STATS / "04-separation.csv", float_format="%.3f")
    save_table(table_app_axis(day), STATS / "04-axis-cost.csv", float_format="%.3f")
    save_table(table_warming(day), STATS / "04-warming-signal.csv", float_format="%.3f")
    save_table(table_occlusion(day), STATS / "04-occlusion.csv", float_format="%.3f")
    save_table(table_anchor_sweep(day), STATS / "04-anchor-sweep.csv", float_format="%.3f")
    save_table(table_resolution(day), STATS / "04-resolution.csv", float_format="%.3f")
    save_table(table_variables(clean_df), STATS / "04-variables.csv", float_format="%.3f")
    save_table(table_small_multiples(day), STATS / "04-small-multiples.csv",
               float_format="%.3f")
    save_table(table_heatmap_signal(day), STATS / "04-heatmap-signal.csv",
               float_format="%.3f")
    save_table(table_heatmap_cells(day), STATS / "04-heatmap-cells.csv", float_format="%.3f")
    save_table(table_band_width(day), STATS / "04-band-width.csv", float_format="%.3f")
    save_table(table_envelope(day), STATS / "04-envelope-escape.csv", float_format="%.3f")
    save_table(table_cumulative(clean_df), STATS / "04-cumulative.csv", float_format="%.3f")

    fig_forms(day)
    fig_separation(sep)
    fig_heatmap_detail(day)
