import { Section } from './controls';

export function ModelPanel() {
  return (
    <>
      <Section title="Research question">
        <p>
          <b>How robust is a rotary tuned mass damper across ocean conditions, and when does it help or hurt the stability of a floating
          SPAR wind turbine?</b>
        </p>
        <p className="small muted">
          Showing that a well-tuned damper can reduce pitch isn't new. This lab asks whether the reduction survives realistic variation in
          sea state, wind, damper stroke limits and platform detuning, and it reports increases as readily as decreases.
        </p>
      </Section>
      <Section title="What the model says (v1)">
        <ul className="small list">
          <li>
            <b>Swell near the ~30 s pitch resonance (parked):</b> the damper sharply reduces pitch. This is the textbook TMD case.
          </li>
          <li>
            <b>Wind seas well above resonance:</b> little to gain, and the extra top mass and the damper's gravity coupling can make response
            slightly worse.
          </li>
          <li>
            <b>Operating with turbulent wind:</b> aerodynamic damping already suppresses the pitch resonance. Meanwhile a soft,
            low-frequency damper mounted on a tilting tower <i>softens</i> the platform at slow (turbulent) frequencies, because tilt makes
            gravity push the damper mass downwind. RMS pitch can go <i>up</i>.
          </li>
          <li>
            <b>Stroke is the binding constraint:</b> a damper tuned to 30 s stays nearly still in space, so it must travel as far as the
            nacelle moves (metres). Respecting a stroke limit means heavier damping and less benefit.
          </li>
        </ul>
        <p className="small muted">Check these claims yourself in the Robustness and Optimise tabs; they're computed, not hard-coded.</p>
      </Section>
      <Section title="Model">
        <ul className="small list">
          <li>
            <b>Platform:</b> OC3-Hywind spar with the NREL 5-MW turbine (Jonkman 2010; Jonkman et al. 2009). Rigid body in surge, heave and
            pitch about the still-water line; rigid tower.
          </li>
          <li>
            <b>Hydrodynamics:</b> Morison strip theory (C<sub>m</sub> = 2, C<sub>d</sub> = 0.6) with finite-depth Airy kinematics; keel
            Froude–Krylov + added mass for heave; quadratic drag equivalently linearised (Borgman for irregular, Lorentz for regular),
            iterated with the response. Radiation damping neglected (small for a slender spar).
          </li>
          <li>
            <b>Mooring:</b> OC3 linearised stiffness about the undisplaced position, plus OC3 additional linear damping.
          </li>
          <li>
            <b>Wind:</b> steady thrust from the 5-MW thrust curve; aero damping ∂T/∂U = 2T/U (detuned controller); IEC Kaimal turbulence
            with a simple rotor-averaging filter.
          </li>
          <li>
            <b>Rotary TMD:</b> a body pivoting about an axis parallel to the pitch axis, with mass m, CM offset r from the pivot, centroidal
            inertia J<sub>c</sub>, torsional spring k<sub>d</sub> and damper c<sub>d</sub>. Equations come from a linearised Lagrangian and
            include gravity coupling (pendulum stiffness m·g·r and top-mass destabilisation −m·g·h<sub>p</sub>). The mean offset is solved
            with the damper re-centred.
          </li>
          <li>
            <b>Analysis:</b> frequency-domain RAOs and spectra (exact for the linear model) plus an RK4 time-domain simulation of two
            identical platforms, with and without TMD, under the same random realisation. Tower-base moment from the free body above
            z = 10 m; fatigue via rainflow (m = 4) and a narrow-band spectral DEL.
          </li>
        </ul>
      </Section>
      <Section title="Limits of v1">
        <ul className="small list">
          <li>Linear small-angle model: results with damper rotations beyond ~30° are qualitative.</li>
          <li>No tower flexibility, no second-order slow-drift loads, no blade-pitch controller dynamics, no current.</li>
          <li>Costs are placeholder order-of-magnitude numbers.</li>
        </ul>
      </Section>
      <Section title="Sources">
        <ul className="small list">
          <li>J. Jonkman, Definition of the Floating System for Phase IV of OC3, NREL/TP-500-47535, 2010.</li>
          <li>J. Jonkman, S. Butterfield, W. Musial, G. Scott, Definition of a 5-MW Reference Wind Turbine for Offshore System Development, NREL/TP-500-38060, 2009.</li>
          <li>J. P. Den Hartog, Mechanical Vibrations, 1956 (TMD optimum).</li>
          <li>DNV-RP-C205, Environmental Conditions and Environmental Loads (JONSWAP).</li>
          <li>IEC 61400-1 (turbulence model); ASTM E1049 (rainflow counting).</li>
        </ul>
      </Section>
    </>
  );
}
