import type { DataSource } from './source.ts';
import type { Meta, YearData } from './types.ts';

/** Fetches one committed JSON chunk per year, caching what it has already read. */
export class JsonYearSource implements DataSource {
  readonly #base: string;
  readonly #years = new Map<number, Promise<YearData>>();
  #meta: Promise<Meta> | undefined;

  /** `base` is Vite's BASE_URL, so a GitHub Pages sub-path is a config change. */
  constructor(base: string = import.meta.env.BASE_URL) {
    this.#base = base.endsWith('/') ? base : `${base}/`;
  }

  meta(): Promise<Meta> {
    this.#meta ??= this.#get<Meta>('data/meta.json').then((m) => {
      if (!Array.isArray(m.years) || !Array.isArray(m.variables)) {
        throw new Error('meta.json is missing its years or variables list');
      }
      return m;
    });
    return this.#meta;
  }

  year(year: number): Promise<YearData> {
    let pending = this.#years.get(year);
    if (!pending) {
      pending = this.#get<YearData>(`data/years/${year}.json`).then((d) => {
        // Timestamps are reconstructed as start + i * 3600s, so a column of the
        // wrong length would silently shift every point after it.
        for (const [key, values] of Object.entries(d.columns)) {
          if (values.length !== d.hours) {
            throw new Error(
              `${year}.json: column "${key}" has ${values.length} values, expected ${d.hours}`,
            );
          }
        }
        return d;
      });
      // A failed fetch must not be cached as a permanent failure.
      pending.catch(() => this.#years.delete(year));
      this.#years.set(year, pending);
    }
    return pending;
  }

  async #get<T>(path: string): Promise<T> {
    const url = `${this.#base}${path}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText} for ${url}`);
    return (await response.json()) as T;
  }
}
