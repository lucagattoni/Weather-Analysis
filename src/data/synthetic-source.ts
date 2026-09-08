import type { DataSource } from './source.ts';
import type { Meta, YearData } from './types.ts';

/**
 * A second DataSource that exists from day one. It is what proves the seam in
 * plan section 4 is real rather than assumed: swap it into main.ts and the app
 * runs with no chunks on disk.
 */
export class SyntheticSource implements DataSource {
  readonly #years = [2023, 2024];

  async meta(): Promise<Meta> {
    return {
      station: { name: 'SYNTHETIC', height_m: 0, lat: 0, lon: 0 },
      source: { provider: 'synthetic', dataset: 'generated', licence: '—', licence_url: '' },
      years: this.#years.map((year) => ({
        year,
        start: `${year}-01-01T00:00:00Z`,
        hours: year % 4 === 0 ? 8784 : 8760,
      })),
      variables: [
        { key: 'temp', label: 'Air temperature', unit: '°C', min: -11.5, max: 29.1, decimals: 1 },
      ],
    };
  }

  async year(year: number): Promise<YearData> {
    const hours = year % 4 === 0 ? 8784 : 8760;
    const temp = Array.from({ length: hours }, (_, i) =>
      Math.round((9 + 8 * Math.sin((2 * Math.PI * i) / hours - Math.PI / 2)) * 10) / 10,
    );
    return { year, start: `${year}-01-01T00:00:00Z`, hours, columns: { temp } };
  }
}
