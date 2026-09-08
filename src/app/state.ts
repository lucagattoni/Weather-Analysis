import type { VarKey } from '../data/types.ts';

/**
 * Plural from the start. The POC controls put exactly one year and one variable
 * in here; the model and the adapter already handle N of each, so overlays are
 * a controls change rather than a model change (plan section 4).
 */
export interface AppState {
  years: number[];
  variables: VarKey[];
  /** Reserved for the zoom/range roadmap item; unused by the POC. */
  xRange?: [number, number];
}

type Listener = (state: AppState) => void;

export class Store {
  #state: AppState;
  readonly #listeners = new Set<Listener>();

  constructor(initial: AppState) {
    this.#state = initial;
  }

  get state(): Readonly<AppState> {
    return this.#state;
  }

  update(patch: Partial<AppState>): void {
    this.#state = { ...this.#state, ...patch };
    for (const listener of this.#listeners) listener(this.#state);
  }

  subscribe(listener: Listener): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }
}
