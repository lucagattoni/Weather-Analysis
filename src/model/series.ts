import type { Series } from '../chart/adapter.ts';
import { CANONICAL_YEAR } from '../chart/adapter.ts';
import type { VariableMeta, YearData } from '../data/types.ts';
import { combine } from './resample.ts';

const HOUR_MS = 3_600_000;
const isLeap = (y: number) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

/**
 * Moves a timestamp onto the canonical year, keeping month, day and time.
 * This is what puts every selected year on one shared 1 Jan – 31 Dec axis.
 */
function toCanonical(ms: number): number {
  const d = new Date(ms);
  return Date.UTC(
    CANONICAL_YEAR,
    d.getUTCMonth(),
    d.getUTCDate(),
    d.getUTCHours(),
    d.getUTCMinutes(),
  );
}

/**
 * Pure transforms from loaded chunks to drawable series. No I/O, no DOM.
 * Already handles N years by N variables even though the POC controls put
 * exactly one of each into the state.
 */

/**
 * Turns one variable of one year into a line.
 *
 * Two kinds of value become a gap, and neither is touched in the chunk itself:
 * a missing reading (null), and a sentinel, which is a real observation that is
 * not a measurement on this scale (clht 999 means no cloud ceiling).
 */
export function seriesFor(
  year: YearData,
  variable: VariableMeta,
  stepHours = 1,
  xKind: 'time' | 'dayOfYear' = 'time',
): Series {
  const values = year.columns[variable.key];
  if (!values) throw new Error(`${year.year}.json has no column "${variable.key}"`);

  const startMs = Date.parse(year.start);
  if (Number.isNaN(startMs)) throw new Error(`${year.year}.json has an unreadable start "${year.start}"`);

  // Sentinels and missing readings become NaN first, so resampling never averages
  // a "no cloud ceiling" 999 or a "calm" 0 in as if it were a measurement.
  const hourly = new Float64Array(values.length);
  for (let i = 0; i < values.length; i += 1) {
    const v = values[i];
    hourly[i] = v === null || v === variable.sentinel ? Number.NaN : v;
  }

  const step = Math.max(1, Math.round(stepHours));
  const buckets = Math.ceil(hourly.length / step);
  const x = new Float64Array(buckets);
  const y = new Float64Array(buckets);
  for (let b = 0; b < buckets; b += 1) {
    const from = b * step;
    const to = Math.min(from + step, hourly.length);
    // Plotted at the mean timestamp of the hours it covers, so a 6-hour point
    // sits in the middle of its window rather than at its leading edge.
    x[b] = startMs + ((from + to - 1) / 2) * HOUR_MS;
    // A short final bucket cannot carry a total: a 7-day step whose last block
    // holds one day would draw a seventh of the rainfall of its neighbours and
    // look like a dry week. Means are unaffected, so only sums are dropped.
    const short = to - from < step;
    y[b] = step === 1
      ? hourly[from]
      : short && variable.aggregate === 'sum'
        ? Number.NaN
        : combine(hourly, from, to, variable.aggregate);
  }

  if (xKind === 'dayOfYear') {
    const canonX: number[] = [];
    const canonY: number[] = [];
    // The canonical year is a leap year, so a non-leap year has nothing to put in
    // 29 February. One NaN there is what stops the line being drawn straight
    // across the missing day (decision B: a gap, never an invented or dropped
    // reading).
    const gapAt = isLeap(year.year) ? null : Date.UTC(CANONICAL_YEAR, 1, 29, 12);
    let gapDone = gapAt === null;
    for (let i = 0; i < x.length; i += 1) {
      const cx = toCanonical(x[i]);
      if (!gapDone && gapAt !== null && cx > gapAt) {
        canonX.push(gapAt);
        canonY.push(Number.NaN);
        gapDone = true;
      }
      canonX.push(cx);
      canonY.push(y[i]);
    }
    return {
      id: `${year.year}:${variable.key}`,
      label: String(year.year),
      unit: variable.unit,
      scale: variable.key,
      x: Float64Array.from(canonX),
      y: Float64Array.from(canonY),
    };
  }

  return {
    id: `${year.year}:${variable.key}`,
    label: String(year.year),
    unit: variable.unit,
    scale: variable.key,
    x,
    y,
  };
}

export function buildSeries(
  loaded: ReadonlyMap<number, YearData>,
  years: readonly number[],
  variables: readonly VariableMeta[],
  stepHours = 1,
  xKind: 'time' | 'dayOfYear' = 'time',
): Series[] {
  const out: Series[] = [];
  for (const year of years) {
    const data = loaded.get(year);
    if (!data) continue;
    for (const variable of variables) out.push(seriesFor(data, variable, stepHours, xKind));
  }
  return out;
}

/** The whole canonical year, which every overlaid year shares. */
export function canonicalRange(): [number, number] {
  return [Date.UTC(CANONICAL_YEAR, 0, 1), Date.UTC(CANONICAL_YEAR + 1, 0, 1)];
}

/**
 * Always a whole calendar year, so a partial year shows an empty remainder
 * rather than stretching its months across the full width.
 */
export function yearRange(years: readonly number[]): [number, number] {
  const first = Math.min(...years);
  const last = Math.max(...years);
  return [Date.UTC(first, 0, 1), Date.UTC(last + 1, 0, 1)];
}

/**
 * How a year selection reads: "2025", "1990–1995 · 6 years", or, when the
 * selection has holes in it, "4 years · 1946–2025". `all` is every year the data
 * holds, which is what makes a run contiguous even where the archive itself has
 * a gap.
 */
export function describeYears(selected: readonly number[], all: readonly number[]): string {
  // Deduplicated, not just sorted: the count and the contiguity test both read
  // the length, and a repeated year would make a selection with a hole in it
  // claim to be a solid run.
  const list = [...new Set(selected)].sort((a, b) => a - b);
  if (list.length === 0) return 'none';
  if (list.length === 1) return String(list[0]);
  const lo = list[0];
  const hi = list[list.length - 1];
  const between = all.filter((y) => y >= lo && y <= hi).length;
  return between === list.length
    ? `${lo}–${hi} · ${list.length} years`
    : `${list.length} years · ${lo}–${hi}`;
}
