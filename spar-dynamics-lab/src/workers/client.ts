import * as Comlink from 'comlink';
import type { AnalysisApi } from './analysis.worker';

let remote: Comlink.Remote<AnalysisApi> | null = null;

/** Lazily started analysis worker (sweeps and optimisation run off the main thread). */
export function analysisWorker(): Comlink.Remote<AnalysisApi> {
  if (!remote) {
    const w = new Worker(new URL('./analysis.worker.ts', import.meta.url), { type: 'module' });
    remote = Comlink.wrap<AnalysisApi>(w);
  }
  return remote;
}

export const proxy = Comlink.proxy;
