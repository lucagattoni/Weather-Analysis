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
// measured size. dataZoom is registered but not switched on: the POC has no
// zoom, and enabling it later is a change inside this file (plan section 8).
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

interface TooltipPoint {
  seriesName?: string;
  value?: [number, number | null];
  marker?: string;
}

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
  readonly #onResize: () => void;

  constructor(container: HTMLElement) {
    this.#chart = echarts.init(container, undefined, { renderer: 'canvas' });
    this.#onResize = () => this.#chart.resize();
    window.addEventListener('resize', this.#onResize);
  }

  render(view: ChartView): void {
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
        grid: { left: 76, right: 24, top: 28, bottom: 48, containLabel: false },
        legend: { show: view.series.length > 1, top: 0 },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'line' },
          formatter: (points: TooltipPoint[]) => {
            if (!points.length || !points[0].value) return '';
            const rows = points.map((p) => {
              const value = p.value?.[1];
              const info = p.seriesName === undefined ? undefined : byLabel.get(p.seriesName);
              const shown = value === null || value === undefined
                ? 'no reading'
                : `${value.toFixed(info?.decimals ?? 1)} ${info?.unit ?? ''}`.trim();
              return `${p.marker ?? ''}${p.seriesName}: <b>${shown}</b>`;
            });
            return `${UTC_STAMP.format(points[0].value[0])} UTC<br>${rows.join('<br>')}`;
          },
        },
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
          lineStyle: { width: 1 },
        })),
      },
      // Replace rather than merge, so dropping a series actually drops it.
      true,
    );
  }

  destroy(): void {
    window.removeEventListener('resize', this.#onResize);
    this.#chart.dispose();
  }
}
