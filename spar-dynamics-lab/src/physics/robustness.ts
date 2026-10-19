import { SparParams } from './params';
import { CaseMetrics, FAST_GRID, evaluateCase, metricsOf } from './optimize';
import { analyze } from './frequency';
import { baselineModes } from './model';
import { TmdDesign } from './tmd';
import { SeaState } from './waves';
import { WindState } from './wind';

export type RobustMetric = 'pitchSigmaDeg' | 'pitchMaxDeg' | 'towerDel';

export interface RobustnessMap {
  hs: number[];
  tp: number[];
  wind: WindState;
  /** [i_hs][j_tp] percentage change with TMD vs without (negative = TMD helps). */
  change: Record<RobustMetric, number[][]>;
  base: CaseMetrics[][];
  withTmd: CaseMetrics[][];
}

const pct = (a: number, b: number) => (b > 0 ? (100 * (a - b)) / b : 0);

/** Sweep Hs × Tp for one wind condition, comparing with/without TMD under identical inputs. */
export function robustnessMap(
  params: SparParams,
  tmd: TmdDesign,
  wind: WindState,
  hs: number[],
  tp: number[],
  gamma = 3.3,
  onProgress?: (p: number) => void,
): RobustnessMap {
  const keys: RobustMetric[] = ['pitchSigmaDeg', 'pitchMaxDeg', 'towerDel'];
  const change = Object.fromEntries(keys.map((k) => [k, hs.map(() => tp.map(() => 0))])) as RobustnessMap['change'];
  const base: CaseMetrics[][] = [];
  const withTmd: CaseMetrics[][] = [];
  let done = 0;
  hs.forEach((h, i) => {
    base.push([]);
    withTmd.push([]);
    tp.forEach((t, j) => {
      const sea: SeaState = { kind: 'irregular', height: h, period: t, gamma, seed: 1 };
      const b = evaluateCase(params, null, sea, wind);
      const w = evaluateCase(params, tmd, sea, wind);
      base[i].push(b);
      withTmd[i].push(w);
      for (const k of keys) change[k][i][j] = pct(w[k], b[k]);
      onProgress?.(++done / (hs.length * tp.length));
    });
  });
  return { hs, tp, wind, change, base, withTmd };
}

export interface DetuningPoint {
  /** Actual platform pitch frequency / as-designed pitch frequency. */
  freqFactor: number;
  stiffnessScale: number;
  baseSigmaDeg: number;
  tmdSigmaDeg: number;
  changePct: number;
}

/**
 * Detuning sensitivity: the platform's pitch frequency drifts (ballast,
 * marine growth, mooring change) while the damper keeps its as-built tuning.
 */
export function detuningCurve(
  params: SparParams,
  tmd: TmdDesign,
  sea: SeaState,
  wind: WindState,
  freqFactors: number[],
  onProgress?: (p: number) => void,
): DetuningPoint[] {
  const omegaDesign = baselineModes(params).pitch.omega;
  return freqFactors.map((f, i) => {
    // pitch-dominated mode: ω ∝ √K55 to first order
    const stiffnessScale = f * f;
    const opts = { omegas: FAST_GRID, dragIterations: 4 };
    const common = { params, wind, pitchStiffnessScale: stiffnessScale, tmdOmegaRef: omegaDesign };
    const b = metricsOf(analyze({ ...common, tmd: null }, sea, opts));
    const w = metricsOf(analyze({ ...common, tmd }, sea, opts));
    onProgress?.((i + 1) / freqFactors.length);
    return {
      freqFactor: f,
      stiffnessScale,
      baseSigmaDeg: b.pitchSigmaDeg,
      tmdSigmaDeg: w.pitchSigmaDeg,
      changePct: pct(w.pitchSigmaDeg, b.pitchSigmaDeg),
    };
  });
}
