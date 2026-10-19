import { describe, expect, it } from 'vitest';
import { OC3_HYWIND, OC3_REFERENCE, SparParams } from '../params';
import { LinearModel, PITCH, assembleModel, baselineMatrices, baselineModes, effectiveMassRatio } from '../model';
import { analyze, raoPeak, transfer } from '../frequency';
import { Simulator } from '../timeDomain';
import { waveComponents } from '../waves';
import { DEFAULT_TMD, TmdDesign, denHartog } from '../tmd';
import { damageEquivalentLoad, rainflow } from '../fatigue';
import { Recorder } from '../recorder';
import { frequencyGrid } from '../waves';

const parked = { speed: 0, turbulence: 'off' as const };
const rel = (a: number, b: number) => Math.abs(a - b) / Math.abs(b);

describe('V1 — natural periods vs OC3 (rigid tower)', () => {
  const modes = baselineModes(OC3_HYWIND);
  it('surge ≈ 0.008 Hz', () => expect(rel(modes.surge.freqHz, OC3_REFERENCE.naturalFrequencyHz.surge)).toBeLessThan(0.05));
  it('heave ≈ 0.0324 Hz', () => expect(rel(modes.heave.freqHz, OC3_REFERENCE.naturalFrequencyHz.heave)).toBeLessThan(0.05));
  it('pitch ≈ 0.034 Hz (rigid tower allowed ±8%)', () =>
    expect(rel(modes.pitch.freqHz, OC3_REFERENCE.naturalFrequencyHz.pitch)).toBeLessThan(0.08));
  it('hydrostatics and system CM match the definition', () => {
    const b = baselineMatrices(OC3_HYWIND);
    expect(rel(b.hs.c55, OC3_REFERENCE.hydrostaticPitch)).toBeLessThan(0.01);
    expect(Math.abs(b.zG - OC3_REFERENCE.systemCmZ)).toBeLessThan(0.5);
  });
});

function undamped(): SparParams {
  return { ...OC3_HYWIND, extraDamping: { b11: 0, b33: 0, b55: 0 } };
}

describe('V2 — free decay', () => {
  it('conserves energy without damping and oscillates at the eigenperiod', () => {
    const model = assembleModel({ params: undamped(), wind: parked, tmd: null });
    const sim = new Simulator(model, [], []);
    sim.x[PITCH] = (2 * Math.PI) / 180;
    const e0 = sim.energy();
    const dt = 0.05;
    let lastSign = Math.sign(sim.x[PITCH]);
    const crossings: number[] = [];
    for (let i = 0; i < 6000; i++) {
      sim.step(dt);
      const s = Math.sign(sim.x[PITCH]);
      if (s !== lastSign) crossings.push(sim.t);
      lastSign = s;
    }
    expect(rel(sim.energy(), e0)).toBeLessThan(1e-4);
    // pitch-dominated zero crossings are half-periods (surge coupling is weak)
    const halfPeriods = crossings.slice(1).map((t, i) => t - crossings[i]);
    const mean = halfPeriods.reduce((a, b) => a + b, 0) / halfPeriods.length;
    const period = baselineModes(undamped()).pitch.periodS;
    expect(rel(2 * mean, period)).toBeLessThan(0.03);
  });
});

describe('V3 — time domain agrees with frequency domain', () => {
  it('regular wave amplitude matches the RAO', () => {
    const sea = { kind: 'regular' as const, height: 2, period: 14, gamma: 3.3, seed: 1 };
    for (const tmd of [null, DEFAULT_TMD]) {
      const a = analyze({ params: OC3_HYWIND, wind: parked, tmd }, sea);
      const sim = new Simulator(a.model, waveComponents(sea, OC3_HYWIND.waterDepth), []);
      let mx = -Infinity;
      let mn = Infinity;
      for (let i = 0; i < 4000; i++) {
        sim.step(0.05);
        const p = sim.outputs().pitch;
        mx = Math.max(mx, p);
        mn = Math.min(mn, p);
      }
      expect(rel((mx - mn) / 2, a.stats.pitch.expectedMax)).toBeLessThan(0.01);
    }
  });

  it('irregular sea + turbulent wind std matches the spectral σ', () => {
    const sea = { kind: 'irregular' as const, height: 4, period: 11, gamma: 3.3, seed: 3 };
    const wind = { speed: 10, turbulence: 'B' as const };
    const a = analyze({ params: OC3_HYWIND, wind, tmd: DEFAULT_TMD }, sea);
    // compare against the realisation itself over a long run
    const sim = new Simulator(a.model, waveComponents(sea, OC3_HYWIND.waterDepth, 300), []);
    const rec = new Recorder(['pitch', 'towerMoment'], 0.5, 100);
    for (let i = 0; i < 36000 / 2; i++) {
      sim.step(0.2);
      rec.push(sim.t, sim.outputs());
    }
    expect(rel(rec.stats('pitch').std, a.stats.pitch.sigmaWave)).toBeLessThan(0.1);
    expect(rel(rec.stats('pitch').mean, a.stats.pitch.mean)).toBeLessThan(0.01);
  });
});

/** Minimal 2-DOF primary + translational TMD as a LinearModel for transfer(). */
function sdofWithTmd(mu: number, f: number, zeta: number): LinearModel {
  const md = mu;
  const wd = f;
  const kd = md * wd * wd;
  const cd = 2 * zeta * md * wd;
  return {
    n: 2,
    M: [
      [1, 0],
      [0, md],
    ],
    C: [
      [cd, -cd],
      [-cd, cd],
    ],
    K: [
      [1 + kd, -kd],
      [-kd, kd],
    ],
  } as unknown as LinearModel;
}

describe('V4 — Den Hartog equal-peak optimum', () => {
  const mu = 0.05;
  const grid = frequencyGrid(0.5, 1.6, 3000);
  const peak = (m: LinearModel) =>
    Math.max(...grid.map((w) => Math.hypot(...((x) => [x.re[0], x.im[0]])(transfer(m, w, { re: [1, 0], im: [0, 0] })))));
  it('reproduces the analytical peak √(1 + 2/μ)', () => {
    const dh = denHartog(mu);
    expect(rel(peak(sdofWithTmd(mu, dh.freqRatio, dh.dampingRatio)), Math.sqrt(1 + 2 / mu))).toBeLessThan(0.03);
  });
  it('is near-optimal against a brute-force search', () => {
    const dh = denHartog(mu);
    let best = Infinity;
    for (let f = 0.9; f <= 1.0; f += 0.005)
      for (let z = 0.05; z <= 0.25; z += 0.01) best = Math.min(best, peak(sdofWithTmd(mu, f, z)));
    expect(peak(sdofWithTmd(mu, dh.freqRatio, dh.dampingRatio)) / best).toBeLessThan(1.02);
  });
  it('a Den Hartog-tuned rotary TMD lowers the parked pitch RAO peak', () => {
    const muEff = effectiveMassRatio(OC3_HYWIND, DEFAULT_TMD);
    const dh = denHartog(muEff);
    const tmd: TmdDesign = { ...DEFAULT_TMD, freqRatio: dh.freqRatio, dampingRatio: dh.dampingRatio };
    const sea = { kind: 'irregular' as const, height: 2, period: 25, gamma: 3.3, seed: 1 };
    const base = analyze({ params: OC3_HYWIND, wind: parked, tmd: null }, sea);
    const withTmd = analyze({ params: OC3_HYWIND, wind: parked, tmd }, sea);
    const p0 = raoPeak(base.omegas, base.rao.pitch, 0.5).value;
    const p1 = raoPeak(withTmd.omegas, withTmd.rao.pitch, 0.5).value;
    expect(p1).toBeLessThan(0.6 * p0);
  });
  it('a vanishing TMD recovers the baseline', () => {
    const sea = { kind: 'irregular' as const, height: 4, period: 12, gamma: 3.3, seed: 1 };
    const base = analyze({ params: OC3_HYWIND, wind: parked, tmd: null }, sea);
    const tiny = analyze({ params: OC3_HYWIND, wind: parked, tmd: { ...DEFAULT_TMD, mass: 1 } }, sea);
    expect(rel(tiny.stats.pitch.sigma, base.stats.pitch.sigma)).toBeLessThan(1e-3);
  });
});

describe('V5 — rainflow and DEL', () => {
  it('matches the ASTM E1049 example', () => {
    const cycles = rainflow([-2, 1, -3, 5, -1, 3, -4, 4, -2]);
    const hist = new Map<number, number>();
    for (const c of cycles) hist.set(c.range, (hist.get(c.range) ?? 0) + c.count);
    expect(Object.fromEntries([...hist.entries()].sort((a, b) => a[0] - b[0]))).toEqual({ 3: 0.5, 4: 1.5, 6: 0.5, 8: 1, 9: 0.5 });
  });
  it('DEL of a sine is 2A·f^{1/m}', () => {
    const f = 0.1;
    const A = 3;
    const T = 1000;
    const y = Array.from({ length: T * 20 }, (_, i) => A * Math.sin(2 * Math.PI * f * (i / 20)));
    expect(rel(damageEquivalentLoad(y, T, 4), 2 * A * f ** 0.25)).toBeLessThan(0.01);
  });
});
