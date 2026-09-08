// The only contract between the app and whatever draws the chart.
// Nothing outside src/chart/ may import a charting library (plan section 4).

/** One line. `y` holds NaN where the line must break. */
export interface Series {
  id: string;
  label: string;
  unit: string;
  /** Which y-axis this series belongs to, matched against Axis.scale. */
  scale: string;
  /** Milliseconds since the epoch, UTC. */
  x: Float64Array;
  y: Float64Array;
}

export interface Axis {
  scale: string;
  label: string;
  range: [number, number];
  side: 'left' | 'right';
  decimals: number;
}

export interface ChartView {
  xKind: 'time' | 'dayOfYear';
  xRange: [number, number];
  yAxes: Axis[];
  series: Series[];
}

export interface ChartAdapter {
  render(view: ChartView): void;
  destroy(): void;
}
