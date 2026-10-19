/**
 * Reference system: OC3-Hywind spar + NREL 5-MW baseline turbine.
 *
 * Sources
 *  [J10] J. Jonkman, "Definition of the Floating System for Phase IV of OC3",
 *        NREL/TP-500-47535, 2010.
 *  [J09] J. Jonkman et al., "Definition of a 5-MW Reference Wind Turbine for
 *        Offshore System Development", NREL/TP-500-38060, 2009.
 *
 * Coordinates: x downwind / wave direction, z up, origin at the still-water
 * line (SWL) on the platform centreline. Pitch θ is positive when the tower
 * top moves toward +x.
 */

export const G = 9.80665; // m/s² (as used in [J10])
export const RHO_WATER = 1025; // kg/m³
export const RHO_AIR = 1.225; // kg/m³

/** A hull section: radius varies linearly from zTop to zBottom. */
export interface HullSection {
  zTop: number;
  zBottom: number;
  rTop: number;
  rBottom: number;
}

export interface PointMass {
  name: string;
  mass: number;
  z: number;
  /** Rotational inertia about its own CM for rotation about the pitch axis. */
  inertia: number;
}

export interface SparParams {
  waterDepth: number;
  hull: HullSection[];
  /** Platform (incl. ballast) as a rigid body. */
  platform: PointMass;
  tower: PointMass;
  towerBaseZ: number;
  towerTopZ: number;
  towerBaseDiameter: number;
  towerTopDiameter: number;
  rotor: PointMass;
  nacelle: PointMass;
  hubHeight: number;
  rotorDiameter: number;
  /** Linearised mooring stiffness about the undisplaced position [J10, §3]. */
  mooring: { k11: number; k15: number; k33: number; k55: number };
  /** Additional linear damping prescribed by [J10] (surge/heave). */
  extraDamping: { b11: number; b33: number; b55: number };
  mooringGeometry: {
    lines: number;
    fairleadDepth: number;
    fairleadRadius: number;
    anchorDepth: number;
    anchorRadius: number;
    unstretchedLength: number;
  };
  /** Morison coefficients. */
  ca: number;
  cd: number;
  /** Heave added mass at the keel (hemisphere-like approximation). */
  keelAddedMassFactor: number;
}

export const OC3_HYWIND: SparParams = {
  waterDepth: 320,
  hull: [
    // Ø6.5 m above taper, tapers to Ø9.4 m between 4 m and 12 m depth [J10, Table 2-1].
    // (Freeboard from +10 m to SWL is not wetted and is ignored by the hydro model.)
    { zTop: 0, zBottom: -4, rTop: 3.25, rBottom: 3.25 },
    { zTop: -4, zBottom: -12, rTop: 3.25, rBottom: 4.7 },
    { zTop: -12, zBottom: -120, rTop: 4.7, rBottom: 4.7 },
  ],
  platform: { name: 'platform', mass: 7_466_330, z: -89.9155, inertia: 4_229_230_000 },
  // Tower [J10, §2]: 249,718 kg, CM 43.4 m above SWL, 10 m → 87.6 m. Own inertia ≈ mL²/12.
  tower: { name: 'tower', mass: 249_718, z: 43.4, inertia: (249_718 * 77.6 * 77.6) / 12 },
  towerBaseZ: 10,
  towerTopZ: 87.6,
  towerBaseDiameter: 6.5,
  towerTopDiameter: 3.87,
  // RNA [J09]: rotor 110 t at the hub, nacelle 240 t (CM 1.75 m above yaw bearing).
  rotor: { name: 'rotor', mass: 110_000, z: 90, inertia: 1.9e7 },
  nacelle: { name: 'nacelle', mass: 240_000, z: 89.35, inertia: 2.6e6 },
  hubHeight: 90,
  rotorDiameter: 126,
  mooring: { k11: 41_180, k15: -2_821_000, k33: 11_940, k55: 311_100_000 },
  extraDamping: { b11: 100_000, b33: 130_000, b55: 0 },
  mooringGeometry: {
    lines: 3,
    fairleadDepth: 70,
    fairleadRadius: 5.2,
    anchorDepth: 320,
    anchorRadius: 853.87,
    unstretchedLength: 902.2,
  },
  ca: 1.0,
  cd: 0.6,
  keelAddedMassFactor: 2 / 3,
};

/** Published reference values used for validation. */
export const OC3_REFERENCE = {
  displacedVolume: 8029.21, // m³ [J10]
  hydrostaticHeave: 332_941, // N/m [J10]
  hydrostaticPitch: -4_999_180_000, // N·m/rad (buoyancy + waterplane only) [J10]
  // Natural frequencies from FAST free-decay with flexible tower (Jonkman 2010, OC3 Phase IV).
  // A rigid-tower model is expected to sit slightly above the pitch value.
  naturalFrequencyHz: { surge: 0.008, heave: 0.0324, pitch: 0.034 },
  systemCmZ: -78.0, // m, approx. total system CM
};

/**
 * Approximate steady-state thrust curve of the NREL 5-MW turbine (digitised
 * from [J09] Fig. 9-1; values are approximate, ±5%). Wind speed m/s → thrust N.
 */
export const THRUST_CURVE: ReadonlyArray<readonly [number, number]> = [
  [3, 110e3],
  [4, 160e3],
  [5, 230e3],
  [6, 310e3],
  [7, 400e3],
  [8, 505e3],
  [9, 610e3],
  [10, 700e3],
  [11, 780e3],
  [11.4, 800e3],
  [12, 660e3],
  [13, 570e3],
  [14, 510e3],
  [15, 465e3],
  [16, 430e3],
  [18, 380e3],
  [20, 345e3],
  [22, 315e3],
  [25, 290e3],
];

/** Rotor speed (rpm) vs wind speed for the visual rotor and Kaimal coherence. */
export const ROTOR_SPEED_CURVE: ReadonlyArray<readonly [number, number]> = [
  [3, 6.97],
  [5, 7.5],
  [7, 8.4],
  [9, 10.3],
  [11.4, 12.1],
  [25, 12.1],
];

export const CUT_IN = 3;
export const CUT_OUT = 25;
export const RATED_WIND = 11.4;

export function interp(table: ReadonlyArray<readonly [number, number]>, x: number): number {
  if (x <= table[0][0]) return table[0][1];
  const last = table[table.length - 1];
  if (x >= last[0]) return last[1];
  for (let i = 1; i < table.length; i++) {
    const [x1, y1] = table[i];
    if (x <= x1) {
      const [x0, y0] = table[i - 1];
      return y0 + ((y1 - y0) * (x - x0)) / (x1 - x0);
    }
  }
  return last[1];
}

/** Hull radius at depth z (z ≤ 0). Returns 0 outside the wetted hull. */
export function hullRadius(p: SparParams, z: number): number {
  for (const s of p.hull) {
    if (z <= s.zTop && z >= s.zBottom) {
      const t = (s.zTop - z) / (s.zTop - s.zBottom);
      return s.rTop + t * (s.rBottom - s.rTop);
    }
  }
  return 0;
}

export function draft(p: SparParams): number {
  return -p.hull[p.hull.length - 1].zBottom;
}

/** Rigid-body point masses of the baseline structure (no TMD). */
export function structuralMasses(p: SparParams): PointMass[] {
  return [p.platform, p.tower, p.rotor, p.nacelle];
}
