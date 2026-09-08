import type { Meta } from '../data/types.ts';
import type { Store } from './state.ts';

/**
 * The only place that reads the DOM. Controls write to the store and nothing
 * else; replacing them with a multi-select or a URL-driven state touches this
 * file alone.
 */
export function mountControls(meta: Meta, store: Store): void {
  const yearInput = document.querySelector<HTMLInputElement>('#year');
  const yearList = document.querySelector<HTMLDataListElement>('#years');
  const variableSelect = document.querySelector<HTMLSelectElement>('#variable');
  if (!yearInput || !yearList || !variableSelect) {
    throw new Error('index.html is missing #year, #years or #variable');
  }

  const known = new Set(meta.years.map((y) => y.year));

  yearList.replaceChildren(
    ...meta.years.map((y) => {
      const option = document.createElement('option');
      option.value = String(y.year);
      return option;
    }),
  );

  variableSelect.replaceChildren(
    ...meta.variables.map((v) => {
      const option = document.createElement('option');
      option.value = v.key;
      option.textContent = v.unit ? `${v.label} (${v.unit})` : v.label;
      return option;
    }),
  );

  yearInput.value = String(store.state.years[0]);
  variableSelect.value = store.state.variables[0];

  yearInput.addEventListener('change', () => {
    const year = Number(yearInput.value.trim());
    // An unknown year is ignored: the input keeps what was typed, the chart
    // keeps what it has, and main.ts puts the reason in the status line.
    if (!Number.isInteger(year) || !known.has(year)) {
      store.update({ years: [] });
      return;
    }
    store.update({ years: [year] });
  });

  variableSelect.addEventListener('change', () => {
    store.update({ variables: [variableSelect.value] });
  });
}
