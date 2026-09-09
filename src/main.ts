// Composition root: the only file that knows all four layers.
import './style.css';

import { mountControls } from './app/controls.ts';
import { Store } from './app/state.ts';
import type { AppState } from './app/state.ts';
import { EChartsAdapter } from './chart/echarts.ts';
import { JsonYearSource } from './data/json-year-source.ts';
import type { DataSource } from './data/source.ts';
import type { Meta, VariableMeta, YearData } from './data/types.ts';
import { buildSeries, canonicalRange, describeYears, yearRange } from './model/series.ts';
import { axesFor } from './model/scales.ts';
import { describeCadence } from './model/resample.ts';
import { styleSeries } from './model/style.ts';
import { CANONICAL_YEAR } from './chart/adapter.ts';

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

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
const themeMode = (): 'light' | 'dark' => (darkQuery.matches ? 'dark' : 'light');

/**
 * The zoom window is always stored in the canonical year, whatever the chart is
 * showing. That is what lets it survive a change of year selection (decision C):
 * a window means "10 June to 20 August", not "10 June 2025 to 20 August 2025".
 */
const sameDayIn = (ms: number, year: number): number => {
  const d = new Date(ms);
  return Date.UTC(year, d.getUTCMonth(), d.getUTCDate(), d.getUTCHours(), d.getUTCMinutes());
};
const toDisplay = (win: [number, number], year: number): [number, number] =>
  [sameDayIn(win[0], year), sameDayIn(win[1], year)];
const toCanonicalWindow = (win: [number, number]): [number, number] =>
  [sameDayIn(win[0], CANONICAL_YEAR), sameDayIn(win[1], CANONICAL_YEAR)];

/** Guards against a slow fetch landing after a newer selection. */
let latestRequest = 0;

async function draw(meta: Meta, state: Readonly<AppState>): Promise<void> {
  const request = (latestRequest += 1);
  const { years, variables: variableKeys, xRange, stepHours, lineOpacity } = state;

  const variables = variableKeys
    .map((key) => meta.variables.find((v) => v.key === key))
    .filter((v): v is VariableMeta => v !== undefined);
  if (variables.length === 0) {
    say('Unknown variable.');
    return;
  }

  // Removing the last chip is allowed, so an empty selection is a state the app
  // has to draw: an empty chart on the right axes, not the previous years left
  // on screen with nothing in the controls to explain them.
  const axes = axesFor(variables);
  const named = axes.map((a) => a.label).join(' · ');
  const allYears = meta.years.map((y) => y.year);

  if (years.length === 0) {
    adapter.render({
      xKind: 'dayOfYear',
      xRange: canonicalRange(),
      yAxes: axes,
      series: [],
      lineOpacity,
      title: named,
    });
    say('No years shown. Click a year on the strip above, or pick one from Add.');
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

  // One year keeps its own dates; two or more share the canonical Jan-Dec axis.
  const xKind = years.length > 1 ? 'dayOfYear' : 'time';
  const xRangeFull = xKind === 'dayOfYear' ? canonicalRange() : yearRange(years);
  const series = styleSeries(
    buildSeries(loaded, years, variables, stepHours, xKind),
    themeMode(),
  );
  const which = describeYears(years, allYears);
  adapter.render({
    xKind,
    xRange: xRangeFull,
    xWindow: xRange && (xKind === 'dayOfYear' ? xRange : toDisplay(xRange, years[0])),
    yAxes: axes,
    series,
    lineOpacity,
    title: `${named} · ${which}`,
  });

  const gaps = series.reduce(
    (total, s) => total + s.y.reduce((n, v) => (Number.isNaN(v) ? n + 1 : n), 0),
    0,
  );
  const points = series.reduce((total, s) => total + s.y.length, 0);
  // A cadence, not "means": rain and sunshine are summed rather than averaged.
  const detail = describeCadence(stepHours);
  say(
    `${which}: ${points.toLocaleString('en-GB')} points, ${detail}`
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

  // Hourly and fully opaque, and nothing moves either on its own: the sliders
  // are the only thing that changes detail or alpha.
  const store = new Store({
    years: [defaultYear],
    variables: [defaultVariable],
    stepHours: 1,
    lineOpacity: 1,
  });
  mountControls(meta, store);

  // A zoom reported by the chart is recorded but must not trigger a re-render,
  // or applying it would report it again and loop. So the chart is redrawn only
  // when the selection changes, or when a zoom window is cleared.
  const keyOf = (s: Readonly<AppState>) =>
    `${s.years.join()}|${s.variables.join()}|${s.stepHours}|${s.lineOpacity}`;
  let lastKey = keyOf(store.state);
  let lastXRange = store.state.xRange;

  adapter.onXRangeChange((range) => {
    // Zooming back out to the whole year is not a window: dropping it here is
    // what makes the reset control disappear once there is nothing to reset.
    const state = store.state;
    if (state.years.length === 0) return;
    const [lo, hi] = state.years.length > 1 ? canonicalRange() : yearRange(state.years);
    const wholeYear = range[0] <= lo && range[1] >= hi;
    store.update({
      xRange: wholeYear ? undefined : toCanonicalWindow(range),
    });
  });

  store.subscribe((state) => {
    const key = keyOf(state);
    const zoomCleared = state.xRange === undefined && lastXRange !== undefined;
    lastXRange = state.xRange;
    if (key === lastKey && !zoomCleared) return;
    lastKey = key;
    void draw(meta, state);
  });

  // The ramps are chosen per theme, so a theme change is a re-render.
  darkQuery.addEventListener('change', () => {
    void draw(meta, store.state);
  });

  await draw(meta, store.state);
}

start().catch((error: unknown) => {
  say(`Failed to start: ${(error as Error).message}`);
  console.error(error);
});
