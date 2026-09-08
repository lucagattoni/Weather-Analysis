// Composition root: the only file that knows all four layers.
import './style.css';

import { mountControls } from './app/controls.ts';
import { Store } from './app/state.ts';
import type { AppState } from './app/state.ts';
import { EChartsAdapter } from './chart/echarts.ts';
import { JsonYearSource } from './data/json-year-source.ts';
import type { DataSource } from './data/source.ts';
import type { Meta, VariableMeta, YearData } from './data/types.ts';
import { buildSeries, yearRange } from './model/series.ts';
import { axesFor } from './model/scales.ts';

// Swap this for SyntheticSource to run with no chunks on disk.
const source: DataSource = new JsonYearSource();

const chartEl = document.querySelector<HTMLDivElement>('#chart');
const statusEl = document.querySelector<HTMLParagraphElement>('#status');
if (!chartEl || !statusEl) throw new Error('index.html is missing #chart or #status');

const say = (message: string) => {
  statusEl.textContent = message;
};

const adapter = new EChartsAdapter(chartEl);
const loaded = new Map<number, YearData>();

/** Guards against a slow fetch landing after a newer selection. */
let latestRequest = 0;

async function draw(meta: Meta, state: Readonly<AppState>): Promise<void> {
  const request = (latestRequest += 1);
  const { years, variables: variableKeys, xRange } = state;

  if (years.length === 0) {
    say('That year is not in the data. Pick one between '
      + `${meta.years[0].year} and ${meta.years[meta.years.length - 1].year}.`);
    return;
  }

  const variables = variableKeys
    .map((key) => meta.variables.find((v) => v.key === key))
    .filter((v): v is VariableMeta => v !== undefined);
  if (variables.length === 0) {
    say('Unknown variable.');
    return;
  }

  const missing = years.filter((y) => !loaded.has(y));
  if (missing.length) say(`Loading ${missing.join(', ')}…`);

  try {
    const fetched = await Promise.all(missing.map((y) => source.year(y)));
    if (request !== latestRequest) return;
    for (const data of fetched) loaded.set(data.year, data);
  } catch (error) {
    if (request !== latestRequest) return;
    say(`Could not load ${missing.join(', ')}: ${(error as Error).message}`);
    return;
  }

  const series = buildSeries(loaded, years, variables);
  adapter.render({
    xKind: 'time',
    xRange: yearRange(years),
    xWindow: xRange,
    yAxes: axesFor(variables),
    series,
  });

  const gaps = series.reduce(
    (total, s) => total + s.y.reduce((n, v) => (Number.isNaN(v) ? n + 1 : n), 0),
    0,
  );
  const hours = series.reduce((total, s) => total + s.y.length, 0);
  say(
    `${years.join(', ')}: ${hours.toLocaleString('en-GB')} hourly readings`
    + (gaps ? `, ${gaps.toLocaleString('en-GB')} shown as gaps` : '')
    + '. Scroll to zoom, drag to pan.',
  );
}

async function start(): Promise<void> {
  say('Loading…');
  const meta = await source.meta();

  // Default to the most recent complete year, so the first chart is a full one.
  const complete = meta.years.filter((y) => y.hours >= 8760);
  const defaultYear = (complete.at(-1) ?? meta.years[meta.years.length - 1]).year;
  const defaultVariable = meta.variables.some((v) => v.key === 'temp')
    ? 'temp'
    : meta.variables[0].key;

  const store = new Store({ years: [defaultYear], variables: [defaultVariable] });
  mountControls(meta, store);

  // A zoom reported by the chart is recorded but must not trigger a re-render,
  // or applying it would report it again and loop. So the chart is redrawn only
  // when the selection changes, or when a zoom window is cleared.
  const keyOf = (s: Readonly<AppState>) => `${s.years.join()}|${s.variables.join()}`;
  let lastKey = keyOf(store.state);
  let lastXRange = store.state.xRange;

  adapter.onXRangeChange((range) => {
    // Zooming back out to the whole year is not a window: dropping it here is
    // what makes the reset control disappear once there is nothing to reset.
    const state = store.state;
    if (state.years.length === 0) return;
    const [lo, hi] = yearRange(state.years);
    const wholeYear = range[0] <= lo && range[1] >= hi;
    store.update({ xRange: wholeYear ? undefined : range });
  });

  store.subscribe((state) => {
    const key = keyOf(state);
    const zoomCleared = state.xRange === undefined && lastXRange !== undefined;
    lastXRange = state.xRange;
    if (key === lastKey && !zoomCleared) return;
    lastKey = key;
    void draw(meta, state);
  });

  await draw(meta, store.state);
}

start().catch((error: unknown) => {
  say(`Failed to start: ${(error as Error).message}`);
  console.error(error);
});
