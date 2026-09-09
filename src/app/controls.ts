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
 * No gesture needs a modifier key or a hover, because a phone has neither:
 *
 *   tap a tick          adds that year, or removes it if it is already shown
 *   drag across ticks   adds every year swept, previewed live
 *   a chip              removes that year
 *   only <year>         removes all but the most recent selected
 *   keyboard            arrows move the cursor, space toggles, shift-arrow sweeps
 *
 * The one gesture that is not universal is the drag. On a narrow screen the
 * strip is wider than its track and `touch-action: pan-x` gives a horizontal
 * swipe to scrolling, which is how a finger reaches 1946; the browser then
 * cancels the pointer and the sweep never happens. Reaching the old years
 * matters more than sweeping them, so the trade stands and the hint below says
 * which gesture the device actually has. Tapping adds and removes everywhere.
 */
export function mountControls(meta: Meta, store: Store): void {
  const q = <T extends Element>(sel: string): T => {
    const el = document.querySelector<T>(sel);
    if (!el) throw new Error(`index.html is missing ${sel}`);
    return el;
  };
  const track = q<HTMLDivElement>('.year-track');
  const strip = q<HTMLDivElement>('#year-strip');
  const scale = q<HTMLDivElement>('#year-scale');
  const chips = q<HTMLParagraphElement>('#year-chips');
  const hint = q<HTMLParagraphElement>('#year-hint');
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

  // Promise only the gesture this device has: a finger scrolls the strip rather
  // than sweeping it, so telling a phone to "drag across for a span" is telling
  // it to do something that will not work.
  const coarse = window.matchMedia('(pointer: coarse)');
  const showHint = () => {
    hint.textContent = coarse.matches
      ? 'tap a year to add or remove it, swipe the strip to reach older years'
      : 'tap a year to add or remove it, drag across for a span';
    strip.title = hint.textContent;
  };
  showHint();
  coarse.addEventListener('change', showHint);

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
      // Mirrored, because the strip reads right to left in time.
      el.style.left = `${(1 - (i + 0.5) / years.length) * 100}%`;
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

  /**
   * The chips are the chart's legend as well as its controls: one list, not a
   * legend and a set of chips naming the same years. So the swatch draws the
   * year's real line, dash and all, because identity is never colour alone --
   * two of the three shades in a decade differ only by their dash pattern.
   */
  const paintChips = (set: ReadonlySet<number>) => {
    const mode = themeMode();
    const list = sorted(set);
    const only = list.length === 1;
    const nodes: Node[] = list.map((year) => {
      const style = styleForYear(year, mode);
      // The last year standing is a legend entry and nothing more: a remove
      // control that refuses to remove would be worse than none.
      const chip = document.createElement(only ? 'span' : 'button');
      const swatch = document.createElement('span');
      swatch.className = 'swatch';
      swatch.style.borderTopColor = style.color;
      swatch.style.borderTopStyle = style.dash === 'solid' ? 'solid' : style.dash;
      chip.append(swatch, document.createTextNode(label(year)));
      if (chip instanceof HTMLButtonElement) {
        chip.type = 'button';
        chip.title = `Remove ${year}`;
        chip.addEventListener('click', () => commit(withoutYear(year)));
      }
      return chip;
    });
    if (list.length > 1) {
      // Not "clear", which would empty the selection: it leaves the most recent
      // year of the selection, and names the year it is going to leave.
      const keep = list[list.length - 1];
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'clear';
      button.title = `Remove every year except ${keep}`;
      button.textContent = `only ${keep}`;
      button.addEventListener('click', () => commit(new Set([keep])));
      nodes.push(button);
    }
    chips.replaceChildren(...nodes);
  };

  /**
   * On a narrow screen the strip is wider than the track and scrolls inside it,
   * so a year the app just selected can be off screen. Only `scrollLeft` moves:
   * scrollIntoView would take the page with it.
   */
  const keepVisible = (year: number) => {
    const el = ticks[years.indexOf(year)];
    if (!el) return;
    const view = track.getBoundingClientRect();
    const tick = el.getBoundingClientRect();
    const margin = 24;
    if (tick.left < view.left) track.scrollLeft -= view.left - tick.left + margin;
    else if (tick.right > view.right) track.scrollLeft += tick.right - view.right + margin;
  };

  /**
   * The live preview during a drag: the strip only. A drag can sweep eighty
   * years, and rebuilding eighty chips on every pointer move to show what the
   * strip is already showing would be the one expensive thing in this file.
   */
  const preview = (set: ReadonlySet<number>) => {
    paintStrip(set);
  };

  /** Both halves of the control, from the committed selection. No store write. */
  const repaint = () => {
    paintStrip(selected);
    paintChips(selected);
  };

  // A year selection is a set of years, and nothing else about it is app state.
  const publish = () => {
    repaint();
    store.update({ years: sorted(selected) });
  };

  // The gesture hint is a first-run instruction. Once a year has been picked by
  // hand it has been read, and the row it costs is better spent on the chart.
  const publishByHand = () => {
    hint.hidden = true;
    publish();
  };

  /**
   * The one way a gesture changes the selection. A selection of no years is not
   * a state the app offers: there would be nothing to look at and nothing to say
   * where you were, so a gesture that would empty it does nothing instead. Every
   * removal goes through here, so the rule is stated once.
   */
  const commit = (next: ReadonlySet<number>) => {
    if (next.size === 0) return;
    selected.clear();
    for (const y of next) selected.add(y);
    publishByHand();
  };

  const withoutYear = (year: number): Set<number> => {
    const next = new Set(selected);
    next.delete(year);
    return next;
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
  /** Which pointer owns the drag, so a second finger cannot steer it. */
  let dragPointer: number | null = null;

  const dragResult = (): Set<number> => {
    const set = new Set(selected);
    if (dragAnchor === null) return set;
    if (dragCurrent === null || dragCurrent === dragAnchor) {
      if (!set.has(dragAnchor)) set.add(dragAnchor);
      // Taking the last year off would leave nothing to look at, so the tap
      // does nothing. Checked here as well as in `commit` so that the live
      // preview shows what will actually happen.
      else if (set.size > 1) set.delete(dragAnchor);
      return set;
    }
    for (const year of spanBetween(dragAnchor, dragCurrent)) set.add(year);
    return set;
  };

  const endDrag = (pointerId: number) => {
    dragAnchor = null;
    dragCurrent = null;
    dragPointer = null;
    if (strip.hasPointerCapture(pointerId)) strip.releasePointerCapture(pointerId);
  };

  /** True for events from any pointer other than the one that started the drag. */
  const notOurs = (event: PointerEvent) =>
    dragAnchor === null || event.pointerId !== dragPointer;

  strip.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    // A drag is already running under another pointer. A palm brushing the strip
    // mid-sweep used to move the anchor to wherever it landed, so the gesture
    // committed a span nobody asked for; the second pointer is ignored instead.
    if (dragAnchor !== null) return;
    const year = yearUnder(event.clientX, event.clientY);
    if (year === null) return;
    event.preventDefault();
    strip.focus({ preventScroll: true });
    dragAnchor = year;
    dragCurrent = year;
    dragPointer = event.pointerId;
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
    if (notOurs(event)) return;
    // The button is no longer down, so the release happened somewhere this
    // element never heard about: capture was refused, or the window lost it.
    // Without this the preview would follow the pointer for ever. Mouse only:
    // `buttons` is what a mouse release reliably reports, and trusting it for a
    // touch would risk ending a sweep that is still under the finger.
    if (event.pointerType === 'mouse' && event.buttons === 0) {
      const result = dragResult();
      endDrag(event.pointerId);
      commit(result);
      return;
    }
    const year = yearUnder(event.clientX, event.clientY);
    if (year === null || year === dragCurrent) return;
    dragCurrent = year;
    cursor = year;
    preview(dragResult());
  });

  strip.addEventListener('pointerup', (event) => {
    if (notOurs(event)) return;
    const result = dragResult();
    endDrag(event.pointerId);
    commit(result);
  });

  // A touch that turns into a scroll, or a pointer the browser takes away.
  // The committed selection is repainted, so the preview never sticks.
  strip.addEventListener('pointercancel', (event) => {
    if (notOurs(event)) return;
    endDrag(event.pointerId);
    publish();
  });

  strip.addEventListener('keydown', (event) => {
    const i = years.indexOf(cursor);
    let next = i;
    // The strip runs most-recent-first, so left is later and right is earlier.
    switch (event.key) {
      case 'ArrowLeft': next = i + 1; break;
      case 'ArrowRight': next = i - 1; break;
      case 'PageDown': next = i - 10; break;
      case 'PageUp': next = i + 10; break;
      case 'Home': next = years.length - 1; break;
      case 'End': next = 0; break;
      case ' ':
      case 'Enter': {
        event.preventDefault();
        // Holding the key down auto-repeats, and each repeat would toggle again:
        // the year's fate would come down to how long the key was held. One
        // press, one toggle.
        if (event.repeat) return;
        const toggled = selected.has(cursor)
          ? withoutYear(cursor)
          : new Set(selected).add(cursor);
        keyAnchor = cursor;
        commit(toggled);
        return;
      }
      default:
        return;
    }
    event.preventDefault();
    cursor = years[Math.min(years.length - 1, Math.max(0, next))];
    if (event.shiftKey) {
      const swept = new Set(selected);
      for (const year of spanBetween(keyAnchor, cursor)) swept.add(year);
      commit(swept);
    } else {
      // Moving the cursor selects nothing. Painting the strip moves the ring;
      // going through `commit` would rebuild every chip and write the same year
      // list to the store on each arrow press.
      keyAnchor = cursor;
      paintStrip(selected);
    }
    keepVisible(cursor);
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

  // Both the ticks and the chip swatches carry a year's colour, and the ramps are
  // chosen per theme. Repainting only the strip left the chips, which are the
  // chart's legend, showing the previous theme's colours until the next edit.
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', repaint);

  publish();
  keepVisible(cursor);
}
