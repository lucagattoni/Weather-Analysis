import type { Meta } from '../data/types.ts';
import { STEP_HOURS, samplesPerDay } from '../model/resample.ts';
import type { Store } from './state.ts';

/**
 * The only place that reads the DOM. Controls write to the store and nothing
 * else; replacing them with a multi-select or a URL-driven state touches this
 * file alone.
 */
export function mountControls(meta: Meta, store: Store): void {
  const yearSelect = document.querySelector<HTMLSelectElement>('#year');
  const variableSelect = document.querySelector<HTMLSelectElement>('#variable');
  const stepInput = document.querySelector<HTMLInputElement>('#step');
  const stepValue = document.querySelector<HTMLOutputElement>('#step-value');
  const opacityInput = document.querySelector<HTMLInputElement>('#opacity');
  const opacityValue = document.querySelector<HTMLOutputElement>('#opacity-value');
  const resetZoom = document.querySelector<HTMLButtonElement>('#reset-zoom');
  if (!yearSelect || !variableSelect || !stepInput || !stepValue
      || !opacityInput || !opacityValue || !resetZoom) {
    throw new Error('index.html is missing one of the control elements');
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

  // The step slider indexes into STEP_HOURS rather than carrying hours directly,
  // so its notches land on the divisors of 24 and nowhere between them.
  stepInput.max = String(STEP_HOURS.length - 1);
  stepInput.value = String(Math.max(0, STEP_HOURS.indexOf(store.state.stepHours)));
  opacityInput.value = String(Math.round(store.state.lineOpacity * 100));

  const showStep = (hours: number) => {
    const perDay = samplesPerDay(hours);
    stepValue.textContent = `${hours} h · ${perDay}/day`;
  };
  const showOpacity = (fraction: number) => {
    opacityValue.textContent = `${Math.round(fraction * 100)}%`;
  };
  showStep(store.state.stepHours);
  showOpacity(store.state.lineOpacity);

  // A different year is a different time span, so any zoom window is dropped.
  yearSelect.addEventListener('change', () => {
    store.update({ years: [Number(yearSelect.value)], xRange: undefined });
  });

  // Changing the variable keeps the zoom: it is the same span, a different line.
  variableSelect.addEventListener('change', () => {
    store.update({ variables: [variableSelect.value] });
  });

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
}
