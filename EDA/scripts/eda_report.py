# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pandas>=2.2",
#   "numpy>=1.26",
#   "matplotlib>=3.9",
#   "scipy>=1.13",
#   "statsmodels>=0.14",
# ]
# ///
"""Generate the figures and tables the EDA documents quote.

    uv run EDA/scripts/eda_report.py --section review
    uv run EDA/scripts/eda_report.py --section forms
    uv run EDA/scripts/eda_report.py --section all

Writes PNGs to `EDA/figures/` and CSVs to `EDA/stats/`. The markdown documents
are written by hand around this output; every number they quote lives in a CSV
here, so a re-run that changes a number shows as a git diff rather than as
silent drift between the prose and the data.

Output is deterministic: same input, byte-identical files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eda_forms import run_forms  # noqa: E402

from eda_common import (  # noqa: E402
    BASELINE,
    DIVERGING,
    GRID,
    INDICATOR_CODES,
    INDICATOR_COLUMNS,
    INK,
    INK_MUTED,
    INK_SECONDARY,
    LAST_COMPLETE_YEAR,
    NORMALS,
    RAW_COLUMNS,
    SERIES,
    STATUS,
    SURFACE,
    TRACE_RAIN_CODES,
    UNDOCUMENTED_INDICATOR,
    VARIABLES,
    apply_style,
    clean,
    daily,
    file_digest,
    load_raw,
    save_fig,
    save_table,
)

REPO = Path(__file__).resolve().parents[2]
FIGURES = REPO / "EDA" / "figures"
STATS = REPO / "EDA" / "stats"
# The gzipped CSV is the committed artefact; the uncompressed one is
# git-ignored, so this default is the file a fresh clone actually has.
# pandas decompresses by extension, so no separate step is needed.
DEFAULT_CSV = REPO / "data" / "dublin_airport-meteo-1946-2026-data.csv.gz"

# A run of identical hourly values longer than this is physically implausible
# for the variable and is reported as a suspected stuck sensor or an outage
# stored as a value. The thresholds differ because the variables do: air
# pressure drifts continuously and never repeats to 0.1 hPa for a day, while
# relative humidity genuinely pins at 100% through a long fog, and rain and
# sunshine are legitimately zero for long stretches.
SUSPECT_RUN_HOURS: dict[str, int] = {
    "temp": 12, "wetb": 12, "dewpt": 18, "vappr": 12, "msl": 12,
    "rhum": 48, "wdsp": 24, "vis": 48, "clht": 72, "clamt": 72,
    "wddir": 24, "sun": 168, "rain": 336,
}


# --------------------------------------------------------------------------
# Section 1 - the complete data review
# --------------------------------------------------------------------------

def table_source(csv_path: Path, raw: pd.DataFrame) -> pd.DataFrame:
    """Provenance: which file, which bytes, which period."""
    rows = {
        "source file": csv_path.name,
        "sha256": file_digest(csv_path),
        "rows": f"{len(raw):,}",
        "columns": str(len(raw.columns) - 4),  # minus the derived year/month/hour/doy
        "first observation (UTC)": str(raw["date"].min()),
        "last observation (UTC)": str(raw["date"].max()),
        "station": "Dublin Airport, 53.428 N, -6.241 E, 71 m",
        "licence": "Met Eireann, CC BY 4.0",
    }
    return pd.DataFrame({"value": pd.Series(rows)}).rename_axis("field")


def table_schema() -> pd.DataFrame:
    """Every raw column mapped to its role, resolving the five duplicate names."""
    from eda_common import VARIABLES_BY_KEY

    rows = []
    for col in RAW_COLUMNS:
        if col == "date":
            rows.append((col, "timestamp", "Date and time", "UTC", ""))
        elif col in INDICATOR_COLUMNS:
            target = col.removeprefix("ind_")
            rows.append((col, "indicator", f"Indicator qualifying `{target}`",
                         "code", "named `ind` in the source header"))
        elif col in ("ww", "w"):
            label = "Present weather" if col == "ww" else "Past weather"
            rows.append((col, "synop code", f"{label} (SYNOP)", "code", ""))
        else:
            v = VARIABLES_BY_KEY[col]
            sentinel = "" if v.sentinel is None else f"{v.sentinel:g} = {v.sentinel_meaning}"
            rows.append((col, "variable", v.label, v.unit, sentinel))
    return pd.DataFrame(
        rows, columns=["column", "role", "meaning", "unit", "note"]
    ).set_index("column")


def table_completeness(raw: pd.DataFrame) -> pd.DataFrame:
    """Null and sentinel census per variable, plus the timestamp continuity check."""
    n = len(raw)
    rows = []
    for v in VARIABLES:
        nulls = int(raw[v.key].isna().sum())
        sentinels = (
            int((raw[v.key] == v.sentinel).sum()) if v.sentinel is not None else 0
        )
        usable = n - nulls - sentinels
        rows.append({
            "variable": v.key,
            "label": v.label,
            "unit": v.unit,
            "rows": n,
            "null": nulls,
            "null %": 100.0 * nulls / n,
            "sentinel": sentinels,
            "sentinel %": 100.0 * sentinels / n,
            "usable": usable,
            "usable %": 100.0 * usable / n,
        })
    return pd.DataFrame(rows).set_index("variable")


def table_continuity(raw: pd.DataFrame) -> pd.DataFrame:
    """Is the hourly series actually continuous? Checked, not assumed."""
    expected = pd.date_range(raw["date"].min(), raw["date"].max(), freq="h")
    present = set(raw["date"])
    missing = [t for t in expected if t not in present]
    gaps = pd.Series(raw["date"].diff().dropna().value_counts()).sort_index()
    rows = {
        "expected hourly timestamps": f"{len(expected):,}",
        "rows present": f"{len(raw):,}",
        "distinct timestamps": f"{raw['date'].nunique():,}",
        "duplicate timestamps": f"{len(raw) - raw['date'].nunique():,}",
        "missing timestamps": f"{len(missing):,}",
        "distinct inter-row gaps": ", ".join(
            f"{str(k)} x {v:,}" for k, v in gaps.items()
        ),
    }
    return pd.DataFrame({"value": pd.Series(rows)}).rename_axis("check")


def table_univariate(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Distribution summary per variable, sentinels already removed.

    Wind direction is circular, so its mean is the circular one and its
    standard deviation and skew are left empty: both describe distance from a
    mean along a line, and there is no line. The arithmetic mean of this column
    reads 205.9 degrees against a circular mean of 235.6, and the gap reaches
    60 degrees within a single month, so it is not a rounding question.
    """
    from eda_common import circular_mean_deg

    rows = []
    for v in VARIABLES:
        s = clean_df[v.key].dropna()
        circular = v.aggregate == "circular"
        rows.append({
            "variable": v.key,
            "unit": v.unit,
            "n": int(s.size),
            "min": s.min(),
            "p5": s.quantile(0.05),
            "p25": s.quantile(0.25),
            "median": s.median(),
            "mean": (circular_mean_deg(s.to_numpy(dtype=float))
                     if circular else s.mean()),
            "p75": s.quantile(0.75),
            "p95": s.quantile(0.95),
            "max": s.max(),
            "std": np.nan if circular else s.std(),
            "skew": np.nan if circular else s.skew(),
        })
    return pd.DataFrame(rows).set_index("variable")


def table_indicator_codes(raw: pd.DataFrame) -> pd.DataFrame:
    """Every indicator value present, with its documented meaning or lack of one."""
    rows = []
    n = len(raw)
    for col in INDICATOR_COLUMNS:
        counts = raw[col].value_counts().sort_index()
        for code, count in counts.items():
            code = int(code)
            meaning = INDICATOR_CODES[col].get(code)
            rows.append({
                "indicator": col,
                "code": code,
                "count": int(count),
                "share %": 100.0 * count / n,
                "documented meaning": meaning if meaning else "NOT IN KeyHourly.txt",
            })
    return pd.DataFrame(rows).set_index("indicator")


def table_indicator_era(raw: pd.DataFrame) -> pd.DataFrame:
    """Per year: the undocumented block, the trace flags, and rain occurrence.

    These three columns together are the reason the precipitation document is
    built on totals rather than on counts of rain hours.
    """
    g = raw.groupby("year")
    out = pd.DataFrame({
        "hours": g.size(),
        "undocumented 111 %": 100.0 * g["ind_temp"].apply(
            lambda s: (s == UNDOCUMENTED_INDICATOR).mean()),
        "trace flagged %": 100.0 * g["ind_rain"].apply(
            lambda s: s.isin(TRACE_RAIN_CODES).mean()),
        "hours with rain > 0 %": 100.0 * g["rain"].apply(lambda s: (s > 0).mean()),
        "annual rain total mm": g["rain"].sum(min_count=1),
    })
    out.index.name = "year"
    return out


def find_undocumented_blocks(raw: pd.DataFrame) -> pd.DataFrame:
    """The contiguous runs of the undocumented indicator value."""
    mask = raw["ind_temp"] == UNDOCUMENTED_INDICATOR
    block_id = (mask != mask.shift()).cumsum()
    rows = []
    for _, g in raw[mask].groupby(block_id[mask]):
        rows.append({
            "start (UTC)": str(g["date"].min()),
            "end (UTC)": str(g["date"].max()),
            "hours": len(g),
        })
    out = pd.DataFrame(rows)
    out.index.name = "block"
    return out


def table_suspect_runs(raw: pd.DataFrame) -> pd.DataFrame:
    """Runs of an identical value long enough to be an outage rather than weather.

    A stuck sensor and a genuinely constant quantity look the same in the data;
    what separates them is how long the constancy lasts relative to how fast the
    variable really moves. The thresholds are in SUSPECT_RUN_HOURS and are
    per-variable for that reason.
    """
    rows = []
    for v in VARIABLES:
        s = raw[v.key]
        run_id = (s != s.shift()).cumsum()
        sizes = s.groupby(run_id).agg(["size", "first"])
        threshold = SUSPECT_RUN_HOURS[v.key]
        flagged = sizes[sizes["size"] >= threshold].sort_values("size", ascending=False)
        for run, row in flagged.head(3).iterrows():
            start_idx = run_id[run_id == run].index[0]
            rows.append({
                "variable": v.key,
                "value": row["first"],
                "hours": int(row["size"]),
                "days": round(int(row["size"]) / 24.0, 1),
                "start (UTC)": str(raw["date"].iloc[start_idx]),
                "threshold hours": threshold,
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["variable", "value", "hours", "days",
                                     "start (UTC)", "threshold hours"]).set_index("variable")
    return out.sort_values(["variable", "hours"], ascending=[True, False]).set_index("variable")


def table_zero_sun_spells(raw: pd.DataFrame) -> pd.DataFrame:
    """Consecutive days recording exactly zero sunshine.

    A sunless winter day in Ireland is ordinary. Twelve in a row is not, and a
    run that long is far likelier to be an instrument gap written as 0.0 than a
    fortnight without a break in the cloud. Reported so a reader can judge
    rather than take the zeros at face value.
    """
    day_sun = raw.groupby(raw["date"].dt.normalize())["sun"].sum(min_count=1)
    zero = day_sun == 0.0
    run_id = (zero != zero.shift()).cumsum()
    rows = []
    for _, g in day_sun[zero].groupby(run_id[zero]):
        if len(g) >= 7:
            rows.append({
                "start": str(g.index.min().date()),
                "end": str(g.index.max().date()),
                "days": len(g),
                "month": g.index.min().strftime("%B"),
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["start", "end", "days", "month"]).rename_axis("spell")
    out = out.sort_values("days", ascending=False).reset_index(drop=True)
    out.index.name = "spell"
    return out


RAIN_BINS: list[tuple[float, float, str]] = [
    (0.0, 0.0, "exactly 0.0"),
    (0.1, 0.1, "0.1 (the smallest step)"),
    (0.2, 0.2, "0.2"),
    (0.3, 0.5, "0.3 to 0.5"),
    (0.6, 1.0, "0.6 to 1.0"),
    (1.1, 1e6, "above 1.0"),
]


def table_rain_granularity(raw: pd.DataFrame) -> pd.DataFrame:
    """What actually changed about rain recording at the 1993 boundary.

    The trace flags vanishing looks alarming until the amounts are binned. If
    the break had changed how rain is measured, every bin would move. If it only
    changed the smallest detectable amount, the step is confined to the bottom
    bin and heavy rain is untouched. This table decides which of those is true,
    and so decides how much of the precipitation document is allowed to cross
    September 1993.
    """
    pre = raw[(raw["year"] >= 1946) & (raw["year"] <= 1992)]
    post = raw[(raw["year"] >= 1994) & (raw["year"] <= LAST_COMPLETE_YEAR)]
    rows = []
    for lo, hi, label in RAIN_BINS:
        a = 100.0 * ((pre["rain"] >= lo) & (pre["rain"] <= hi)).mean()
        b = 100.0 * ((post["rain"] >= lo) & (post["rain"] <= hi)).mean()
        rows.append({"hourly rain (mm)": label, "1946-1992 % of hours": a,
                     "1994-2025 % of hours": b, "step (pp)": b - a})
    out = pd.DataFrame(rows).set_index("hourly rain (mm)")
    return out


def table_rain_daily_thresholds(raw: pd.DataFrame) -> pd.DataFrame:
    """The same question asked of daily totals, which is what document 3 uses."""
    pre = raw[(raw["year"] >= 1946) & (raw["year"] <= 1992)]
    post = raw[(raw["year"] >= 1994) & (raw["year"] <= LAST_COMPLETE_YEAR)]
    d_pre = pre.groupby(pre["date"].dt.normalize())["rain"].sum(min_count=1)
    d_post = post.groupby(post["date"].dt.normalize())["rain"].sum(min_count=1)
    rows = []
    for thr in (0.2, 1.0, 5.0, 10.0, 20.0):
        a = 100.0 * (d_pre >= thr).mean()
        b = 100.0 * (d_post >= thr).mean()
        rows.append({"threshold": f"days >= {thr:g} mm", "1946-1992 %": a,
                     "1994-2025 %": b, "step (pp)": b - a})
    rows.append({"threshold": "mean wet-day amount (>= 1 mm), mm",
                 "1946-1992 %": d_pre[d_pre >= 1].mean(),
                 "1994-2025 %": d_post[d_post >= 1].mean(),
                 "step (pp)": d_post[d_post >= 1].mean() - d_pre[d_pre >= 1].mean()})
    rows.append({"threshold": "mean annual total, mm",
                 "1946-1992 %": pre.groupby("year")["rain"].sum().mean(),
                 "1994-2025 %": post.groupby("year")["rain"].sum().mean(),
                 "step (pp)": post.groupby("year")["rain"].sum().mean()
                              - pre.groupby("year")["rain"].sum().mean()})
    return pd.DataFrame(rows).set_index("threshold")


def table_zero_sun_verified(raw: pd.DataFrame, spells: pd.DataFrame) -> pd.DataFrame:
    """Cross-examine the long zero-sunshine spells against the sky they claim.

    A stuck sunshine sensor and a fortnight of unbroken overcast produce the
    same zeros. Cloud amount, cloud ceiling and rainfall are recorded by
    different instruments, so they can settle it: genuine overcast shows high
    midday cloud, a detected ceiling in every hour, and rain. That is what these
    spells show, so the zeros stay in the analysis as observations.
    """
    if spells.empty:
        return pd.DataFrame()
    rows = []
    for _, spell in spells.head(6).iterrows():
        start = pd.Timestamp(spell["start"])
        end = pd.Timestamp(spell["end"]) + pd.Timedelta("1D")
        window = raw[(raw["date"] >= start) & (raw["date"] < end)]
        midday = window[(window["hour"] >= 10) & (window["hour"] <= 14)]
        month_all = raw[(raw["month"] == start.month) &
                        (raw["hour"] >= 10) & (raw["hour"] <= 14)]
        rows.append({
            "spell": f"{spell['start']} to {spell['end']}",
            "days": int(spell["days"]),
            "midday cloud (okta)": midday["clamt"].mean(),
            "same month, all years (okta)": month_all["clamt"].mean(),
            "midday hours below 6 okta %": 100.0 * (midday["clamt"] < 6).mean(),
            "hours with no ceiling %": 100.0 * (midday["clht"] == 999).mean(),
            "rain over spell (mm)": window["rain"].sum(),
            "verdict": "overcast, consistent" if (midday["clamt"] < 6).mean() < 0.05
                       else "REVIEW",
        })
    return pd.DataFrame(rows).set_index("spell")


def table_zero_sun_by_decade(raw: pd.DataFrame) -> pd.DataFrame:
    """How often a whole day records no sunshine, by decade.

    A real decline, but not necessarily a real climate signal: a modern
    electronic sensor can register a brief weak beam that a Campbell-Stokes card
    would not have burned. The trend and the instrument change point the same
    way, so this number cannot separate them and is reported as a caution.
    """
    day_sun = raw.groupby(raw["date"].dt.normalize())["sun"].sum(min_count=1)
    frame = day_sun.to_frame("sun")
    frame["decade"] = (frame.index.year // 10) * 10
    out = frame.groupby("decade")["sun"].agg(
        **{"days": "size", "days with zero sun %": lambda s: 100.0 * (s == 0).mean(),
           "mean daily sunshine (h)": "mean"})
    return out


def fig_rain_granularity(bins: pd.DataFrame) -> None:
    """Two eras side by side. The step lives in one bin and nowhere else.

    The "exactly 0.0" bin is left off the chart: it is the complement of every
    other bar, it is 87% on its own, and including it would flatten the bins
    that carry the finding. A log axis would fit them all in, but bar length
    would stop being proportional to the value, which is the one thing a bar is
    for. Its share is in the table instead.
    """
    plotted = bins.drop(index="exactly 0.0")
    fig, ax = plt.subplots(figsize=(9.0, 3.4))
    y = np.arange(len(plotted))
    height = 0.38
    gap = 0.02  # surface gap between adjacent bars
    ax.barh(y - (height + gap) / 2, plotted["1946-1992 % of hours"], height=height,
            color=SERIES[0], label="1946-1992, manual era")
    ax.barh(y + (height + gap) / 2, plotted["1994-2025 % of hours"], height=height,
            color=SERIES[1], label="1994-2025, after the break")
    ax.set_yticks(y, plotted.index, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("% of all hours in the era")
    ax.set_xlim(0, 4.9)
    ax.set_title("The 1993 break moves the smallest rain amounts and nothing else")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    for i, (_, row) in enumerate(plotted.iterrows()):
        step = row["step (pp)"]
        emphasise = abs(step) >= 0.5
        ax.annotate(
            f"{step:+.2f} pp",
            xy=(max(row["1994-2025 % of hours"], row["1946-1992 % of hours"]), i),
            xytext=(7, -3), textcoords="offset points", fontsize=8,
            fontweight="bold" if emphasise else "normal",
            color=STATUS["critical"] if emphasise else INK_MUTED)
    zero = bins.loc["exactly 0.0"]
    fig.text(
        0.5,
        -0.02,
        f"Hours with no rain at all fall from {zero['1946-1992 % of hours']:.1f}% to "
        f"{zero['1994-2025 % of hours']:.1f}% ({zero['step (pp)']:+.2f} pp). That bar is "
        f"left off so the rest stays readable.",
        ha="center", fontsize=7.5, color=INK_MUTED)
    save_fig(fig, FIGURES / "01-rain-granularity.png")


def table_break_register(raw: pd.DataFrame, clean_df: pd.DataFrame) -> pd.DataFrame:
    """What the September 1993 break does to each variable, in comparable units.

    Raw differences across the break are not comparable between a pressure in
    hPa and a cloud amount in oktas, so the step is also given in units of the
    variable's own year-to-year standard deviation. That is the number that
    says whether a step is large enough to contaminate a trend: a step of a
    tenth of a standard deviation is noise, a step of two is a different
    instrument wearing the same name.

    This is a screening table, not a verdict. A real step and a real climate
    trend both put a difference here, and nothing in this table separates them;
    it says which variables need the question asked, and the temperature and
    precipitation documents ask it.
    """
    pre_years = (raw["year"] >= 1946) & (raw["year"] <= 1992)
    post_years = (raw["year"] >= 1994) & (raw["year"] <= LAST_COMPLETE_YEAR)
    rows = []
    for v in VARIABLES:
        if v.aggregate == "circular":
            continue  # a mean direction does not subtract meaningfully
        annual_series = (
            clean_df.groupby("year")[v.key].sum(min_count=1)
            if v.aggregate == "sum" else clean_df.groupby("year")[v.key].mean()
        )
        if v.aggregate == "sum":
            # a partial year has a smaller total for arithmetic reasons, not weather
            annual_series = annual_series.loc[:LAST_COMPLETE_YEAR]
        pre = annual_series.loc[1946:1992].mean()
        post = annual_series.loc[1994:LAST_COMPLETE_YEAR].mean()
        sd = annual_series.loc[1946:LAST_COMPLETE_YEAR].std()
        rows.append({
            "quantity": f"{v.label} ({v.unit})",
            "1946-1992": pre,
            "1994-2025": post,
            "step": post - pre,
            "step / annual SD": (post - pre) / sd if sd else np.nan,
        })

    def share(mask: pd.Series, label: str) -> None:
        pre = 100.0 * mask[pre_years].mean()
        post = 100.0 * mask[post_years].mean()
        annual = 100.0 * mask.groupby(raw["year"]).mean()
        sd = annual.loc[1946:LAST_COMPLETE_YEAR].std()
        rows.append({"quantity": label, "1946-1992": pre, "1994-2025": post,
                     "step": post - pre,
                     "step / annual SD": (post - pre) / sd if sd else np.nan})

    share(raw["rain"] > 0, "Hours recording any rain (%)")
    share(raw["rain"] > 1.0, "Hours recording over 1 mm of rain (%)")
    share(raw["wddir"] == 0, "Hours recorded as calm (%)")
    share(raw["clht"] == 999, "Hours with no cloud ceiling (%)")
    share(raw["ind_rain"].isin(TRACE_RAIN_CODES), "Hours flagged trace (%)")
    return pd.DataFrame(rows).set_index("quantity")


def table_climatology(clean_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monthly and hour-of-day climatology, one column per variable.

    Rain and sunshine are amounts per hour, so their monthly figure is the mean
    *monthly total* rather than a mean hourly rate: "72 mm in a typical January"
    is a climatology a reader can use, "0.089 mm in a typical January hour" is
    the same fact rendered unreadable. The hour-of-day figure stays a mean per
    hour, which is what that axis is asking for.
    """
    from eda_common import circular_mean_deg

    def agg(frame: pd.DataFrame, by: str, totals: bool) -> pd.DataFrame:
        cols = {}
        for v in VARIABLES:
            g = frame.groupby(by)[v.key]
            if v.aggregate == "circular":
                cols[v.key] = g.apply(lambda s: circular_mean_deg(s.to_numpy(dtype=float)))
            elif v.aggregate == "sum" and totals:
                # total per calendar month per year, then averaged over years.
                # The completeness gate is the point: the record ends on
                # 2026-08-01 00:00, so August 2026 holds one hour of 744 and was
                # being averaged in as a whole dry, sunless August alongside
                # eighty real ones. Same idea as daily()'s min_hours and
                # annual()'s min_days, which this path never had.
                per_month = frame.groupby(["year", by])[v.key].sum(min_count=1)
                hours = frame.groupby(["year", by])[v.key].count()
                expected = pd.Series(
                    [pd.Period(year=y, month=m, freq="M").days_in_month * 24
                     for y, m in per_month.index],
                    index=per_month.index)
                per_month = per_month.loc[hours >= 0.9 * expected]
                cols[v.key] = per_month.groupby(level=1).mean()
            else:
                cols[v.key] = g.mean()
        return pd.DataFrame(cols)

    monthly = agg(clean_df, "month", totals=True)
    monthly.index.name = "month"
    diurnal = agg(clean_df, "hour", totals=False)
    diurnal.index.name = "hour (UTC)"
    return monthly, diurnal


# Met Eireann's published Dublin Airport 1991-2020 climate averages, monthly
# rainfall in mm and the annual mean air temperature, transcribed from
# https://www.met.ie/cms/assets/uploads/2023/07/www_met_ie_dublin_9120-1.htm
# (the published table gives no annual sunshine total, so sunshine cannot be
# checked this way). This is the only external reference in the review: every
# other number is computed from the source file, and a file can be internally
# consistent and still wrong.
PUBLISHED_1991_2020_RAIN_MM: list[float] = [
    61.8, 52.4, 51.4, 55.0, 57.0, 64.0, 61.0, 73.4, 63.3, 78.4, 82.7, 72.1,
]
PUBLISHED_1991_2020_TEMP_C = 9.7


def table_external_validation(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Check this file against Met Eireann's own published normals.

    Everything else in this review is the data checked against itself, which
    cannot catch a misread unit, a mis-assigned column or a wrong aggregation
    rule: those produce a perfectly self-consistent wrong answer. Recomputing
    the published 1991-2020 normals from this file and comparing is the one
    test that can.
    """
    lo, hi = NORMALS
    window = clean_df[(clean_df["year"] >= lo) & (clean_df["year"] <= hi)]
    monthly_total = (window.groupby(["year", "month"])["rain"].sum(min_count=1)
                     .groupby(level=1).mean())
    rows = []
    for month in range(1, 13):
        mine = float(monthly_total.loc[month])
        theirs = PUBLISHED_1991_2020_RAIN_MM[month - 1]
        rows.append({
            "quantity": f"Rainfall, month {month:02d} (mm)",
            "this file": mine, "Met Eireann published": theirs,
            "difference": mine - theirs,
            "difference %": 100.0 * (mine - theirs) / theirs,
        })
    mine_annual = float(monthly_total.sum())
    theirs_annual = float(sum(PUBLISHED_1991_2020_RAIN_MM))
    rows.append({
        "quantity": "Rainfall, annual total (mm)",
        "this file": mine_annual, "Met Eireann published": theirs_annual,
        "difference": mine_annual - theirs_annual,
        "difference %": 100.0 * (mine_annual - theirs_annual) / theirs_annual,
    })
    mine_temp = float(window["temp"].mean())
    rows.append({
        "quantity": "Air temperature, annual mean (degC)",
        "this file": mine_temp, "Met Eireann published": PUBLISHED_1991_2020_TEMP_C,
        "difference": mine_temp - PUBLISHED_1991_2020_TEMP_C,
        "difference %": 100.0 * (mine_temp - PUBLISHED_1991_2020_TEMP_C)
                        / PUBLISHED_1991_2020_TEMP_C,
    })
    return pd.DataFrame(rows).set_index("quantity")


def table_correlation(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation between variables, on hourly values.

    Wind direction is excluded: a linear correlation on a circular quantity is
    meaningless, since 359 degrees and 1 degree are adjacent but numerically far
    apart.
    """
    keys = [v.key for v in VARIABLES if v.aggregate != "circular"]
    corr = clean_df[keys].corr(method="pearson")
    corr.index.name = "variable"
    return corr


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

# There is deliberately no coverage figure. Every year holds exactly its full
# complement of hours, so a bar chart of them is eighty identical bars carrying
# one bit of information; the continuity table states it in a line instead.


def fig_indicator_era(era: pd.DataFrame, blocks: pd.DataFrame) -> None:
    """The central figure of the review: what changed in September 1993.

    Three stacked panels on a shared time axis rather than one panel with three
    scales. The panels answer, in order: when did the undocumented flag appear,
    what disappeared at the same moment, and what did that do to the data.
    """
    fig, axes = plt.subplots(3, 1, figsize=(9.5, 7.4), sharex=True)
    break_year = 1993.67  # 1 September 1993

    for ax in axes:
        ax.axvline(break_year, color=INK_MUTED, linewidth=1.0, linestyle=(0, (4, 3)))

    ax = axes[0]
    # Complete years only, as fig_rain_total_unaffected does below. Plotting the
    # raw index put a 212-day 2026 on the end, and that year reverts to the
    # documented codes partway through, so the final point fell to 69% directly
    # under a title saying the undocumented value covers everything after 1993.
    era = era.loc[:LAST_COMPLETE_YEAR]
    ax.fill_between(era.index, era["undocumented 111 %"], color=SERIES[0], alpha=0.85,
                    linewidth=0)
    ax.set_ylabel("% of hours")
    ax.set_ylim(0, 105)
    ax.set_title("An undocumented indicator value appears in September 1993 "
                 "and covers everything after it")
    ax.annotate(
        f"value 111 in all five indicator columns\n"
        f"{blocks['hours'].sum():,} hours, {blocks.iloc[0]['start (UTC)'][:10]}"
        f" to {blocks.iloc[-1]['end (UTC)'][:10]}\nnot defined in KeyHourly.txt",
        xy=(2004, 100), xytext=(1996, 44), color=INK_SECONDARY, fontsize=8)

    ax = axes[1]
    ax.fill_between(era.index, era["trace flagged %"], color=SERIES[1], alpha=0.85,
                    linewidth=0)
    ax.set_ylabel("% of hours")
    ax.set_title("Trace-precipitation flags disappear at the same moment")
    ax.annotate("rain indicator 2 or 3,\n\"trace or sum of precipitation\"",
                xy=(1970, 30), xytext=(1948, 8), color=INK_SECONDARY, fontsize=8)

    ax = axes[2]
    ax.plot(era.index, era["hours with rain > 0 %"], color=SERIES[7], linewidth=2.0)
    ax.set_ylabel("% of hours")
    ax.set_xlabel("year")
    ax.set_title("So the share of hours recording any rain jumps, "
                 "with no change in the weather")
    pre = era.loc[1946:1992, "hours with rain > 0 %"].mean()
    post = era.loc[1994:LAST_COMPLETE_YEAR, "hours with rain > 0 %"].mean()
    ax.hlines(pre, 1946, 1993, color=INK_MUTED, linewidth=1.2, linestyle=(0, (2, 2)))
    ax.hlines(post, 1994, LAST_COMPLETE_YEAR, color=INK_MUTED, linewidth=1.2,
              linestyle=(0, (2, 2)))
    ax.annotate(f"{pre:.1f}% of hours", xy=(1962, pre), xytext=(1958, pre - 1.5),
                color=INK_SECONDARY, fontsize=8)
    ax.annotate(f"{post:.1f}% of hours", xy=(2006, post), xytext=(2004, post + 1.1),
                color=INK_SECONDARY, fontsize=8)
    save_fig(fig, FIGURES / "01-indicator-era.png")


def fig_rain_total_unaffected(era: pd.DataFrame) -> None:
    """The companion to the panel above: totals barely move where counts jump."""
    fig, ax = plt.subplots(figsize=(9.5, 3.2))
    complete = era.loc[:LAST_COMPLETE_YEAR]
    ax.plot(complete.index, complete["annual rain total mm"], color=SERIES[0],
            linewidth=1.6)
    ax.axvline(1993.67, color=INK_MUTED, linewidth=1.0, linestyle=(0, (4, 3)))
    pre = complete.loc[1946:1992, "annual rain total mm"].mean()
    post = complete.loc[1994:, "annual rain total mm"].mean()
    ax.hlines(pre, 1946, 1993, color=SERIES[1], linewidth=2.0)
    ax.hlines(post, 1994, LAST_COMPLETE_YEAR, color=SERIES[1], linewidth=2.0)
    ax.annotate(f"mean {pre:.0f} mm", xy=(1965, pre), xytext=(1960, pre - 165),
                color=INK_SECONDARY, fontsize=8)
    ax.annotate(f"mean {post:.0f} mm", xy=(2008, post), xytext=(2003, post + 175),
                color=INK_SECONDARY, fontsize=8)
    ax.set_ylabel("mm")
    ax.set_xlabel("year")
    ax.set_title("Annual totals are barely touched by the same break "
                 "(1946-1992 against 1994-2025)")
    save_fig(fig, FIGURES / "01-rain-total-vs-break.png")


def _grid(n: int) -> tuple[int, int]:
    cols = 4
    return (n + cols - 1) // cols, cols


def fig_distributions(clean_df: pd.DataFrame) -> None:
    rows, cols = _grid(len(VARIABLES))
    fig, axes = plt.subplots(rows, cols, figsize=(11.0, 2.3 * rows))
    flat = axes.ravel()
    for ax, v in zip(flat, VARIABLES):
        s = clean_df[v.key].dropna()
        ax.hist(s, bins=48, color=SERIES[0], linewidth=0, log=True)
        ax.set_title(f"{v.label}\n({v.unit})", fontsize=9)
        ax.tick_params(labelsize=7)
        ax.set_yticks([])
        ax.grid(axis="x", visible=False)
    for ax in flat[len(VARIABLES):]:
        ax.axis("off")
    fig.suptitle("Hourly distributions, sentinels removed (count on a log scale, "
                 "so zero-inflated variables still show their tails)",
                 fontsize=11, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    save_fig(fig, FIGURES / "01-distributions.png")


def fig_profiles(table: pd.DataFrame, xlabel: str, title: str, name: str,
                 xticks: list[int] | None = None, totals: bool = False) -> None:
    rows, cols = _grid(len(VARIABLES))
    fig, axes = plt.subplots(rows, cols, figsize=(11.0, 2.3 * rows))
    flat = axes.ravel()
    for ax, v in zip(flat, VARIABLES):
        unit = (f"{v.unit} per month" if totals and v.aggregate == "sum" else v.unit)
        ax.plot(table.index, table[v.key], color=SERIES[0], linewidth=1.8)
        ax.set_title(f"{v.label}\n({unit})", fontsize=9)
        ax.tick_params(labelsize=7)
        if xticks is not None:
            ax.set_xticks(xticks)
    for ax in flat[len(VARIABLES):]:
        ax.axis("off")
    fig.supxlabel(xlabel, fontsize=9, color=INK_SECONDARY)
    fig.suptitle(title, fontsize=11, fontweight="bold", color=INK, y=1.0)
    fig.tight_layout()
    save_fig(fig, FIGURES / name)


def fig_correlation(corr: pd.DataFrame) -> None:
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("div", list(DIVERGING))
    fig, ax = plt.subplots(figsize=(7.4, 6.4))
    im = ax.imshow(corr.to_numpy(), cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr)), corr.index, fontsize=8)
    ax.grid(visible=False)
    for i in range(len(corr)):
        for j in range(len(corr)):
            value = corr.iloc[i, j]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7,
                    color="#ffffff" if abs(value) > 0.55 else INK_SECONDARY)
    bar = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03)
    bar.set_label("Pearson r", color=INK_SECONDARY, fontsize=8)
    bar.ax.tick_params(labelsize=7, colors=INK_MUTED)
    bar.outline.set_edgecolor(GRID)
    ax.set_title("Five of these columns are two quantities in disguise",
                 fontsize=11, pad=12)
    save_fig(fig, FIGURES / "01-correlation.png")


def fig_zero_sun(raw: pd.DataFrame, spells: pd.DataFrame) -> None:
    """Put the longest zero-sunshine spell next to the sky that was recorded.

    Two panels on a shared day-of-year axis. The first asks whether the
    sunshine reading is anomalous, the second whether a different instrument
    agrees that it should be. A stuck sensor would show the red line on the
    floor of the first panel while the second sat at its normal level; genuine
    overcast puts both at their extremes together, which is what happens.

    The comparison is a median and a 5th-to-95th-percentile band across every
    year, not one line per year: eighty overlapping lines hide exactly the
    thing the figure exists to show.
    """
    if spells.empty:
        return
    worst = spells.iloc[0]
    start_ts = pd.Timestamp(worst["start"])
    end_ts = pd.Timestamp(worst["end"])
    lo, hi = start_ts.dayofyear - 6, end_ts.dayofyear + 6

    day_sun = raw.groupby(raw["date"].dt.normalize())["sun"].sum(min_count=1)
    midday = raw[(raw["hour"] >= 10) & (raw["hour"] <= 14)]
    day_cloud = midday.groupby(midday["date"].dt.normalize())["clamt"].mean()

    fig, axes = plt.subplots(2, 1, figsize=(9.5, 5.6), sharex=True)
    panels = [
        (axes[0], day_sun, "daily sunshine (h)",
         f"Sunshine reads exactly zero for {int(worst['days'])} days from {worst['start']}"),
        (axes[1], day_cloud, "midday cloud (okta)",
         "A different instrument agrees: the sky was full for every one of them"),
    ]
    for ax, series, ylabel, title in panels:
        frame = series.to_frame("v")
        frame["year"] = frame.index.year
        # Leap-adjusted: .dayofyear puts 10 March at 70 in a leap year and 69
        # otherwise, so pooling "all years" by it mixes adjacent calendar days
        # for every day past February. 29 February folds onto 28, as elsewhere.
        doy = np.asarray(frame.index.dayofyear)
        leap = np.asarray(frame.index.is_leap_year)
        frame["doy"] = np.where(leap & (doy >= 60), doy - 1, doy)
        window = frame[(frame["doy"] >= lo) & (frame["doy"] <= hi)]
        stats_by_doy = window.groupby("doy")["v"].agg(
            p05=lambda s: s.quantile(0.05),
            p50="median",
            p95=lambda s: s.quantile(0.95))
        ax.fill_between(stats_by_doy.index, stats_by_doy["p05"], stats_by_doy["p95"],
                        color=INK_MUTED, alpha=0.16, linewidth=0,
                        label="5th to 95th percentile, all years")
        ax.plot(stats_by_doy.index, stats_by_doy["p50"], color=INK_MUTED,
                linewidth=1.4, label="median, all years")
        target = window[window["year"] == start_ts.year].sort_values("doy")
        ax.plot(target["doy"], target["v"], color=STATUS["critical"], linewidth=2.4,
                marker="o", markersize=4, label=str(start_ts.year))
        ax.axvspan(start_ts.dayofyear, end_ts.dayofyear, color=STATUS["critical"],
                   alpha=0.07, linewidth=0)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=10)
    axes[1].set_xlabel("day of year")
    axes[1].set_ylim(0, 8.4)
    axes[0].legend(loc="upper center", ncols=3)
    fig.tight_layout()
    save_fig(fig, FIGURES / "01-zero-sun-spell.png")


def fig_sentinels(raw: pd.DataFrame) -> None:
    """Sentinel share per year, to check the sentinels are stable over time."""
    sentinel_vars = [v for v in VARIABLES if v.sentinel is not None]
    fig, ax = plt.subplots(figsize=(9.5, 3.2))
    for i, v in enumerate(sentinel_vars):
        share = raw.groupby("year")[v.key].apply(lambda s: 100.0 * (s == v.sentinel).mean())
        ax.plot(share.index, share, color=SERIES[i], linewidth=1.8,
                label=f"{v.key} = {v.sentinel:g} ({v.sentinel_meaning.split(',')[0]})")
    ax.axvline(1993.67, color=INK_MUTED, linewidth=1.0, linestyle=(0, (4, 3)))
    ax.set_ylabel("% of hours")
    ax.set_xlabel("year")
    ax.set_title("Sentinel frequency is not stable either")
    ax.legend(loc="center left", ncols=1)
    ax.set_ylim(-1.5, 38)
    ax.annotate("calm hours all but vanish at the same break:\nthe automated "
                "anemometer reports a direction\nwhere the manual observer logged calm",
                xy=(1994, 1.0), xytext=(1997, 8.0), color=INK_SECONDARY, fontsize=8,
                arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.8))
    save_fig(fig, FIGURES / "01-sentinels.png")


def run_review(csv_path: Path) -> None:
    print(f"reading {csv_path}")
    raw = load_raw(csv_path)
    cleaned = clean(raw)
    print(f"  {len(raw):,} rows, {raw['date'].min()} to {raw['date'].max()}")

    print("computing tables")
    source = table_source(csv_path, raw)
    schema = table_schema()
    completeness = table_completeness(raw)
    continuity = table_continuity(raw)
    univariate = table_univariate(cleaned)
    codes = table_indicator_codes(raw)
    era = table_indicator_era(raw)
    blocks = find_undocumented_blocks(raw)
    suspect = table_suspect_runs(raw)
    zero_sun = table_zero_sun_spells(raw)
    monthly, diurnal = table_climatology(cleaned)
    corr = table_correlation(cleaned)
    validation = table_external_validation(cleaned)
    breaks = table_break_register(raw, cleaned)
    rain_bins = table_rain_granularity(raw)
    rain_days = table_rain_daily_thresholds(raw)
    zero_sun_check = table_zero_sun_verified(raw, zero_sun)
    zero_sun_decade = table_zero_sun_by_decade(raw)

    save_table(source, STATS / "01-source.csv", float_format="%s")
    save_table(schema, STATS / "01-schema.csv", float_format="%s")
    save_table(completeness, STATS / "01-completeness.csv", float_format="%.4f")
    save_table(continuity, STATS / "01-continuity.csv", float_format="%s")
    save_table(univariate, STATS / "01-univariate.csv", float_format="%.4f")
    save_table(codes, STATS / "01-indicator-codes.csv", float_format="%.4f")
    save_table(era, STATS / "01-indicator-era.csv", float_format="%.4f")
    save_table(blocks, STATS / "01-undocumented-blocks.csv", float_format="%s")
    save_table(suspect, STATS / "01-suspect-runs.csv", float_format="%.4f")
    save_table(zero_sun, STATS / "01-zero-sun-spells.csv", float_format="%s")
    save_table(monthly, STATS / "01-monthly-climatology.csv", float_format="%.4f")
    save_table(diurnal, STATS / "01-diurnal-climatology.csv", float_format="%.4f")
    save_table(corr, STATS / "01-correlation.csv", float_format="%.4f")
    save_table(validation, STATS / "01-external-validation.csv", float_format="%.4f")
    save_table(breaks, STATS / "01-break-register.csv", float_format="%.4f")
    save_table(rain_bins, STATS / "01-rain-granularity.csv", float_format="%.4f")
    save_table(rain_days, STATS / "01-rain-daily-thresholds.csv", float_format="%.4f")
    save_table(zero_sun_check, STATS / "01-zero-sun-verified.csv", float_format="%.4f")
    save_table(zero_sun_decade, STATS / "01-zero-sun-by-decade.csv", float_format="%.4f")

    print("drawing figures")
    fig_indicator_era(era, blocks)
    fig_rain_total_unaffected(era)
    fig_distributions(cleaned)
    fig_profiles(monthly, "month", "Monthly climatology, 1946-2026",
                 "01-monthly-climatology.png", xticks=[1, 4, 7, 10], totals=True)
    fig_profiles(diurnal, "hour of day (UTC)", "Diurnal cycle, 1946-2026",
                 "01-diurnal-climatology.png", xticks=[0, 6, 12, 18])
    fig_correlation(corr)
    fig_zero_sun(raw, zero_sun)
    fig_sentinels(raw)
    fig_rain_granularity(rain_bins)

    print(f"  tables -> {STATS}")
    print(f"  figures -> {FIGURES}")


# --------------------------------------------------------------------------
# Sections 2 and 3 - temperature and precipitation
# --------------------------------------------------------------------------

def run_temperature(csv_path: Path) -> None:
    import eda_climate as ec

    print(f"reading {csv_path}")
    cleaned = clean(load_raw(csv_path))
    frames = ec.temperature_frames(cleaned)
    ann = frames["annual"]
    day = frames["day"]

    print("computing tables")
    trends = ec.table_temperature_trends(frames)
    breaks = ec.break_test(ann, "degC")
    # The break test is run on every derived temperature series, not only the
    # mean: the review's register flagged temperature as ambiguous, and the
    # ambiguity turns out to live in the daily minimum rather than the mean.
    break_all = pd.DataFrame([
        {"series": name, **ec.step_trend_model(s)}
        for name, s in [
            ("Annual mean", ann),
            ("Mean of daily maxima", frames["annual_max"]),
            ("Mean of daily minima", frames["annual_min"]),
            ("Diurnal temperature range",
             frames["annual_max"] - frames["annual_min"]),
        ]
    ]).set_index("series")
    decades = ec.decade_table(ann, "degC")
    thresholds = ec.table_temperature_thresholds(day)
    extremes = ec.table_temperature_extremes(cleaned, day)
    shift = ec.table_distribution_shift(day)
    anomalies = pd.DataFrame({
        "annual mean (degC)": ann.loc[1946:LAST_COMPLETE_YEAR],
        f"anomaly vs {ec.BASELINE[0]}-{ec.BASELINE[1]} (degC)":
            ec.anomaly(ann).loc[1946:LAST_COMPLETE_YEAR],
    })
    anomalies.index.name = "year"

    save_table(trends, STATS / "02-trends.csv", float_format="%.5f")
    save_table(breaks, STATS / "02-break-test.csv", float_format="%.5f")
    save_table(break_all, STATS / "02-break-test-all-series.csv", float_format="%.5f")
    # Threshold counts inherit whatever discontinuity their input carries. The
    # frost-day count is built on the daily minimum, so if the minimum has a
    # step then so does the count, and a naive reading would report rising
    # frost in a warming climate. Each count is tested the same way.
    break_thresholds = pd.DataFrame([
        {"count": col, **ec.step_trend_model(thresholds[col])}
        for col in thresholds.columns
    ]).set_index("count")
    save_table(break_thresholds, STATS / "02-break-test-thresholds.csv",
               float_format="%.5f")
    # A small p-value for a step at 1993 only means something if 1993 is
    # special. Scanning every candidate break year says whether it is.
    placebo = pd.DataFrame([
        {"series": name, **ec.placebo_break_scan(s)}
        for name, s in [
            ("Annual mean", ann),
            ("Mean of daily maxima", frames["annual_max"]),
            ("Mean of daily minima", frames["annual_min"]),
            ("Diurnal temperature range",
             frames["annual_max"] - frames["annual_min"]),
        ]
    ]).set_index("series")
    save_table(placebo, STATS / "02-placebo-break-scan.csv", float_format="%.5f")
    hourly_step = ec.table_hourly_step(cleaned[cleaned["year"] <= LAST_COMPLETE_YEAR])
    save_table(hourly_step, STATS / "02-hourly-step.csv", float_format="%.5f")
    save_table(decades, STATS / "02-decades.csv", float_format="%.4f")
    save_table(thresholds, STATS / "02-thresholds.csv", float_format="%.1f")
    save_table(extremes, STATS / "02-extremes.csv", float_format="%.3f")
    save_table(shift, STATS / "02-distribution-shift.csv", float_format="%.4f")
    save_table(anomalies, STATS / "02-annual-anomaly.csv", float_format="%.4f")

    print("drawing figures")
    ec.fig_anomaly_bars(ann, "degC",
                        "Annual mean temperature against the 1961-1990 baseline",
                        Path("02-annual-anomaly.png"), FIGURES)
    ec.fig_break_test(ann, "degC",
                      "Does the September 1993 break drive the temperature trend?",
                      Path("02-break-test.png"), FIGURES)
    ec.fig_seasonal_trends(day, "mean", "degC", "Temperature trend by season",
                           Path("02-seasonal-trends.png"), FIGURES)
    ec.fig_temperature_thresholds(thresholds, FIGURES)
    ec.fig_distribution_shift(day, FIGURES)
    ec.fig_step_diagnosis(frames, FIGURES)
    ec.fig_hourly_step(hourly_step, FIGURES)
    print(f"  tables -> {STATS}\n  figures -> {FIGURES}")


def run_precipitation(csv_path: Path) -> None:
    import eda_climate as ec

    print(f"reading {csv_path}")
    cleaned = clean(load_raw(csv_path))
    frames = ec.precipitation_frames(cleaned)
    ann = frames["annual"]
    day = frames["day"]

    print("computing tables")
    trends = ec.table_precipitation_trends(cleaned, frames)
    indices_early = ec.table_precipitation_indices(day)
    # The percentile indices measure whether rain arrives in heavier bursts,
    # which an annual total cannot see, so they get the same trend treatment as
    # everything else rather than only an era-to-era comparison.
    extra = [c for c in indices_early.columns if c.startswith(("R95p", "R99p"))]
    trends = pd.concat([trends, pd.DataFrame([
        ec.trend_row(c, ec._trend_of(indices_early[c]), "mm") for c in extra
    ]).set_index("series")])
    breaks = ec.break_test(ann, "mm")
    decades = ec.decade_table(ann, "mm")
    indices = indices_early
    extremes = ec.table_precipitation_extremes(cleaned, day)
    monthly = ec.table_monthly_shift(cleaned)
    anomalies = pd.DataFrame({
        "annual total (mm)": ann.loc[1946:LAST_COMPLETE_YEAR],
        f"anomaly vs {ec.BASELINE[0]}-{ec.BASELINE[1]} (mm)":
            ec.anomaly(ann).loc[1946:LAST_COMPLETE_YEAR],
    })
    anomalies.index.name = "year"

    save_table(trends, STATS / "03-trends.csv", float_format="%.5f")
    save_table(breaks, STATS / "03-break-test.csv", float_format="%.5f")
    save_table(decades, STATS / "03-decades.csv", float_format="%.3f")
    save_table(indices, STATS / "03-indices.csv", float_format="%.3f")
    save_table(extremes, STATS / "03-extremes.csv", float_format="%.3f")
    save_table(monthly, STATS / "03-monthly-shift.csv", float_format="%.3f")
    save_table(anomalies, STATS / "03-annual-anomaly.csv", float_format="%.3f")

    print("drawing figures")
    ec.fig_anomaly_bars(ann, "mm",
                        "Annual rainfall total against the 1961-1990 baseline",
                        Path("03-annual-anomaly.png"), FIGURES)
    ec.fig_break_test(ann, "mm",
                      "Does the September 1993 break drive the rainfall trend?",
                      Path("03-break-test.png"), FIGURES)
    ec.fig_seasonal_trends(day, "sum", "mm", "Rainfall trend by season",
                           Path("03-seasonal-trends.png"), FIGURES)
    ec.fig_precipitation_indices(indices, FIGURES)
    ec.fig_monthly_shift(monthly, FIGURES)
    print(f"  tables -> {STATS}\n  figures -> {FIGURES}")


# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="source hourly CSV; .gz is decompressed automatically")
    parser.add_argument("--section", default="review",
                        choices=["review", "temperature", "precipitation", "forms", "all"])
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"error: {args.csv} not found", file=sys.stderr)
        return 1

    apply_style()

    if args.section in ("review", "all"):
        run_review(args.csv)
    if args.section in ("temperature", "all"):
        run_temperature(args.csv)
    if args.section in ("precipitation", "all"):
        run_precipitation(args.csv)
    if args.section in ("forms", "all"):
        run_forms(args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
