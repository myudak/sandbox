import { G, RHO_WATER, SparParams, draft, hullRadius } from './params';
import { depthFactors } from './waves';

/** A horizontal slice of the wetted hull used for Morison strip theory. */
export interface Strip {
  z: number;
  dz: number;
  r: number;
  /** Upward-facing projected area change within the strip (taper), m². */
  dAup: number;
}

export function buildStrips(p: SparParams, dz = 1): Strip[] {
  const d = draft(p);
  const n = Math.round(d / dz);
  const h = d / n;
  const strips: Strip[] = [];
  for (let i = 0; i < n; i++) {
    const zTop = -i * h;
    const zBot = -(i + 1) * h;
    const z = 0.5 * (zTop + zBot);
    const rTop = hullRadius(p, zTop - 1e-9);
    const rBot = hullRadius(p, zBot + 1e-9);
    strips.push({ z, dz: h, r: hullRadius(p, z), dAup: Math.PI * (rBot * rBot - rTop * rTop) });
  }
  return strips;
}

export interface Hydrostatics {
  volume: number;
  zB: number;
  waterplaneArea: number;
  waterplaneInertia: number;
  /** ρ g A_wp */
  c33: number;
  /** ρ g V z_B + ρ g I_wp (buoyancy + waterplane only; gravity added separately). */
  c55: number;
}

export function hydrostatics(p: SparParams, strips: Strip[]): Hydrostatics {
  let volume = 0;
  let moment = 0;
  for (const s of strips) {
    const dv = Math.PI * s.r * s.r * s.dz;
    volume += dv;
    moment += dv * s.z;
  }
  const r0 = hullRadius(p, 0);
  const waterplaneArea = Math.PI * r0 * r0;
  const waterplaneInertia = (Math.PI * r0 ** 4) / 4;
  const zB = moment / volume;
  return {
    volume,
    zB,
    waterplaneArea,
    waterplaneInertia,
    c33: RHO_WATER * G * waterplaneArea,
    c55: RHO_WATER * G * volume * zB + RHO_WATER * G * waterplaneInertia,
  };
}

/** Constant (low-frequency) added-mass matrix in [surge, heave, pitch] from strip theory. */
export function addedMass(p: SparParams, strips: Strip[]): number[][] {
  let a11 = 0;
  let a15 = 0;
  let a55 = 0;
  for (const s of strips) {
    const m = RHO_WATER * p.ca * Math.PI * s.r * s.r * s.dz;
    a11 += m;
    a15 += m * s.z;
    a55 += m * s.z * s.z;
  }
  const rk = hullRadius(p, -draft(p) + 1e-9);
  const a33 = RHO_WATER * p.keelAddedMassFactor * Math.PI * rk ** 3;
  return [
    [a11, 0, a15],
    [0, a33, 0],
    [a15, 0, a55],
  ];
}

/**
 * First-order wave excitation per unit wave amplitude, in [surge, heave, pitch].
 *
 * Horizontal: Morison inertia (Cm = 1 + Ca) plus the linearised-drag excitation
 * b(z)·u(z) per strip. Vertical: Froude–Krylov pressure on the keel and the
 * upward-facing taper, plus keel added-mass diffraction. Pitch: moments of the
 * horizontal strip forces about the SWL and the keel pressure gradient.
 *
 * `bz[i]` is the linearised drag coefficient per unit length of strip i
 * [N·s/m²]. Returns real and imaginary parts (convention η = Re(a·e^{iωt})).
 */
export function waveExcitation(
  p: SparParams,
  strips: Strip[],
  bz: ArrayLike<number>,
  omega: number,
  k: number,
): { re: [number, number, number]; im: [number, number, number] } {
  const h = p.waterDepth;
  const cm = 1 + p.ca;
  let f1r = 0;
  let f1i = 0;
  let f3r = 0;
  let f3i = 0;
  let f5r = 0;
  let f5i = 0;
  for (let i = 0; i < strips.length; i++) {
    const s = strips[i];
    const { ch, cp } = depthFactors(k, s.z, h);
    const u = omega * ch; // û (real, in phase with η)
    // dF = [ρ Cm A iω + b] û dz
    const fr = bz[i] * u * s.dz;
    const fi = RHO_WATER * cm * Math.PI * s.r * s.r * omega * u * s.dz;
    f1r += fr;
    f1i += fi;
    f5r += s.z * fr;
    f5i += s.z * fi;
    if (s.dAup !== 0) f3r -= RHO_WATER * G * cp * s.dAup;
  }
  const zk = -draft(p);
  const rk = hullRadius(p, zk + 1e-9);
  const { cp, sh } = depthFactors(k, zk, h);
  const aKeel = Math.PI * rk * rk;
  const a33 = RHO_WATER * p.keelAddedMassFactor * Math.PI * rk ** 3;
  // keel Froude–Krylov + diffraction (added mass × fluid vertical acceleration −ω² sh)
  f3r += RHO_WATER * G * cp * aKeel - a33 * omega * omega * sh;
  // keel pressure gradient moment: i k p̂ I_keel
  f5i += k * RHO_WATER * G * cp * ((Math.PI * rk ** 4) / 4);
  return { re: [f1r, f3r, f5r], im: [f1i, f3i, f5i] };
}

/** Undisturbed horizontal fluid velocity at strip i per unit wave amplitude (real, in phase with η). */
export function fluidVelocity(p: SparParams, s: Strip, omega: number, k: number): number {
  return omega * depthFactors(k, s.z, p.waterDepth).ch;
}

/** Drag linearisation factor: b = factor · σ_r (or U_r) · ½ ρ Cd D. */
export function dragCoefficientPerLength(p: SparParams, s: Strip): number {
  return 0.5 * RHO_WATER * p.cd * 2 * s.r;
}
