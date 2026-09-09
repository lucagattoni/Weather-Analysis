"""Temperature and precipitation sections: trends, anomalies, extremes.

Imported by `eda_report.py`; not run directly. Split out because the data
review and the two climate documents ask different questions of the same
series and mixing them in one file makes both harder to follow.

Every trend is fitted three ways (least squares with an autocorrelation-widened
interval, Mann-Kendall with Sen's slope, and a LOESS smoother for shape) and
every trend that spans September 1993 is also fitted to each sub-period
separately, because the observation-practice change documented in
`EDA/01-data-review.md` is the main threat to all of them.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from eda_common import (
    BASELINE,
    DIVERGING,
    GRID,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    LAST_COMPLETE_YEAR,
    NORMALS,
    SEASONS,
    SERIES,
    STATUS,
    Trend,
    annual,
    clean,
    daily,
    fit_trend,
    loess_curve,
    save_fig,
    save_table,
    seasonal,
)

BREAK_YEAR = 1993
PRE = (1946, 1992)
POST = (1994, LAST_COMPLETE_YEAR)
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


# --------------------------------------------------------------------------
# Shared machinery
# --------------------------------------------------------------------------

def trend_row(label: str, trend: Trend, unit: str) -> dict:
    """One fitted trend as a table row."""
    return {
        "series": label,
        f"OLS slope ({unit}/decade)": trend.slope_per_decade,
        "CI low": trend.ci_low,
        "CI high": trend.ci_high,
        "p (autocorr-adjusted)": trend.p_value,
        f"Sen slope ({unit}/decade)": trend.sen_slope_per_decade,
        "Mann-Kendall p": trend.kendall_p,
        "Kendall tau": trend.kendall_tau,
        "n years": trend.n,
        "lag-1 autocorr": trend.lag1_autocorrelation,
        "effective n": trend.effective_n,
        "methods agree": trend.agrees,
    }


def step_trend_model(series: pd.Series) -> dict:
    """Fit the trend and a September 1993 step jointly, and let them compete.

        y ~ intercept + b1 * (year - centre) + b2 * 1[year >= 1993.67]

    This is the test that matters, and it is not the same as comparing
    sub-period slopes. A step and a trend are partly confounded: a jump halfway
    through a record masquerades as a slope, and a real slope masquerades as a
    jump. Fitting both together asks the only useful question, which is how much
    of each the data supports once the other is allowed to explain what it can.

    A significant step is not proof of an instrument fault. It is proof of a
    discontinuity, and a discontinuity coinciding with a documented change in
    observation practice, in one derived quantity and not its neighbours, is
    what an instrument fault looks like. The document says which is which and on
    what grounds.
    """
    import statsmodels.api as sm

    s = series.loc[1946:LAST_COMPLETE_YEAR].dropna()
    year = s.index.to_numpy(float)
    centre = year.mean()
    design = sm.add_constant(np.column_stack([
        year - centre,
        (year >= BREAK_YEAR + 0.67).astype(float),
    ]))
    model = sm.OLS(s.to_numpy(float), design).fit()
    return {
        "trend with step (per decade)": float(model.params[1] * 10.0),
        "trend p": float(model.pvalues[1]),
        "step at 1993": float(model.params[2]),
        "step p": float(model.pvalues[2]),
        "step CI low": float(model.conf_int()[2][0]),
        "step CI high": float(model.conf_int()[2][1]),
    }


def break_test(series: pd.Series, unit: str) -> pd.DataFrame:
    """Everything that bears on whether September 1993 contaminates the trend.

    Four fits, because no one of them settles it alone: the naive whole-record
    slope that a reader would compute by default, each sub-period on its own,
    and the joint model above that separates a step from a slope. Where the
    naive slope and the joint model's slope disagree, the difference is what
    the break was doing to the naive number.
    """
    rows = []
    for label, (lo, hi) in [("Whole record 1946-2025, no step term",
                             (1946, LAST_COMPLETE_YEAR)),
                            ("Before the break 1946-1992", PRE),
                            ("After the break 1994-2025", POST)]:
        window = series.loc[lo:hi].dropna()
        rows.append(trend_row(label, fit_trend(window.index.to_numpy(float),
                                               window.to_numpy(float)), unit))
    out = pd.DataFrame(rows).set_index("series")

    joint = step_trend_model(series)
    naive = float(out.iloc[0, 0])
    adjusted = joint["trend with step (per decade)"]
    step_real = joint["step p"] < 0.05

    if not step_real:
        verdict = (f"no significant step (p = {joint['step p']:.2g}); "
                   f"the whole-record slope stands")
    elif abs(adjusted) > abs(naive):
        verdict = (f"significant step of {joint['step at 1993']:+.3f} {unit} "
                   f"(p = {joint['step p']:.2g}) SUPPRESSES the naive slope; "
                   f"the real trend is {adjusted:+.4f} {unit}/decade, not {naive:+.4f}")
    else:
        verdict = (f"significant step of {joint['step at 1993']:+.3f} {unit} "
                   f"(p = {joint['step p']:.2g}) INFLATES the naive slope; "
                   f"the real trend is {adjusted:+.4f} {unit}/decade, not {naive:+.4f}")

    out["verdict"] = [verdict, "", ""]
    joint_row = {c: np.nan for c in out.columns}
    joint_row[out.columns[0]] = adjusted
    joint_row["p (autocorr-adjusted)"] = joint["trend p"]
    joint_row["verdict"] = (f"step {joint['step at 1993']:+.3f} {unit} "
                            f"[{joint['step CI low']:+.3f}, {joint['step CI high']:+.3f}], "
                            f"p = {joint['step p']:.3g}")
    out.loc["Joint trend-plus-step model"] = joint_row
    return out


def anomaly(series: pd.Series, period: tuple[int, int] = BASELINE) -> pd.Series:
    lo, hi = period
    return series - series.loc[lo:hi].mean()


def decade_table(series: pd.Series, unit: str, how: str = "mean") -> pd.DataFrame:
    """Per-decade summary against the baseline, with the extreme years named."""
    base = series.loc[BASELINE[0]:BASELINE[1]].mean()
    frame = series.loc[1946:LAST_COMPLETE_YEAR].to_frame("value")
    frame["decade"] = (frame.index // 10) * 10
    rows = []
    for decade, g in frame.groupby("decade"):
        v = g["value"].dropna()
        if v.empty:
            continue
        rows.append({
            "decade": f"{decade}s",
            "years": int(v.size),
            f"mean ({unit})": v.mean(),
            f"anomaly vs {BASELINE[0]}-{BASELINE[1]}": v.mean() - base,
            "highest year": int(v.idxmax()),
            f"highest ({unit})": v.max(),
            "lowest year": int(v.idxmin()),
            f"lowest ({unit})": v.min(),
        })
    return pd.DataFrame(rows).set_index("decade")


# --------------------------------------------------------------------------
# Temperature
# --------------------------------------------------------------------------

def temperature_frames(cleaned: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    day = daily(cleaned, "temp")
    ann = annual(day, how="mean")["value"]
    ann_max = day.groupby("year")["max"].mean()
    ann_min = day.groupby("year")["min"].mean()
    for s in (ann_max, ann_min):
        s.loc[s.index > LAST_COMPLETE_YEAR] = np.nan
    return {"day": day, "annual": ann, "annual_max": ann_max, "annual_min": ann_min}


def table_temperature_trends(frames: dict) -> pd.DataFrame:
    """Annual and seasonal trends, whole record."""
    day = frames["day"]
    rows = [trend_row("Annual mean", _trend_of(frames["annual"]), "degC")]
    seas = seasonal(day, how="mean")
    for name in SEASONS:
        s = seas.loc[name, "value"].loc[1947:LAST_COMPLETE_YEAR].dropna()
        rows.append(trend_row(name, fit_trend(s.index.to_numpy(float),
                                              s.to_numpy(float)), "degC"))
    rows.append(trend_row("Annual mean of daily maxima",
                          _trend_of(frames["annual_max"]), "degC"))
    rows.append(trend_row("Annual mean of daily minima",
                          _trend_of(frames["annual_min"]), "degC"))
    dtr = (day.groupby("year")["max"].mean() - day.groupby("year")["min"].mean())
    rows.append(trend_row("Diurnal temperature range", _trend_of(dtr), "degC"))
    return pd.DataFrame(rows).set_index("series")


def _trend_of(series: pd.Series) -> Trend:
    s = series.loc[1946:LAST_COMPLETE_YEAR].dropna()
    return fit_trend(s.index.to_numpy(float), s.to_numpy(float))


def table_temperature_thresholds(day: pd.DataFrame) -> pd.DataFrame:
    """Days per year crossing each threshold.

    These are counts of days whose hourly extremes cross the threshold, which
    is not the same as a max/min thermometer reading: an hourly series misses a
    brief peak between readings, so every count here is a slight underestimate
    of the true one. The bias is in one direction and roughly constant, so
    trends in these counts survive it better than their absolute values do.
    """
    g = day.loc[day["year"] <= LAST_COMPLETE_YEAR].groupby("year")
    out = pd.DataFrame({
        "frost days (Tmin < 0)": g["min"].apply(lambda s: (s < 0).sum()),
        "ice days (Tmax < 0)": g["max"].apply(lambda s: (s < 0).sum()),
        "warm days (Tmax >= 20)": g["max"].apply(lambda s: (s >= 20).sum()),
        "summer days (Tmax >= 25)": g["max"].apply(lambda s: (s >= 25).sum()),
    })
    out.index.name = "year"
    return out


def table_temperature_extremes(cleaned: pd.DataFrame, day: pd.DataFrame) -> pd.DataFrame:
    """Record values, and the warmest and coldest years and months by anomaly."""
    ann = annual(day, how="mean")["value"]
    ann_anom = anomaly(ann).loc[1946:LAST_COMPLETE_YEAR].dropna()
    month = cleaned.groupby(["year", "month"])["temp"].mean()
    month_base = month.loc[BASELINE[0]:BASELINE[1]].groupby(level=1).mean()
    month_anom = (month - month_base.reindex(month.index.get_level_values(1)).to_numpy())
    month_anom = month_anom[month_anom.index.get_level_values(0) <= LAST_COMPLETE_YEAR]

    rows = []
    for rank, (year, value) in enumerate(ann_anom.nlargest(5).items(), 1):
        rows.append({"kind": "warmest year", "rank": rank, "when": str(int(year)),
                     "value (degC)": ann.loc[year], "anomaly (degC)": value})
    for rank, (year, value) in enumerate(ann_anom.nsmallest(5).items(), 1):
        rows.append({"kind": "coldest year", "rank": rank, "when": str(int(year)),
                     "value (degC)": ann.loc[year], "anomaly (degC)": value})
    for rank, ((year, m), value) in enumerate(month_anom.nlargest(5).items(), 1):
        rows.append({"kind": "warmest month", "rank": rank,
                     "when": f"{MONTH_NAMES[int(m) - 1]} {int(year)}",
                     "value (degC)": month.loc[(year, m)], "anomaly (degC)": value})
    for rank, ((year, m), value) in enumerate(month_anom.nsmallest(5).items(), 1):
        rows.append({"kind": "coldest month", "rank": rank,
                     "when": f"{MONTH_NAMES[int(m) - 1]} {int(year)}",
                     "value (degC)": month.loc[(year, m)], "anomaly (degC)": value})
    hottest = cleaned.loc[cleaned["temp"].idxmax()]
    coldest = cleaned.loc[cleaned["temp"].idxmin()]
    rows.append({"kind": "highest hourly reading", "rank": 1,
                 "when": str(hottest["date"]), "value (degC)": hottest["temp"],
                 "anomaly (degC)": np.nan})
    rows.append({"kind": "lowest hourly reading", "rank": 1,
                 "when": str(coldest["date"]), "value (degC)": coldest["temp"],
                 "anomaly (degC)": np.nan})
    return pd.DataFrame(rows).set_index("kind")


def table_distribution_shift(day: pd.DataFrame) -> pd.DataFrame:
    """Daily-mean temperature percentiles by 30-year period.

    A distribution can move in two ways that a mean cannot tell apart: the
    whole thing slides warmer, or it stays put and its tails spread. The
    percentiles distinguish them. If every percentile moves by about the same
    amount it is a shift; if the upper ones move more than the lower ones the
    distribution is also widening, which matters far more for extremes than
    the change in the mean does.
    """
    periods = [(1946, 1975), (1976, 2005), (1996, 2025)]
    rows = []
    for lo, hi in periods:
        s = day.loc[(day["year"] >= lo) & (day["year"] <= hi), "mean"].dropna()
        row = {"period": f"{lo}-{hi}", "days": int(s.size), "mean": s.mean(),
               "SD": s.std()}
        for q in (1, 5, 25, 50, 75, 95, 99):
            row[f"p{q}"] = s.quantile(q / 100.0)
        rows.append(row)
    out = pd.DataFrame(rows).set_index("period")
    shift = out.loc["1996-2025"] - out.loc["1946-1975"]
    shift.name = "1996-2025 minus 1946-1975"
    return pd.concat([out, shift.to_frame().T])


# --------------------------------------------------------------------------
# Precipitation
# --------------------------------------------------------------------------

def precipitation_frames(cleaned: pd.DataFrame) -> dict:
    day = daily(cleaned, "rain")
    ann = annual(day, how="sum")["value"]
    return {"day": day, "annual": ann}


def table_precipitation_trends(cleaned: pd.DataFrame, frames: dict) -> pd.DataFrame:
    day = frames["day"]
    rows = [trend_row("Annual total", _trend_of(frames["annual"]), "mm")]
    seas = seasonal(day, how="sum")
    for name in SEASONS:
        s = seas.loc[name, "value"].loc[1947:LAST_COMPLETE_YEAR].dropna()
        rows.append(trend_row(name, fit_trend(s.index.to_numpy(float),
                                              s.to_numpy(float)), "mm"))
    wet = day.loc[day["year"] <= LAST_COMPLETE_YEAR].groupby("year")["mean"]
    rows.append(trend_row("Wet days (>= 1 mm)",
                          _trend_of(wet.apply(lambda s: (s >= 1.0).sum())), "days"))
    rows.append(trend_row("Heavy days (>= 10 mm)",
                          _trend_of(wet.apply(lambda s: (s >= 10.0).sum())), "days"))
    rows.append(trend_row("Mean wet-day amount (>= 1 mm)",
                          _trend_of(wet.apply(lambda s: s[s >= 1.0].mean())), "mm"))
    rows.append(trend_row("Wettest day of the year",
                          _trend_of(wet.max()), "mm"))
    hourly_max = (cleaned.loc[cleaned["year"] <= LAST_COMPLETE_YEAR]
                  .groupby("year")["rain"].max())
    rows.append(trend_row("Wettest hour of the year", _trend_of(hourly_max), "mm"))
    return pd.DataFrame(rows).set_index("series")


def table_precipitation_indices(day: pd.DataFrame) -> pd.DataFrame:
    """Per-year indices, including the percentile-based extreme measures.

    R95p and R99p follow the standard definition: the annual total falling on
    days above the 95th and 99th percentile of wet-day amounts in the baseline
    period. They measure whether rain arrives in heavier bursts, which the
    annual total cannot see.
    """
    d = day.loc[day["year"] <= LAST_COMPLETE_YEAR]
    base_wet = d.loc[(d["year"] >= BASELINE[0]) & (d["year"] <= BASELINE[1]), "mean"]
    base_wet = base_wet[base_wet >= 1.0]
    p95, p99 = base_wet.quantile(0.95), base_wet.quantile(0.99)
    g = d.groupby("year")["mean"]
    out = pd.DataFrame({
        "total (mm)": g.sum(min_count=1),
        "wet days >= 0.2 mm": g.apply(lambda s: (s >= 0.2).sum()),
        "wet days >= 1 mm": g.apply(lambda s: (s >= 1.0).sum()),
        "heavy days >= 10 mm": g.apply(lambda s: (s >= 10.0).sum()),
        "very heavy days >= 20 mm": g.apply(lambda s: (s >= 20.0).sum()),
        "mean wet-day amount (mm)": g.apply(lambda s: s[s >= 1.0].mean()),
        "wettest day (mm)": g.max(),
        f"R95p total (mm), p95={p95:.1f}": g.apply(lambda s: s[s > p95].sum()),
        f"R99p total (mm), p99={p99:.1f}": g.apply(lambda s: s[s > p99].sum()),
        "longest dry spell (days)": g.apply(_longest_run_below),
        "longest wet spell (days)": g.apply(_longest_run_at_least),
    })
    out.index.name = "year"
    return out


def _longest_run_below(s: pd.Series, threshold: float = 1.0) -> int:
    mask = (s < threshold).to_numpy()
    return _longest_true_run(mask)


def _longest_run_at_least(s: pd.Series, threshold: float = 1.0) -> int:
    return _longest_true_run((s >= threshold).to_numpy())


def _longest_true_run(mask: np.ndarray) -> int:
    best = run = 0
    for value in mask:
        run = run + 1 if value else 0
        best = max(best, run)
    return int(best)


def table_precipitation_extremes(cleaned: pd.DataFrame, day: pd.DataFrame) -> pd.DataFrame:
    ann = annual(day, how="sum")["value"]
    ann_anom = anomaly(ann).loc[1946:LAST_COMPLETE_YEAR].dropna()
    d = day.loc[day["year"] <= LAST_COMPLETE_YEAR]
    month = (d.groupby(["year", "month"])["mean"].sum(min_count=1))
    rows = []
    for rank, (year, value) in enumerate(ann_anom.nlargest(5).items(), 1):
        rows.append({"kind": "wettest year", "rank": rank, "when": str(int(year)),
                     "value (mm)": ann.loc[year], "anomaly (mm)": value})
    for rank, (year, value) in enumerate(ann_anom.nsmallest(5).items(), 1):
        rows.append({"kind": "driest year", "rank": rank, "when": str(int(year)),
                     "value (mm)": ann.loc[year], "anomaly (mm)": value})
    for rank, ((year, m), value) in enumerate(month.nlargest(5).items(), 1):
        rows.append({"kind": "wettest month", "rank": rank,
                     "when": f"{MONTH_NAMES[int(m) - 1]} {int(year)}",
                     "value (mm)": value, "anomaly (mm)": np.nan})
    for rank, (dayts, value) in enumerate(d["mean"].nlargest(5).items(), 1):
        rows.append({"kind": "wettest day", "rank": rank,
                     "when": str(pd.Timestamp(dayts).date()),
                     "value (mm)": value, "anomaly (mm)": np.nan})
    hourly = cleaned.loc[cleaned["year"] <= LAST_COMPLETE_YEAR]
    for rank, (idx, value) in enumerate(hourly["rain"].nlargest(5).items(), 1):
        rows.append({"kind": "wettest hour", "rank": rank,
                     "when": str(hourly.loc[idx, "date"]),
                     "value (mm)": value, "anomaly (mm)": np.nan})
    return pd.DataFrame(rows).set_index("kind")


def table_monthly_shift(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Monthly rainfall climatology, baseline against current normals."""
    rows = []
    for label, (lo, hi) in [(f"{BASELINE[0]}-{BASELINE[1]}", BASELINE),
                            (f"{NORMALS[0]}-{NORMALS[1]}", NORMALS)]:
        w = cleaned[(cleaned["year"] >= lo) & (cleaned["year"] <= hi)]
        totals = (w.groupby(["year", "month"])["rain"].sum(min_count=1)
                  .groupby(level=1).mean())
        rows.append(pd.Series(totals, name=label))
    out = pd.DataFrame(rows).T
    out["change (mm)"] = out.iloc[:, 1] - out.iloc[:, 0]
    out["change %"] = 100.0 * out["change (mm)"] / out.iloc[:, 0]

    # A 28% shift in a single month looks like a finding and is usually noise:
    # monthly rainfall is skewed and its year-to-year spread is large next to
    # the difference between two 30-year means. Welch's t-test on the two sets
    # of annual monthly totals says which changes the data actually supports,
    # and it does not assume equal variance between the periods.
    from scipy import stats as sps
    pvals, sig = [], []
    for month in range(1, 13):
        samples = []
        for lo, hi in (BASELINE, NORMALS):
            w = cleaned[(cleaned["year"] >= lo) & (cleaned["year"] <= hi)
                        & (cleaned["month"] == month)]
            samples.append(w.groupby("year")["rain"].sum(min_count=1).dropna())
        result = sps.ttest_ind(samples[1], samples[0], equal_var=False)
        pvals.append(float(result.pvalue))
        sig.append("yes" if result.pvalue < 0.05 else "no")
    out["p (Welch)"] = pvals
    out["significant at 5%"] = sig
    out.index = [MONTH_NAMES[i - 1] for i in out.index]
    out.index.name = "month"
    return out


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

def fig_anomaly_bars(series: pd.Series, unit: str, title: str, path: Path,
                     figures: Path) -> None:
    """Anomalies against the baseline, warm above the line and cold below.

    A diverging encoding is the right one here because the quantity has a
    meaningful zero: the baseline mean. Blue to red through a neutral midpoint,
    never a rainbow.
    """
    a = anomaly(series).loc[1946:LAST_COMPLETE_YEAR].dropna()
    fig, ax = plt.subplots(figsize=(9.5, 3.6))
    colours = [DIVERGING[2] if v > 0 else DIVERGING[0] for v in a]
    ax.bar(a.index, a, color=colours, width=0.84, linewidth=0)
    x, y = a.index.to_numpy(float), a.to_numpy(float)
    # Two spans, because the span is a choice and not a fact: a narrow one
    # follows the data and can invent structure, a wide one flattens real
    # turns. Showing both lets a reader see which features survive the choice.
    ax.plot(x, loess_curve(x, y, frac=0.30), color=INK, linewidth=2.0,
            label="LOESS, span 0.30")
    ax.plot(x, loess_curve(x, y, frac=0.55), color=INK, linewidth=1.3,
            linestyle=(0, (4, 2)), label="LOESS, span 0.55")
    ax.axhline(0, color=INK_MUTED, linewidth=1.0)
    ax.axvline(BREAK_YEAR + 0.67, color=INK_MUTED, linewidth=1.0,
               linestyle=(0, (4, 3)))
    ax.set_ylabel(f"anomaly ({unit})")
    ax.set_xlabel("year")
    ax.set_title(title)
    ax.annotate("Sept 1993\nbreak", xy=(BREAK_YEAR + 0.67, ax.get_ylim()[1] * 0.72),
                xytext=(1996, ax.get_ylim()[1] * 0.72), color=INK_SECONDARY,
                fontsize=8)
    ax.legend(loc="upper left")
    save_fig(fig, figures / path)


def fig_break_test(series: pd.Series, unit: str, title: str, path: Path,
                   figures: Path) -> None:
    """The whole-record fit against the two sub-period fits, on one axis."""
    fig, ax = plt.subplots(figsize=(9.5, 3.8))
    s = series.loc[1946:LAST_COMPLETE_YEAR].dropna()
    ax.plot(s.index, s, color=INK_MUTED, linewidth=1.1, marker="o", markersize=2.6,
            alpha=0.7, label="annual value")
    specs = [("Whole record", (1946, LAST_COMPLETE_YEAR), SERIES[0]),
             ("1946-1992", PRE, SERIES[1]),
             ("1994-2025", POST, SERIES[2])]
    for label, (lo, hi), colour in specs:
        w = s.loc[lo:hi]
        x, y = w.index.to_numpy(float), w.to_numpy(float)
        t = fit_trend(x, y)
        ax.plot(x, np.polyval(np.polyfit(x, y, 1), x), color=colour, linewidth=2.2,
                label=f"{label}: {t.slope_per_decade:+.3f} {unit}/decade")
    ax.axvline(BREAK_YEAR + 0.67, color=INK_MUTED, linewidth=1.0,
               linestyle=(0, (4, 3)))
    ax.set_ylabel(unit)
    ax.set_xlabel("year")
    ax.set_title(title)
    ax.legend(loc="upper left", ncols=2)
    save_fig(fig, figures / path)


def fig_seasonal_trends(day: pd.DataFrame, how: str, unit: str, title: str,
                        path: Path, figures: Path) -> None:
    seas = seasonal(day, how=how)
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 5.6), sharex=True)
    for ax, (name, colour) in zip(axes.ravel(), zip(SEASONS, SERIES)):
        s = seas.loc[name, "value"].loc[1947:LAST_COMPLETE_YEAR].dropna()
        x, y = s.index.to_numpy(float), s.to_numpy(float)
        t = fit_trend(x, y)
        ax.plot(x, y, color=colour, linewidth=1.1, alpha=0.55, marker="o",
                markersize=2.4)
        ax.plot(x, np.polyval(np.polyfit(x, y, 1), x), color=INK, linewidth=2.0)
        ax.plot(x, loess_curve(x, y, frac=0.30), color=STATUS["critical"],
                linewidth=1.6)
        verdict = "significant" if t.ols_significant else "not significant"
        ax.set_title(f"{name}: {t.slope_per_decade:+.3f} {unit}/decade, {verdict}",
                     fontsize=9.5)
        ax.set_ylabel(unit)
    for ax in axes[1]:
        ax.set_xlabel("year")
    fig.suptitle(title, fontsize=11, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    save_fig(fig, figures / path)


def fig_temperature_thresholds(counts: pd.DataFrame, figures: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 5.4), sharex=True)
    for ax, (col, colour) in zip(axes.ravel(), zip(counts.columns, SERIES)):
        s = counts[col].dropna()
        x, y = s.index.to_numpy(float), s.to_numpy(float)
        t = fit_trend(x, y)
        ax.plot(x, y, color=colour, linewidth=1.1, alpha=0.6, marker="o",
                markersize=2.4)
        ax.plot(x, loess_curve(x, y, frac=0.30), color=INK, linewidth=2.0)
        verdict = "significant" if t.ols_significant else "not significant"
        ax.set_title(f"{col}: {t.slope_per_decade:+.2f} days/decade, {verdict}",
                     fontsize=9.5)
        ax.set_ylabel("days per year")
    for ax in axes[1]:
        ax.set_xlabel("year")
    fig.suptitle("Threshold day counts, from hourly extremes", fontsize=11,
                 fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    save_fig(fig, figures / "02-thresholds.png")


def fig_distribution_shift(day: pd.DataFrame, figures: Path) -> None:
    """Two 30-year periods overlaid, so a shift is distinguishable from a spread."""
    fig, ax = plt.subplots(figsize=(9.0, 3.6))
    specs = [((1946, 1975), SERIES[0]), ((1996, 2025), SERIES[1])]
    bins = np.linspace(-6, 24, 61)
    for (lo, hi), colour in specs:
        s = day.loc[(day["year"] >= lo) & (day["year"] <= hi), "mean"].dropna()
        ax.hist(s, bins=bins, histtype="step", linewidth=2.0, color=colour,
                density=True, label=f"{lo}-{hi}, mean {s.mean():.2f} degC")
    ax.set_xlabel("daily mean temperature (degC)")
    ax.set_ylabel("density")
    ax.set_yticks([])
    ax.set_title("Two 30-year periods: the whole distribution slides warmer")
    ax.legend(loc="upper left")
    save_fig(fig, figures / "02-distribution-shift.png")


def fig_precipitation_indices(idx: pd.DataFrame, figures: Path) -> None:
    picks = ["wet days >= 1 mm", "heavy days >= 10 mm",
             "mean wet-day amount (mm)", "wettest day (mm)"]
    fig, axes = plt.subplots(2, 2, figsize=(10.0, 5.4), sharex=True)
    for ax, (col, colour) in zip(axes.ravel(), zip(picks, SERIES)):
        s = idx[col].dropna()
        x, y = s.index.to_numpy(float), s.to_numpy(float)
        t = fit_trend(x, y)
        ax.plot(x, y, color=colour, linewidth=1.1, alpha=0.6, marker="o",
                markersize=2.4)
        ax.plot(x, loess_curve(x, y, frac=0.30), color=INK, linewidth=2.0)
        ax.axvline(BREAK_YEAR + 0.67, color=INK_MUTED, linewidth=1.0,
                   linestyle=(0, (4, 3)))
        verdict = "significant" if t.ols_significant else "not significant"
        ax.set_title(f"{col}: {t.slope_per_decade:+.3f}/decade, {verdict}",
                     fontsize=9.5)
    for ax in axes[1]:
        ax.set_xlabel("year")
    fig.suptitle("Precipitation indices, with the September 1993 break marked",
                 fontsize=11, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    save_fig(fig, figures / "03-indices.png")


def fig_monthly_shift(shift: pd.DataFrame, figures: Path) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 3.6))
    x = np.arange(len(shift))
    width = 0.39
    gap = 0.02
    ax.bar(x - (width + gap) / 2, shift.iloc[:, 0], width=width, color=SERIES[0],
           label=shift.columns[0])
    ax.bar(x + (width + gap) / 2, shift.iloc[:, 1], width=width, color=SERIES[1],
           label=shift.columns[1])
    ax.set_xticks(x, [m[:3] for m in shift.index], fontsize=8)
    ax.set_ylabel("mean monthly total (mm)")
    ax.set_title("Monthly rainfall: baseline against current normals")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    save_fig(fig, figures / "03-monthly-shift.png")


def fig_step_diagnosis(frames: dict, figures: Path) -> None:
    """Where the September 1993 discontinuity actually lives.

    Three panels, same axis. The daily maximum crosses the break without a
    step; the daily minimum drops by most of a degree; the difference between
    them therefore jumps. That pattern is what makes the case that the step is
    instrumental rather than climatic: a real climate shift does not lift the
    afternoon and drop the night on the same day, and nothing else in the record
    changed at that hour.
    """
    series = [
        ("Mean of daily maxima", frames["annual_max"], SERIES[1]),
        ("Mean of daily minima", frames["annual_min"], SERIES[0]),
        ("Diurnal temperature range", frames["annual_max"] - frames["annual_min"],
         SERIES[3]),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(9.5, 7.6), sharex=True)
    for ax, (name, s, colour) in zip(axes, series):
        s = s.loc[1946:LAST_COMPLETE_YEAR].dropna()
        x, y = s.index.to_numpy(float), s.to_numpy(float)
        model = step_trend_model(s)
        ax.plot(x, y, color=colour, linewidth=1.2, alpha=0.65, marker="o",
                markersize=2.6)
        centre = x.mean()
        slope = model["trend with step (per decade)"] / 10.0
        step = model["step at 1993"]
        base = y.mean() - slope * (x - centre).mean() - step * (x >= BREAK_YEAR + 0.67).mean()
        for lo, hi in [(1946, BREAK_YEAR), (BREAK_YEAR + 1, LAST_COMPLETE_YEAR)]:
            seg = x[(x >= lo) & (x <= hi)]
            ax.plot(seg, base + slope * (seg - centre)
                    + step * (seg >= BREAK_YEAR + 0.67), color=INK, linewidth=2.2)
        ax.axvline(BREAK_YEAR + 0.67, color=INK_MUTED, linewidth=1.0,
                   linestyle=(0, (4, 3)))
        marker = "significant" if model["step p"] < 0.05 else "not significant"
        ax.set_title(
            f"{name}: trend {model['trend with step (per decade)']:+.3f} degC/decade, "
            f"step {model['step at 1993']:+.2f} degC ({marker}, p = {model['step p']:.2g})",
            fontsize=9.5)
        ax.set_ylabel("degC")
    axes[2].set_xlabel("year")
    fig.suptitle("The 1993 discontinuity is in the daily minimum alone",
                 fontsize=11, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    save_fig(fig, figures / "02-step-diagnosis.png")
