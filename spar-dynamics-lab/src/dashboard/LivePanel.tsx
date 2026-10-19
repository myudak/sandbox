import { useMemo, useState } from 'react';
import { SCENARIOS, useApp } from '../state/store';
import { engine } from '../sim/engine';
import { useEngineVersion, useTicker } from '../sim/useEngine';
import { effectiveMassRatio, OutputKey } from '../physics/model';
import { OC3_HYWIND } from '../physics/params';
import { denHartog } from '../physics/tmd';
import { raoPeak } from '../physics/frequency';
import { Chart, COLORS } from './Chart';
import { Delta, Section, Segmented, Slider, Toggle } from './controls';
import { DEG, fmt, pctChange } from './format';

export function ControlPanel() {
  const s = useApp();
  const v = useEngineVersion();
  const derived = engine.tmd?.analysis.model.tmd;
  const mu = useMemo(() => effectiveMassRatio(OC3_HYWIND, s.tmd), [s.tmd]);
  void v;
  const sc = SCENARIOS.find((x) => x.id === s.scenarioId);
  return (
    <>
      <Section title="Scenario">
        <div className="chips">
          {SCENARIOS.map((x) => (
            <button key={x.id} className={x.id === s.scenarioId ? 'chip on' : 'chip'} onClick={() => s.applyScenario(x.id)}>
              {x.name}
            </button>
          ))}
        </div>
        <p className="muted small">{sc ? sc.blurb : 'Custom conditions.'}</p>
      </Section>

      <Section title="Sea state">
        <Segmented
          value={s.sea.kind}
          options={[
            { value: 'irregular', label: 'Irregular (JONSWAP)' },
            { value: 'regular', label: 'Regular' },
          ]}
          onChange={(kind) => s.setSea({ kind })}
        />
        <Slider
          label={s.sea.kind === 'regular' ? 'Wave height H' : 'Significant height Hs'}
          value={s.sea.height}
          min={0}
          max={14}
          step={0.25}
          unit="m"
          digits={2}
          onChange={(height) => s.setSea({ height })}
        />
        <Slider
          label={s.sea.kind === 'regular' ? 'Period T' : 'Peak period Tp'}
          value={s.sea.period}
          min={4}
          max={35}
          step={0.5}
          unit="s"
          onChange={(period) => s.setSea({ period })}
        />
        {s.sea.kind === 'irregular' && (
          <div className="row">
            <Slider label="Peak enhancement γ" value={s.sea.gamma} min={1} max={7} step={0.1} onChange={(gamma) => s.setSea({ gamma })} />
            <button className="ghost-btn" onClick={() => s.setSea({ seed: s.sea.seed + 1 })} title="New random phases, same spectrum">
              Seed {s.sea.seed} ↻
            </button>
          </div>
        )}
      </Section>

      <Section title="Wind">
        <Slider
          label="Hub wind speed"
          value={s.wind.speed}
          min={0}
          max={28}
          step={0.2}
          unit="m/s"
          hint="Cut-in 3 m/s, rated 11.4 m/s, cut-out 25 m/s (parked outside)"
          onChange={(speed) => s.setWind({ speed })}
        />
        <Segmented
          label="Turbulence (IEC class)"
          value={s.wind.turbulence}
          options={[
            { value: 'off', label: 'Steady' },
            { value: 'A', label: 'A' },
            { value: 'B', label: 'B' },
            { value: 'C', label: 'C' },
          ]}
          onChange={(turbulence) => s.setWind({ turbulence })}
        />
        <p className="muted small">
          {engine.base
            ? engine.base.analysis.model.thrust > 0
              ? `Operating · thrust ${fmt(engine.base.analysis.model.thrust / 1e3, 0)} kN · aero damping ${fmt(engine.base.analysis.model.aeroDamping / 1e3, 0)} kN·s/m`
              : 'Parked / idling · no thrust'
            : ''}
        </p>
      </Section>

      <Section
        title="Rotary TMD"
        aside={
          <button
            className="ghost-btn"
            title="Set f and ζ to the Den Hartog optimum for this damper's effective mass ratio"
            onClick={() => s.setTmd(denHartog(mu))}
          >
            Den Hartog tune
          </button>
        }
      >
        <Slider label="Mass" value={s.tmd.mass / 1000} min={5} max={400} step={5} unit="t" digits={0} onChange={(m) => s.setTmd({ mass: m * 1000 })} />
        <Slider
          label="CM offset from pivot"
          value={s.tmd.arm}
          min={-10}
          max={10}
          step={0.25}
          unit="m"
          digits={2}
          hint="Negative: CM above the pivot (inverted pendulum). Positive: hanging pendulum. 0: balanced flywheel."
          onChange={(arm) => s.setTmd({ arm })}
        />
        <Slider label="Radius of gyration" value={s.tmd.gyration} min={0.2} max={6} step={0.1} unit="m" onChange={(gyration) => s.setTmd({ gyration })} />
        <Slider label="Pivot height" value={s.tmd.pivotZ} min={10} max={88} step={1} unit="m" digits={0} onChange={(pivotZ) => s.setTmd({ pivotZ })} />
        <Slider
          label="Frequency ratio f = ω_d/ω_pitch"
          value={s.tmd.freqRatio}
          min={0.3}
          max={2}
          step={0.01}
          digits={2}
          onChange={(freqRatio) => s.setTmd({ freqRatio })}
        />
        <Slider label="Damping ratio ζ" value={s.tmd.dampingRatio} min={0.005} max={1} step={0.005} digits={3} onChange={(dampingRatio) => s.setTmd({ dampingRatio })} />
        {derived && (
          <dl className="facts">
            <dt>Effective mass ratio μ</dt>
            <dd>{fmt(mu * 100, 1)}%</dd>
            <dt>Damper period</dt>
            <dd>{fmt((2 * Math.PI) / derived.omegaD, 1)} s</dd>
            <dt>Spring k_d</dt>
            <dd>{fmt(derived.kd / 1e6, 2)} MN·m/rad</dd>
            <dt>Inertia J_d</dt>
            <dd>{fmt(derived.jd / 1e6, 2)} t·km²</dd>
          </dl>
        )}
        {derived && !derived.feasible && (
          <p className="warn" role="alert">
            ⚠ This tuning needs a negative-stiffness spring ({fmt(derived.kdRequired / 1e6, 2)} MN·m/rad): gravity alone already
            makes the pendulum faster than the target. Using k_d = 0, so the damper runs at {fmt((2 * Math.PI) / derived.omegaD, 1)} s
            instead of {fmt((2 * Math.PI) / derived.omegaTarget, 1)} s.
          </p>
        )}
        {engine.tmd && !engine.tmd.analysis.model.stable && <p className="warn">⚠ The coupled system is statically unstable.</p>}
      </Section>

      <Section title="View">
        <Segmented
          label="Solid turbine"
          value={s.primary}
          options={[
            { value: 'tmd', label: 'With TMD' },
            { value: 'base', label: 'Without TMD' },
          ]}
          onChange={(primary) => s.set({ primary })}
        />
        <div className="row wrap">
          <Toggle label="Ghost of the other case" checked={s.ghost} onChange={(ghost) => s.set({ ghost })} />
          <Toggle label="Nacelle cutaway" checked={s.cutaway} onChange={(cutaway) => s.set({ cutaway })} />
        </div>
        <Slider label="Time scale" value={s.timeScale} min={0.5} max={20} step={0.5} unit="×" onChange={(timeScale) => s.set({ timeScale })} />
        <Slider
          label="Motion exaggeration (visual only)"
          value={s.exaggeration}
          min={1}
          max={10}
          step={0.5}
          unit="×"
          onChange={(exaggeration) => s.set({ exaggeration })}
        />
      </Section>
    </>
  );
}

interface Row {
  label: string;
  unit: string;
  without: number;
  withTmd: number;
  digits?: number;
  note?: string;
}

/** Side-by-side comparison under identical environmental input. */
export function MetricsTable() {
  useEngineVersion();
  useTicker(500);
  const b = engine.base;
  const t = engine.tmd;
  if (!b || !t) return null;
  const sb = b.analysis.stats;
  const st = t.analysis.stats;
  const rb = b.rec;
  const rt = t.rec;
  const raoB = raoPeak(b.analysis.omegas, b.analysis.rao.pitch, 1).value * DEG;
  const raoT = raoPeak(t.analysis.omegas, t.analysis.rao.pitch, 1).value * DEG;
  const dur = rb.duration();
  const spectral: Row[] = [
    { label: 'Pitch σ', unit: '°', without: sb.pitch.sigma * DEG, withTmd: st.pitch.sigma * DEG, digits: 3 },
    {
      label: 'Pitch max (mean + 3 h)',
      unit: '°',
      without: (Math.abs(sb.pitch.mean) + sb.pitch.expectedMax) * DEG,
      withTmd: (Math.abs(st.pitch.mean) + st.pitch.expectedMax) * DEG,
    },
    { label: 'Mean pitch', unit: '°', without: sb.pitch.mean * DEG, withTmd: st.pitch.mean * DEG },
    { label: 'Peak pitch RAO', unit: '°/m', without: raoB, withTmd: raoT },
    { label: 'Surge σ', unit: 'm', without: sb.surge.sigma, withTmd: st.surge.sigma },
    { label: 'Heave σ', unit: 'm', without: sb.heave.sigma, withTmd: st.heave.sigma, digits: 3 },
    { label: 'Nacelle accel. σ', unit: 'm/s²', without: sb.nacelleAccel.sigma, withTmd: st.nacelleAccel.sigma, digits: 3 },
    { label: 'Tower-base moment σ', unit: 'MN·m', without: sb.towerMoment.sigma / 1e6, withTmd: st.towerMoment.sigma / 1e6, digits: 1 },
    { label: 'Tower DEL (narrow-band)', unit: 'MN·m', without: b.analysis.towerDelNarrowBand / 1e6, withTmd: t.analysis.towerDelNarrowBand / 1e6, digits: 1 },
  ];
  const sim: Row[] = [
    { label: 'Pitch std', unit: '°', without: rb.stats('pitch').std * DEG, withTmd: rt.stats('pitch').std * DEG, digits: 3 },
    { label: 'Pitch peak |θ|', unit: '°', without: absPeak(rb.stats('pitch')) * DEG, withTmd: absPeak(rt.stats('pitch')) * DEG },
    { label: 'Tower DEL (rainflow)', unit: 'MN·m', without: rb.towerDel() / 1e6, withTmd: rt.towerDel() / 1e6, digits: 1 },
  ];
  const strokeDeg = st.damper.expectedMax * DEG;
  const travel = Math.abs(t.analysis.model.tmd?.design.arm ?? 0) * st.damper.expectedMax;
  return (
    <Section title="Results · identical waves & wind" aside={<span className="muted small">t = {fmt(dur, 0)} s simulated</span>}>
      <table className="metrics">
        <thead>
          <tr>
            <th>Metric</th>
            <th>
              <i className="sw" style={{ background: COLORS.without }} /> Without
            </th>
            <th>
              <i className="sw" style={{ background: COLORS.withTmd }} /> With TMD
            </th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          <tr className="group">
            <td colSpan={4}>Spectral (exact for the linear model)</td>
          </tr>
          {spectral.map((r) => (
            <MetricRow key={r.label} r={r} />
          ))}
          <tr className="group">
            <td colSpan={4}>This time-domain realisation</td>
          </tr>
          {sim.map((r) => (
            <MetricRow key={r.label} r={r} />
          ))}
        </tbody>
      </table>
      <p className={strokeDeg > useApp.getState().constraints.maxStrokeDeg ? 'warn' : 'muted small'}>
        Damper stroke (expected 3 h max): {fmt(strokeDeg, 0)}° rotation ≈ {fmt(travel, 2)} m CM travel
        {strokeDeg > 30 ? ' — beyond the small-angle range where the linear model is trustworthy.' : '.'}
      </p>
    </Section>
  );
}

function absPeak(s: { min: number; max: number }) {
  return Math.max(Math.abs(s.min), Math.abs(s.max));
}

function MetricRow({ r }: { r: Row }) {
  const d = r.digits ?? 2;
  return (
    <tr>
      <td>
        {r.label} <small className="muted">{r.unit}</small>
      </td>
      <td className="num">{fmt(r.without, d)}</td>
      <td className="num">{fmt(r.withTmd, d)}</td>
      <td className="num">
        <Delta pct={pctChange(Math.abs(r.withTmd), Math.abs(r.without))} />
      </td>
    </tr>
  );
}

const SERIES: { key: OutputKey; label: string; unit: string; scale: number }[] = [
  { key: 'pitch', label: 'Pitch', unit: '°', scale: DEG },
  { key: 'surge', label: 'Surge', unit: 'm', scale: 1 },
  { key: 'heave', label: 'Heave', unit: 'm', scale: 1 },
  { key: 'towerMoment', label: 'Tower-base moment', unit: 'MN·m', scale: 1e-6 },
  { key: 'nacelleAccel', label: 'Nacelle accel.', unit: 'm/s²', scale: 1 },
  { key: 'damper', label: 'Damper angle β', unit: '°', scale: DEG },
];

export function LiveChart() {
  const [key, setKey] = useState<OutputKey>('pitch');
  const [win, setWin] = useState(300);
  useEngineVersion();
  const tick = useTicker(250);
  const spec = SERIES.find((s) => s.key === key)!;
  const data = useMemo(() => {
    const b = engine.base;
    const t = engine.tmd;
    if (!b || !t) return [[], [], []] as [number[], number[], number[]];
    const time = b.rec.series('time');
    const tEnd = time.length ? time[time.length - 1] : 0;
    let i0 = 0;
    while (i0 < time.length && time[i0] < tEnd - win) i0++;
    const yb = b.rec.series(key);
    const yt = t.rec.series(key);
    const n = Math.min(time.length, yt.length);
    const xs: number[] = [];
    const a: (number | null)[] = [];
    const c: number[] = [];
    for (let i = i0; i < n; i++) {
      xs.push(time[i]);
      a.push(key === 'damper' ? null : yb[i] * spec.scale);
      c.push(yt[i] * spec.scale);
    }
    return [xs, a, c] as [number[], (number | null)[], number[]];
  }, [tick, key, win]);
  return (
    <Section
      title="Live time series"
      aside={
        <div className="row">
          <select value={key} onChange={(e) => setKey(e.target.value as OutputKey)} aria-label="Output">
            {SERIES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
          <select value={win} onChange={(e) => setWin(+e.target.value)} aria-label="Window">
            <option value={120}>2 min</option>
            <option value={300}>5 min</option>
            <option value={600}>10 min</option>
          </select>
        </div>
      }
    >
      <Chart
        data={data as never}
        series={[
          { label: 'Without TMD', color: COLORS.without },
          { label: 'With TMD', color: COLORS.withTmd },
        ]}
        xLabel="Time [s]"
        yLabel={`${spec.label} [${spec.unit}]`}
        height={190}
        fmtX={(v) => (Number.isInteger(v) ? v.toFixed(0) : v.toFixed(1))}
        fmtY={(v) => v.toPrecision(3)}
      />
    </Section>
  );
}
