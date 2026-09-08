// The one file that knows a chart library exists. Swapping ECharts for another
// library means writing a sibling of this file, nothing else (plan section 4).
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsType } from 'echarts/core';

import type { Axis, ChartAdapter, ChartView, Series } from './adapter.ts';

// Registering only these keeps the bundle tree-shaken; see the README for the
// measured size.
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

const UTC_STAMP = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

/** On the shared axis the year belongs to the series, not to the x position. */
const DAY_STAMP = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

/** Closest you may zoom in, so the window can never collapse to nothing. */
const MIN_SPAN_MS = 6 * 3_600_000;
/** How much one wheel notch changes the visible span. */
const ZOOM_STEP = 1.35;

interface TooltipPoint {
  seriesName?: string;
  value?: [number, number | null];
  marker?: string;
}

const clamp = (value: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, value));

/** ECharts wants null, not NaN, to break a line. */
function toPairs(series: Series): Array<[number, number | null]> {
  const pairs = new Array<[number, number | null]>(series.x.length);
  for (let i = 0; i < series.x.length; i += 1) {
    const v = series.y[i];
    pairs[i] = [series.x[i], Number.isNaN(v) ? null : v];
  }
  return pairs;
}

function yAxisOption(axis: Axis) {
  return {
    type: 'value' as const,
    name: axis.label,
    nameLocation: 'middle' as const,
    nameGap: 46,
    min: axis.range[0],
    max: axis.range[1],
    position: axis.side,
    axisLabel: { hideOverlap: true },
    splitLine: { show: true },
  };
}

export class EChartsAdapter implements ChartAdapter {
  readonly #chart: EChartsType;
  readonly #container: HTMLElement;
  readonly #onResize: () => void;
  readonly #detachRoam: () => void;
  #onXRange: ((range: [number, number]) => void) | undefined;
  /** Full x extent of the current view. */
  #extent: [number, number] | undefined;
  /** The window currently on screen. */
  #applied: [number, number] | undefined;

  constructor(container: HTMLElement) {
    this.#container = container;
    this.#chart = echarts.init(container, undefined, { renderer: 'canvas' });
    this.#onResize = () => this.#chart.resize();
    window.addEventListener('resize', this.#onResize);

    // The slider moves the window without going through this class, so its
    // changes are picked up here. A window equal to the one just applied is
    // this adapter hearing its own render and must not be reported onwards.
    this.#chart.on('dataZoom', () => {
      const option = this.#chart.getOption() as {
        dataZoom?: Array<{ startValue?: number; endValue?: number }>;
      };
      const zoom = option.dataZoom?.[0];
      if (zoom?.startValue === undefined || zoom.endValue === undefined) return;
      const range: [number, number] = [zoom.startValue, zoom.endValue];
      if (this.#applied && range[0] === this.#applied[0] && range[1] === this.#applied[1]) return;
      this.#applied = range;
      this.#onXRange?.(range);
    });

    this.#detachRoam = this.#installRoam();
  }

  onXRangeChange(handler: (range: [number, number]) => void): void {
    this.#onXRange = handler;
  }

  /** Data value under a client x coordinate, using the chart's own mapping. */
  #valueAt(clientX: number): number | undefined {
    const left = this.#container.getBoundingClientRect().left;
    const value = this.#chart.convertFromPixel({ xAxisIndex: 0 }, clientX - left);
    return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
  }

  /** Milliseconds per horizontal pixel, measured off the live axis. */
  #msPerPixel(): number | undefined {
    const a = this.#chart.convertFromPixel({ xAxisIndex: 0 }, 100);
    const b = this.#chart.convertFromPixel({ xAxisIndex: 0 }, 200);
    if (typeof a !== 'number' || typeof b !== 'number') return undefined;
    const per = (b - a) / 100;
    return Number.isFinite(per) && per > 0 ? per : undefined;
  }

  #setWindow(lo: number, hi: number): void {
    if (!this.#extent) return;
    const [min, max] = this.#extent;
    const span = clamp(hi - lo, MIN_SPAN_MS, max - min);
    const start = clamp(lo, min, max - span);
    this.#chart.dispatchAction({ type: 'dataZoom', startValue: start, endValue: start + span });
    this.#applied = [start, start + span];
    this.#onXRange?.(this.#applied);
  }

  /**
   * Wheel to zoom, drag to pan.
   *
   * ECharts' own `inside` roam controller receives the wheel event here but does
   * not act on it, so the interaction is driven explicitly through dispatchAction
   * instead. It stays inside this file, which is where plan section 8 puts zoom
   * and pan, and it anchors the zoom on the cursor rather than the centre.
   */
  #installRoam(): () => void {
    const onWheel = (event: WheelEvent) => {
      if (!this.#extent || !this.#applied) return;
      event.preventDefault();
      const [lo, hi] = this.#applied;
      const span = hi - lo;
      const anchor = clamp(this.#valueAt(event.clientX) ?? lo + span / 2, lo, hi);
      const next = clamp(
        span * (event.deltaY < 0 ? 1 / ZOOM_STEP : ZOOM_STEP),
        MIN_SPAN_MS,
        this.#extent[1] - this.#extent[0],
      );
      const share = span === 0 ? 0.5 : (anchor - lo) / span;
      this.#setWindow(anchor - next * share, anchor - next * share + next);
    };

    let panning = false;
    let lastX = 0;

    const zoomedIn = () =>
      this.#extent !== undefined
      && this.#applied !== undefined
      && this.#applied[1] - this.#applied[0] < this.#extent[1] - this.#extent[0];

    const onPointerDown = (event: PointerEvent) => {
      // Nothing to pan while the whole year is on screen.
      if (event.button !== 0 || !zoomedIn()) return;
      panning = true;
      lastX = event.clientX;
      this.#container.setPointerCapture(event.pointerId);
      this.#container.style.cursor = 'grabbing';
    };

    const onPointerMove = (event: PointerEvent) => {
      if (!panning || !this.#applied) return;
      const per = this.#msPerPixel();
      if (per === undefined) return;
      const shift = (event.clientX - lastX) * per;
      lastX = event.clientX;
      this.#setWindow(this.#applied[0] - shift, this.#applied[1] - shift);
    };

    const stop = (event: PointerEvent) => {
      if (!panning) return;
      panning = false;
      this.#container.releasePointerCapture?.(event.pointerId);
      this.#container.style.cursor = '';
    };

    this.#container.addEventListener('wheel', onWheel, { passive: false });
    this.#container.addEventListener('pointerdown', onPointerDown);
    this.#container.addEventListener('pointermove', onPointerMove);
    this.#container.addEventListener('pointerup', stop);
    this.#container.addEventListener('pointercancel', stop);

    return () => {
      this.#container.removeEventListener('wheel', onWheel);
      this.#container.removeEventListener('pointerdown', onPointerDown);
      this.#container.removeEventListener('pointermove', onPointerMove);
      this.#container.removeEventListener('pointerup', stop);
      this.#container.removeEventListener('pointercancel', stop);
    };
  }

  render(view: ChartView): void {
    const multi = view.series.length > 1;
    this.#extent = [view.xRange[0], view.xRange[1]];
    const window_ = view.xWindow ?? view.xRange;
    this.#applied = [window_[0], window_[1]];

    const axisIndex = new Map(view.yAxes.map((a, i) => [a.scale, i]));
    const decimalsFor = new Map(view.yAxes.map((a) => [a.scale, a.decimals]));
    // ECharts identifies a series by name, so the tooltip looks up unit and
    // precision by label rather than searching the series list per row.
    const byLabel = new Map(
      view.series.map((s) => [s.label, { unit: s.unit, decimals: decimalsFor.get(s.scale) ?? 1 }]),
    );

    this.#chart.setOption(
      {
        useUTC: true,
        animation: false,
        grid: {
          left: 76,
          right: multi ? 64 : 32,
          top: multi ? 46 : 28,
          bottom: 92,
          containLabel: false,
        },
        // Identity is never colour alone: the legend renders each year's real
        // line style, and a small selection is labelled at the line's end too.
        legend: {
          show: multi,
          type: 'scroll' as const,
          top: 0,
          icon: 'roundRect',
          itemWidth: 22,
          textStyle: { fontSize: 11 },
        },
        tooltip: {
          // With many years on screen an axis tooltip would list all of them, so
          // past a handful the pointer reports only the line under the cursor.
          trigger: view.series.length > 6 ? ('item' as const) : ('axis' as const),
          axisPointer: { type: 'line' },
          formatter: (raw: TooltipPoint | TooltipPoint[]) => {
            const points = Array.isArray(raw) ? raw : [raw];
            if (!points.length || !points[0].value) return '';
            const rows = points.map((p) => {
              const value = p.value?.[1];
              const info = p.seriesName === undefined ? undefined : byLabel.get(p.seriesName);
              const shown = value === null || value === undefined
                ? 'no reading'
                : `${value.toFixed(info?.decimals ?? 1)} ${info?.unit ?? ''}`.trim();
              return `${p.marker ?? ''}${p.seriesName}: <b>${shown}</b>`;
            });
            const stamp = view.xKind === 'dayOfYear' ? DAY_STAMP : UTC_STAMP;
            return `${stamp.format(points[0].value[0])} UTC<br>${rows.join('<br>')}`;
          },
        },
        // Zoom and pan act on time only, so the fixed y-scale that makes years
        // comparable is never rescaled by a zoom.
        dataZoom: [
          {
            type: 'slider',
            xAxisIndex: 0,
            height: 30,
            bottom: 34,
            startValue: window_[0],
            endValue: window_[1],
          },
        ],
        xAxis: {
          type: 'time',
          min: view.xRange[0],
          max: view.xRange[1],
          axisLabel: { hideOverlap: true },
        },
        yAxis: view.yAxes.map(yAxisOption),
        series: view.series.map((s) => ({
          type: 'line' as const,
          name: s.label,
          yAxisIndex: axisIndex.get(s.scale) ?? 0,
          data: toPairs(s),
          showSymbol: false,
          connectNulls: false,
          sampling: 'lttb' as const,
          ...(s.color ? { color: s.color, itemStyle: { color: s.color } } : {}),
          lineStyle: {
            width: 1,
            opacity: view.lineOpacity ?? 1,
            type: s.dash ?? ('solid' as const),
            ...(s.color ? { color: s.color } : {}),
          },
          // Four or fewer series also get a direct label, so the eye does not
          // have to travel to the legend and back.
          endLabel: {
            show: view.series.length > 1 && view.series.length <= 4,
            formatter: s.label,
            fontSize: 11,
            distance: 4,
          },
        })),
      },
      // Replace rather than merge, so dropping a series actually drops it.
      true,
    );
  }

  destroy(): void {
    window.removeEventListener('resize', this.#onResize);
    this.#detachRoam();
    this.#chart.dispose();
  }
}
