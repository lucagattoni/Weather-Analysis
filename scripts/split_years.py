# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "numpy>=1.26"]
# ///
"""Split the Met Eireann Dublin Airport hourly CSV into per-year JSON chunks.

Build-time step (CLAUDE.md, "Languages"): runs once per data refresh and emits
static facts under public/data/. Nothing here runs in the browser; the app only
ever reads the JSON this writes.

    uv run scripts/split_years.py --csv data/<file>.csv.gz --out public/data

Output is deterministic: same input, byte-identical files, so a re-run does not
churn git. Nothing carries a generation timestamp for that reason.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# The variable registry. Order here is the order of the dropdown in the app.
# `sentinel` is a value that is a real observation but not a measurement on the
# variable's scale: it is excluded from the global min/max (so the y-axis fits
# the actual data) and the app's model layer turns it into a gap in the line.
# The source's five duplicate `ind` columns and the SYNOP codes ww/w are dropped.
# `aggregate` says how a run of hours combines when the app resamples to a coarser
# step. A plain mean is wrong for three of the thirteen:
#   sum      - rain and sunshine are amounts per hour, so a day is their total,
#              not their average. A mean reads 0.09 mm/h instead of 2.21 mm/day.
#   circular - a mean of degrees is not a direction. Hours reading 340, 330, 300,
#              290, 280, 270 average naively to 175 (due south) against a circular
#              mean of 355 (due north); the two disagree by over 30 degrees on 50
#              days of 2025 alone.
VARIABLES: list[dict] = [
    {"key": "rain",  "label": "Precipitation amount",      "unit": "mm",          "sentinel": None, "aggregate": "sum"},
    {"key": "temp",  "label": "Air temperature",           "unit": "°C",     "sentinel": None, "aggregate": "mean"},
    {"key": "wetb",  "label": "Wet bulb temperature",      "unit": "°C",     "sentinel": None, "aggregate": "mean"},
    {"key": "dewpt", "label": "Dew point temperature",     "unit": "°C",     "sentinel": None, "aggregate": "mean"},
    {"key": "vappr", "label": "Vapour pressure",           "unit": "hPa",         "sentinel": None, "aggregate": "mean"},
    {"key": "rhum",  "label": "Relative humidity",         "unit": "%",           "sentinel": None, "aggregate": "mean"},
    {"key": "msl",   "label": "Mean sea level pressure",   "unit": "hPa",         "sentinel": None, "aggregate": "mean"},
    {"key": "wdsp",  "label": "Mean wind speed",           "unit": "knot",        "sentinel": None, "aggregate": "mean"},
    # 0 = calm, which is not a direction and is not north (360 is north). 1.77% of
    # readings. Left in the chunk, excluded from the range and from the circular
    # mean, so 12,472 calm hours are not reported as due north.
    {"key": "wddir", "label": "Predominant wind direction","unit": "°",      "sentinel": 0,    "aggregate": "circular"},
    {"key": "sun",   "label": "Sunshine duration",         "unit": "h",           "sentinel": None, "aggregate": "sum"},
    {"key": "vis",   "label": "Visibility",                "unit": "m",           "sentinel": None, "aggregate": "mean"},
    # 999 = no cloud ceiling. 26.5% of rows; the real ceiling never exceeds 440.
    {"key": "clht",  "label": "Cloud ceiling height",      "unit": "100s of ft",  "sentinel": 999,  "aggregate": "mean"},
    # 9 = sky obscured. One row in the whole series; the okta scale is 0..8.
    {"key": "clamt", "label": "Cloud amount",              "unit": "okta",        "sentinel": 9,    "aggregate": "mean"},
]
KEYS = [v["key"] for v in VARIABLES]

# The source writes a missing value as a single space, not an empty field.
# Number(" ") is 0 in JavaScript, so failing to catch this would silently record
# 255 missing visibility readings as 0 m.
NA_VALUES = [" ", ""]
DATE_FORMAT = "%d-%b-%Y %H:%M"


def read_station(info_path: Path) -> dict:
    """Read station metadata from the source's info file rather than hardcoding it."""
    text = info_path.read_text(encoding="utf-8", errors="replace")

    def find(pattern: str) -> str | None:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None

    height = find(r"^Station Height:\s*([-\d.]+)")
    lat = find(r"^Latitude:\s*([-\d.]+)")
    lon = find(r"^Longitude:\s*([-\d.]+)")
    return {
        "name": find(r"^Station Name:\s*(.+)$") or "UNKNOWN",
        "height_m": float(height) if height else None,
        "lat": float(lat) if lat else None,
        "lon": float(lon) if lon else None,
    }


def decimals_for(values: np.ndarray) -> int:
    """Smallest decimal count that represents every value exactly."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0
    for d in range(4):
        if np.allclose(finite, np.round(finite, d), rtol=0, atol=1e-9):
            return d
    return 3


def check_invariants(ts: pd.Series, frame: pd.DataFrame) -> None:
    """Re-check at every run what the chunk schema assumes about the source.

    The app reconstructs timestamps as start + i * 3600s and never reads a date
    from a chunk, so a gap or a duplicate here would silently shift every point
    after it.
    """
    problems: list[str] = []
    if not ts.is_monotonic_increasing:
        problems.append("timestamps are not strictly chronological")
    dupes = int(ts.duplicated().sum())
    if dupes:
        problems.append(f"{dupes} duplicate timestamps")
    steps = ts.diff().dropna()
    bad = steps[steps != pd.Timedelta(hours=1)]
    if len(bad):
        problems.append(f"{len(bad)} steps are not exactly one hour: {bad.value_counts().to_dict()}")
    missing_cols = [k for k in KEYS if k not in frame.columns]
    if missing_cols:
        problems.append(f"columns absent from the source: {missing_cols}")
    if problems:
        raise SystemExit("Source data failed its invariants:\n  - " + "\n  - ".join(problems))


def column_values(values: np.ndarray, decimals: int) -> list:
    """NaN becomes JSON null; everything else is rounded to the source precision.

    Rounding here (rather than letting float repr decide) is what makes the
    output byte-identical between runs.
    """
    if decimals == 0:
        return [None if not np.isfinite(v) else int(round(v)) for v in values]
    return [None if not np.isfinite(v) else round(float(v), decimals) for v in values]


def write_json(path: Path, payload: dict, *, compact: bool) -> int:
    separators = (",", ":") if compact else (",", ": ")
    indent = None if compact else 2
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=separators, indent=indent) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, type=Path, help="gzipped source CSV")
    ap.add_argument("--out", required=True, type=Path, help="output directory (public/data)")
    ap.add_argument("--info", type=Path, default=None,
                    help="station info file (default: the -info.txt beside --csv)")
    args = ap.parse_args()

    info_path = args.info or Path(str(args.csv).replace("-data.csv.gz", "-info.txt"))
    if not args.csv.exists():
        raise SystemExit(f"No such file: {args.csv}")
    if not info_path.exists():
        raise SystemExit(f"No such file: {info_path}")

    print(f"reading {args.csv} ...", file=sys.stderr)
    df = pd.read_csv(args.csv, compression="gzip", na_values=NA_VALUES,
                     usecols=["date"] + KEYS)
    ts = pd.to_datetime(df["date"], format=DATE_FORMAT)
    check_invariants(ts, df)
    print(f"  {len(df):,} rows, {ts.iloc[0]} .. {ts.iloc[-1]} UTC, contiguous hourly",
          file=sys.stderr)

    columns = {k: df[k].to_numpy(dtype="float64") for k in KEYS}

    # Global range and precision per variable, sentinels excluded.
    variables: list[dict] = []
    for spec in VARIABLES:
        raw = columns[spec["key"]]
        sentinel = spec["sentinel"]
        clean = raw[raw != sentinel] if sentinel is not None else raw
        finite = clean[np.isfinite(clean)]
        if finite.size == 0:
            raise SystemExit(f"{spec['key']}: no usable values")
        dec = decimals_for(raw)
        entry = {
            "key": spec["key"],
            "label": spec["label"],
            "unit": spec["unit"],
            "min": round(float(finite.min()), dec) if dec else int(finite.min()),
            "max": round(float(finite.max()), dec) if dec else int(finite.max()),
            "decimals": dec,
            "aggregate": spec["aggregate"],
        }
        if sentinel is not None:
            entry["sentinel"] = sentinel
        variables.append(entry)

    args.out.mkdir(parents=True, exist_ok=True)
    years_dir = args.out / "years"
    years_dir.mkdir(parents=True, exist_ok=True)

    year_of = ts.dt.year.to_numpy()
    year_meta: list[dict] = []
    total_bytes = 0
    for year in sorted(set(int(y) for y in year_of)):
        mask = year_of == year
        start = ts[mask].iloc[0]
        hours = int(mask.sum())
        chunk = {
            "year": year,
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hours": hours,
            "columns": {v["key"]: column_values(columns[v["key"]][mask], v["decimals"])
                        for v in variables},
        }
        total_bytes += write_json(years_dir / f"{year}.json", chunk, compact=True)
        year_meta.append({"year": year, "start": chunk["start"], "hours": hours})

    meta = {
        "station": read_station(info_path),
        "source": {
            "provider": "Met Éireann",
            "dataset": "Dublin Airport hourly observations",
            "licence": "CC BY 4.0",
            "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "years": year_meta,
        "variables": variables,
    }
    write_json(args.out / "meta.json", meta, compact=False)

    print(f"wrote {len(year_meta)} year chunks ({total_bytes/1e6:.1f} MB) "
          f"and meta.json to {args.out}", file=sys.stderr)
    print(f"  years {year_meta[0]['year']}..{year_meta[-1]['year']}, "
          f"last year {year_meta[-1]['hours']:,} hours", file=sys.stderr)


if __name__ == "__main__":
    main()
