import { G, SparParams, structuralMasses } from './params';
import { Strip, addedMass, buildStrips, hydrostatics } from './hydro';
import { Mat, Vec, generalizedEigen, inverse, solve, symmetricEigen, zeros } from './linalg';
import { TmdDerived, TmdDesign, addTmdTerms, deriveTmd } from './tmd';
import { WindState, aeroDamping, meanThrust } from './wind';

/** Generalised coordinates: surge x1 [m], heave x3 [m], pitch θ [rad], damper β [rad]. */
export const SURGE = 0;
export const HEAVE = 1;
export const PITCH = 2;
export const DAMPER = 3;

export type OutputKey = 'surge' | 'heave' | 'pitch' | 'damper' | 'towerMoment' | 'nacelleAccel';

/**
 * A physical output written as a linear map of the state:
 *   y = cx·x + cv·ẋ + ca·ẍ + dT·T′ (+ mean)
 * where T′ is the turbulent thrust fluctuation. The same map serves the
 * frequency domain and the time domain, so both report identical quantities.
 */
export interface OutputMap {
  cx: Vec;
  cv: Vec;
  ca: Vec;
  dT: number;
}

export interface ModelConfig {
  params: SparParams;
  wind: WindState;
  tmd: TmdDesign | null;
  /**
   * Detuning study: scales the platform pitch restoring (e.g. ballast or
   * marine-growth changes) while the damper keeps its as-built tuning.
   */
  pitchStiffnessScale?: number;
  /** Pitch frequency the damper was tuned to; defaults to this platform's own. */
  tmdOmegaRef?: number;
}

export interface LinearModel {
  config: ModelConfig;
  strips: Strip[];
  n: number;
  M: Mat;
  Minv: Mat;
  /** Damping without the sea-state-dependent linearised drag. */
  Cstruct: Mat;
  C: Mat;
  K: Mat;
  /** Linearised drag per unit length of each strip [N·s/m²]. */
  bz: Float64Array;
  /** Generalised-force direction of a fore-aft force at the hub. */
  windDir: Vec;
  meanForce: Vec;
  meanState: Vec;
  thrust: number;
  aeroDamping: number;
  outputs: Record<OutputKey, OutputMap>;
  tmd: (TmdDerived & { design: TmdDesign }) | null;
  /** Statically stable (K positive definite). */
  stable: boolean;
  /** Baseline (no-TMD) pitch natural frequency used for TMD tuning [rad/s]. */
  omegaPitchRef: number;
}

/** Rigid-body + added mass and hydrostatic/gravity/mooring stiffness for the 3-DOF baseline. */
export function baselineMatrices(p: SparParams, strips = buildStrips(p)) {
  const masses = structuralMasses(p);
  let m = 0;
  let s = 0;
  let i55 = 0;
  for (const pm of masses) {
    m += pm.mass;
    s += pm.mass * pm.z;
    i55 += pm.inertia + pm.mass * pm.z * pm.z;
  }
  const Mrb: Mat = [
    [m, 0, s],
    [0, m, 0],
    [s, 0, i55],
  ];
  const A = addedMass(p, strips);
  const M = Mrb.map((r, i) => r.map((v, j) => v + A[i][j]));
  const hs = hydrostatics(p, strips);
  const mo = p.mooring;
  const K: Mat = [
    [mo.k11, 0, mo.k15],
    [0, hs.c33 + mo.k33, 0],
    [mo.k15, 0, hs.c55 - m * G * (s / m) + mo.k55],
  ];
  return { M, K, Mrb, A, hs, totalMass: m, zG: s / m };
}

export interface ModeInfo {
  omega: number;
  periodS: number;
  freqHz: number;
  shape: Vec;
}

/** Undamped natural modes of a mass/stiffness pair, labelled by dominant DOF. */
export function naturalModes(M: Mat, K: Mat, labels: string[]): Record<string, ModeInfo> {
  const { values, vectors } = generalizedEigen(K, M);
  const out: Record<string, ModeInfo> = {};
  const n = M.length;
  const used = new Set<string>();
  // assign each mode to its DOF of largest kinetic-energy share
  for (let mIdx = 0; mIdx < n; mIdx++) {
    const phi = vectors.map((r) => r[mIdx]);
    const share = phi.map((v, i) => v * v * M[i][i]);
    const order = share.map((v, i) => [v, i] as const).sort((a, b) => b[0] - a[0]);
    let label = labels[order[0][1]];
    for (const [, i] of order)
      if (!used.has(labels[i])) {
        label = labels[i];
        break;
      }
    used.add(label);
    const omega = Math.sqrt(Math.max(values[mIdx], 0));
    out[label] = { omega, periodS: (2 * Math.PI) / omega, freqHz: omega / (2 * Math.PI), shape: phi };
  }
  return out;
}

export function baselineModes(p: SparParams) {
  const { M, K } = baselineMatrices(p);
  return naturalModes(M, K, ['surge', 'heave', 'pitch']);
}

/**
 * Effective TMD mass ratio in the platform pitch mode:
 *   μ = γ² / (J_d M*),  with M* = φᵀMφ (φ normalised to unit nacelle motion)
 * and γ the coupling between the mode and the damper coordinate.
 */
export function effectiveMassRatio(p: SparParams, t: TmdDesign): number {
  const { M } = baselineMatrices(p);
  const modes = naturalModes(M, baselineMatrices(p).K, ['surge', 'heave', 'pitch']);
  const phi = modes.pitch.shape.slice();
  const nac = phi[SURGE] + p.hubHeight * phi[PITCH];
  for (let i = 0; i < 3; i++) phi[i] /= nac;
  let mStar = 0;
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) mStar += phi[i] * M[i][j] * phi[j];
  const jc = t.mass * t.gyration ** 2;
  const jd = jc + t.mass * t.arm ** 2;
  const gamma = t.mass * -t.arm * (phi[SURGE] + (t.pivotZ - t.arm) * phi[PITCH]) + jc * phi[PITCH];
  return (gamma * gamma) / (jd * mStar);
}

/** Assemble the linear model. `bz` (linearised drag per strip) defaults to zero. */
export function assembleModel(config: ModelConfig, bz?: Float64Array): LinearModel {
  const p = config.params;
  const strips = buildStrips(p);
  const base = baselineMatrices(p, strips);
  const ks = config.pitchStiffnessScale ?? 1;
  base.K[PITCH][PITCH] *= ks;
  const modes = naturalModes(base.M, base.K, ['surge', 'heave', 'pitch']);
  const omegaPitchRef = config.tmdOmegaRef ?? modes.pitch.omega;
  const withTmd = !!config.tmd && config.tmd.enabled;
  const n = withTmd ? 4 : 3;
  const M = zeros(n);
  const K = zeros(n);
  const Cs = zeros(n);
  for (let i = 0; i < 3; i++)
    for (let j = 0; j < 3; j++) {
      M[i][j] = base.M[i][j];
      K[i][j] = base.K[i][j];
    }
  // OC3 additional linear damping
  Cs[SURGE][SURGE] += p.extraDamping.b11;
  Cs[HEAVE][HEAVE] += p.extraDamping.b33;
  Cs[PITCH][PITCH] += p.extraDamping.b55;
  // aerodynamic damping on hub fore-aft velocity ẋ1 + h θ̇
  const h = p.hubHeight;
  const ba = aeroDamping(config.wind);
  const windDir = new Array<number>(n).fill(0);
  windDir[SURGE] = 1;
  windDir[PITCH] = h;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) Cs[i][j] += ba * windDir[i] * windDir[j];

  let tmd: LinearModel['tmd'] = null;
  if (withTmd && config.tmd) {
    const d = deriveTmd(config.tmd, omegaPitchRef);
    addTmdTerms(config.tmd, d, M, Cs, K);
    tmd = { ...d, design: config.tmd };
  }

  const drag = bz ?? new Float64Array(strips.length);
  const C = Cs.map((r) => r.slice());
  for (let i = 0; i < strips.length; i++) {
    const s = strips[i];
    const b = drag[i] * s.dz;
    C[SURGE][SURGE] += b;
    C[SURGE][PITCH] += b * s.z;
    C[PITCH][SURGE] += b * s.z;
    C[PITCH][PITCH] += b * s.z * s.z;
  }

  const thrust = meanThrust(config.wind);
  const meanForce = windDir.map((v) => v * thrust);
  const kEig = symmetricEigen(K).values;
  const stable = kEig.every((v) => v > 0);
  // Mean offset: the damper is assumed re-centred by a slow preload/actuator,
  // so the static solve locks β = 0 and only the platform DOFs carry the mean load.
  const meanState = new Array<number>(n).fill(0);
  if (stable) {
    const x = solve(
      K.slice(0, 3).map((r) => r.slice(0, 3)),
      meanForce.slice(0, 3),
    );
    for (let i = 0; i < 3; i++) meanState[i] = x[i];
  }

  return {
    config,
    strips,
    n,
    M,
    Minv: inverse(M),
    Cstruct: Cs,
    C,
    K,
    bz: drag,
    windDir,
    meanForce,
    meanState,
    thrust,
    aeroDamping: ba,
    outputs: buildOutputs(p, n, ba, tmd?.design ?? null, tmd),
    tmd,
    stable,
    omegaPitchRef,
  };
}

function unit(n: number, i: number): Vec {
  const v = new Array<number>(n).fill(0);
  v[i] = 1;
  return v;
}

/**
 * Tower-base (z = 10 m) fore-aft bending moment from the free body above it:
 *   M_b = T_total (h − z_tb) + Σ m_i g l_i θ − Σ m_i l_i a_i − Σ I_i θ̈  (+ damper terms)
 * with l_i = z_i − z_tb, a_i = ẍ1 + z_i θ̈ and T_total = T + T′ − b(ẋ1 + h θ̇).
 */
function buildOutputs(
  p: SparParams,
  n: number,
  ba: number,
  t: TmdDesign | null,
  d: TmdDerived | null,
): Record<OutputKey, OutputMap> {
  const z0 = p.towerBaseZ;
  const h = p.hubHeight;
  const cx = new Array<number>(n).fill(0);
  const cv = new Array<number>(n).fill(0);
  const ca = new Array<number>(n).fill(0);
  for (const pm of [p.tower, p.rotor, p.nacelle]) {
    const l = pm.z - z0;
    cx[PITCH] += pm.mass * G * l;
    ca[SURGE] -= pm.mass * l;
    ca[PITCH] -= pm.mass * l * pm.z + pm.inertia;
  }
  cv[SURGE] -= ba * (h - z0);
  cv[PITCH] -= ba * h * (h - z0);
  if (t && d && n === 4) {
    const zc = t.pivotZ - t.arm;
    const l = zc - z0;
    cx[PITCH] += t.mass * G * l;
    cx[DAMPER] += -t.mass * G * t.arm;
    ca[SURGE] -= t.mass * l;
    ca[PITCH] -= t.mass * l * zc + d.jc;
    ca[DAMPER] -= t.mass * l * -t.arm + d.jc;
  }
  const zero = () => new Array<number>(n).fill(0);
  const nac = zero();
  nac[SURGE] = 1;
  nac[PITCH] = h;
  return {
    surge: { cx: unit(n, SURGE), cv: zero(), ca: zero(), dT: 0 },
    heave: { cx: unit(n, HEAVE), cv: zero(), ca: zero(), dT: 0 },
    pitch: { cx: unit(n, PITCH), cv: zero(), ca: zero(), dT: 0 },
    damper: { cx: n === 4 ? unit(n, DAMPER) : zero(), cv: zero(), ca: zero(), dT: 0 },
    towerMoment: { cx, cv, ca, dT: h - z0 },
    nacelleAccel: { cx: zero(), cv: zero(), ca: nac, dT: 0 },
  };
}

/** Evaluate an output's mean value (static). */
export function outputMean(model: LinearModel, key: OutputKey): number {
  const o = model.outputs[key];
  let y = o.cx.reduce((s, v, i) => s + v * model.meanState[i], 0);
  if (key === 'towerMoment') y += model.thrust * o.dT;
  return y;
}
