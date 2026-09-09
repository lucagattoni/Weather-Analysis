"""Shared loading, cleaning, aggregation and trend fitting for the EDA documents.

Build-time code (CLAUDE.md, "Languages"): run once per data refresh by
`scripts/eda_report.py`, never in the browser. Everything it emits under `EDA/`
is a static fact - a figure or a table - that the markdown documents quote.

Determinism is a requirement, not a nicety: same input, byte-identical output,
so re-running does not churn git and a changed number shows up as a real diff.
That means no timestamps in any output, sorted iteration order, fixed figure
size and DPI, and the non-interactive matplotlib backend.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display, and identical output on every machine

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from statsmodels.nonparametric.smoothers_lowess import lowess  # noqa: E402

# --------------------------------------------------------------------------
# Schema
# --------------------------------------------------------------------------

# The source CSV has five columns literally named `ind`, so pandas renames them
# ind.1..ind.4 and the association with the variable each one qualifies is lost.
# This is the header as it actually is, in order, with each indicator bound to
# the variable it belongs to. Derived from the column order in the source file
# and confirmed against Met Eireann's KeyHourly.txt.
RAW_COLUMNS: list[str] = [
    "date",
    "ind_rain", "rain",
    "ind_temp", "temp",
    "ind_wetb", "wetb",
    "dewpt", "vappr", "rhum", "msl",
    "ind_wdsp", "wdsp",
    "ind_wddir", "wddir",
    "ww", "w", "sun", "vis", "clht", "clamt",
]

INDICATOR_COLUMNS: list[str] = [
    "ind_rain", "ind_temp", "ind_wetb", "ind_wdsp", "ind_wddir",
]


@dataclass(frozen=True)
class Variable:
    """One measured quantity.

    `sentinel` is a value that is a real observation but not a measurement on
    the variable's own scale, so it is excluded from ranges, means and
    histograms. `aggregate` says how a run of hours combines: a plain mean is
    wrong for the three amounts-per-hour and for a direction in degrees.
    """

    key: str
    label: str
    unit: str
    sentinel: float | None
    aggregate: str  # mean | sum | circular
    sentinel_meaning: str = ""


# Order here is the order tables and small-multiple grids are drawn in.
VARIABLES: list[Variable] = [
    Variable("temp",  "Air temperature",           "degC",        None, "mean"),
    Variable("rain",  "Precipitation amount",      "mm",          None, "sum"),
    Variable("wetb",  "Wet bulb temperature",      "degC",        None, "mean"),
    Variable("dewpt", "Dew point temperature",     "degC",        None, "mean"),
    Variable("vappr", "Vapour pressure",           "hPa",         None, "mean"),
    Variable("rhum",  "Relative humidity",         "%",           None, "mean"),
    Variable("msl",   "Mean sea level pressure",   "hPa",         None, "mean"),
    Variable("wdsp",  "Mean wind speed",           "knot",        None, "mean"),
    Variable("wddir", "Predominant wind direction", "deg",           0, "circular",
             "0 = calm, which is not a direction and is not north (360 is north)"),
    Variable("sun",   "Sunshine duration",         "h",           None, "sum"),
    Variable("vis",   "Visibility",                "m",           None, "mean"),
    Variable("clht",  "Cloud ceiling height",      "100s of ft",   999, "mean",
             "999 = no cloud ceiling detected"),
    Variable("clamt", "Cloud amount",              "okta",           9, "mean",
             "9 = sky obscured; the okta scale is 0..8"),
]

VARIABLES_BY_KEY: dict[str, Variable] = {v.key: v for v in VARIABLES}

# Verbatim from Met Eireann's KeyHourly.txt
# (https://www.met.ie/cms/assets/uploads/2018/05/KeyHourly.txt). The value 111,
# which covers 40% of this file, appears nowhere in that document.
INDICATOR_CODES: dict[str, dict[int, str]] = {
    "ind_rain": {
        0: "satisfactory", 1: "deposition", 2: "trace or sum of precipitation",
        3: "trace or sum of deposition", 4: "estimate precipitation",
        5: "estimate deposition", 6: "estimate trace of precipitation",
    },
    "ind_temp": {
        0: "positive", 1: "negative", 2: "positive estimated",
        3: "negative estimated", 4: "not available",
    },
    "ind_wetb": {
        0: "positive", 1: "negative", 2: "positive estimated",
        3: "negative estimated", 4: "not available", 5: "frozen negative",
    },
    "ind_wdsp": {
        2: "over 60 minutes", 4: "over 60 minutes and defective",
        6: "over 60 minutes and partially defective", 7: "n/a",
    },
    "ind_wddir": {
        2: "over 60 minutes", 4: "over 60 minutes and defective",
        6: "over 60 minutes and partially defective", 7: "n/a",
    },
}

UNDOCUMENTED_INDICATOR = 111

# Rain indicator codes whose rows are trace observations rather than measured
# amounts. Their near-total disappearance in September 1993 is what makes rain
# *occurrence* incomparable across that boundary; see the data review document.
TRACE_RAIN_CODES: tuple[int, ...] = (2, 3)

# WMO reference period, chosen as the anomaly baseline: it is the period
# published Irish and global series use, and it sits wholly inside the
# pre-1993 observation era.
BASELINE = (1961, 1990)
# The current WMO operational normals, tabulated alongside for reference.
NORMALS = (1991, 2020)

# 2026 is a partial year (ends 1 August), so it is excluded from every annual
# statistic and every trend. Stated in each document rather than left implicit.
LAST_COMPLETE_YEAR = 2025

SEASONS: dict[str, tuple[int, ...]] = {
    "Winter (DJF)": (12, 1, 2),
    "Spring (MAM)": (3, 4, 5),
    "Summer (JJA)": (6, 7, 8),
    "Autumn (SON)": (9, 10, 11),
}

# --------------------------------------------------------------------------
# Palette - the validated reference instance, light surface
# --------------------------------------------------------------------------

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
# Diverging pair for polarity (anomalies, correlations): blue to red through a
# neutral gray midpoint, never a rainbow and never a hue in the middle.
DIVERGING = ("#2a78d6", "#f0efec", "#d03b3b")
STATUS = {"good": "#0ca30c", "warning": "#fab219",
          "serious": "#ec835a", "critical": "#d03b3b"}


def apply_style() -> None:
    """Chart chrome: recessive grid and axes, thin marks, text in ink tokens."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.labelsize": 9,
        "axes.labelcolor": INK_SECONDARY,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelcolor": INK_SECONDARY,
        "ytick.labelcolor": INK_SECONDARY,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "legend.labelcolor": INK_SECONDARY,
        "lines.linewidth": 2.0,
        "lines.markersize": 4,
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "figure.autolayout": False,
    })


# --------------------------------------------------------------------------
# Loading and cleaning
# --------------------------------------------------------------------------

def load_raw(csv_path: Path) -> pd.DataFrame:
    """Read the source CSV with the real column names and a parsed timestamp.

    Nothing is dropped or altered here: sentinels, trace zeros and the
    undocumented indicator all survive, because the data review has to be able
    to count them. `clean()` is the step that removes them.
    """
    df = pd.read_csv(csv_path, skipinitialspace=True, low_memory=False)
    if len(df.columns) != len(RAW_COLUMNS):
        raise SystemExit(
            f"{csv_path}: expected {len(RAW_COLUMNS)} columns, found "
            f"{len(df.columns)}: {list(df.columns)}"
        )
    df.columns = RAW_COLUMNS
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y %H:%M")
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["hour"] = df["date"].dt.hour
    df["doy"] = df["date"].dt.dayofyear
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Replace each variable's sentinel with NaN so it never enters a statistic.

    A sentinel is a real observation, just not a measurement on the variable's
    scale: `clht` 999 means no ceiling was detected, not a ceiling at 99,900
    feet, and averaging it in would put the mean cloud base above the
    stratosphere. Counting them is the data review's job; this is the frame
    every other statistic runs on.
    """
    out = df.copy()
    for var in VARIABLES:
        if var.sentinel is not None:
            out.loc[out[var.key] == var.sentinel, var.key] = np.nan
    return out


def season_of(month: pd.Series) -> pd.Series:
    """Map month number to meteorological season label."""
    lookup = {m: name for name, months in SEASONS.items() for m in months}
    return month.map(lookup)


def season_year(date: pd.Series) -> pd.Series:
    """The year a season belongs to, with December counted into the next winter.

    Winter 1963 means December 1962 through February 1963, so December's rows
    carry the following year. Without this a "winter" is three months from two
    different winters and the coldest winter on record moves.
    """
    return date.dt.year + (date.dt.month == 12).astype(int)


# --------------------------------------------------------------------------
# Aggregation ladder
# --------------------------------------------------------------------------

def circular_mean_deg(values: np.ndarray) -> float:
    """Mean of directions in degrees. A naive mean of angles is not a direction."""
    v = values[~np.isnan(values)]
    if v.size == 0:
        return float("nan")
    rad = np.deg2rad(v)
    angle = np.rad2deg(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean()))
    return float(angle % 360.0)


def daily(df: pd.DataFrame, key: str, how: str | None = None,
          min_hours: int = 20) -> pd.DataFrame:
    """Collapse hourly rows to one row per day for one variable.

    `min_hours` is a completeness gate: a day assembled from a handful of hours
    is not a daily mean, and letting it through would put a spurious extreme in
    every threshold count. This series is hourly-complete, so the gate almost
    never fires, but it is the difference between a statistic that is right and
    one that happens to be right.

    Returns mean, min, max and count per day. The min and max are extremes of
    the hourly readings, not the true daily extremes a max/min thermometer
    records; the difference is small but systematic and every document that
    quotes a threshold count says so.
    """
    var = VARIABLES_BY_KEY[key]
    how = how or var.aggregate
    g = df.groupby(df["date"].dt.normalize())[key]
    if how == "circular":
        agg = g.apply(lambda s: circular_mean_deg(s.to_numpy(dtype=float)))
        out = agg.to_frame("mean")
        out["min"] = np.nan
        out["max"] = np.nan
    else:
        out = pd.DataFrame({
            "mean": g.sum(min_count=1) if how == "sum" else g.mean(),
            "min": g.min(),
            "max": g.max(),
        })
    out["count"] = g.count()
    out.index.name = "day"
    out.loc[out["count"] < min_hours, ["mean", "min", "max"]] = np.nan
    out["year"] = out.index.year
    out["month"] = out.index.month
    out["season"] = season_of(out["month"])
    out["season_year"] = season_year(out.index.to_series())
    return out


def annual(day: pd.DataFrame, how: str, min_days: int = 350) -> pd.DataFrame:
    """One row per calendar year, from the daily frame.

    `min_days` drops a year assembled from too few days, which is what makes
    2026 disappear from every trend without a special case anywhere else.
    """
    g = day.groupby("year")["mean"]
    total = g.sum(min_count=1) if how == "sum" else g.mean()
    out = pd.DataFrame({"value": total, "days": g.count()})
    out.loc[out["days"] < min_days, "value"] = np.nan
    return out


def seasonal(day: pd.DataFrame, how: str, min_days: int = 85) -> pd.DataFrame:
    """One row per season per year, indexed (season, season_year)."""
    g = day.groupby(["season", "season_year"])["mean"]
    total = g.sum(min_count=1) if how == "sum" else g.mean()
    out = pd.DataFrame({"value": total, "days": g.count()})
    out.loc[out["days"] < min_days, "value"] = np.nan
    return out


def baseline_mean(series: pd.Series, period: tuple[int, int] = BASELINE) -> float:
    """Mean over the baseline years, for anomalies."""
    lo, hi = period
    window = series.loc[(series.index >= lo) & (series.index <= hi)]
    return float(window.mean())


# --------------------------------------------------------------------------
# Trend estimation - three ways, because the disagreements are informative
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Trend:
    """A fitted trend, reported per decade."""

    slope_per_decade: float
    ci_low: float
    ci_high: float
    p_value: float
    n: int
    lag1_autocorrelation: float
    effective_n: float
    sen_slope_per_decade: float
    kendall_tau: float
    kendall_p: float

    @property
    def ols_significant(self) -> bool:
        return self.p_value < 0.05

    @property
    def mk_significant(self) -> bool:
        return self.kendall_p < 0.05

    @property
    def agrees(self) -> bool:
        """Both tests significant with the same sign, or both not significant."""
        if self.ols_significant != self.mk_significant:
            return False
        if not self.ols_significant:
            return True
        return np.sign(self.slope_per_decade) == np.sign(self.sen_slope_per_decade)


def fit_trend(x: pd.Series | np.ndarray, y: pd.Series | np.ndarray) -> Trend:
    """Least squares and Mann-Kendall on the same series.

    The least-squares confidence interval is widened for lag-1 autocorrelation.
    An annual weather series is not a set of independent draws: a warm year
    follows a warm year more often than chance, so the naive interval is too
    narrow and reports significance that is not there. The standard correction
    replaces n with an effective sample size

        n_eff = n * (1 - r1) / (1 + r1)

    where r1 is the lag-1 autocorrelation of the residuals, and inflates the
    standard error by sqrt(n / n_eff). It is only a first-order fix and it does
    nothing about longer-range persistence, which is why the non-parametric
    test is reported next to it rather than instead of it.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    n = x.size
    if n < 10:
        raise ValueError(f"need at least 10 points to fit a trend, got {n}")

    reg = stats.linregress(x, y)
    residuals = y - (reg.intercept + reg.slope * x)

    # Lag-1 autocorrelation of the residuals, not of the raw series: it is the
    # persistence the straight line failed to account for that matters.
    if residuals.std(ddof=0) > 0:
        r1 = float(np.corrcoef(residuals[:-1], residuals[1:])[0, 1])
    else:
        r1 = 0.0
    r1 = min(max(r1, 0.0), 0.99)  # a negative r1 would narrow the interval; don't
    n_eff = n * (1.0 - r1) / (1.0 + r1)
    n_eff = max(n_eff, 3.0)

    inflation = np.sqrt(n / n_eff)
    stderr = reg.stderr * inflation
    df_eff = max(n_eff - 2.0, 1.0)
    tcrit = float(stats.t.ppf(0.975, df_eff))
    # The p-value is recomputed on the effective degrees of freedom too, or the
    # widened interval and the reported significance would contradict each other.
    p_adj = float(2.0 * stats.t.sf(abs(reg.slope / stderr), df_eff)) if stderr > 0 else 1.0

    # Sen's slope: the median of all pairwise slopes. Unmoved by outliers, which
    # is what makes it the right companion for skewed rainfall series.
    idx_i, idx_j = np.triu_indices(n, k=1)
    dx = x[idx_j] - x[idx_i]
    valid = dx != 0
    sen = float(np.median((y[idx_j] - y[idx_i])[valid] / dx[valid]))

    tau, mk_p = stats.kendalltau(x, y)

    return Trend(
        slope_per_decade=float(reg.slope * 10.0),
        ci_low=float((reg.slope - tcrit * stderr) * 10.0),
        ci_high=float((reg.slope + tcrit * stderr) * 10.0),
        p_value=p_adj,
        n=n,
        lag1_autocorrelation=r1,
        effective_n=float(n_eff),
        sen_slope_per_decade=sen * 10.0,
        kendall_tau=float(tau),
        kendall_p=float(mk_p),
    )


def loess_curve(x: np.ndarray, y: np.ndarray, frac: float = 0.30) -> np.ndarray:
    """LOESS smoother, to show whether a straight line is the right description.

    `frac` is a choice, not a fact: a smaller span follows the data more closely
    and invents structure, a larger one flattens real turns. Every figure that
    uses this shows a second span so the reader can see how much of the shape
    survives the choice.
    """
    fitted = lowess(y, x, frac=frac, it=3, return_sorted=False)
    return np.asarray(fitted, dtype=float)


def describe_trend(trend: Trend, unit: str) -> str:
    """One sentence a document can quote, hedged exactly as far as the fit allows."""
    direction = "rising" if trend.slope_per_decade > 0 else "falling"
    verdict = (
        "significant at the 5% level after the autocorrelation correction"
        if trend.ols_significant else
        "not significant at the 5% level once autocorrelation is accounted for"
    )
    agreement = "" if trend.agrees else " The two methods disagree, so the trend is not settled."
    return (
        f"{direction} {abs(trend.slope_per_decade):.3f} {unit} per decade "
        f"(95% CI {trend.ci_low:.3f} to {trend.ci_high:.3f}), {verdict}; "
        f"Sen's slope {trend.sen_slope_per_decade:+.3f} {unit} per decade, "
        f"Mann-Kendall p = {trend.kendall_p:.2g}.{agreement}"
    )


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def save_fig(fig: plt.Figure, path: Path) -> Path:
    """Write a PNG with no embedded timestamp, so re-runs are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="png", bbox_inches="tight", pad_inches=0.18,
                metadata={"Software": None})
    plt.close(fig)
    return path


def save_table(df: pd.DataFrame, path: Path, float_format: str = "%.4f") -> Path:
    """Write a CSV deterministically.

    Every number the documents quote lands here, so a re-run that changes a
    figure shows up as a git diff rather than as silent drift between the prose
    and the data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, float_format=float_format, lineterminator="\n")
    return path


def file_digest(path: Path) -> str:
    """SHA-256 of the source file, so a document says which data it describes."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def markdown_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    """Render a frame as a GitHub markdown table, for pasting into a document."""
    def cell(v: object) -> str:
        if isinstance(v, float):
            return "-" if np.isnan(v) else floatfmt.format(v)
        return str(v)

    header = "| " + " | ".join([df.index.name or ""] + [str(c) for c in df.columns]) + " |"
    rule = "|" + "---|" * (len(df.columns) + 1)
    rows = [
        "| " + " | ".join([str(idx)] + [cell(v) for v in row]) + " |"
        for idx, row in zip(df.index, df.to_numpy())
    ]
    return "\n".join([header, rule, *rows])
