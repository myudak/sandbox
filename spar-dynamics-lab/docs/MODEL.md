# SPAR Dynamics Lab: model notes

## Research question

How robust is a rotary tuned mass damper (TMD) across ocean conditions, and
when does it help or hurt the stability of a floating SPAR wind turbine?

## Reference system

OC3-Hywind spar with the NREL 5-MW turbine. All numbers are in
`src/physics/params.ts`, with sources.

| Quantity | Value |
|---|---|
| Draft / water depth | 120 m / 320 m |
| Hull diameter | 6.5 m above 4 m depth, tapers to 9.4 m below 12 m |
| Platform mass, CM, pitch inertia | 7,466,330 kg, −89.92 m, 4.229e9 kg·m² |
| Tower / rotor / nacelle | 249,718 kg / 110,000 kg / 240,000 kg |
| Mooring (linearised) | K11 41.18 kN/m, K15 −2.821 MN/rad, K33 11.94 kN/m, K55 311.1 MN·m/rad |
| Extra linear damping | B11 100 kN·s/m, B33 130 kN·s/m |

## Equations of motion

Generalised coordinates `q = [x1, x3, θ, β]`: surge and heave of the
still-water-line reference point, pitch θ (positive = tower top moves
downwind) and the damper's rotation β relative to the platform.

```
M q̈ + C q̇ + K q = F_wave(t) + w·(T + T′(t))
```

`w = [1, 0, h_hub, 0]` maps a hub force into generalised forces.

**Rigid body.** `M11 = m`, `M15 = Σ mᵢzᵢ`, `M55 = Σ (Iᵢ + mᵢzᵢ²)`, `M33 = m`.

**Hydrostatics and gravity.**
- `K33 = ρgA_wp`
- `K55 = ρgV z_B + ρgI_wp − m g z_G`

Both come from the hull geometry and match the published 8029 m³ and
−4.999 GN·m/rad.

**Hydrodynamics.** Morison strip theory over 1 m strips:
- Added mass: `A11 = Σ ρC_aA dz`, `A15 = Σ ρC_aA z dz`, `A55 = Σ ρC_aA z² dz`.
- Horizontal excitation per strip: `(iωρC_mA + b(z))·û(z) dz`, with finite-depth Airy velocity `û = ωa·cosh k(z+h)/sinh kh`.
- Heave: Froude–Krylov pressure on the keel and the upward-facing taper, plus keel added-mass diffraction.

**Drag linearisation.** Quadratic Morison drag `½ρC_dD|u_r|u_r` is replaced by `b(z)·u_r`, with:
- `b = √(8/π)·σ_r·½ρC_dD` for irregular seas (Borgman);
- `b = 8/(3π)·U_r·½ρC_dD` for regular waves (Lorentz).

The relative-velocity statistics come from the response itself, so the
scheme iterates (under-relaxed, up to 6 times, until a 1% change). Every
configuration, with or without TMD and in each sea state, is linearised on
its own.

**Wind.**
- Thrust `T(U)` from the 5-MW curve.
- Aerodynamic damping `∂T/∂U = 2T/U`, applied to the hub's fore–aft velocity. This is quasi-steady and assumes the OC3 detuned controller.
- Turbulence: IEC normal turbulence model with the Kaimal spectrum and a simple rotor-averaging admittance, giving the thrust fluctuation spectrum `S_T = (2T/U)²·S_u·|χ|²`.

## Rotary TMD

A rigid body pivots about an axis parallel to the pitch axis at height
`h_p`. Its CM is offset `r` along the tower axis: `r > 0` hangs below the
pivot, `r < 0` is an inverted pendulum, and `r = 0` is a balanced flywheel.
It has centroidal inertia `J_c = m·ρ_g²`, a torsional spring `k_d` and a
viscous damper `c_d`. The CM's horizontal position is
`x_c = x1 + (h_p − r)θ − rβ`, so the linearised Lagrangian is:

```
T = ½ m (ẋ_c² + ẋ3²) + ½ J_c (θ̇ + β̇)²
V = −½ m g h_p θ² + ½ m g r (θ + β)² + ½ k_d β²
D = ½ c_d β̇²
```

Tuning follows from `J_d = J_c + m r²`:
- `ω_d² = (k_d + m g r)/J_d` sets `k_d = J_d (f·ω_pitch)² − m g r`.
- `c_d = 2ζ J_d ω_d`.

When `k_d` would have to be negative, the target is infeasible for a real
spring: the app flags this and uses `k_d = 0`.

The effective mass ratio used for the Den Hartog start is
`μ = γ²/(J_d M*)`. Here `M* = φᵀMφ` is the modal mass of the pitch mode,
with φ normalised to unit nacelle motion, and γ is the coupling between
that mode and β.

**Mean offset.** The static solve locks β = 0, i.e. the damper is assumed
to be re-centred by a slow preload or actuator. Without that, a soft
pitch-tuned damper on a tilted platform would deflect by roughly g·θ/ω_d²,
which is metres.

## Outputs

Every output is a linear map `y = c_x·x + c_v·ẋ + c_a·ẍ + d_T·T′`. The
frequency and time domains therefore report identical quantities: surge,
heave, pitch, damper angle, nacelle fore–aft acceleration and tower-base
fore–aft bending moment.

**Tower-base moment** comes from the free body above z = 10 m: thrust
moment + gravity moment of the tilted masses − inertial moments, including
the damper's terms.

## Analysis

**Frequency domain.** `X(ω) = [K − ω²M + iωC]⁻¹ F(ω)` on a 700-point
log grid from 0.02 to 4 rad/s. The response spectrum is
`S_y = |H_wave|²S_η + |H_wind|²S_T`, assuming uncorrelated wind and waves.
- σ comes from m₀; ν₀ = √(m₂/m₀)/2π.
- Expected 3-hour maximum: `σ√(2 ln(ν₀·10800))`.
- Narrow-band 1 Hz DEL (m = 4): `2√2·σ·Γ(3)^{1/4}·ν₀^{1/4}`.

**Time domain.** RK4 at Δt = 0.1 s, with the forcing evaluated through
rotating phasors. Two simulators, with and without TMD, run in lockstep on
the same wave components and the same turbulent-thrust realisation. The
initial state is the exact steady-state response, so there is no start-up
transient. The tower-base DEL comes from rainflow counting (ASTM E1049).

**Optimiser.** Den Hartog start, then a 5 × 4 grid, then bounded
Nelder–Mead over (f, ζ). The objective is the with/without ratio of:
- RMS pitch,
- peak RAO,
- tower DEL, or
- a weighted RMS pitch over a small scatter of conditions.

The penalties are:
- expected 3-hour damper rotation above the limit,
- an infeasible spring,
- mass above the limit,
- static instability.

**Robustness.** For each Hs × Tp cell, the % change with vs without TMD for
one wind condition, with drag re-linearised in every cell. **Detuning**
scales the platform pitch restoring by `(1 + Δf)²` and keeps the damper's
as-built tuning.

## Validation

`npm test` runs the same checks the Validation tab shows:

| Check | Result |
|---|---|
| Surge / heave / pitch natural frequency vs OC3 | 125.0 s / 30.8 s / 30.0 s vs 0.008 / 0.0324 / 0.034 Hz (pitch +2%, rigid tower) |
| Displaced volume, hydrostatic pitch restoring | 8029.1 m³, −5.008 GN·m/rad |
| Energy conservation, undamped free decay | < 0.01% over 300 s |
| Time-domain vs RAO, regular wave | < 1% |
| Irregular-sea σ, time vs spectral | < 10% |
| Den Hartog equal-peak amplification √(1+2/μ) | < 3%; brute-force optimum within 2% |
| Vanishing damper mass → baseline | < 0.1% |
| Rainflow on the ASTM E1049 example, sine DEL | exact, < 1% |

Not yet validated: comparison against OpenFAST runs. The thrust curve is an
approximate digitisation, and the turbulence admittance is approximate.

## What the v1 model shows

These are computed in the app, not hard-coded. Defaults: 100 t damper,
inverted arm 5 m.

- **Parked, long swell (Tp ≈ 25–30 s):** RMS pitch drops by roughly
  50–75%. The pitch RAO peak falls from ≈ 3.8 to ≈ 0.8 °/m.
- **Parked, wind sea above resonance (Tp ≈ 9–18 s):** RMS pitch rises by
  about 3–12%. The added top mass and the damper's gravity coupling cost
  more than the damper buys.
- **Operating with turbulent wind:** aerodynamic damping already suppresses
  the resonance, and the damper's tilt–gravity coupling softens the
  platform at turbulent frequencies. RMS pitch rises by roughly 10–30%.
- **Stroke is the binding constraint:** a damper tuned to ~30 s stays
  nearly still in space, so its travel matches the nacelle's motion
  (metres). With a 45° rotation limit, the parked-swell optimum is heavily
  damped (f ≈ 1.7, ζ ≈ 0.4) for about −59% RMS pitch.

## Roadmap (v2)

- Large-angle and quadratic-drag time domain
- Quasi-static catenary mooring tensions
- Tower flexibility (fore–aft mode)
- Blade-pitch controller dynamics, including the negative-damping case
- Second-order slow-drift wave loads
- OpenFAST comparison
