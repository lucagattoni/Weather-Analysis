import type { Aggregate } from '../data/types.ts';

/**
 * Combining a run of hours into one point. Pure, no I/O and no DOM.
 *
 * Only divisors of 24 are offered: a 5-hour bucket would straddle midnight and
 * drift through the day, so the same slot would mean a different time of day on
 * consecutive days. The range runs from every hour to one point a week.
 *
 * A 24-hour bucket is the first step that removes the within-day swing
 * completely: one year's median day moves 6.4 °C at hourly and still 4.2 °C at
 * six-hourly, which is the noise each line carries on top of the difference
 * between years. Beyond a day the steps smooth weather itself, not the diurnal
 * cycle, which is what makes many overlaid years readable as seasonal shapes.
 *
 * Multi-day buckets are blocks of hours counted from 1 January, so a leap year's
 * block boundaries sit a day off a non-leap year's after February. Each block is
 * still plotted at the real calendar date of its middle, so the overlay stays
 * honest; the two just are not sampling identical date ranges, which they cannot,
 * because the years are not the same length.
 */
export const STEP_HOURS: readonly number[] = [1, 2, 3, 4, 6, 8, 12, 24, 48, 96, 168];

/** How a step reads on the slider: below a day in hours, at or above it in days. */
export function describeStep(stepHours: number): string {
  if (stepHours < 24) return `${stepHours} h · ${24 / stepHours}/day`;
  const days = stepHours / 24;
  return days === 1 ? '1 day' : `${days} days`;
}

/** How a step reads mid-sentence, as the cadence of the points on the line. */
export function describeCadence(stepHours: number): string {
  if (stepHours === 1) return 'hourly';
  if (stepHours === 24) return 'daily';
  if (stepHours < 24) return `every ${stepHours} h`;
  return `every ${stepHours / 24} days`;
}

/**
 * One bucket of `values[from..to)`, honouring the variable's own aggregate.
 * Returns NaN for a bucket that cannot be summarised, which the chart draws as a gap.
 */
export function combine(
  values: Float64Array,
  from: number,
  to: number,
  aggregate: Aggregate,
): number {
  if (aggregate === 'circular') {
    // Averaging degrees is not averaging directions: 350 and 10 average to 180,
    // the opposite of the truth. Average the unit vectors instead.
    let sumCos = 0;
    let sumSin = 0;
    let n = 0;
    for (let i = from; i < to; i += 1) {
      const v = values[i];
      if (Number.isNaN(v)) continue;
      const radians = (v * Math.PI) / 180;
      sumCos += Math.cos(radians);
      sumSin += Math.sin(radians);
      n += 1;
    }
    if (n === 0) return Number.NaN;
    const degrees = (Math.atan2(sumSin / n, sumCos / n) * 180) / Math.PI;
    return (degrees + 360) % 360;
  }

  let total = 0;
  let n = 0;
  let missing = 0;
  for (let i = from; i < to; i += 1) {
    const v = values[i];
    if (Number.isNaN(v)) {
      missing += 1;
      continue;
    }
    total += v;
    n += 1;
  }
  if (n === 0) return Number.NaN;
  // A partial total is a wrong number rather than a noisy one, so a sum needs
  // every hour in the bucket. A mean is happy with what it has.
  if (aggregate === 'sum') return missing > 0 ? Number.NaN : total;
  return total / n;
}
