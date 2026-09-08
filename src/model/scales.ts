import type { Axis } from '../chart/adapter.ts';
import type { VariableMeta } from '../data/types.ts';

/**
 * Fixed y-range per variable: the global range from meta.json, rounded outward
 * to a round step. The same variable therefore gets the same axis on every
 * year, which is what makes years comparable by eye.
 */

/** Manual overrides, the registry escape hatch from plan section 4. */
const RANGE_OVERRIDES: Record<string, [number, number]> = {
  // A compass, not a measurement: the axis should read 0..360, not 0..375.
  wddir: [0, 360],
};

/** Roughly how many gridline intervals a rounded axis should end up with. */
const TARGET_INTERVALS = 10;

/** The closest 1 / 2 / 2.5 / 5 / 10 times a power of ten. */
function niceStep(target: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(target));
  let best = magnitude;
  for (const multiple of [1, 2, 2.5, 5, 10]) {
    const candidate = multiple * magnitude;
    if (Math.abs(candidate - target) < Math.abs(best - target)) best = candidate;
  }
  return best;
}

export function roundOutward(min: number, max: number): [number, number] {
  const span = max - min;
  if (!(span > 0)) return [min - 1, max + 1];
  const step = niceStep(span / TARGET_INTERVALS);
  const places = Math.max(0, -Math.floor(Math.log10(step)) + 1);
  // The epsilon keeps a max that already sits on a gridline (100% humidity,
  // 1 h of sun) from gaining a whole empty step above it.
  const lo = Math.floor(min / step + 1e-9) * step;
  const hi = Math.ceil(max / step - 1e-9) * step;
  return [Number(lo.toFixed(places)), Number(hi.toFixed(places))];
}

export function axisFor(variable: VariableMeta, side: 'left' | 'right' = 'left'): Axis {
  const override = RANGE_OVERRIDES[variable.key];
  return {
    scale: variable.key,
    label: variable.unit ? `${variable.label} (${variable.unit})` : variable.label,
    range: override ?? roundOutward(variable.min, variable.max),
    side,
    decimals: variable.decimals,
  };
}

/** One axis per variable on show; the second and later ones sit on the right. */
export function axesFor(variables: VariableMeta[]): Axis[] {
  return variables.map((v, i) => axisFor(v, i === 0 ? 'left' : 'right'));
}
