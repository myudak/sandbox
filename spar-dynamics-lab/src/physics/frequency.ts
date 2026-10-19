import { complexSolve } from './linalg';
import { LinearModel, ModelConfig, OutputKey, PITCH, SURGE, assembleModel, outputMean } from './model';
import { dragCoefficientPerLength, fluidVelocity, waveExcitation } from './hydro';
import { SeaState, frequencyGrid, jonswap, trapz, waveNumber } from './waves';
import { thrustSpectrum } from './wind';

export const OUTPUT_KEYS: OutputKey[] = ['surge', 'heave', 'pitch', 'damper', 'towerMoment', 'nacelleAccel'];

export interface Complex {
  re: number[];
  im: number[];
}

/** Steady-state response X(ω) = [K − ω²M + iωC]⁻¹ F. */
export function transfer(model: LinearModel, omega: number, F: Complex): Complex {
  const n = model.n;
  const ar = model.K.map((r, i) => r.map((k, j) => k - omega * omega * model.M[i][j]));
  const ai = model.C.map((r) => r.map((c) => omega * c));
  return complexSolve(ar, ai, F.re.slice(0, n), F.im.slice(0, n));
}

/** Generalised wave force per unit wave amplitude, padded to the model's DOF count. */
export function waveForce(model: LinearModel, omega: number, k = waveNumber(omega, model.config.params.waterDepth)): Complex {
  const f = waveExcitation(model.config.params, model.strips, model.bz, omega, k);
  const re = new Array<number>(model.n).fill(0);
  const im = new Array<number>(model.n).fill(0);
  re[SURGE] = f.re[0];
  re[1] = f.re[1];
  re[PITCH] = f.re[2];
  im[SURGE] = f.im[0];
  im[1] = f.im[1];
  im[PITCH] = f.im[2];
  return { re, im };
}

export function windForce(model: LinearModel): Complex {
  return { re: model.windDir.slice(), im: new Array<number>(model.n).fill(0) };
}

/** Complex output y(ω) for state response X and thrust-fluctuation input tIn (complex). */
export function outputResponse(
  model: LinearModel,
  key: OutputKey,
  omega: number,
  X: Complex,
  tIn: { re: number; im: number } = { re: 0, im: 0 },
): { re: number; im: number } {
  const o = model.outputs[key];
  let re = o.dT * tIn.re;
  let im = o.dT * tIn.im;
  const w2 = omega * omega;
  for (let i = 0; i < model.n; i++) {
    const gr = o.cx[i] - w2 * o.ca[i];
    const gi = omega * o.cv[i];
    re += gr * X.re[i] - gi * X.im[i];
    im += gr * X.im[i] + gi * X.re[i];
  }
  return { re, im };
}

export interface OutputStats {
  mean: number;
  sigma: number;
  sigmaWave: number;
  sigmaWind: number;
  /** Mean zero-upcrossing frequency [Hz]. */
  nu0: number;
  /** Expected dynamic maximum: 3-hour Rayleigh estimate (irregular) or amplitude (regular). */
  expectedMax: number;
}

export interface FrequencyAnalysis {
  model: LinearModel;
  omegas: number[];
  waveSpectrum: number[];
  thrustSpectrum: number[];
  /** |y| per metre of wave amplitude (RAO). */
  rao: Record<OutputKey, number[]>;
  /** Response power spectral density (wave + wind) [unit²·s/rad]. */
  psd: Record<OutputKey, number[]>;
  stats: Record<OutputKey, OutputStats>;
  /** Narrow-band 1 Hz damage-equivalent tower-base moment (m = 4) [N·m]. */
  towerDelNarrowBand: number;
}

export interface AnalysisOptions {
  omegas?: number[];
  dragIterations?: number;
}

const DEFAULT_GRID = frequencyGrid();

/** Cached wave kinematics on a frequency grid: wave numbers, strip velocities and drag-free excitation. */
interface HydroTable {
  k: Float64Array;
  /** u[q][i]: horizontal fluid velocity at strip i per unit amplitude. */
  u: Float64Array[];
  base: Complex[];
}

const tables = new WeakMap<number[], Map<object, HydroTable>>();

function hydroTable(model: LinearModel, omegas: number[]): HydroTable {
  const p = model.config.params;
  let byParams = tables.get(omegas);
  if (!byParams) tables.set(omegas, (byParams = new Map()));
  let tab = byParams.get(p);
  if (tab) return tab;
  const zeroDrag = new Float64Array(model.strips.length);
  const k = new Float64Array(omegas.length);
  const u: Float64Array[] = [];
  const base: Complex[] = [];
  for (let q = 0; q < omegas.length; q++) {
    const w = omegas[q];
    k[q] = waveNumber(w, p.waterDepth);
    u.push(Float64Array.from(model.strips, (s) => fluidVelocity(p, s, w, k[q])));
    const f = waveExcitation(p, model.strips, zeroDrag, w, k[q]);
    base.push({ re: f.re.slice(), im: f.im.slice() });
  }
  tab = { k, u, base };
  byParams.set(p, tab);
  return tab;
}

/** Wave force at grid point q using the cached table (adds the linearised-drag excitation). */
function waveForceQ(model: LinearModel, tab: HydroTable, q: number): Complex {
  let d1 = 0;
  let d5 = 0;
  const u = tab.u[q];
  for (let i = 0; i < model.strips.length; i++) {
    const s = model.strips[i];
    const f = model.bz[i] * u[i] * s.dz;
    d1 += f;
    d5 += f * s.z;
  }
  const b = tab.base[q];
  const re = new Array<number>(model.n).fill(0);
  const im = new Array<number>(model.n).fill(0);
  re[SURGE] = b.re[0] + d1;
  re[1] = b.re[1];
  re[PITCH] = b.re[2] + d5;
  im[SURGE] = b.im[0];
  im[1] = b.im[1];
  im[PITCH] = b.im[2];
  return { re, im };
}

function relVelocityStd(model: LinearModel, sea: SeaState, omegas: number[]): Float64Array {
  const p = model.config.params;
  const ns = model.strips.length;
  const wave = new Float64Array(ns);
  const wind = new Float64Array(ns);
  const regular = sea.kind === 'regular';
  const ws = regular ? [(2 * Math.PI) / sea.period] : omegas;
  const tab = regular ? null : hydroTable(model, omegas);
  const wf = windForce(model);
  for (let q = 0; q < ws.length; q++) {
    const w = ws[q];
    const k = tab ? tab.k[q] : waveNumber(w, p.waterDepth);
    const S = regular ? 0.5 * (sea.height / 2) ** 2 : jonswap(w, sea.height, sea.period, sea.gamma);
    const ST = thrustSpectrum(w, model.config.wind, p.rotorDiameter);
    const Xw = S > 1e-12 ? transfer(model, w, tab ? waveForceQ(model, tab, q) : waveForce(model, w, k)) : null;
    const Xt = !regular && ST > 0 ? transfer(model, w, wf) : null;
    for (let i = 0; i < ns; i++) {
      const s = model.strips[i];
      if (Xw) {
        // u_r = û − iω(X1 + z X5)
        const uf = tab ? tab.u[q][i] : fluidVelocity(p, s, w, k);
        const ur = uf + w * (Xw.im[SURGE] + s.z * Xw.im[PITCH]);
        const ui = -w * (Xw.re[SURGE] + s.z * Xw.re[PITCH]);
        const v = (ur * ur + ui * ui) * S;
        wave[i] += regular ? v : v * weight(ws, q);
      }
      if (Xt) {
        const ur = w * (Xt.im[SURGE] + s.z * Xt.im[PITCH]);
        const ui = -w * (Xt.re[SURGE] + s.z * Xt.re[PITCH]);
        wind[i] += (ur * ur + ui * ui) * ST * weight(ws, q);
      }
    }
  }
  const out = new Float64Array(ns);
  for (let i = 0; i < ns; i++) out[i] = Math.sqrt(wave[i] + wind[i]);
  return out;
}

/** Trapezoid weight of grid point q. */
function weight(x: number[], q: number): number {
  const a = q > 0 ? x[q] - x[q - 1] : 0;
  const b = q < x.length - 1 ? x[q + 1] - x[q] : 0;
  return 0.5 * (a + b);
}

/**
 * Equivalent linearisation of quadratic Morison drag ½ρC_d D |u_r| u_r:
 * Borgman (irregular): b = √(8/π) σ_r · ½ρC_dD; Lorentz (regular): b = 8/(3π) U_r · ½ρC_dD.
 * Iterated because the relative velocity depends on the response.
 */
export function linearizeDrag(config: ModelConfig, sea: SeaState, iterations = 6, omegas = coarseGrid()): LinearModel {
  let model = assembleModel(config);
  if (!model.stable) return model;
  const regularOnly = sea.kind === 'regular' && config.wind.turbulence === 'off';
  const factor = regularOnly ? 8 / (3 * Math.PI) : Math.sqrt(8 / Math.PI);
  let bz = new Float64Array(model.strips.length);
  for (let it = 0; it < iterations; it++) {
    const sr = relVelocityStd(model, sea, omegas);
    const next = new Float64Array(bz.length);
    for (let i = 0; i < bz.length; i++) {
      // σ_r → amplitude for the regular case
      const amp = regularOnly ? sr[i] * Math.SQRT2 : sr[i];
      const target = factor * amp * dragCoefficientPerLength(config.params, model.strips[i]);
      next[i] = it === 0 ? target : 0.5 * (bz[i] + target);
    }
    let change = 0;
    let norm = 0;
    for (let i = 0; i < bz.length; i++) {
      change = Math.max(change, Math.abs(next[i] - bz[i]));
      norm = Math.max(norm, Math.abs(next[i]));
    }
    bz = next;
    model = assembleModel(config, bz);
    if (it > 0 && change <= 0.01 * norm) break;
  }
  return model;
}

let coarse: number[] | null = null;
function coarseGrid() {
  return (coarse ??= frequencyGrid(0.02, 4, 260));
}

/** Full spectral analysis of a configuration in a sea state (with drag linearisation). */
export function analyze(config: ModelConfig, sea: SeaState, opts: AnalysisOptions = {}): FrequencyAnalysis {
  const model = linearizeDrag(config, sea, opts.dragIterations ?? 6);
  return analyzeModel(model, sea, opts.omegas ?? DEFAULT_GRID);
}

export function analyzeModel(model: LinearModel, sea: SeaState, omegas: number[] = DEFAULT_GRID): FrequencyAnalysis {
  const p = model.config.params;
  const regular = sea.kind === 'regular';
  const waveSpectrum = omegas.map((w) => (regular ? 0 : jonswap(w, sea.height, sea.period, sea.gamma)));
  const tSpec = omegas.map((w) => thrustSpectrum(w, model.config.wind, p.rotorDiameter));
  const rao = {} as Record<OutputKey, number[]>;
  const psd = {} as Record<OutputKey, number[]>;
  const windPsd = {} as Record<OutputKey, number[]>;
  const wavePsd = {} as Record<OutputKey, number[]>;
  for (const key of OUTPUT_KEYS) {
    rao[key] = [];
    psd[key] = [];
    windPsd[key] = [];
    wavePsd[key] = [];
  }
  const wf = windForce(model);
  const tab = hydroTable(model, omegas);
  for (let q = 0; q < omegas.length; q++) {
    const w = omegas[q];
    const Xw = model.stable ? transfer(model, w, waveForceQ(model, tab, q)) : null;
    const Xt = model.stable && tSpec[q] > 0 ? transfer(model, w, wf) : null;
    for (const key of OUTPUT_KEYS) {
      let a2 = 0;
      if (Xw) {
        const y = outputResponse(model, key, w, Xw);
        a2 = y.re * y.re + y.im * y.im;
      }
      let t2 = 0;
      if (Xt) {
        const y = outputResponse(model, key, w, Xt, { re: 1, im: 0 });
        t2 = y.re * y.re + y.im * y.im;
      }
      rao[key].push(Math.sqrt(a2));
      wavePsd[key].push(a2 * waveSpectrum[q]);
      windPsd[key].push(t2 * tSpec[q]);
      psd[key].push(a2 * waveSpectrum[q] + t2 * tSpec[q]);
    }
  }

  const stats = {} as Record<OutputKey, OutputStats>;
  let regularResp: Record<OutputKey, number> | null = null;
  if (regular && model.stable) {
    const w0 = (2 * Math.PI) / sea.period;
    const X = transfer(model, w0, waveForce(model, w0));
    regularResp = {} as Record<OutputKey, number>;
    for (const key of OUTPUT_KEYS) {
      const y = outputResponse(model, key, w0, X);
      regularResp[key] = Math.hypot(y.re, y.im) * (sea.height / 2);
    }
  }
  for (const key of OUTPUT_KEYS) {
    const m0w = trapz(omegas, windPsd[key]);
    const m0s = regularResp ? 0.5 * regularResp[key] ** 2 : trapz(omegas, wavePsd[key]);
    const m0 = m0w + m0s;
    let m2 = trapz(
      omegas,
      omegas.map((w, i) => w * w * windPsd[key][i]),
    );
    if (regularResp) m2 += ((2 * Math.PI) / sea.period) ** 2 * m0s;
    else
      m2 += trapz(
        omegas,
        omegas.map((w, i) => w * w * wavePsd[key][i]),
      );
    const sigma = Math.sqrt(m0);
    const nu0 = m0 > 0 ? Math.sqrt(m2 / m0) / (2 * Math.PI) : 0;
    const pureRegular = regularResp && m0w === 0;
    const nPeaks = Math.max(nu0 * 10800, 2);
    stats[key] = {
      mean: model.stable ? outputMean(model, key) : NaN,
      sigma,
      sigmaWave: Math.sqrt(m0s),
      sigmaWind: Math.sqrt(m0w),
      nu0,
      expectedMax: pureRegular ? regularResp![key] : sigma * Math.sqrt(2 * Math.log(nPeaks)),
    };
  }
  const tm = stats.towerMoment;
  const towerDelNarrowBand = 2 * Math.SQRT2 * tm.sigma * Math.pow(2, 0.25) * Math.pow(tm.nu0, 0.25);
  if (regular) for (const key of OUTPUT_KEYS) psd[key] = wavePsd[key].map((_, i) => windPsd[key][i]);
  return { model, omegas, waveSpectrum, thrustSpectrum: tSpec, rao, psd, stats, towerDelNarrowBand };
}

/** Peak of an RAO curve and the frequency it occurs at. */
export function raoPeak(omegas: number[], rao: number[], wMax = Infinity): { omega: number; value: number } {
  let best = 0;
  let idx = 0;
  for (let i = 0; i < omegas.length; i++)
    if (omegas[i] <= wMax && rao[i] > best) {
      best = rao[i];
      idx = i;
    }
  return { omega: omegas[idx], value: best };
}
