import type { Aggregate } from '../data/types.ts';

/**
 * Combining a run of hours into one point. Pure, no I/O and no DOM.
 *
 * Only divisors of 24 are offered: a 5-hour bucket would straddle midnight and
 * drift through the day, so the same slot would mean a different time of day on
 * consecutive days. The range runs from every hour to one point per day.
 *
 * The top of the range is where overlaid years actually separate. A 24-hour
 * bucket is the only step that removes the within-day swing completely: one
 * year's median day moves 6.4 °C at hourly and still 4.2 °C at six-hourly, which
 * is the noise each line carries on top of the difference between years.
 */
export const STEP_HOURS: readonly number[] = [1, 2, 3, 4, 6, 8, 12, 24];

export function samplesPerDay(stepHours: number): number {
  return 24 / stepHours;
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
