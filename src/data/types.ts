// The contract between the build-time chunking script and the app.
// Mirrors the schema written by scripts/split_years.py; see plan section 3.

export type VarKey = string;

export interface VariableMeta {
  key: VarKey;
  label: string;
  unit: string;
  /** Global range over the whole series, sentinels excluded. */
  min: number;
  max: number;
  decimals: number;
  /** A real observation that is not a measurement on this scale (clht 999). */
  sentinel?: number;
  /** How a run of hours combines when the app resamples to a coarser step. */
  aggregate: Aggregate;
}

/**
 * A plain mean is wrong for three of the thirteen variables.
 * `sum` for amounts per hour (rain, sunshine): a day is their total, not their
 * average. `circular` for wind direction: a mean of degrees is not a direction.
 */
export type Aggregate = 'mean' | 'sum' | 'circular';

export interface YearMeta {
  year: number;
  /** ISO-8601 UTC timestamp of the first hour. */
  start: string;
  hours: number;
}

export interface Meta {
  station: { name: string; height_m: number | null; lat: number | null; lon: number | null };
  source: { provider: string; dataset: string; licence: string; licence_url: string };
  years: YearMeta[];
  variables: VariableMeta[];
}

export interface YearData {
  year: number;
  start: string;
  hours: number;
  /** One array per variable, `hours` long. null = missing reading. */
  columns: Record<VarKey, Array<number | null>>;
}
