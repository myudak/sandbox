import { describe, expect, it } from 'vitest';
import { complexSolve, generalizedEigen, inverse, matMul } from '../linalg';
import { frequencyGrid, jonswap, mulberry32, trapz, waveComponents, waveNumber } from '../waves';
import { G, OC3_HYWIND, OC3_REFERENCE, hullRadius } from '../params';

describe('linalg', () => {
  it('inverts a matrix', () => {
    const a = [
      [4, 1, 2],
      [1, 5, 3],
      [2, 3, 6],
    ];
    const p = matMul(a, inverse(a));
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) expect(p[i][j]).toBeCloseTo(i === j ? 1 : 0, 12);
  });

  it('solves a complex system', () => {
    // (1+i) x = 2  →  x = 1 − i
    const { re, im } = complexSolve([[1]], [[1]], [2], [0]);
    expect(re[0]).toBeCloseTo(1, 12);
    expect(im[0]).toBeCloseTo(-1, 12);
    // 2×2 check against direct multiplication
    const ar = [
      [3, -1],
      [2, 4],
    ];
    const ai = [
      [0.5, 2],
      [-1, 0.3],
    ];
    const x = complexSolve(ar, ai, [1, -2], [0.5, 1]);
    for (let i = 0; i < 2; i++) {
      let sr = 0;
      let si = 0;
      for (let j = 0; j < 2; j++) {
        sr += ar[i][j] * x.re[j] - ai[i][j] * x.im[j];
        si += ar[i][j] * x.im[j] + ai[i][j] * x.re[j];
      }
      expect(sr).toBeCloseTo([1, -2][i], 10);
      expect(si).toBeCloseTo([0.5, 1][i], 10);
    }
  });

  it('solves the generalised eigenproblem of a 2-mass chain', () => {
    const m = 2;
    const k = 50;
    const M = [
      [m, 0],
      [0, m],
    ];
    const K = [
      [2 * k, -k],
      [-k, 2 * k],
    ];
    const { values } = generalizedEigen(K, M);
    expect(values[0]).toBeCloseTo(k / m, 9);
    expect(values[1]).toBeCloseTo((3 * k) / m, 9);
  });
});

describe('waves', () => {
  it('satisfies the dispersion relation in finite depth', () => {
    for (const w of [0.1, 0.3, 0.8, 2]) {
      const k = waveNumber(w, 320);
      expect(G * k * Math.tanh(k * 320)).toBeCloseTo(w * w, 9);
    }
  });

  it('JONSWAP integrates to Hs²/16', () => {
    const hs = 6;
    const tp = 10;
    const w = frequencyGrid(0.05, 6, 4000);
    const m0 = trapz(
      w,
      w.map((x) => jonswap(x, hs, tp, 3.3)),
    );
    expect(Math.sqrt(m0) * 4).toBeCloseTo(hs, 1);
  });

  it('irregular realisation reproduces Hs and is seed-deterministic', () => {
    const sea = { kind: 'irregular' as const, height: 4, period: 9, gamma: 3.3, seed: 7 };
    const a = waveComponents(sea, 320);
    const b = waveComponents(sea, 320);
    expect(a).toEqual(b);
    const m0 = a.reduce((s, c) => s + 0.5 * c.amp * c.amp, 0);
    expect(4 * Math.sqrt(m0)).toBeGreaterThan(3.7);
    expect(4 * Math.sqrt(m0)).toBeLessThan(4.1);
    const r = mulberry32(1);
    expect(r()).not.toEqual(r());
  });
});

describe('OC3 geometry', () => {
  it('reproduces the published displaced volume and hydrostatics', () => {
    let v = 0;
    const dz = 0.01;
    for (let z = -dz / 2; z > -120; z -= dz) v += Math.PI * hullRadius(OC3_HYWIND, z) ** 2 * dz;
    expect(Math.abs(v - OC3_REFERENCE.displacedVolume) / OC3_REFERENCE.displacedVolume).toBeLessThan(0.002);
    const c33 = 1025 * G * Math.PI * 3.25 ** 2;
    expect(Math.abs(c33 - OC3_REFERENCE.hydrostaticHeave) / OC3_REFERENCE.hydrostaticHeave).toBeLessThan(0.005);
  });
});
