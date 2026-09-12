"""Measure how well four chart forms separate years, for `EDA/04-chart-forms.md`.

Run through the report entry point:

    uv run EDA/scripts/eda_report.py --section forms

The app draws overlaid lines on a fixed y-scale. That works for two or three
years and stops working well before twenty, because the between-year difference
is small next to a single year's own swing. Four forms were proposed as the next
chart; this module measures each against the real series so the choice is made
on numbers rather than on which one sounds best.

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
PLOT_WIDTH_PX = 1200
PLOT_HEIGHT_PX = 520

# Where the app's fixed temperature axis sits, from `public/data/meta.json`
# rounded outward the way `src/model/scales.ts` rounds it.
APP_TEMP_AXIS = (-15.0, 30.0)

# From `EDA/stats/02-break-test.csv`, the joint trend-plus-step fit in document
# 2: the trend once a step at 1993 is in the model, and the step itself. The
# step is NEGATIVE, so it holds the whole-series difference down rather than
# propping it up. It is not significant on the annual mean on its own
# (p = 0.242); document 2 section 2.4 makes the case from the hour-by-hour
# decomposition instead. Both numbers are quoted, not refitted, so this module
# cannot drift from the document that owns them.
DOC02_TREND_PER_DECADE = 0.14511
DOC02_STEP_AT_1993_C = -0.262


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


def _axis_span(values: np.ndarray, pad: float = 0.0) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    return float(finite.max() - finite.min()) * (1.0 + pad)


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
            "trend_implied_c": DOC02_TREND_PER_DECADE * gap_years / 10.0,
            "measured_minus_trend_implied_c": float(late.mean() - early.mean())
            - DOC02_TREND_PER_DECADE * gap_years / 10.0,
        })
    return pd.DataFrame(rows).set_index("window")


def _swap_rate(matrix: pd.DataFrame) -> float:
    """Share of days on which a pair of years swaps which one is on top.

    Averaged over every pair. A line the eye can follow keeps its place; one
    that changes places with its neighbours on a quarter of all days cannot be
    followed by position, only by colour.
    """
    swaps = []
    years = list(matrix.index)
    for i, a in enumerate(years):
        for b in years[i + 1:]:
            diff = (matrix.loc[a] - matrix.loc[b]).to_numpy()
            diff = diff[np.isfinite(diff)]
            sign = np.sign(diff)
            sign = sign[sign != 0]
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


def table_heatmap_cells(day: pd.DataFrame) -> pd.DataFrame:
    """Cell size for a heatmap of years by day of year, at a real plot size."""
    # 1946 to 2025 is 80 complete years, which is what the archive holds; 81
    # would start the window in 1945 and there are no 1945 rows. The column
    # count is 365 because the leap-day fold shares 28 and 29 February.
    columns = int(day["doy"].max())
    full = int(day["year"].max() - day["year"].min())
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
        this = day.loc[day["year"] == year].set_index("doy")["mean"]
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
    out = pd.DataFrame(rows).set_index("year")
    out.attrs["band_width_median_c"] = float(band["width"].median())
    return out


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
    wide = _matrix(work, hi - 29, hi, "mean")
    im = ax.imshow(wide.to_numpy(), aspect="auto", cmap="RdBu_r",
                   extent=(1, 366, float(wide.index.max()) + 0.5, float(wide.index.min()) - 0.5))
    ax.set_title(f"Heatmap, {int(wide.index.min())}-{int(wide.index.max())}",
                 color=INK, fontsize=10)
    ax.set_ylabel("year", color=INK_SECONDARY)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="°C")

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
    save_table(table_heatmap_cells(day), STATS / "04-heatmap-cells.csv", float_format="%.3f")
    save_table(table_band_width(day), STATS / "04-band-width.csv", float_format="%.3f")
    save_table(table_envelope(day), STATS / "04-envelope-escape.csv", float_format="%.3f")
    save_table(table_cumulative(clean_df), STATS / "04-cumulative.csv", float_format="%.3f")

    fig_forms(day)
    fig_separation(sep)
