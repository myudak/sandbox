import { useEffect, useState, useSyncExternalStore } from 'react';
import { engine } from './engine';

/** Re-render when the engine rebuilds (new configuration). */
export function useEngineVersion() {
  return useSyncExternalStore(engine.subscribe, engine.getVersion);
}

/** Re-render on a fixed interval while mounted (for live readouts). */
export function useTicker(ms: number) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
  return tick;
}
