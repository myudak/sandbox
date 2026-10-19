import { G } from './params';
import type { Mat } from './linalg';

/**
 * Rotary tuned mass damper: a rigid body pivoting about a horizontal axis
 * (parallel to the platform pitch axis) fixed to the tower at height `pivotZ`.
 * Its CM sits a distance `arm` from the pivot along the tower axis
 * (positive = below the pivot, i.e. a hanging pendulum; negative = above it,
 * i.e. an inverted pendulum; 0 = a balanced flywheel). A torsional spring k_d
 * and viscous damper c_d act on the relative angle β.
 *
 * The user tunes it through:
 *   f  = ω_d / ω_pitch   (frequency ratio vs the baseline platform pitch frequency)
 *   ζ  = c_d / (2 J_d ω_d)
 * with ω_d² = (k_d + m g r) / J_d and J_d = J_c + m r² (inertia about the pivot).
 */
export interface TmdDesign {
  enabled: boolean;
  /** Damper mass [kg]. */
  mass: number;
  /** CM offset from the pivot along the tower axis, positive downward [m]. */
  arm: number;
  /** Radius of gyration of the damper body about its own CM [m]. */
  gyration: number;
  /** Pivot height above SWL [m]. */
  pivotZ: number;
  freqRatio: number;
  dampingRatio: number;
}

export const DEFAULT_TMD: TmdDesign = {
  enabled: true,
  mass: 100_000,
  arm: -5,
  gyration: 1.0,
  pivotZ: 86,
  freqRatio: 1.0,
  dampingRatio: 0.3,
};

export interface TmdDerived {
  /** Inertia about the pivot [kg·m²]. */
  jd: number;
  jc: number;
  /** Achieved damper frequency [rad/s] (differs from the target when infeasible). */
  omegaD: number;
  omegaTarget: number;
  /** Spring stiffness the target frequency would need [N·m/rad]; negative = needs a negative-stiffness mechanism. */
  kdRequired: number;
  /** Spring stiffness actually used (a real spring cannot be negative). */
  kd: number;
  cd: number;
  feasible: boolean;
}

export function deriveTmd(t: TmdDesign, omegaPitch: number): TmdDerived {
  const jc = t.mass * t.gyration * t.gyration;
  const jd = jc + t.mass * t.arm * t.arm;
  const omegaTarget = t.freqRatio * omegaPitch;
  const kdRequired = jd * omegaTarget * omegaTarget - t.mass * G * t.arm;
  const kd = Math.max(0, kdRequired);
  const omegaD = Math.sqrt((kd + t.mass * G * t.arm) / jd);
  const cd = 2 * t.dampingRatio * jd * omegaD;
  return { jd, jc, omegaD, omegaTarget, kdRequired, kd, cd, feasible: kdRequired >= 0 };
}

/**
 * Adds the damper's linearised Lagrangian terms to 4×4 M, C, K over
 * q = [x1, x3, θ, β] (in place).
 *
 *   CM position  x_c = x1 + (h_p − r) θ − r β,  z_c ≈ x3 + h_p − r
 *   T = ½ m (ẋ_c² + ẋ3²) + ½ J_c (θ̇ + β̇)²
 *   V = −½ m g h_p θ² + ½ m g r (θ + β)² + ½ k_d β²
 *   D = ½ c_d β̇²
 */
export function addTmdTerms(t: TmdDesign, d: TmdDerived, M: Mat, C: Mat, K: Mat): void {
  const m = t.mass;
  const r = t.arm;
  const a = [1, 0, t.pivotZ - r, -r];
  const b = [0, 0, 1, 1];
  for (let i = 0; i < 4; i++)
    for (let j = 0; j < 4; j++) {
      M[i][j] += m * a[i] * a[j] + d.jc * b[i] * b[j];
      K[i][j] += m * G * r * b[i] * b[j];
    }
  M[1][1] += m;
  K[2][2] += -m * G * t.pivotZ;
  K[3][3] += d.kd;
  C[3][3] += d.cd;
}

/** Den Hartog optimum for an undamped primary: f = 1/(1+μ), ζ = √(3μ / 8(1+μ)³). */
export function denHartog(mu: number): { freqRatio: number; dampingRatio: number } {
  return { freqRatio: 1 / (1 + mu), dampingRatio: Math.sqrt((3 * mu) / (8 * (1 + mu) ** 3)) };
}
