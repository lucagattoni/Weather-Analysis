import type { Meta } from '../data/types.ts';
import { STEP_HOURS, samplesPerDay } from '../model/resample.ts';
import { styleForYear } from '../model/style.ts';
import type { Store } from './state.ts';

/**
 * The only place that reads the DOM. Controls write to the store and nothing
 * else; replacing them with a URL-driven state touches this file alone.
 *
 * The year selection is a contiguous range plus a set of individual extras. Both
 * live here because they are input state, not app state: the store only ever
 * sees the years they add up to.
 */
export function mountControls(meta: Meta, store: Store): void {
  const q = <T extends Element>(sel: string): T => {
    const el = document.querySelector<T>(sel);
    if (!el) throw new Error(`index.html is missing ${sel}`);
    return el;
  };
  const fromInput = q<HTMLInputElement>('#year-from');
  const toInput = q<HTMLInputElement>('#year-to');
  const rangeValue = q<HTMLOutputElement>('#year-range-value');
  const fill = q<HTMLSpanElement>('#year-range .fill');
  const addSelect = q<HTMLSelectElement>('#year-add');
  const chips = q<HTMLParagraphElement>('#year-chips');
  const variableSelect = q<HTMLSelectElement>('#variable');
  const stepInput = q<HTMLInputElement>('#step');
  const stepValue = q<HTMLOutputElement>('#step-value');
  const opacityInput = q<HTMLInputElement>('#opacity');
  const opacityValue = q<HTMLOutputElement>('#opacity-value');
  const resetZoom = q<HTMLButtonElement>('#reset-zoom');

  const years = meta.years.map((y) => y.year);
  const first = years[0];
  const last = years[years.length - 1];
  const partial = new Set(meta.years.filter((y) => y.hours < 8760).map((y) => y.year));
  const known = new Set(years);
  const extras = new Set<number>();
  const themeMode = (): 'light' | 'dark' =>
    window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

  const option = (value: string, text: string): HTMLOptionElement => {
    const el = document.createElement('option');
    el.value = value;
    el.textContent = text;
    return el;
  };

  for (const input of [fromInput, toInput]) {
    input.min = String(first);
    input.max = String(last);
    input.step = '1';
  }
  const startYear = store.state.years[0] ?? last;
  fromInput.value = String(startYear);
  toInput.value = String(startYear);

  variableSelect.replaceChildren(
    ...meta.variables.map((v) => option(v.key, v.unit ? `${v.label} (${v.unit})` : v.label)),
  );
  variableSelect.value = store.state.variables[0];

  addSelect.replaceChildren(
    option('', 'year…'),
    ...years.map((y) => option(String(y), partial.has(y) ? `${y} (partial)` : String(y))),
  );

  stepInput.max = String(STEP_HOURS.length - 1);
  stepInput.value = String(Math.max(0, STEP_HOURS.indexOf(store.state.stepHours)));
  opacityInput.value = String(Math.round(store.state.lineOpacity * 100));

  const bounds = (): [number, number] => {
    const a = Number(fromInput.value);
    const b = Number(toInput.value);
    return a <= b ? [a, b] : [b, a];
  };

  const selection = (): number[] => {
    const [lo, hi] = bounds();
    const set = new Set<number>();
    for (let y = lo; y <= hi; y += 1) if (known.has(y)) set.add(y);
    for (const y of extras) set.add(y);
    return [...set].sort((a, b) => a - b);
  };

  const paintChips = () => {
    const mode = themeMode();
    chips.replaceChildren(
      ...[...extras].sort((a, b) => a - b).map((y) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.title = `Remove ${y}`;
        const swatch = document.createElement('span');
        swatch.className = 'swatch';
        swatch.style.background = styleForYear(y, mode).color;
        button.append(swatch, document.createTextNode(String(y)));
        button.addEventListener('click', () => {
          extras.delete(y);
          paintChips();
          publish();
        });
        return button;
      }),
    );
  };

  const paintRange = () => {
    const [lo, hi] = bounds();
    const span = last - first;
    fill.style.left = `${((lo - first) / span) * 100}%`;
    fill.style.right = `${100 - ((hi - first) / span) * 100}%`;
    const count = selection().length;
    rangeValue.textContent = lo === hi
      ? `${lo}${partial.has(lo) ? ' (partial)' : ''}`
      : `${lo}–${hi} · ${count} year${count === 1 ? '' : 's'}`;
  };

  // A year selection is a set of years, and nothing else about it is app state.
  const publish = () => {
    paintRange();
    store.update({ years: selection() });
  };

  for (const input of [fromInput, toInput]) {
    input.addEventListener('input', () => {
      // Dragging one knob past the other swaps their roles rather than blocking,
      // so a drag never sticks against an invisible wall.
      publish();
    });
  }

  addSelect.addEventListener('change', () => {
    const y = Number(addSelect.value);
    addSelect.value = '';
    if (!known.has(y)) return;
    const [lo, hi] = bounds();
    // Already covered by the range, so adding it as an extra would be a no-op
    // chip the user could not get rid of by moving the slider.
    if (y >= lo && y <= hi) return;
    extras.add(y);
    paintChips();
    publish();
  });

  variableSelect.addEventListener('change', () => {
    store.update({ variables: [variableSelect.value] });
  });

  const showStep = (hours: number) => {
    stepValue.textContent = `${hours} h · ${samplesPerDay(hours)}/day`;
  };
  const showOpacity = (fraction: number) => {
    opacityValue.textContent = `${Math.round(fraction * 100)}%`;
  };
  showStep(store.state.stepHours);
  showOpacity(store.state.lineOpacity);

  // `input` rather than `change`, so both sliders track the drag.
  stepInput.addEventListener('input', () => {
    const hours = STEP_HOURS[Number(stepInput.value)] ?? 1;
    showStep(hours);
    store.update({ stepHours: hours });
  });

  opacityInput.addEventListener('input', () => {
    const fraction = Number(opacityInput.value) / 100;
    showOpacity(fraction);
    store.update({ lineOpacity: fraction });
  });

  resetZoom.addEventListener('click', () => {
    store.update({ xRange: undefined });
  });

  store.subscribe((state) => {
    resetZoom.hidden = state.xRange === undefined;
  });

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', paintChips);

  paintChips();
  paintRange();
  store.update({ years: selection() });
}
