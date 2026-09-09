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
  /** Set by the model. Absent means the chart picks. */
  color?: string;
  dash?: 'solid' | 'dashed' | 'dotted';
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
  /** The full extent of the x axis. */
  xRange: [number, number];
  /** The zoomed window to restore, if any. Absent means show the full extent. */
  xWindow?: [number, number];
  yAxes: Axis[];
  series: Series[];
  /** One line naming what is plotted. The app writes the words, the chart places them. */
  title?: string;
  /** 0..1. Below 1, overlapping lines show through each other. */
  lineOpacity?: number;
}

/** A leap year, so 29 February has a slot on the shared day-of-year axis. */
export const CANONICAL_YEAR = 2024;

export interface ChartAdapter {
  render(view: ChartView): void;
  /** Reports the visible x window after the viewer zooms or pans. */
  onXRangeChange(handler: (range: [number, number]) => void): void;
  destroy(): void;
}
