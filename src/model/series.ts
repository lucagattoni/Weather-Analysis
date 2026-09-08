import type { Series } from '../chart/adapter.ts';
import type { VariableMeta, YearData } from '../data/types.ts';
import { combine } from './resample.ts';

const HOUR_MS = 3_600_000;

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
export function seriesFor(year: YearData, variable: VariableMeta, stepHours = 1): Series {
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
    y[b] = step === 1 ? hourly[from] : combine(hourly, from, to, variable.aggregate);
  }
  return {
    id: `${year.year}:${variable.key}`,
    label: `${variable.label} ${year.year}`,
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
): Series[] {
  const out: Series[] = [];
  for (const year of years) {
    const data = loaded.get(year);
    if (!data) continue;
    for (const variable of variables) out.push(seriesFor(data, variable, stepHours));
  }
  return out;
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
