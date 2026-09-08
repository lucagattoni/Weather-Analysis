import type { Series } from '../chart/adapter.ts';

/**
 * How a year becomes a line style. Pure: no DOM, no chart library.
 *
 * Hue comes from the decade, shade from the year's position in the decade
 * divided by three, dash from that position modulo three. All three are derived
 * from the year number and never from its position in the selection, so widening
 * the range never repaints a line that was already on screen.
 *
 *   2020 light solid   2021 light dashed   2022 light dotted
 *   2023 mid   solid   2024 mid   dashed   2025 mid   dotted
 *   2026 dark  solid   ...
 *
 * Twelve combinations per decade cover a decade's ten years with two spare.
 *
 * The ramps below are generated, not chosen. Every one passes the ordinal checks
 * (monotone lightness, adjacent gap, contrast against its own surface, single
 * hue), and all eight hues pass the categorical checks against each other at
 * every shade level, in both light and dark. They live between OKLab lightness
 * 0.50 and 0.80 because that is the only window where all eight hues hold enough
 * chroma to still read as a colour; outside it the pale end washes to grey and
 * the dark end sinks into the surface. Light mode stops at 0.72 so its lightest
 * step still clears the near-white surface.
 *
 * Decision A (plan section 8): the hue cycles modulo eight. There are nine
 * decades in 1946-2026 and eight hues, so the 1940s and the 2020s share one.
 * That is only reachable by selecting across the whole 81-year span.
 */

export type DashKind = 'solid' | 'dashed' | 'dotted';

const DASHES: readonly DashKind[] = ['solid', 'dashed', 'dotted'];

/** Eight decade hues, four shades each, light to dark. Generated and validated. */
const RAMPS: Record<'light' | 'dark', readonly (readonly string[])[]> = {
  light: [
  // blue
  ['#62a6fe', '#428eee', '#2977d5', '#0961bd'],
  // orange
  ['#fd7845', '#e3602b', '#c94806', '#a83a00'],
  // aqua
  ['#37bf89', '#05a873', '#038e61', '#027650'],
  // yellow
  ['#db9404', '#bd8006', '#a16c00', '#865901'],
  // magenta
  ['#e97ca5', '#d0668f', '#b74f79', '#9f3964'],
  // green
  ['#56c050', '#3da838', '#1f911b', '#017901'],
  // violet
  ['#9a96fe', '#847cef', '#6f65d6', '#5b4fbd'],
  // red
  ['#fe726c', '#ec514f', '#d13739', '#b71723'],
  ],
  dark: [
  // blue
  ['#91c1fe', '#53a0ff', '#3280dd', '#0761bc'],
  // orange
  ['#ffa383', '#f57242', '#d1521d', '#a93900'],
  // aqua
  ['#64d7a6', '#3fb787', '#06976a', '#007651'],
  // yellow
  ['#f5ae46', '#d38e1a', '#ad7204', '#875800'],
  // magenta
  ['#ff9bb9', '#f06a98', '#cd4a7a', '#aa285e'],
  // green
  ['#71da6a', '#4fb94a', '#2b9927', '#017901'],
  // violet
  ['#b9b4fe', '#998ef3', '#7c70d1', '#6052b0'],
  // red
  ['#fea09d', '#f17170', '#ce5153', '#ab3137'],
  ],
};

export interface YearStyle {
  color: string;
  dash: DashKind;
}

export function styleForYear(year: number, mode: 'light' | 'dark'): YearStyle {
  const decade = Math.floor(year / 10) * 10;
  const hue = (((decade - 1940) / 10) % 8 + 8) % 8;
  const withinDecade = year - decade;
  // Ten years over four shades: 0,0,0, 1,1,1, 2,2,2, 3.
  const shade = Math.min(3, Math.floor(withinDecade / 3));
  return {
    color: RAMPS[mode][hue][shade],
    dash: DASHES[withinDecade % 3],
  };
}

/** Applies a style to every series, keyed by the year in its id (`${year}:${key}`). */
export function styleSeries(series: Series[], mode: 'light' | 'dark'): Series[] {
  return series.map((s) => {
    const year = Number(s.id.split(':')[0]);
    if (!Number.isFinite(year)) return s;
    const { color, dash } = styleForYear(year, mode);
    return { ...s, color, dash };
  });
}
