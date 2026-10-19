import { CUT_IN, CUT_OUT, ROTOR_SPEED_CURVE, THRUST_CURVE, interp } from './params';

export type TurbulenceClass = 'off' | 'A' | 'B' | 'C';

export interface WindState {
  /** Mean hub-height wind speed [m/s]. */
  speed: number;
  turbulence: TurbulenceClass;
}

const I_REF: Record<Exclude<TurbulenceClass, 'off'>, number> = { A: 0.16, B: 0.14, C: 0.12 };

export function operating(wind: WindState): boolean {
  return wind.speed >= CUT_IN && wind.speed <= CUT_OUT;
}

/** Steady-state rotor thrust [N]; zero when parked. */
export function meanThrust(wind: WindState): number {
  return operating(wind) ? interp(THRUST_CURVE, wind.speed) : 0;
}

/**
 * Linearised aerodynamic damping ∂T/∂U [N·s/m] felt by the hub's fore-aft
 * velocity. Quasi-steady, constant-C_T assumption: T ∝ U² ⇒ ∂T/∂U = 2T/U.
 * This corresponds to the OC3 detuned controller, which does not respond at
 * platform frequencies; an un-detuned pitch controller would make this
 * negative above rated (not modelled in v1).
 */
export function aeroDamping(wind: WindState): number {
  return operating(wind) ? (2 * meanThrust(wind)) / wind.speed : 0;
}

/** Rotor speed for the visual rotor [rpm]. */
export function rotorRpm(wind: WindState): number {
  return operating(wind) ? interp(ROTOR_SPEED_CURVE, wind.speed) : 0;
}

/** IEC 61400-1 normal turbulence model: σ_u = I_ref (0.75 U + 5.6). */
export function turbulenceSigma(wind: WindState): number {
  if (wind.turbulence === 'off' || wind.speed <= 0) return 0;
  return I_REF[wind.turbulence] * (0.75 * wind.speed + 5.6);
}

const KAIMAL_L = 8.1 * 42; // IEC longitudinal integral scale for hub height > 60 m

/** Kaimal longitudinal velocity spectrum per rad/s [m²/s² · s/rad]. */
export function kaimal(omega: number, wind: WindState): number {
  const sigma = turbulenceSigma(wind);
  if (sigma === 0 || omega <= 0) return 0;
  const f = omega / (2 * Math.PI);
  const lu = KAIMAL_L / wind.speed;
  const sf = (4 * sigma * sigma * lu) / (1 + 6 * f * lu) ** (5 / 3);
  return sf / (2 * Math.PI);
}

/** Simple rotor-averaging admittance |χ(f)|² for a disc of diameter D (approximate). */
export function rotorAdmittance(omega: number, wind: WindState, diameter: number): number {
  const f = omega / (2 * Math.PI);
  return 1 / (1 + ((2 * f * diameter) / Math.max(wind.speed, 1)) ** (4 / 3));
}

/** Spectrum of the turbulent rotor-thrust fluctuation T′ [N² · s/rad]. */
export function thrustSpectrum(omega: number, wind: WindState, diameter: number): number {
  if (!operating(wind)) return 0;
  const g = aeroDamping(wind);
  return g * g * kaimal(omega, wind) * rotorAdmittance(omega, wind, diameter);
}
