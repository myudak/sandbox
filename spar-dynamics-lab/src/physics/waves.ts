import { G } from './params';

/** Linear (Airy) wave dispersion ω² = g k tanh(k h), solved by Newton iteration. */
export function waveNumber(omega: number, depth: number): number {
  const k0 = (omega * omega) / G;
  if (k0 * depth > 20) return k0; // deep water
  let k = Math.max(k0, omega / Math.sqrt(G * depth));
  for (let i = 0; i < 50; i++) {
    const th = Math.tanh(k * depth);
    const f = G * k * th - omega * omega;
    const df = G * th + G * k * depth * (1 - th * th);
    const dk = f / df;
    k -= dk;
    if (Math.abs(dk) < 1e-12 * k) break;
  }
  return k;
}

/** Depth-attenuation factors for a wave of number k at elevation z (z ≤ 0) in depth h, overflow-safe. */
export function depthFactors(k: number, z: number, h: number) {
  const e2 = Math.exp(-2 * k * h);
  const a = Math.exp(k * z);
  const b = Math.exp(-k * (z + 2 * h));
  return {
    /** cosh(k(z+h))/sinh(kh): horizontal velocity per unit (ω·a). */
    ch: (a + b) / (1 - e2),
    /** sinh(k(z+h))/sinh(kh): vertical velocity per unit (ω·a). */
    sh: (a - b) / (1 - e2),
    /** cosh(k(z+h))/cosh(kh): dynamic pressure per unit (ρ g a). */
    cp: (a + b) / (1 + e2),
  };
}

export interface SeaState {
  kind: 'regular' | 'irregular';
  /** Regular: wave height H. Irregular: significant wave height Hs. [m] */
  height: number;
  /** Regular: period T. Irregular: peak period Tp. [s] */
  period: number;
  gamma: number;
  seed: number;
}

/** JONSWAP spectrum S(ω) [m²·s/rad] in the DNV-RP-C205 form. */
export function jonswap(omega: number, hs: number, tp: number, gamma = 3.3): number {
  if (omega <= 0) return 0;
  const wp = (2 * Math.PI) / tp;
  const sigma = omega <= wp ? 0.07 : 0.09;
  const ag = 1 - 0.287 * Math.log(gamma);
  const r = Math.exp(-0.5 * ((omega - wp) / (sigma * wp)) ** 2);
  return ag * (5 / 16) * hs * hs * wp ** 4 * omega ** -5 * Math.exp(-1.25 * (omega / wp) ** -4) * gamma ** r;
}

/** A single sinusoidal wave component η = a·cos(ωt − kx + ε). */
export interface WaveComponent {
  omega: number;
  k: number;
  amp: number;
  phase: number;
}

/** Deterministic PRNG (mulberry32) so a seed reproduces a sea state exactly. */
export function mulberry32(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Wave components for a sea state. Irregular seas use random-phase
 * superposition with frequencies jittered inside equal-width bins, so the
 * realisation does not repeat over a long simulation.
 */
export function waveComponents(sea: SeaState, depth: number, n = 200): WaveComponent[] {
  if (sea.height <= 0) return [];
  if (sea.kind === 'regular') {
    const omega = (2 * Math.PI) / sea.period;
    return [{ omega, k: waveNumber(omega, depth), amp: sea.height / 2, phase: 0 }];
  }
  const wp = (2 * Math.PI) / sea.period;
  const lo = 0.5 * wp;
  const hi = 3.5 * wp;
  const dw = (hi - lo) / n;
  const rnd = mulberry32(sea.seed);
  const out: WaveComponent[] = [];
  for (let i = 0; i < n; i++) {
    const omega = lo + (i + 0.2 + 0.6 * rnd()) * dw;
    const amp = Math.sqrt(2 * jonswap(omega, sea.height, sea.period, sea.gamma) * dw);
    out.push({ omega, k: waveNumber(omega, depth), amp, phase: 2 * Math.PI * rnd() });
  }
  return out;
}

export function elevation(components: WaveComponent[], t: number, x = 0): number {
  let s = 0;
  for (const c of components) s += c.amp * Math.cos(c.omega * t - c.k * x + c.phase);
  return s;
}

/** Log-spaced analysis grid; dense enough to resolve lightly damped resonances. */
export function frequencyGrid(wMin = 0.02, wMax = 4.0, n = 700): number[] {
  const r = Math.log(wMax / wMin);
  return Array.from({ length: n }, (_, i) => wMin * Math.exp((r * i) / (n - 1)));
}

/** Trapezoidal integration on a non-uniform grid. */
export function trapz(x: number[], y: number[]): number {
  let s = 0;
  for (let i = 1; i < x.length; i++) s += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1]);
  return s;
}

/** Wave spectrum on a grid for a sea state; regular waves return null (handled as a single line). */
export function seaSpectrum(sea: SeaState, omegas: number[]): number[] | null {
  if (sea.kind === 'regular') return null;
  return omegas.map((w) => jonswap(w, sea.height, sea.period, sea.gamma));
}
