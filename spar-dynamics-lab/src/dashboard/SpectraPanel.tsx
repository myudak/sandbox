import { useMemo, useState } from 'react';
import { engine } from '../sim/engine';
import { useEngineVersion } from '../sim/useEngine';
import { OutputKey, baselineModes } from '../physics/model';
import { OC3_HYWIND } from '../physics/params';
import { raoPeak } from '../physics/frequency';
import { Chart, COLORS } from './Chart';
import { Section } from './controls';
import { DEG, fmt } from './format';

const OUTS: { key: OutputKey; label: string; unit: string; scale: number }[] = [
  { key: 'pitch', label: 'Pitch', unit: '°', scale: DEG },
  { key: 'surge', label: 'Surge', unit: 'm', scale: 1 },
  { key: 'heave', label: 'Heave', unit: 'm', scale: 1 },
  { key: 'towerMoment', label: 'Tower-base moment', unit: 'MN·m', scale: 1e-6 },
  { key: 'nacelleAccel', label: 'Nacelle accel.', unit: 'm/s²', scale: 1 },
];

const W_MAX = 1.2;

export function SpectraPanel() {
  const v = useEngineVersion();
  const [key, setKey] = useState<OutputKey>('pitch');
  const spec = OUTS.find((o) => o.key === key)!;
  const modes = useMemo(() => baselineModes(OC3_HYWIND), []);
  const d = useMemo(() => {
    const b = engine.base?.analysis;
    const t = engine.tmd?.analysis;
    if (!b || !t) return null;
    const idx = b.omegas.map((w, i) => (w <= W_MAX ? i : -1)).filter((i) => i >= 0);
    const xs = idx.map((i) => b.omegas[i]);
    const rao = [xs, idx.map((i) => b.rao[key][i] * spec.scale), idx.map((i) => t.rao[key][i] * spec.scale)];
    const s2 = spec.scale * spec.scale;
    const psd = [xs, idx.map((i) => b.psd[key][i] * s2), idx.map((i) => t.psd[key][i] * s2)];
    const input = [xs, idx.map((i) => b.waveSpectrum[i])];
    const thrust = [xs, idx.map((i) => b.thrustSpectrum[i] / 1e10)];
    return {
      rao,
      psd,
      input,
      thrust,
      hasThrust: b.thrustSpectrum.some((x) => x > 0),
      hasWave: b.waveSpectrum.some((x) => x > 0),
      peakB: raoPeak(b.omegas, b.rao[key], W_MAX),
      peakT: raoPeak(t.omegas, t.rao[key], W_MAX),
    };
  }, [v, key]);
  if (!d) return null;
  const regular = engine.sea?.kind === 'regular';
  return (
    <>
      <Section
        title="Response amplitude operator"
        aside={
          <select value={key} onChange={(e) => setKey(e.target.value as OutputKey)} aria-label="Output">
            {OUTS.map((o) => (
              <option key={o.key} value={o.key}>
                {o.label}
              </option>
            ))}
          </select>
        }
      >
        <Chart
          data={d.rao as never}
          series={[
            { label: 'Without TMD', color: COLORS.without },
            { label: 'With TMD', color: COLORS.withTmd },
          ]}
          xLabel="ω [rad/s]"
          yLabel={`${spec.label} per m wave [${spec.unit}/m]`}
          height={210}
          fmtX={(x) => x.toFixed(2)}
          fmtY={(x) => x.toPrecision(3)}
        />
        <p className="muted small">
          Peak without: {fmt(d.peakB.value * spec.scale, 3)} at T = {fmt((2 * Math.PI) / d.peakB.omega, 1)} s · with TMD:{' '}
          {fmt(d.peakT.value * spec.scale, 3)} at T = {fmt((2 * Math.PI) / d.peakT.omega, 1)} s. Natural periods (no TMD): surge{' '}
          {fmt(modes.surge.periodS, 0)} s, heave {fmt(modes.heave.periodS, 1)} s, pitch {fmt(modes.pitch.periodS, 1)} s. The RAO
          includes drag linearised for the current sea state and aero damping for the current wind.
        </p>
      </Section>
      <Section title="Response spectrum">
        {regular && !d.hasThrust ? (
          <p className="muted small">Regular waves put all energy in one line at T = {engine.sea?.period} s; see the RAO above.</p>
        ) : (
          <Chart
            data={d.psd as never}
            series={[
              { label: 'Without TMD', color: COLORS.without },
              { label: 'With TMD', color: COLORS.withTmd },
            ]}
            xLabel="ω [rad/s]"
            yLabel={`S [${spec.unit}²·s/rad]`}
            height={190}
            fmtX={(x) => x.toFixed(2)}
            fmtY={(x) => x.toPrecision(2)}
          />
        )}
      </Section>
      <Section title="Environmental input">
        {d.hasWave && (
          <Chart data={d.input as never} series={[{ label: 'Wave spectrum S_η', color: COLORS.aux }]} xLabel="ω [rad/s]" yLabel="S_η [m²·s/rad]" height={140} fmtX={(x) => x.toFixed(2)} fmtY={(x) => x.toPrecision(2)} />
        )}
        {d.hasThrust && (
          <Chart
            data={d.thrust as never}
            series={[{ label: 'Turbulent thrust S_T', color: COLORS.aux }]}
            xLabel="ω [rad/s]"
            yLabel="S_T [10¹⁰ N²·s/rad]"
            height={140}
            fmtX={(x) => x.toFixed(2)}
            fmtY={(x) => x.toPrecision(2)}
          />
        )}
        {!d.hasWave && !d.hasThrust && <p className="muted small">{regular ? 'Single regular wave component.' : 'No input energy.'}</p>}
        <p className="muted small">
          The pitch resonance sits at ω ≈ {fmt(modes.pitch.omega, 2)} rad/s. Wind-sea energy is mostly above it; long swell and turbulent
          wind put energy right on it.
        </p>
      </Section>
    </>
  );
}
