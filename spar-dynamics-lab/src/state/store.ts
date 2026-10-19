import { create } from 'zustand';
import { DEFAULT_TMD, TmdDesign } from '../physics/tmd';
import type { SeaState } from '../physics/waves';
import type { WindState } from '../physics/wind';
import { DEFAULT_CONSTRAINTS, Constraints, Objective } from '../physics/optimize';

export type Tab = 'live' | 'spectra' | 'optimize' | 'robustness' | 'validation' | 'model';
export type CameraPreset = 'overview' | 'waterline' | 'underwater' | 'nacelle';

export interface Scenario {
  id: string;
  name: string;
  blurb: string;
  sea: SeaState;
  wind: WindState;
}

export const SCENARIOS: Scenario[] = [
  {
    id: 'swell',
    name: 'Parked · long swell',
    blurb: 'Swell near the 30 s pitch resonance — where a tuned damper should shine.',
    sea: { kind: 'irregular', height: 2, period: 25, gamma: 3.3, seed: 1 },
    wind: { speed: 0, turbulence: 'off' },
  },
  {
    id: 'storm',
    name: 'Parked · storm',
    blurb: 'Hs 8 m, Tp 14 s: wave energy well above the pitch resonance.',
    sea: { kind: 'irregular', height: 8, period: 14, gamma: 3.3, seed: 1 },
    wind: { speed: 0, turbulence: 'off' },
  },
  {
    id: 'rated',
    name: 'Operating · rated wind',
    blurb: '11.4 m/s with IEC class B turbulence: aero damping and low-frequency wind loads.',
    sea: { kind: 'irregular', height: 4, period: 10, gamma: 3.3, seed: 1 },
    wind: { speed: 11.4, turbulence: 'B' },
  },
  {
    id: 'regular',
    name: 'Regular wave at resonance',
    blurb: 'A clean 30 s regular wave — the textbook resonance case.',
    sea: { kind: 'regular', height: 2, period: 30, gamma: 3.3, seed: 1 },
    wind: { speed: 0, turbulence: 'off' },
  },
];

interface AppState {
  tab: Tab;
  scenarioId: string | null;
  sea: SeaState;
  wind: WindState;
  tmd: TmdDesign;
  /** Which simulation is drawn solid; the other is the optional ghost. */
  primary: 'tmd' | 'base';
  ghost: boolean;
  cutaway: boolean;
  timeScale: number;
  exaggeration: number;
  paused: boolean;
  camera: CameraPreset;
  cameraNonce: number;
  objective: Objective;
  constraints: Constraints;
  set: (p: Partial<AppState>) => void;
  setSea: (p: Partial<SeaState>) => void;
  setWind: (p: Partial<WindState>) => void;
  setTmd: (p: Partial<TmdDesign>) => void;
  applyScenario: (id: string) => void;
  goCamera: (c: CameraPreset) => void;
}

const first = SCENARIOS[0];

export const useApp = create<AppState>((set) => ({
  tab: 'live',
  scenarioId: first.id,
  sea: first.sea,
  wind: first.wind,
  tmd: DEFAULT_TMD,
  primary: 'tmd',
  ghost: true,
  cutaway: false,
  timeScale: 5,
  exaggeration: 3,
  paused: false,
  camera: 'overview',
  cameraNonce: 0,
  objective: 'pitchRms',
  constraints: DEFAULT_CONSTRAINTS,
  set: (p) => set(p),
  setSea: (p) => set((s) => ({ sea: { ...s.sea, ...p }, scenarioId: null })),
  setWind: (p) => set((s) => ({ wind: { ...s.wind, ...p }, scenarioId: null })),
  setTmd: (p) => set((s) => ({ tmd: { ...s.tmd, ...p } })),
  applyScenario: (id) => {
    const sc = SCENARIOS.find((s) => s.id === id);
    if (sc) set({ sea: sc.sea, wind: sc.wind, scenarioId: id });
  },
  goCamera: (c) =>
    set((s) => ({
      camera: c,
      cameraNonce: s.cameraNonce + 1,
      // the damper close-up reads best with the nacelle open and no ghost overlapping it
      cutaway: c === 'nacelle' ? true : s.cutaway,
      ghost: c === 'nacelle' ? false : s.ghost,
    })),
}));
