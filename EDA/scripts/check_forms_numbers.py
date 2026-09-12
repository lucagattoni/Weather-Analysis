# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2"]
# ///
"""Check every number `EDA/04-chart-forms.md` quotes against the CSV it came from.

    uv run EDA/scripts/check_forms_numbers.py

The project convention is that prose is written by hand around generated output,
and that every number a document quotes exists in `EDA/stats/` so drift shows up
as a git diff. That makes drift *visible*; it does not make it *fail*. This makes
it fail.

Each expectation below is a number as the document prints it, checked against the
CSV to the rounding the document uses. It is deliberately dumb and duplicated: if
a measurement moves and the prose does not, or the prose is edited and the
measurement does not, this exits non-zero and names the pair. Four adversarial
review passes over this document found stale numbers left behind by partial
corrections three separate times, which is the failure this exists to catch.

Run it after any edit to the document or to `eda_forms.py`.
"""

from pathlib import Path
import pandas as pd

S = Path("EDA/stats")
fails, checks = [], 0

def eq(label, got, want, tol=0.00501):
    global checks
    checks += 1
    if abs(float(got) - float(want)) > tol:
        fails.append(f"{label}: doc says {want}, CSV says {got}")

sep = pd.read_csv(S / "04-separation.csv", index_col=0)
doc_sep = {  # years: (separation, raw axis, raw %, anomaly axis, anomaly %)
    2: (2.13, 23.06, 9.2, 14.44, 14.7),
    3: (3.79, 23.06, 16.4, 14.44, 26.2),
    5: (5.31, 24.50, 21.7, 15.30, 34.7),
    10: (7.22, 24.67, 29.3, 15.64, 46.2),
    20: (8.85, 30.09, 29.4, 21.27, 41.6),
    30: (9.65, 30.09, 32.1, 21.27, 45.4),
}
for y, (a, b, c, d, e) in doc_sep.items():
    r = sep.loc[y]
    eq(f"sep n={y} separation", r["raw_separation_c"], a)
    eq(f"sep n={y} raw axis", r["raw_axis_span_c"], b)
    eq(f"sep n={y} raw pct", r["raw_separation_pct_of_axis"], c, 0.05)
    eq(f"sep n={y} ano axis", r["anomaly_axis_span_c"], d)
    eq(f"sep n={y} ano pct", r["anomaly_separation_pct_of_axis"], e, 0.05)

occ = pd.read_csv(S / "04-occlusion.csv", index_col=0)
eq("section1 separation @10", occ.loc[10, "separation_c"], 7.22)
eq("section1 spread @10", occ.loc[10, "cross_year_sd_c"], 2.36)
eq("section1 roughness @10", occ.loc[10, "roughness_c"], 1.20)
eq("section1 swap @10", occ.loc[10, "pct_days_pair_swaps_raw"], 25.8, 0.05)
eq("spread @2", occ.loc[2, "cross_year_sd_c"], 1.51)
eq("spread @20", occ.loc[20, "cross_year_sd_c"], 2.43)
eq("spread @30", occ.loc[30, "cross_year_sd_c"], 2.40)
eq("roughness/sep @2 under 1", occ.loc[2, "roughness_over_separation"], 0.537, 0.01)
for y, v in ((2, 28.022), (10, 25.844), (30, 25.517)):
    eq(f"swap raw n={y}", occ.loc[y, "pct_days_pair_swaps_raw"], v, 0.0005)
    eq(f"swap anomaly n={y}", occ.loc[y, "pct_days_pair_swaps_anomaly"], v, 0.0005)
    if occ.loc[y, "pct_days_pair_swaps_raw"] != occ.loc[y, "pct_days_pair_swaps_anomaly"]:
        fails.append(f"swap raw != anomaly at n={y}")

ax = pd.read_csv(S / "04-axis-cost.csv", index_col=0)
eq("app axis span", ax.iloc[0]["span_c"], 45.0)
eq("app axis pct", ax.iloc[0]["separation_pct_of_axis"], 16.0, 0.05)
eq("fitted axis span", ax.iloc[1]["span_c"], 24.67)
eq("fitted axis pct", ax.iloc[1]["separation_pct_of_axis"], 29.3, 0.05)
eq("anomaly axis pct", ax.iloc[2]["separation_pct_of_axis"], 46.2, 0.05)

sw = pd.read_csv(S / "04-anchor-sweep.csv", index_col=0)
doc_sw = {"2006-2025": (8.85, 2.43, 25.2), "1986-2005": (8.69, 2.32, 25.5),
          "1983-2002": (8.81, 2.37, 25.1), "1978-1997": (8.80, 2.36, 24.8),
          "1966-1985": (8.58, 2.25, 24.9), "1946-1965": (8.57, 2.32, 24.6)}
for w, (a, b, c) in doc_sw.items():
    eq(f"sweep {w} separation", sw.loc[w, "separation_c"], a)
    eq(f"sweep {w} spread", sw.loc[w, "cross_year_sd_c"], b)
    eq(f"sweep {w} swap", sw.loc[w, "pct_days_pair_swaps"], c, 0.05)
crossers = [w for w in sw.index if sw.loc[w, "crosses_1993"]]
if len(crossers) != 3:
    fails.append(f"doc says three windows straddle 1993, CSV says {len(crossers)}")
lo = sw["pct_days_pair_swaps"].min(); hi = sw["pct_days_pair_swaps"].max()
eq("sweep swap min", lo, 24.6, 0.05); eq("sweep swap max", hi, 25.5, 0.05)

hm = pd.read_csv(S / "04-heatmap-cells.csv", index_col=0)
for y, cells, h in ((10, 3650, 52.0), (30, 10950, 17.3), (80, 29200, 6.5)):
    eq(f"heatmap n={y} cells", hm.loc[y, "cells"], cells, 0.5)
    eq(f"heatmap n={y} cell height", hm.loc[y, "cell_height_px"], h, 0.05)
eq("heatmap cell width", hm.loc[10, "cell_width_px"], 3.3, 0.05)

wm = pd.read_csv(S / "04-warming-signal.csv", index_col=0)
w0, w1 = wm.iloc[0], wm.iloc[1]
eq("warming whole measured", w0["difference_c"], 0.43, 0.005)
eq("warming whole gap", w0["years_between_window_centres"], 50)
eq("warming whole trend implied", w0["trend_implied_c"], 0.73, 0.005)
eq("warming whole shortfall", w0["measured_minus_trend_implied_c"], -0.29, 0.005)
eq("warming post93 measured", w1["difference_c"], 0.22, 0.005)
eq("warming post93 gap", w1["years_between_window_centres"], 17)
eq("warming post93 trend implied", w1["trend_implied_c"], 0.25, 0.005)
eq("warming post93 shortfall", w1["measured_minus_trend_implied_c"], -0.03, 0.005)
eq("warming pct of app axis", w0["pct_of_app_axis"], 0.96, 0.005)

bt = pd.read_csv(S / "02-break-test.csv", index_col=0)
joint = bt.loc[[i for i in bt.index if "Joint" in str(i)][0]]
eq("doc02 trend", joint["OLS slope (degC/decade)"], 0.145, 0.0005)
v = str(joint["verdict"])
for token in ("-0.262", "-0.706", "+0.182", "0.242"):
    checks += 1
    if token not in v:
        fails.append(f"doc quotes {token} for the 1993 step; not in 02-break-test verdict: {v!r}")

bw = pd.read_csv(S / "04-band-width.csv", index_col=0)
eq("band median", bw.iloc[0]["median_width_c"], 5.83)
eq("band min", bw.iloc[0]["min_width_c"], 2.88)
eq("band max", bw.iloc[0]["max_width_c"], 10.10)

env = pd.read_csv(S / "04-envelope-escape.csv", index_col=0)
for y, d, pct in ((2025, 96, 26.3), (2018, 93, 25.5), (2010, 119, 32.6), (1963, 101, 27.7)):
    eq(f"envelope {y} days", env.loc[y, "days_outside_10_90"], d, 0.5)
    eq(f"envelope {y} pct", env.loc[y, "pct_outside"], pct, 0.05)

cu = pd.read_csv(S / "04-cumulative.csv")
cu = cu.set_index(["variable", "window"])
for key, mn, mx, mid in ((("rain", "2016-2025"), 662, 1002, 144),
                         (("rain", "whole series"), 555, 1095, 350),
                         (("sun", "2016-2025"), 1319, 1648, 288),
                         (("sun", "whole series"), 1240, 1740, 364)):
    eq(f"cumulative {key} min", cu.loc[key, "annual_min"], mn, 0.6)
    eq(f"cumulative {key} max", cu.loc[key, "annual_max"], mx, 0.6)
    eq(f"cumulative {key} 1 July", cu.loc[key, "spread_at_1_july"], mid, 0.6)
eq("rain factor", cu.loc[("rain", "whole series"), "annual_max"] / cu.loc[("rain", "whole series"), "annual_min"], 2.0, 0.05)
eq("sun factor", cu.loc[("sun", "whole series"), "annual_max"] / cu.loc[("sun", "whole series"), "annual_min"], 1.4, 0.05)
eq("mean crossings after 1 Apr", cu["crossings_per_pair_after_1_apr"].mean(), 3.4, 0.05)


res = pd.read_csv(S / "04-resolution.csv", index_col=0)
for step, pts, sd, rate, cr in (("1 day", 365, 2.36, 25.8, 94.3), ("2 days", 183, 2.10, 32.4, 59.3),
                                ("4 days", 92, 1.81, 38.9, 35.8), ("1 week", 53, 1.62, 39.7, 21.0),
                                ("4 weeks (beyond the slider)", 14, 0.99, 39.8, 5.6)):
    r = res.loc[step]
    eq(f"res {step} points", r["points_per_year"], pts, 0.5)
    eq(f"res {step} spread", r["cross_year_sd_c"], sd)
    eq(f"res {step} rate", r["pct_points_pair_swaps"], rate, 0.05)
    eq(f"res {step} crossings", r["crossings_per_pair_per_year"], cr, 0.05)

var = pd.read_csv(S / "04-variables.csv", index_col=0)
for k, rate, tied in (("msl", 18.4, 0.0), ("temp", 25.8, 0.1), ("wdsp", 33.3, 0.4),
                      ("rhum", 35.0, 0.1), ("rain", 36.3, 18.5), ("vis", 36.3, 0.2), ("sun", 42.9, 2.4)):
    eq(f"var {k} rate", var.loc[k, "pct_days_pair_swaps"], rate, 0.05)
    eq(f"var {k} tied", var.loc[k, "pct_days_tied"], tied, 0.05)
for k, hold in (("msl", 18.4), ("temp", 25.8), ("wdsp", 33.2), ("rhum", 35.0),
                ("rain", 29.5), ("vis", 36.3), ("sun", 41.9)):
    eq(f"var {k} ties-hold", var.loc[k, "pct_days_pair_swaps_ties_hold"], hold, 0.0501)


sm = pd.read_csv(S / "04-small-multiples.csv", index_col=0)
for y, w, h, share in ((4, 600, 260, 25.0), (10, 300, 173, 10.0), (30, 200, 104, 3.3), (80, 133, 58, 1.3)):
    eq(f"sm {y} width", sm.loc[y, "panel_width_px"], w, 0.5)
    eq(f"sm {y} height", sm.loc[y, "panel_height_px"], h, 0.5)
    eq(f"sm {y} share", sm.loc[y, "panel_area_share_pct"], share, 0.0501)

hs = pd.read_csv(S / "04-heatmap-signal.csv", index_col=0)
for cell, cells, trend, row in (("1 day", 365, 0.17, 1.59), ("1 week", 53, 0.25, 1.40),
                                ("1 month", 13, 0.34, 1.24), ("1 season", 5, 0.42, 1.14)):
    eq(f"hs {cell} cells", hs.loc[cell, "cells_per_year"], cells, 0.5)
    eq(f"hs {cell} trend/noise", hs.loc[cell, "trend_over_cell_noise"], trend, 0.00501)
    eq(f"hs {cell} year/rownoise", hs.loc[cell, "year_over_row_noise"], row, 0.005)
for cell, eff in (("1 day", 70), ("1 week", 28), ("1 month", 10), ("1 season", 5)):
    eq(f"hs {cell} effective cells", hs.loc[cell, "effective_cells_per_row"], eff, 0.5)

occ2 = pd.read_csv(S / "04-occlusion.csv", index_col=0)
for y, pairs, cr in ((2, 1, 0.28), (5, 10, 2.56), (10, 45, 11.63), (20, 190, 47.83), (30, 435, 111.00)):
    eq(f"pairs n={y}", occ2.loc[y, "pairs_on_screen"], pairs, 0.5)
    eq(f"crossings n={y}", occ2.loc[y, "expected_crossings_per_point"], cr, 0.005)
eq("swap n=5", occ2.loc[5, "pct_days_pair_swaps_raw"], 25.6, 0.05)
eq("swap n=20", occ2.loc[20, "pct_days_pair_swaps_raw"], 25.2, 0.05)

print(f"{checks} numeric claims checked against the CSVs")
if fails:
    print(f"\n{len(fails)} MISMATCHES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("all match")
