import type { Series } from '../chart/adapter.ts';
import type { VariableMeta, YearData } from '../data/types.ts';

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
export function seriesFor(year: YearData, variable: VariableMeta): Series {
  const values = year.columns[variable.key];
  if (!values) throw new Error(`${year.year}.json has no column "${variable.key}"`);

  const startMs = Date.parse(year.start);
  if (Number.isNaN(startMs)) throw new Error(`${year.year}.json has an unreadable start "${year.start}"`);

  const x = new Float64Array(values.length);
  const y = new Float64Array(values.length);
  for (let i = 0; i < values.length; i += 1) {
    x[i] = startMs + i * HOUR_MS;
    const v = values[i];
    y[i] = v === null || v === variable.sentinel ? Number.NaN : v;
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
): Series[] {
  const out: Series[] = [];
  for (const year of years) {
    const data = loaded.get(year);
    if (!data) continue;
    for (const variable of variables) out.push(seriesFor(data, variable));
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
