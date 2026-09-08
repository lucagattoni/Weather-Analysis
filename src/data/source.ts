import type { Meta, YearData } from './types.ts';

/**
 * Where the app gets its data. Two members, so a second implementation is
 * cheap: a Range-request source, DuckDB-WASM or a live API replaces this file
 * without the model, adapter or app changing (plan section 4).
 */
export interface DataSource {
  meta(): Promise<Meta>;
  year(year: number): Promise<YearData>;
}
