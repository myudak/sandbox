import type { OutputKey } from './model';
import { damageEquivalentLoad } from './fatigue';

export interface RunningStats {
  n: number;
  mean: number;
  rms: number;
  /** Standard deviation about the mean. */
  std: number;
  min: number;
  max: number;
  /** max |y − mean| */
  peakDyn: number;
}

/**
 * Collects time-domain outputs: running moments for every output plus a
 * decimated ring buffer per output for charts and rainflow counting.
 */
export class Recorder {
  readonly keys: OutputKey[];
  readonly sampleDt: number;
  readonly capacity: number;
  private sums: Record<string, { n: number; s: number; s2: number; min: number; max: number }> = {};
  private buf: Record<string, Float64Array> = {};
  readonly time: Float64Array;
  private head = 0;
  private len = 0;
  private nextSample = 0;
  /** Unbounded history of the tower moment, decimated, used for DEL. */
  private delSeries: number[] = [];
  private t0 = 0;
  private tLast = 0;

  constructor(keys: OutputKey[], sampleDt = 0.25, capacity = 2400) {
    this.keys = keys;
    this.sampleDt = sampleDt;
    this.capacity = capacity;
    this.time = new Float64Array(capacity);
    for (const k of keys) {
      this.sums[k] = { n: 0, s: 0, s2: 0, min: Infinity, max: -Infinity };
      this.buf[k] = new Float64Array(capacity);
    }
  }

  push(t: number, y: Record<OutputKey, number>) {
    if (this.len === 0 && this.nextSample === 0) this.t0 = t;
    this.tLast = t;
    for (const k of this.keys) {
      const v = y[k];
      const a = this.sums[k];
      a.n++;
      a.s += v;
      a.s2 += v * v;
      if (v < a.min) a.min = v;
      if (v > a.max) a.max = v;
    }
    if (t + 1e-9 >= this.nextSample) {
      this.nextSample = t + this.sampleDt;
      this.time[this.head] = t;
      for (const k of this.keys) this.buf[k][this.head] = y[k];
      this.head = (this.head + 1) % this.capacity;
      this.len = Math.min(this.len + 1, this.capacity);
      if (this.keys.includes('towerMoment')) this.delSeries.push(y.towerMoment);
    }
  }

  stats(k: OutputKey): RunningStats {
    const a = this.sums[k];
    const mean = a.n ? a.s / a.n : 0;
    const ms = a.n ? a.s2 / a.n : 0;
    const std = Math.sqrt(Math.max(ms - mean * mean, 0));
    return {
      n: a.n,
      mean,
      rms: Math.sqrt(ms),
      std,
      min: a.min,
      max: a.max,
      peakDyn: a.n ? Math.max(a.max - mean, mean - a.min) : 0,
    };
  }

  duration() {
    return this.tLast - this.t0;
  }

  /** Chronological copy of the buffered series. */
  series(k: OutputKey | 'time'): Float64Array {
    const src = k === 'time' ? this.time : this.buf[k];
    const out = new Float64Array(this.len);
    const start = (this.head - this.len + this.capacity) % this.capacity;
    for (let i = 0; i < this.len; i++) out[i] = src[(start + i) % this.capacity];
    return out;
  }

  /** 1 Hz damage-equivalent tower-base moment (m = 4) over the whole run. */
  towerDel(m = 4): number {
    return damageEquivalentLoad(this.delSeries, this.duration(), m);
  }
}
