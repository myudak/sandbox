import { SparParams } from './params';
import { FrequencyAnalysis, analyze, raoPeak } from './frequency';
import { baselineMatrices, effectiveMassRatio } from './model';
import { TmdDesign, denHartog } from './tmd';
import { SeaState, frequencyGrid } from './waves';
import { WindState } from './wind';

export type Objective = 'pitchRms' | 'pitchRaoPeak' | 'towerDel' | 'robust';

export const OBJECTIVE_LABELS: Record<Objective, string> = {
  pitchRms: 'RMS pitch (current sea state)',
  pitchRaoPeak: 'Peak pitch RAO (H∞)',
  towerDel: 'Tower-base DEL (current sea state)',
  robust: 'Weighted RMS pitch over a scatter of conditions',
};

export interface LoadCase {
  name: string;
  sea: SeaState;
  wind: WindState;
  weight: number;
}

/** A small, illustrative scatter of operating and parked conditions for robust design. */
export const DEFAULT_SCATTER: LoadCase[] = [
  { name: 'Operating, moderate sea', sea: irr(2.5, 8), wind: { speed: 8, turbulence: 'B' }, weight: 0.3 },
  { name: 'Rated wind, rough sea', sea: irr(4, 10), wind: { speed: 11.4, turbulence: 'B' }, weight: 0.25 },
  { name: 'Above rated, rough sea', sea: irr(5, 11), wind: { speed: 18, turbulence: 'B' }, weight: 0.15 },
  { name: 'Parked storm', sea: irr(9, 14), wind: { speed: 0, turbulence: 'off' }, weight: 0.1 },
  { name: 'Parked long swell', sea: irr(3, 22), wind: { speed: 0, turbulence: 'off' }, weight: 0.1 },
  { name: 'Idling, long swell', sea: irr(2, 18), wind: { speed: 2, turbulence: 'off' }, weight: 0.1 },
];

function irr(hs: number, tp: number): SeaState {
  return { kind: 'irregular', height: hs, period: tp, gamma: 3.3, seed: 1 };
}

export interface Constraints {
  /** Max damper mass as a fraction of the baseline system mass. */
  maxMassRatio: number;
  /** Max expected (3 h) damper rotation [deg]; keeps the linear model and end-stops honest. */
  maxStrokeDeg: number;
}

export const DEFAULT_CONSTRAINTS: Constraints = { maxMassRatio: 0.02, maxStrokeDeg: 45 };

/** Rough cost model (order of magnitude only). */
export interface CostModel {
  /** € per tonne of installed damper mass (steel + fabrication). */
  perTonne: number;
  /** € fixed: spring/damper hardware, integration, installation. */
  fixed: number;
  /** € per tonne of extra platform steel needed to carry the top mass (structural knock-on). */
  structuralPerTonne: number;
}

export const DEFAULT_COST: CostModel = { perTonne: 6000, fixed: 400_000, structuralPerTonne: 2500 };

export function damperCost(t: TmdDesign, c: CostModel = DEFAULT_COST): number {
  const tonnes = t.mass / 1000;
  return c.fixed + tonnes * (c.perTonne + c.structuralPerTonne);
}

export interface CaseMetrics {
  pitchSigmaDeg: number;
  pitchMaxDeg: number;
  pitchRaoPeak: number;
  towerDel: number;
  strokeDeg: number;
  feasible: boolean;
  stable: boolean;
}

const DEG = 180 / Math.PI;
export const FAST_GRID = frequencyGrid(0.02, 4, 260);

export function metricsOf(a: FrequencyAnalysis): CaseMetrics {
  const s = a.stats;
  return {
    pitchSigmaDeg: s.pitch.sigma * DEG,
    pitchMaxDeg: (Math.abs(s.pitch.mean) + s.pitch.expectedMax) * DEG,
    pitchRaoPeak: raoPeak(a.omegas, a.rao.pitch, 1.0).value * DEG,
    towerDel: a.towerDelNarrowBand,
    strokeDeg: s.damper.expectedMax * DEG,
    feasible: a.model.tmd ? a.model.tmd.feasible : true,
    stable: a.model.stable,
  };
}

export function evaluateCase(params: SparParams, tmd: TmdDesign | null, sea: SeaState, wind: WindState): CaseMetrics {
  return metricsOf(analyze({ params, wind, tmd }, sea, { omegas: FAST_GRID, dragIterations: 4 }));
}

export interface StudyContext {
  params: SparParams;
  sea: SeaState;
  wind: WindState;
  objective: Objective;
  constraints: Constraints;
  scatter?: LoadCase[];
}

export interface Evaluation {
  /** Objective with TMD divided by the same objective without TMD (< 1 is better). */
  ratio: number;
  /** Ratio plus constraint penalties (what the optimiser minimises). */
  penalised: number;
  strokeDeg: number;
  feasible: boolean;
  violations: string[];
}

function scalar(m: CaseMetrics, objective: Objective): number {
  switch (objective) {
    case 'pitchRaoPeak':
      return m.pitchRaoPeak;
    case 'towerDel':
      return m.towerDel;
    default:
      return m.pitchSigmaDeg;
  }
}

/** Baseline values are reused across evaluations of the same context. */
export function makeEvaluator(ctx: StudyContext) {
  const cases: LoadCase[] =
    ctx.objective === 'robust' ? ctx.scatter ?? DEFAULT_SCATTER : [{ name: 'current', sea: ctx.sea, wind: ctx.wind, weight: 1 }];
  const base = cases.map((c) => scalar(evaluateCase(ctx.params, null, c.sea, c.wind), ctx.objective));
  const totalMass = baselineMatrices(ctx.params).totalMass;
  let count = 0;
  const evaluate = (t: TmdDesign): Evaluation => {
    count++;
    let ratio = 0;
    let wsum = 0;
    let stroke = 0;
    let feasible = true;
    let stable = true;
    cases.forEach((c, i) => {
      const m = evaluateCase(ctx.params, t, c.sea, c.wind);
      ratio += c.weight * (scalar(m, ctx.objective) / Math.max(base[i], 1e-12));
      wsum += c.weight;
      stroke = Math.max(stroke, m.strokeDeg);
      feasible &&= m.feasible;
      stable &&= m.stable;
    });
    ratio /= wsum;
    const violations: string[] = [];
    let pen = 0;
    if (!stable) {
      violations.push('statically unstable');
      pen += 100;
    }
    if (!feasible) {
      violations.push('needs a negative-stiffness spring');
      pen += 1;
    }
    if (stroke > ctx.constraints.maxStrokeDeg) {
      violations.push(`stroke ${stroke.toFixed(0)}° > ${ctx.constraints.maxStrokeDeg}°`);
      pen += 4 * (stroke / ctx.constraints.maxStrokeDeg - 1) ** 2 + 0.05;
    }
    if (t.mass > ctx.constraints.maxMassRatio * totalMass + 1e-6) {
      violations.push('mass above limit');
      pen += 1;
    }
    return { ratio, penalised: ratio + pen, strokeDeg: stroke, feasible: violations.length === 0, violations };
  };
  return { evaluate, evaluations: () => count, totalMass };
}

/** Bounded Nelder–Mead in 2-D. */
export function nelderMead(
  f: (x: number[]) => number,
  x0: number[],
  step: number[],
  lo: number[],
  hi: number[],
  maxIter = 60,
): { x: number[]; fx: number } {
  const clamp = (x: number[]) => x.map((v, i) => Math.min(hi[i], Math.max(lo[i], v)));
  const n = x0.length;
  let simplex = [clamp(x0)];
  for (let i = 0; i < n; i++) {
    const x = x0.slice();
    x[i] += step[i];
    simplex.push(clamp(x));
  }
  let fs = simplex.map(f);
  for (let it = 0; it < maxIter; it++) {
    const order = fs.map((v, i) => [v, i] as const).sort((a, b) => a[0] - b[0]);
    simplex = order.map(([, i]) => simplex[i]);
    fs = order.map(([v]) => v);
    if (Math.abs(fs[n] - fs[0]) < 1e-5 * (Math.abs(fs[0]) + 1e-9)) break;
    const c = Array.from({ length: n }, (_, j) => simplex.slice(0, n).reduce((s, x) => s + x[j], 0) / n);
    const along = (t: number) => clamp(c.map((v, j) => v + t * (simplex[n][j] - v)));
    const xr = along(-1);
    const fr = f(xr);
    if (fr < fs[0]) {
      const xe = along(-2);
      const fe = f(xe);
      if (fe < fr) {
        simplex[n] = xe;
        fs[n] = fe;
      } else {
        simplex[n] = xr;
        fs[n] = fr;
      }
    } else if (fr < fs[n - 1]) {
      simplex[n] = xr;
      fs[n] = fr;
    } else {
      const xc = along(fr < fs[n] ? -0.5 : 0.5);
      const fc = f(xc);
      if (fc < Math.min(fr, fs[n])) {
        simplex[n] = xc;
        fs[n] = fc;
      } else {
        for (let i = 1; i <= n; i++) {
          simplex[i] = clamp(simplex[i].map((v, j) => simplex[0][j] + 0.5 * (v - simplex[0][j])));
          fs[i] = f(simplex[i]);
        }
      }
    }
  }
  const best = fs.indexOf(Math.min(...fs));
  return { x: simplex[best], fx: fs[best] };
}

export interface TuningResult {
  design: TmdDesign;
  evaluation: Evaluation;
  start: TmdDesign;
  muEff: number;
  evaluations: number;
  cost: number;
}

/**
 * Tune frequency ratio and damping ratio for a fixed damper geometry: Den
 * Hartog start → coarse grid → Nelder–Mead, all on the penalised objective.
 */
export function optimizeTuning(ctx: StudyContext, geometry: TmdDesign, onProgress?: (p: number) => void): TuningResult {
  const ev = makeEvaluator(ctx);
  const muEff = effectiveMassRatio(ctx.params, geometry);
  const dh = denHartog(muEff);
  const start = { ...geometry, enabled: true, freqRatio: dh.freqRatio, dampingRatio: dh.dampingRatio };
  const at = (x: number[]) => ({ ...geometry, enabled: true, freqRatio: x[0], dampingRatio: x[1] });
  let best = { x: [start.freqRatio, start.dampingRatio], fx: ev.evaluate(start).penalised };
  const fs = [0.6, 0.8, 0.95, 1.1, 1.3];
  const zs = [0.05, 0.15, 0.3, 0.5];
  let k = 0;
  for (const f of fs)
    for (const z of zs) {
      const v = ev.evaluate(at([f, z])).penalised;
      if (v < best.fx) best = { x: [f, z], fx: v };
      onProgress?.((0.5 * ++k) / (fs.length * zs.length));
    }
  let iter = 0;
  const nm = nelderMead(
    (x) => {
      onProgress?.(Math.min(0.99, 0.5 + 0.5 * (++iter / 80)));
      return ev.evaluate(at(x)).penalised;
    },
    best.x,
    [0.05, 0.05],
    [0.3, 0.005],
    [2.0, 1.0],
    40,
  );
  const design = at(nm.fx < best.fx ? nm.x : best.x);
  onProgress?.(1);
  return { design, evaluation: ev.evaluate(design), start, muEff, evaluations: ev.evaluations(), cost: damperCost(design) };
}

export interface ParetoPoint {
  massRatio: number;
  mass: number;
  design: TmdDesign;
  ratio: number;
  reductionPct: number;
  strokeDeg: number;
  cost: number;
  feasible: boolean;
}

/** Optimal tuning at a range of damper masses: the mass/benefit/cost trade-off. */
export function paretoFront(
  ctx: StudyContext,
  geometry: TmdDesign,
  massRatios: number[],
  onProgress?: (p: number) => void,
): ParetoPoint[] {
  const totalMass = baselineMatrices(ctx.params).totalMass;
  const out: ParetoPoint[] = [];
  massRatios.forEach((mr, i) => {
    const g = { ...geometry, mass: mr * totalMass };
    const r = optimizeTuning({ ...ctx, constraints: { ...ctx.constraints, maxMassRatio: 1 } }, g, (p) =>
      onProgress?.((i + p) / massRatios.length),
    );
    out.push({
      massRatio: mr,
      mass: g.mass,
      design: r.design,
      ratio: r.evaluation.ratio,
      reductionPct: (1 - r.evaluation.ratio) * 100,
      strokeDeg: r.evaluation.strokeDeg,
      cost: r.cost,
      feasible: r.evaluation.feasible,
    });
  });
  return out;
}
