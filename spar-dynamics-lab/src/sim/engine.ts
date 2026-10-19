import { OC3_HYWIND } from '../physics/params';
import { FrequencyAnalysis, OUTPUT_KEYS, analyze } from '../physics/frequency';
import { Simulator, thrustComponents } from '../physics/timeDomain';
import { Recorder } from '../physics/recorder';
import { SeaState, WaveComponent, waveComponents } from '../physics/waves';
import { WindState, rotorRpm } from '../physics/wind';
import type { TmdDesign } from '../physics/tmd';
import type { OutputKey } from '../physics/model';

export interface Run {
  analysis: FrequencyAnalysis;
  sim: Simulator;
  rec: Recorder;
  last: Record<OutputKey, number>;
}

const DT = 0.1;
const SAMPLE_EVERY = 2; // record every 0.2 s
const MAX_STEPS_PER_FRAME = 1500;

/**
 * Owns the two lock-stepped simulations (with / without TMD) driven by the
 * identical wave and wind realisation, plus their frequency-domain analyses.
 * Lives outside React; components subscribe to `version` for rebuilds and
 * read state imperatively every frame.
 */
class Engine {
  version = 0;
  base: Run | null = null;
  tmd: Run | null = null;
  waves: WaveComponent[] = [];
  sea: SeaState | null = null;
  wind: WindState | null = null;
  rotorAngle = 0;
  private steps = 0;
  private listeners = new Set<() => void>();
  buildMs = 0;

  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };

  getVersion = () => this.version;

  configure(sea: SeaState, wind: WindState, tmd: TmdDesign) {
    const t0 = performance.now();
    const params = OC3_HYWIND;
    this.sea = sea;
    this.wind = wind;
    this.waves = waveComponents(sea, params.waterDepth);
    const make = (design: TmdDesign | null): Run => {
      const analysis = analyze({ params, wind, tmd: design }, sea);
      const thrust = thrustComponents(analysis.model, sea.seed);
      const sim = new Simulator(analysis.model, this.waves, thrust);
      const rec = new Recorder(OUTPUT_KEYS, 0.2, 3000);
      const last = sim.outputs();
      rec.push(0, last);
      return { analysis, sim, rec, last };
    };
    this.base = make(null);
    this.tmd = make({ ...tmd, enabled: true });
    this.steps = 0;
    this.buildMs = performance.now() - t0;
    this.version++;
    this.listeners.forEach((l) => l());
  }

  get t() {
    return this.base?.sim.t ?? 0;
  }

  advance(realDt: number, timeScale: number) {
    if (!this.base || !this.tmd) return;
    const n = Math.min(Math.round((Math.min(realDt, 0.1) * timeScale) / DT), MAX_STEPS_PER_FRAME);
    for (let i = 0; i < n; i++) {
      for (const r of [this.base, this.tmd]) {
        r.sim.step(DT);
      }
      if (++this.steps % SAMPLE_EVERY === 0)
        for (const r of [this.base, this.tmd]) {
          r.last = r.sim.outputs();
          r.rec.push(r.sim.t, r.last);
        }
    }
    if (this.wind) this.rotorAngle += ((rotorRpm(this.wind) * 2 * Math.PI) / 60) * n * DT;
  }
}

export const engine = new Engine();
