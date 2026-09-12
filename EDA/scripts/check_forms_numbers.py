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

Three kinds of check, because three kinds of drift have got through.

`eq` compares a number as the document prints it against the CSV cell it came
from, to the rounding the document uses. It is deliberately dumb and duplicated,
and it catches a measurement that moved under settled prose. On its own it does
not read the document at all, so prose edited without touching the literal here
used to pass in silence.

`says` requires the document to still print a given sentence verbatim. `under`
checks a bound the prose asserts across many cells. Both exist for claims the
prose *derives* from cells rather than quoting from them: a difference, a ratio,
an "every other variable is under X". Nothing checked that class until the fifth
review pass, which found three of them wrong at once - a "less than 0.2 points"
that was 1.020 for sunshine, a "share of the area" that was 1/N rather than an
area, and a spread that fell 32% and was written as 31%.

Six adversarial review passes over this document have found numbers left stale by
corrections applied in one place and not another, five separate times. That is the
failure this exists to catch.

What it cannot catch, stated so nobody reads a pass here as a clean bill: it reads
CSVs and the markdown, never `src/`. Every claim the document makes about the app
- that `VariableMeta` carries one range, that `axisFor` builds from two fields,
that `AppState` has no mode, that `Series` has no band - is checked by hand or not
at all. The same goes for the figures, whose axes it never looks at; the sixth
pass found the lead figure had been drawing its heatmap panel into 3.5% of its
width, and nothing here would have noticed.

Run it after any edit to the document or to `eda_forms.py`.
"""

import re
from pathlib import Path
import pandas as pd

S = Path("EDA/stats")
DOC = Path("EDA/04-chart-forms.md").read_text()
fails, checks = [], 0

def eq(label, got, want, tol=0.00501):
    global checks
    checks += 1
    if abs(float(got) - float(want)) > tol:
        fails.append(f"{label}: doc says {want}, CSV says {got}")

def says(label, snippet):
    """The document must still print this text verbatim.

    `eq` compares a literal transcribed from the prose against a CSV, so the
    prose itself is never read: edit the document alone and every `eq` still
    passes while the sentence is wrong. Pair `says` with `eq` wherever a claim
    is arithmetic the prose performs rather than a cell it quotes.
    """
    global checks
    checks += 1
    if snippet not in DOC:
        fails.append(f"{label}: the document no longer contains {snippet!r}")

def under(label, got, limit):
    global checks
    checks += 1
    if not float(got) < limit:
        fails.append(f"{label}: {float(got):.3f} is not under the {limit} the doc claims")

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
doc_env = ((2025, 96, 26.3), (2018, 93, 25.5), (2010, 119, 32.6),
           (1995, 102, 27.9), (1963, 101, 27.7))
checks += 1
if set(env.index) != {y for y, _, _ in doc_env}:
    fails.append(f"envelope: CSV holds {sorted(env.index)}, the table prints "
                 f"{sorted(y for y, _, _ in doc_env)}")
for y, d, pct in (r for r in doc_env if r[0] in env.index):
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
for step, pts, sd, rate, cr in (("1 day", 365, 2.36, 25.8, 94.3), ("2 days", 182, 2.10, 32.6, 59.3),
                                ("4 days", 91, 1.78, 39.1, 35.6), ("1 week", 52, 1.61, 40.2, 20.9),
                                ("4 weeks (beyond the slider)", 13, 0.97, 39.3, 5.1)):
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
for y, w, h, share in ((4, 600, 260, 25.0), (10, 300, 173, 8.3), (30, 200, 104, 3.3), (80, 133, 58, 1.2)):
    eq(f"sm {y} width", sm.loc[y, "panel_width_px"], w, 0.5)
    eq(f"sm {y} height", sm.loc[y, "panel_height_px"], h, 0.5)
    eq(f"sm {y} share", sm.loc[y, "panel_area_share_pct"], share, 0.0501)

hs = pd.read_csv(S / "04-heatmap-signal.csv", index_col=0)
for cell, cells, trend, row in (("1 day", 365, 0.17, 1.59), ("1 week", 52, 0.24, 1.38),
                                ("1 month", 12, 0.39, 1.31), ("1 season", 4, 0.53, 1.16)):
    eq(f"hs {cell} cells", hs.loc[cell, "cells_per_year"], cells, 0.5)
    eq(f"hs {cell} trend/noise", hs.loc[cell, "trend_over_cell_noise"], trend, 0.00501)
    eq(f"hs {cell} year/rownoise", hs.loc[cell, "year_over_row_noise"], row, 0.005)
for cell, eff in (("1 day", 70), ("1 week", 27), ("1 month", 10), ("1 season", 4)):
    eq(f"hs {cell} effective cells", hs.loc[cell, "effective_cells_per_row"], eff, 0.5)

occ2 = pd.read_csv(S / "04-occlusion.csv", index_col=0)
for y, pairs, cr in ((2, 1, 0.28), (5, 10, 2.56), (10, 45, 11.63), (20, 190, 47.83), (30, 435, 111.00)):
    eq(f"pairs n={y}", occ2.loc[y, "pairs_on_screen"], pairs, 0.5)
    eq(f"crossings n={y}", occ2.loc[y, "expected_crossings_per_point"], cr, 0.005)
eq("swap n=5", occ2.loc[5, "pct_days_pair_swaps_raw"], 25.6, 0.05)
eq("swap n=20", occ2.loc[20, "pct_days_pair_swaps_raw"], 25.2, 0.05)

# --- Claims derived from cells, rather than quoted from them ---------------
# Everything above checks one number against the cell it came from. The prose
# also states differences, ratios and comparisons *between* cells, and nothing
# checked those. The fifth review pass found three of them wrong at once,
# including a "less than 0.2 points" that was in fact 1.020 for sunshine.

gap = var["pct_days_pair_swaps"] - var["pct_days_pair_swaps_ties_hold"]
eq("ties gap sun", gap["sun"], 1.0, 0.051)
says("ties gap sun in prose", "1.0 points apart")
for k in ("temp", "rhum", "msl", "wdsp", "vis"):
    under(f"ties gap {k}", gap[k], 0.2)
says("ties gap others in prose", "less than 0.2 points")

# Ordinal claims. The prose ranks variables against each other and nothing
# sorted anything, so "second lowest" was only ever true by inspection.
order = var["pct_days_pair_swaps"].sort_values()
checks += 1
if list(order.index[:2]) != ["msl", "temp"]:
    fails.append(f"swap order: doc says temp is second lowest after msl, CSV ranks {list(order.index[:2])}")
says("temp second lowest in prose", "second *lowest*")
says("msl named as the one below it", "only mean sea\nlevel pressure tangles less, at 18.4%")
eq("msl swap rate", var.loc["msl", "pct_days_pair_swaps"], 18.4, 0.05)

tied = var["pct_days_tied"].sort_values(ascending=False)
checks += 1
if list(tied.index[:2]) != ["rain", "sun"]:
    fails.append(f"tied order: doc says sun is second after rain, CSV ranks {list(tied.index[:2])}")

# Roughness sits below separation at every year count, not the two once quoted.
for y in occ.index:
    under(f"roughness under separation n={y}", occ.loc[y, "roughness_over_separation"], 1.0)

for step, nominal in (("1 day", 1), ("1 week", 7), ("1 month", 30), ("1 season", 91)):
    checks += 1
    if hs.loc[step, "cells_per_year"] != 365 // nominal:
        fails.append(f"hs {step}: {hs.loc[step, 'cells_per_year']} cells, but 365//{nominal} "
                     f"= {365 // nominal}; a short final cell is back")
trend_flat = hs["trend_signal_c"]
under("trend signal spread across cell sizes", trend_flat.max() - trend_flat.min(), 0.01)
# Built from the CSV, not typed out: a says() with a hand-written literal only
# proves the document contains that string, and it passed for a full pass while
# the string held the right four values in the wrong order.
says("trend signal sequence, generated from the CSV",
     ", ".join(f"{v:.3f}" for v in hs["trend_signal_c"]))
says("daily against season row noise, generated from the CSV",
     f'{hs.loc["1 day", "year_over_row_noise"]:.2f} against '
     f'{hs.loc["1 season", "year_over_row_noise"]:.2f}')

eq("axis cost ratio 2.9x",
   ax.iloc[2]["separation_pct_of_axis"] / ax.iloc[0]["separation_pct_of_axis"], 2.9, 0.05)
says("2.9x in section 2", "2.9 times\nthe plot height")
says("2.9x restated in the table", "**yes, 2.9\u00d7**")

eq("points per pixel at 30 years", 365 / sm.loc[30, "panel_width_px"], 1.8, 0.05)
says("points per pixel in prose", "1.8 points per pixel")

daily, weekly = res.loc["1 day"], res.loc["1 week"]
eq("spread fall daily to weekly",
   100 * (daily["cross_year_sd_c"] - weekly["cross_year_sd_c"]) / daily["cross_year_sd_c"], 32, 0.5)
says("spread fall in section 1", "falls 32% over the same range")
says("spread fall restated in 4.1", "costs 32% of the")

eq("crossing ratio daily to weekly",
   daily["crossings_per_pair_per_year"] / weekly["crossings_per_pair_per_year"], 4.5, 0.25)
says("crossing ratio in prose", "factor of four and a half")

# The panel share is the panel's real share of the plot, not 1/N: a grid that
# does not divide evenly leaves empty slots and every panel is smaller.
for y in sm.index:
    eq(f"sm {y} share is area, not 1/N",
       sm.loc[y, "panel_area_share_pct"],
       100 * sm.loc[y, "panel_width_px"] * sm.loc[y, "panel_height_px"] / (1200 * 520), 0.005)
says("sm empty slots explained", "leave two slots empty, so each panel gets 8.3%")

# The shape of the occlusion argument: pairs grow as N(N-1)/2, and crossings
# are pairs times the swap rate. Section 1 rests on both.
for y in (2, 5, 10, 20, 30):
    eq(f"pairs formula n={y}", occ2.loc[y, "pairs_on_screen"], y * (y - 1) / 2, 0.5)
    eq(f"crossings are pairs x rate n={y}", occ2.loc[y, "expected_crossings_per_point"],
       occ2.loc[y, "pairs_on_screen"] * occ2.loc[y, "pct_days_pair_swaps_raw"] / 100, 0.01)

# Subtracting a normal cannot move separation. That identity is the document's
# proof that the anomaly buys nothing in occlusion, so it is checked, not assumed.
for y in sep.index:
    eq(f"anomaly separation identical n={y}",
       sep.loc[y, "anomaly_separation_c"], sep.loc[y, "raw_separation_c"], 0.0005)
    eq(f"anomaly swap rate identical n={y}",
       occ2.loc[y, "pct_days_pair_swaps_anomaly"], occ2.loc[y, "pct_days_pair_swaps_raw"], 0.0005)

prov = DOC.split("## 6. Provenance", 1)[-1]
listed = set(re.findall(r"`(EDA/(?:stats|figures)/[^`]+)`", prov))
on_disk = ({str(f) for f in Path("EDA/stats").glob("04-*.csv")}
           | {str(f) for f in Path("EDA/figures").glob("04-*.png")})
checks += 1
if on_disk - listed:
    fails.append(f"provenance: generated but not listed in section 6: "
                 f"{sorted(on_disk - listed)}")

print(f"{checks} numeric claims checked against the CSVs")
if fails:
    print(f"\n{len(fails)} MISMATCHES:")
    for f in fails:
        print("  -", f)
    raise SystemExit(1)
print("all match")
