import type { Meta } from '../data/types.ts';
import { STEP_HOURS, describeStep } from '../model/resample.ts';
import { styleForYear } from '../model/style.ts';
import type { Store } from './state.ts';

/**
 * The only place that reads the DOM. Controls write to the store and nothing
 * else; replacing them with a URL-driven state touches this file alone.
 *
 * The year selection is a plain set of years and nothing else. It used to be a
 * contiguous range plus a set of extras, which is why only the extras had chips:
 * a range cannot express "1990 to 2000 without 1995", so the years it contributed
 * were not removable and could not honestly be shown as removable chips. A set
 * can express every selection, so every selected year gets a chip and every chip
 * removes.
 *
 * Every gesture below works with a finger and none needs a modifier key, because
 * a phone has no shift key and no hover:
 *
 *   tap a tick          adds that year, or removes it if it is already shown
 *   drag across ticks   adds every year swept, previewed live
 *   a chip              removes that year
 *   clear               removes all of them
 *   keyboard            arrows move the cursor, space toggles, shift-arrow sweeps
 */
export function mountControls(meta: Meta, store: Store): void {
  const q = <T extends Element>(sel: string): T => {
    const el = document.querySelector<T>(sel);
    if (!el) throw new Error(`index.html is missing ${sel}`);
    return el;
  };
  const strip = q<HTMLDivElement>('#year-strip');
  const scale = q<HTMLDivElement>('#year-scale');
  const chips = q<HTMLParagraphElement>('#year-chips');
  const variableSelect = q<HTMLSelectElement>('#variable');
  const stepInput = q<HTMLInputElement>('#step');
  const stepValue = q<HTMLOutputElement>('#step-value');
  const opacityInput = q<HTMLInputElement>('#opacity');
  const opacityValue = q<HTMLOutputElement>('#opacity-value');
  const resetZoom = q<HTMLButtonElement>('#reset-zoom');

  const years = meta.years.map((y) => y.year);
  const last = years[years.length - 1];
  const partial = new Set(meta.years.filter((y) => y.hours < 8760).map((y) => y.year));
  const known = new Set(years);
  const themeMode = (): 'light' | 'dark' =>
    window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

  const label = (year: number) => (partial.has(year) ? `${year} (partial)` : String(year));

  /** The whole year selection. Sorted only on the way out. */
  const selected = new Set<number>(store.state.years.filter((y) => known.has(y)));
  if (selected.size === 0) selected.add(last);
  /** The year the keyboard is on, and the year a shift-arrow sweeps from. */
  let cursor = [...selected].sort((a, b) => a - b)[0];
  let keyAnchor = cursor;

  const ticks = years.map((year) => {
    const el = document.createElement('span');
    el.className = partial.has(year) ? 'tick partial' : 'tick';
    el.id = `year-tick-${year}`;
    el.dataset.year = String(year);
    el.title = label(year);
    el.setAttribute('role', 'option');
    el.setAttribute('aria-label', partial.has(year) ? `${year}, partial year` : String(year));
    return el;
  });
  strip.replaceChildren(...ticks);

  scale.replaceChildren(
    ...years.flatMap((year, i) => {
      if (year % 10 !== 0) return [];
      const el = document.createElement('span');
      el.textContent = String(year);
      el.style.left = `${((i + 0.5) / years.length) * 100}%`;
      return [el];
    }),
  );

  variableSelect.replaceChildren(
    ...meta.variables.map((v) => {
      const el = document.createElement('option');
      el.value = v.key;
      el.textContent = v.unit ? `${v.label} (${v.unit})` : v.label;
      return el;
    }),
  );
  variableSelect.value = store.state.variables[0];

  stepInput.max = String(STEP_HOURS.length - 1);
  stepInput.value = String(Math.max(0, STEP_HOURS.indexOf(store.state.stepHours)));
  opacityInput.value = String(Math.round(store.state.lineOpacity * 100));

  const sorted = (set: ReadonlySet<number>): number[] => [...set].sort((a, b) => a - b);

  /** Every year from a to b inclusive, whichever way round they came. */
  const spanBetween = (a: number, b: number): number[] => {
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    return years.filter((y) => y >= lo && y <= hi);
  };

  const paintStrip = (set: ReadonlySet<number>) => {
    const mode = themeMode();
    years.forEach((year, i) => {
      const el = ticks[i];
      const on = set.has(year);
      el.classList.toggle('on', on);
      el.classList.toggle('cursor', year === cursor);
      el.style.setProperty('--tick', on ? styleForYear(year, mode).color : '');
      el.setAttribute('aria-selected', String(on));
    });
    strip.setAttribute('aria-activedescendant', `year-tick-${cursor}`);
  };

  const paintChips = (set: ReadonlySet<number>) => {
    const mode = themeMode();
    const list = sorted(set);
    const nodes: Node[] = list.map((year) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.title = `Remove ${year}`;
      const swatch = document.createElement('span');
      swatch.className = 'swatch';
      swatch.style.background = styleForYear(year, mode).color;
      button.append(swatch, document.createTextNode(label(year)));
      button.addEventListener('click', () => {
        selected.delete(year);
        publish();
      });
      return button;
    });
    if (list.length > 1) {
      const clear = document.createElement('button');
      clear.type = 'button';
      clear.className = 'clear';
      clear.title = 'Remove every year';
      clear.textContent = 'clear';
      clear.addEventListener('click', () => {
        selected.clear();
        publish();
      });
      nodes.push(clear);
    }
    const hint = document.createElement('span');
    hint.className = 'hint';
    hint.textContent = list.length
      ? 'tap a year to add or remove it, drag across for a span'
      : 'no years shown — tap a year above';
    nodes.push(hint);
    chips.replaceChildren(...nodes);
  };

  /**
   * The live preview during a drag: the strip only. A drag can sweep eighty
   * years, and rebuilding eighty chips on every pointer move to show what the
   * strip is already showing would be the one expensive thing in this file.
   */
  const preview = (set: ReadonlySet<number>) => {
    paintStrip(set);
  };

  // A year selection is a set of years, and nothing else about it is app state.
  const publish = () => {
    paintStrip(selected);
    paintChips(selected);
    store.update({ years: sorted(selected) });
  };

  // The tick under a point, found by hit-testing the DOM rather than by dividing
  // the width: the strip scrolls on a narrow screen, and a computed slice would
  // then be measuring against the wrong origin.
  const yearUnder = (clientX: number, clientY: number): number | null => {
    const el = document.elementFromPoint(clientX, clientY);
    const tick = el instanceof Element ? el.closest<HTMLElement>('.tick') : null;
    const year = Number(tick?.dataset.year);
    return Number.isFinite(year) && known.has(year) ? year : null;
  };

  // The drag in progress: where it started and where it is now. A drag that
  // never leaves its first tick is a tap, which toggles; one that moves adds
  // every year it swept. Deciding on release rather than on press is what lets
  // the preview show exactly what will be committed.
  let dragAnchor: number | null = null;
  let dragCurrent: number | null = null;

  const dragResult = (): Set<number> => {
    const set = new Set(selected);
    if (dragAnchor === null) return set;
    if (dragCurrent === null || dragCurrent === dragAnchor) {
      if (set.has(dragAnchor)) set.delete(dragAnchor);
      else set.add(dragAnchor);
      return set;
    }
    for (const year of spanBetween(dragAnchor, dragCurrent)) set.add(year);
    return set;
  };

  const endDrag = (pointerId: number) => {
    dragAnchor = null;
    dragCurrent = null;
    if (strip.hasPointerCapture(pointerId)) strip.releasePointerCapture(pointerId);
  };

  strip.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    const year = yearUnder(event.clientX, event.clientY);
    if (year === null) return;
    event.preventDefault();
    strip.focus({ preventScroll: true });
    dragAnchor = year;
    dragCurrent = year;
    cursor = year;
    keyAnchor = year;
    preview(dragResult());
    // Capture keeps a drag alive when the pointer leaves the strip. Not worth
    // failing the gesture over: without it the drag just ends at the edge.
    try {
      strip.setPointerCapture(event.pointerId);
    } catch {
      /* this pointer cannot be captured */
    }
  });

  strip.addEventListener('pointermove', (event) => {
    if (dragAnchor === null) return;
    const year = yearUnder(event.clientX, event.clientY);
    if (year === null || year === dragCurrent) return;
    dragCurrent = year;
    cursor = year;
    preview(dragResult());
  });

  strip.addEventListener('pointerup', (event) => {
    if (dragAnchor === null) return;
    const result = dragResult();
    endDrag(event.pointerId);
    selected.clear();
    for (const year of result) selected.add(year);
    publish();
  });

  // A touch that turns into a scroll, or a pointer the browser takes away.
  // The committed selection is repainted, so the preview never sticks.
  strip.addEventListener('pointercancel', (event) => {
    if (dragAnchor === null) return;
    endDrag(event.pointerId);
    publish();
  });

  strip.addEventListener('keydown', (event) => {
    const i = years.indexOf(cursor);
    let next = i;
    switch (event.key) {
      case 'ArrowLeft': next = i - 1; break;
      case 'ArrowRight': next = i + 1; break;
      case 'PageDown': next = i - 10; break;
      case 'PageUp': next = i + 10; break;
      case 'Home': next = 0; break;
      case 'End': next = years.length - 1; break;
      case ' ':
      case 'Enter':
        event.preventDefault();
        if (selected.has(cursor)) selected.delete(cursor);
        else selected.add(cursor);
        keyAnchor = cursor;
        publish();
        return;
      default:
        return;
    }
    event.preventDefault();
    cursor = years[Math.min(years.length - 1, Math.max(0, next))];
    if (event.shiftKey) for (const year of spanBetween(keyAnchor, cursor)) selected.add(year);
    else keyAnchor = cursor;
    publish();
  });

  variableSelect.addEventListener('change', () => {
    store.update({ variables: [variableSelect.value] });
  });

  const showStep = (hours: number) => {
    stepValue.textContent = describeStep(hours);
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

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    preview(selected);
  });

  publish();
}
