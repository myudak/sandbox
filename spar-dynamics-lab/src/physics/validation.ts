import { OC3_HYWIND, OC3_REFERENCE } from './params';
import { LinearModel, PITCH, assembleModel, baselineMatrices, baselineModes } from './model';
import { analyze, transfer } from './frequency';
import { Simulator } from './timeDomain';
import { frequencyGrid, waveComponents } from './waves';
import { DEFAULT_TMD, denHartog } from './tmd';
import { damageEquivalentLoad, rainflow } from './fatigue';

export interface Check {
  id: string;
  group: string;
  name: string;
  value: string;
  reference: string;
  pass: boolean;
  note?: string;
}

const rel = (a: number, b: number) => Math.abs(a - b) / Math.abs(b);
const pct = (x: number) => `${(100 * x).toFixed(2)}%`;

/** The validation suite shown in the app (mirrors the unit tests). */
export function runValidation(onProgress?: (p: number) => void): Check[] {
  const out: Check[] = [];
  const steps = 6;
  let k = 0;
  const tick = () => onProgress?.(++k / steps);

  const modes = baselineModes(OC3_HYWIND);
  const ref = OC3_REFERENCE.naturalFrequencyHz;
  const nat = (name: 'surge' | 'heave' | 'pitch', tol: number, note?: string) => {
    const e = rel(modes[name].freqHz, ref[name]);
    out.push({
      id: `nat-${name}`,
      group: 'OC3 benchmark',
      name: `${name[0].toUpperCase()}${name.slice(1)} natural frequency`,
      value: `${modes[name].freqHz.toFixed(4)} Hz (${modes[name].periodS.toFixed(1)} s)`,
      reference: `${ref[name]} Hz · tol ${pct(tol)}`,
      pass: e < tol,
      note: `error ${pct(e)}${note ? ` — ${note}` : ''}`,
    });
  };
  nat('surge', 0.05);
  nat('heave', 0.05);
  nat('pitch', 0.08, 'FAST value includes tower flexibility, which lowers pitch frequency; a rigid tower sits slightly higher');
  const b = baselineMatrices(OC3_HYWIND);
  out.push({
    id: 'hydro',
    group: 'OC3 benchmark',
    name: 'Displaced volume',
    value: `${b.hs.volume.toFixed(1)} m³`,
    reference: `${OC3_REFERENCE.displacedVolume} m³`,
    pass: rel(b.hs.volume, OC3_REFERENCE.displacedVolume) < 0.005,
  });
  out.push({
    id: 'c55',
    group: 'OC3 benchmark',
    name: 'Hydrostatic pitch restoring',
    value: `${(b.hs.c55 / 1e9).toFixed(3)} GN·m/rad`,
    reference: `${(OC3_REFERENCE.hydrostaticPitch / 1e9).toFixed(3)} GN·m/rad`,
    pass: rel(b.hs.c55, OC3_REFERENCE.hydrostaticPitch) < 0.01,
  });
  tick();

  // free decay & energy
  const params0 = { ...OC3_HYWIND, extraDamping: { b11: 0, b33: 0, b55: 0 } };
  const m0 = assembleModel({ params: params0, wind: { speed: 0, turbulence: 'off' }, tmd: null });
  const sim = new Simulator(m0, [], []);
  sim.x[PITCH] = (2 * Math.PI) / 180;
  const e0 = sim.energy();
  for (let i = 0; i < 6000; i++) sim.step(0.05);
  const de = rel(sim.energy(), e0);
  out.push({
    id: 'energy',
    group: 'Numerics',
    name: 'Energy conservation, undamped free decay (300 s, RK4 dt 0.05 s)',
    value: pct(de),
    reference: '< 0.01%',
    pass: de < 1e-4,
  });
  tick();

  // time vs frequency domain
  const sea = { kind: 'regular' as const, height: 2, period: 14, gamma: 3.3, seed: 1 };
  const a = analyze({ params: OC3_HYWIND, wind: { speed: 0, turbulence: 'off' }, tmd: DEFAULT_TMD }, sea);
  const s2 = new Simulator(a.model, waveComponents(sea, OC3_HYWIND.waterDepth), []);
  let mx = -Infinity;
  let mn = Infinity;
  for (let i = 0; i < 4000; i++) {
    s2.step(0.05);
    const p = s2.outputs().pitch;
    mx = Math.max(mx, p);
    mn = Math.min(mn, p);
  }
  const amp = (mx - mn) / 2;
  out.push({
    id: 'td-fd',
    group: 'Numerics',
    name: 'Time-domain pitch amplitude vs RAO (regular H 2 m, T 14 s, with TMD)',
    value: `${((amp * 180) / Math.PI).toFixed(4)}°`,
    reference: `${((a.stats.pitch.expectedMax * 180) / Math.PI).toFixed(4)}° · tol 1%`,
    pass: rel(amp, a.stats.pitch.expectedMax) < 0.01,
  });
  tick();

  // Den Hartog
  const mu = 0.05;
  const dh = denHartog(mu);
  const grid = frequencyGrid(0.5, 1.6, 2000);
  const sdof = (f: number, z: number) => {
    const kd = mu * f * f;
    const cd = 2 * z * mu * f;
    return {
      n: 2,
      M: [
        [1, 0],
        [0, mu],
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
  };
  const peak = (m: LinearModel) =>
    Math.max(
      ...grid.map((w) => {
        const x = transfer(m, w, { re: [1, 0], im: [0, 0] });
        return Math.hypot(x.re[0], x.im[0]);
      }),
    );
  const p = peak(sdof(dh.freqRatio, dh.dampingRatio));
  const theory = Math.sqrt(1 + 2 / mu);
  out.push({
    id: 'denhartog',
    group: 'TMD theory',
    name: 'Den Hartog equal-peak amplification (μ = 5%)',
    value: p.toFixed(3),
    reference: `√(1+2/μ) = ${theory.toFixed(3)} · tol 3%`,
    pass: rel(p, theory) < 0.03,
  });
  tick();

  const parked = { speed: 0, turbulence: 'off' as const };
  const swell = { kind: 'irregular' as const, height: 4, period: 12, gamma: 3.3, seed: 1 };
  const base = analyze({ params: OC3_HYWIND, wind: parked, tmd: null }, swell);
  const tiny = analyze({ params: OC3_HYWIND, wind: parked, tmd: { ...DEFAULT_TMD, mass: 1 } }, swell);
  const dt = rel(tiny.stats.pitch.sigma, base.stats.pitch.sigma);
  out.push({
    id: 'limit',
    group: 'TMD theory',
    name: 'Vanishing damper mass recovers the baseline',
    value: pct(dt),
    reference: '< 0.1%',
    pass: dt < 1e-3,
  });
  tick();

  // rainflow
  const cycles = rainflow([-2, 1, -3, 5, -1, 3, -4, 4, -2]);
  const hist: Record<number, number> = {};
  for (const c of cycles) hist[c.range] = (hist[c.range] ?? 0) + c.count;
  const expected: Record<number, number> = { 3: 0.5, 4: 1.5, 6: 0.5, 8: 1, 9: 0.5 };
  out.push({
    id: 'rainflow',
    group: 'Fatigue',
    name: 'Rainflow counting, ASTM E1049 example',
    value: Object.entries(hist)
      .map(([r, n]) => `${r}:${n}`)
      .join(' '),
    reference: Object.entries(expected)
      .map(([r, n]) => `${r}:${n}`)
      .join(' '),
    pass: JSON.stringify(hist) === JSON.stringify(expected),
  });
  const y = Array.from({ length: 20000 }, (_, i) => 3 * Math.sin(2 * Math.PI * 0.1 * (i / 20)));
  const del = damageEquivalentLoad(y, 1000, 4);
  out.push({
    id: 'del',
    group: 'Fatigue',
    name: 'DEL of a sine (A = 3, f = 0.1 Hz, m = 4)',
    value: del.toFixed(4),
    reference: `2A·f^(1/m) = ${(6 * 0.1 ** 0.25).toFixed(4)}`,
    pass: rel(del, 6 * 0.1 ** 0.25) < 0.01,
  });
  tick();
  return out;
}
