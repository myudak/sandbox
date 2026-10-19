import { LinearModel, OutputKey, outputMean } from './model';
import { transfer, waveForce, windForce } from './frequency';
import { WaveComponent, mulberry32 } from './waves';
import { thrustSpectrum } from './wind';
import type { Vec } from './linalg';

/** A sinusoidal thrust-fluctuation component T′ = amp·cos(ωt + phase) [N]. */
export interface ThrustComponent {
  omega: number;
  amp: number;
  phase: number;
}

/** Random-phase realisation of the turbulent thrust spectrum. */
export function thrustComponents(model: LinearModel, seed: number, n = 160): ThrustComponent[] {
  const wind = model.config.wind;
  const d = model.config.params.rotorDiameter;
  const lo = 0.01;
  const hi = 2.5;
  const r = Math.log(hi / lo);
  const rnd = mulberry32(seed ^ 0x9e3779b9);
  const out: ThrustComponent[] = [];
  for (let i = 0; i < n; i++) {
    const w0 = lo * Math.exp((r * i) / n);
    const w1 = lo * Math.exp((r * (i + 1)) / n);
    const omega = w0 + (0.2 + 0.6 * rnd()) * (w1 - w0);
    const s = thrustSpectrum(omega, wind, d);
    if (s <= 0) continue;
    out.push({ omega, amp: Math.sqrt(2 * s * (w1 - w0)), phase: 2 * Math.PI * rnd() });
  }
  return out;
}

interface Harmonic {
  omega: number;
  /** complex generalised-force amplitude (n) including wave amplitude & phase */
  fr: Float64Array;
  fi: Float64Array;
  /** thrust amplitude (complex), only for wind components */
  tr: number;
  ti: number;
  /** current phasor e^{iωt} */
  cr: number;
  ci: number;
  /** half-step rotor e^{iω dt/2} */
  hr: number;
  hi: number;
}

/**
 * Linear time-domain simulator, RK4 on M ẍ + C ẋ + K x = F′(t) for the
 * dynamic part x′ about the mean offset. The initial state is the exact
 * steady-state response of the linear system, so there is no start-up
 * transient and statistics are valid from t = 0.
 */
export class Simulator {
  readonly model: LinearModel;
  t = 0;
  x: Float64Array;
  v: Float64Array;
  private harmonics: Harmonic[] = [];
  private dt = -1;
  private stepCount = 0;
  private tmpF: Float64Array;
  private tmpR: Float64Array;
  private k1x: Float64Array;
  private k1v: Float64Array;
  private k2x: Float64Array;
  private k2v: Float64Array;
  private k3x: Float64Array;
  private k3v: Float64Array;
  private k4x: Float64Array;
  private k4v: Float64Array;
  private xs: Float64Array;
  private vs: Float64Array;
  private meanOut: Record<OutputKey, number>;

  constructor(model: LinearModel, waves: WaveComponent[], thrust: ThrustComponent[]) {
    this.model = model;
    const n = model.n;
    this.x = new Float64Array(n);
    this.v = new Float64Array(n);
    this.tmpF = new Float64Array(n);
    this.tmpR = new Float64Array(n);
    this.k1x = new Float64Array(n);
    this.k1v = new Float64Array(n);
    this.k2x = new Float64Array(n);
    this.k2v = new Float64Array(n);
    this.k3x = new Float64Array(n);
    this.k3v = new Float64Array(n);
    this.k4x = new Float64Array(n);
    this.k4v = new Float64Array(n);
    this.xs = new Float64Array(n);
    this.vs = new Float64Array(n);
    this.meanOut = {} as Record<OutputKey, number>;
    for (const key of Object.keys(model.outputs) as OutputKey[]) this.meanOut[key] = outputMean(model, key);
    if (!model.stable) return;

    const wf = windForce(model);
    const add = (omega: number, F: { re: number[]; im: number[] }, ar: number, ai: number, isWind: boolean) => {
      const fr = new Float64Array(n);
      const fi = new Float64Array(n);
      for (let i = 0; i < n; i++) {
        fr[i] = F.re[i] * ar - F.im[i] * ai;
        fi[i] = F.re[i] * ai + F.im[i] * ar;
      }
      this.harmonics.push({ omega, fr, fi, tr: isWind ? ar : 0, ti: isWind ? ai : 0, cr: 1, ci: 0, hr: 1, hi: 0 });
      // steady-state initial condition
      const X = transfer(model, omega, { re: Array.from(fr), im: Array.from(fi) });
      for (let i = 0; i < n; i++) {
        this.x[i] += X.re[i];
        this.v[i] += -omega * X.im[i];
      }
    };
    for (const c of waves) {
      if (c.amp === 0) continue;
      add(c.omega, waveForce(model, c.omega, c.k), c.amp * Math.cos(c.phase), c.amp * Math.sin(c.phase), false);
    }
    for (const c of thrust) add(c.omega, wf, c.amp * Math.cos(c.phase), c.amp * Math.sin(c.phase), true);
  }

  get stable() {
    return this.model.stable;
  }

  private setDt(dt: number) {
    this.dt = dt;
    for (const h of this.harmonics) {
      h.hr = Math.cos(0.5 * h.omega * dt);
      h.hi = Math.sin(0.5 * h.omega * dt);
    }
  }

  private resync() {
    for (const h of this.harmonics) {
      h.cr = Math.cos(h.omega * this.t);
      h.ci = Math.sin(h.omega * this.t);
    }
  }

  /** Fluctuating generalised force at the current phasors (+ `half` half-steps ahead). */
  private force(out: Float64Array, half: 0 | 1 | 2): number {
    out.fill(0);
    let tq = 0;
    const n = this.model.n;
    for (const h of this.harmonics) {
      let cr = h.cr;
      let ci = h.ci;
      for (let s = 0; s < half; s++) {
        const r = cr * h.hr - ci * h.hi;
        ci = cr * h.hi + ci * h.hr;
        cr = r;
      }
      for (let i = 0; i < n; i++) out[i] += h.fr[i] * cr - h.fi[i] * ci;
      tq += h.tr * cr - h.ti * ci;
    }
    return tq;
  }

  private deriv(x: Float64Array, v: Float64Array, F: Float64Array, dx: Float64Array, dv: Float64Array) {
    const { Minv, C, K, n } = this.model;
    const r = this.tmpR;
    for (let i = 0; i < n; i++) {
      let s = F[i];
      for (let j = 0; j < n; j++) s -= C[i][j] * v[j] + K[i][j] * x[j];
      r[i] = s;
    }
    for (let i = 0; i < n; i++) {
      dx[i] = v[i];
      let a = 0;
      for (let j = 0; j < n; j++) a += Minv[i][j] * r[j];
      dv[i] = a;
    }
  }

  step(dt: number) {
    if (!this.model.stable) {
      this.t += dt;
      return;
    }
    if (dt !== this.dt) this.setDt(dt);
    const n = this.model.n;
    const F = this.tmpF;
    const { x, v, xs, vs } = this;
    this.force(F, 0);
    this.deriv(x, v, F, this.k1x, this.k1v);
    this.force(F, 1);
    for (let i = 0; i < n; i++) {
      xs[i] = x[i] + 0.5 * dt * this.k1x[i];
      vs[i] = v[i] + 0.5 * dt * this.k1v[i];
    }
    this.deriv(xs, vs, F, this.k2x, this.k2v);
    for (let i = 0; i < n; i++) {
      xs[i] = x[i] + 0.5 * dt * this.k2x[i];
      vs[i] = v[i] + 0.5 * dt * this.k2v[i];
    }
    this.deriv(xs, vs, F, this.k3x, this.k3v);
    this.force(F, 2);
    for (let i = 0; i < n; i++) {
      xs[i] = x[i] + dt * this.k3x[i];
      vs[i] = v[i] + dt * this.k3v[i];
    }
    this.deriv(xs, vs, F, this.k4x, this.k4v);
    for (let i = 0; i < n; i++) {
      x[i] += (dt / 6) * (this.k1x[i] + 2 * this.k2x[i] + 2 * this.k3x[i] + this.k4x[i]);
      v[i] += (dt / 6) * (this.k1v[i] + 2 * this.k2v[i] + 2 * this.k3v[i] + this.k4v[i]);
    }
    // advance phasors one full step
    for (const h of this.harmonics) {
      const r1 = h.hr * h.hr - h.hi * h.hi;
      const i1 = 2 * h.hr * h.hi;
      const r = h.cr * r1 - h.ci * i1;
      h.ci = h.cr * i1 + h.ci * r1;
      h.cr = r;
    }
    this.t += dt;
    if (++this.stepCount % 256 === 0) this.resync();
  }

  /** Total (mean + dynamic) generalised displacement. */
  position(): Vec {
    return Array.from(this.x, (v, i) => v + this.model.meanState[i]);
  }

  /** Evaluate all outputs at the current state. */
  outputs(): Record<OutputKey, number> {
    const n = this.model.n;
    const F = this.tmpF;
    const tq = this.model.stable ? this.force(F, 0) : 0;
    const a = new Float64Array(n);
    if (this.model.stable) this.deriv(this.x, this.v, F, new Float64Array(n), a);
    const res = {} as Record<OutputKey, number>;
    for (const key of Object.keys(this.model.outputs) as OutputKey[]) {
      const o = this.model.outputs[key];
      let y = this.meanOut[key] + o.dT * tq;
      for (let i = 0; i < n; i++) y += o.cx[i] * this.x[i] + o.cv[i] * this.v[i] + o.ca[i] * a[i];
      res[key] = y;
    }
    return res;
  }

  /** Mechanical energy of the dynamic part (for conservation tests). */
  energy(): number {
    const { M, K, n } = this.model;
    let e = 0;
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) e += 0.5 * (M[i][j] * this.v[i] * this.v[j] + K[i][j] * this.x[i] * this.x[j]);
    return e;
  }
}
