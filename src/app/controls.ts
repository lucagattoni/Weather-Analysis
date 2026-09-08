import type { Meta } from '../data/types.ts';
import type { Store } from './state.ts';

/**
 * The only place that reads the DOM. Controls write to the store and nothing
 * else; replacing them with a multi-select or a URL-driven state touches this
 * file alone.
 */
export function mountControls(meta: Meta, store: Store): void {
  const yearSelect = document.querySelector<HTMLSelectElement>('#year');
  const variableSelect = document.querySelector<HTMLSelectElement>('#variable');
  const resetZoom = document.querySelector<HTMLButtonElement>('#reset-zoom');
  if (!yearSelect || !variableSelect || !resetZoom) {
    throw new Error('index.html is missing #year, #variable or #reset-zoom');
  }

  const option = (value: string, text: string): HTMLOptionElement => {
    const el = document.createElement('option');
    el.value = value;
    el.textContent = text;
    return el;
  };

  // A select rather than an input with a datalist: a datalist popup cannot be
  // opened by clicking, which left the control usable only by typing a year.
  yearSelect.replaceChildren(
    ...meta.years.map((y) =>
      option(String(y.year), y.hours < 8760 ? `${y.year} (partial)` : String(y.year)),
    ),
  );
  variableSelect.replaceChildren(
    ...meta.variables.map((v) => option(v.key, v.unit ? `${v.label} (${v.unit})` : v.label)),
  );

  yearSelect.value = String(store.state.years[0]);
  variableSelect.value = store.state.variables[0];

  // A different year is a different time span, so any zoom window is dropped.
  yearSelect.addEventListener('change', () => {
    store.update({ years: [Number(yearSelect.value)], xRange: undefined });
  });

  // Changing the variable keeps the zoom: it is the same span, a different line.
  variableSelect.addEventListener('change', () => {
    store.update({ variables: [variableSelect.value] });
  });

  resetZoom.addEventListener('click', () => {
    store.update({ xRange: undefined });
  });

  store.subscribe((state) => {
    resetZoom.hidden = state.xRange === undefined;
  });
}
