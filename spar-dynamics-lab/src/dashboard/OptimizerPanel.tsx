import { useState } from 'react';
import { useApp } from '../state/store';
import { analysisWorker, proxy } from '../workers/client';
import { OBJECTIVE_LABELS, Objective, ParetoPoint, TuningResult, DEFAULT_SCATTER } from '../physics/optimize';
import { Chart, COLORS } from './Chart';
import { Progress, Section, Slider } from './controls';
import { fmt, fmtEuro } from './format';

const MASS_RATIOS = [0.0025, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04];

export function OptimizerPanel() {
  const s = useApp();
  const [busy, setBusy] = useState<'opt' | 'pareto' | null>(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<TuningResult | null>(null);
  const [pareto, setPareto] = useState<ParetoPoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy('opt');
    setProgress(0);
    setError(null);
    try {
      const r = await analysisWorker().optimize(s.sea, s.wind, s.objective, s.constraints, s.tmd, proxy(setProgress));
      setResult(r);
    } catch (e) {
      setError(String(e));
    }
    setBusy(null);
  };
  const runPareto = async () => {
    setBusy('pareto');
    setProgress(0);
    setError(null);
    try {
      setPareto(await analysisWorker().pareto(s.sea, s.wind, s.objective, s.constraints, s.tmd, MASS_RATIOS, proxy(setProgress)));
    } catch (e) {
      setError(String(e));
    }
    setBusy(null);
  };

  return (
    <>
      <Section title="Objective & constraints">
        <div className="field">
          <div className="field-label">Minimise</div>
          <select value={s.objective} onChange={(e) => s.set({ objective: e.target.value as Objective })}>
            {(Object.keys(OBJECTIVE_LABELS) as Objective[]).map((k) => (
              <option key={k} value={k}>
                {OBJECTIVE_LABELS[k]}
              </option>
            ))}
          </select>
        </div>
        {s.objective === 'robust' && (
          <ul className="muted small list">
            {DEFAULT_SCATTER.map((c) => (
              <li key={c.name}>
                {c.name}: Hs {c.sea.height} m, Tp {c.sea.period} s, wind {c.wind.speed} m/s ({Math.round(c.weight * 100)}%)
              </li>
            ))}
          </ul>
        )}
        <Slider
          label="Max damper mass"
          value={s.constraints.maxMassRatio * 100}
          min={0.25}
          max={5}
          step={0.25}
          unit="% of system"
          digits={2}
          onChange={(v) => s.set({ constraints: { ...s.constraints, maxMassRatio: v / 100 } })}
        />
        <Slider
          label="Max damper rotation (3 h expected)"
          value={s.constraints.maxStrokeDeg}
          min={10}
          max={120}
          step={5}
          unit="°"
          digits={0}
          onChange={(v) => s.set({ constraints: { ...s.constraints, maxStrokeDeg: v } })}
        />
        <p className="muted small">
          Tunes f and ζ for the current damper geometry ({fmt(s.tmd.mass / 1000, 0)} t, CM offset {fmt(s.tmd.arm, 1)} m). Start: Den Hartog,
          then a coarse grid, then Nelder–Mead. Constraint violations are penalised; a spring that would need negative stiffness is
          infeasible.
        </p>
        <div className="row">
          <button className="primary" disabled={!!busy} onClick={run}>
            Optimise tuning
          </button>
          <button disabled={!!busy} onClick={runPareto}>
            Mass trade-off sweep
          </button>
        </div>
        {busy && <Progress value={progress} label={busy === 'opt' ? 'Optimising…' : 'Sweeping damper mass…'} />}
        {error && <p className="warn">{error}</p>}
      </Section>

      {result && (
        <Section title="Optimum">
          <dl className="facts">
            <dt>Frequency ratio f</dt>
            <dd>
              {fmt(result.design.freqRatio, 3)} <small className="muted">(Den Hartog {fmt(result.start.freqRatio, 3)})</small>
            </dd>
            <dt>Damping ratio ζ</dt>
            <dd>
              {fmt(result.design.dampingRatio, 3)} <small className="muted">(Den Hartog {fmt(result.start.dampingRatio, 3)})</small>
            </dd>
            <dt>Objective vs no TMD</dt>
            <dd className={result.evaluation.ratio < 1 ? 'good-text' : 'bad-text'}>
              {result.evaluation.ratio < 1 ? '▼' : '▲'} {fmt((result.evaluation.ratio - 1) * 100, 1)}%
            </dd>
            <dt>Damper rotation</dt>
            <dd>{fmt(result.evaluation.strokeDeg, 0)}°</dd>
            <dt>Rough cost</dt>
            <dd>{fmtEuro(result.cost)}</dd>
            <dt>Evaluations</dt>
            <dd>{result.evaluations}</dd>
          </dl>
          {result.evaluation.violations.length > 0 ? (
            <p className="warn">⚠ Constraints not met: {result.evaluation.violations.join('; ')}. The best compromise is shown.</p>
          ) : (
            <p className="muted small">All constraints satisfied.</p>
          )}
          {result.evaluation.ratio >= 1 && (
            <p className="warn">
              In these conditions no tuning of this damper beats having no damper: the best achievable is a change of{' '}
              {fmt((result.evaluation.ratio - 1) * 100, 1)}%.
            </p>
          )}
          <button onClick={() => s.setTmd({ freqRatio: result.design.freqRatio, dampingRatio: result.design.dampingRatio })}>
            Apply to damper
          </button>
        </Section>
      )}

      {pareto && (
        <Section title="Benefit vs damper mass (each point re-optimised)">
          <Chart
            data={[pareto.map((p) => p.massRatio * 100), pareto.map((p) => p.reductionPct)] as never}
            series={[{ label: 'Reduction', color: COLORS.withTmd, points: true }]}
            xLabel="Damper mass [% of system]"
            yLabel="Objective reduction [%]"
            height={180}
            fmtX={(v) => v.toFixed(2)}
            fmtY={(v) => v.toFixed(1)}
          />
          <table className="metrics">
            <thead>
              <tr>
                <th>Mass</th>
                <th>f / ζ</th>
                <th>Reduction</th>
                <th>Rotation</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {pareto.map((p) => (
                <tr key={p.massRatio}>
                  <td>
                    {fmt(p.mass / 1000, 0)} t <small className="muted">({fmt(p.massRatio * 100, 2)}%)</small>
                  </td>
                  <td className="num">
                    {fmt(p.design.freqRatio, 2)} / {fmt(p.design.dampingRatio, 2)}
                  </td>
                  <td className="num">{fmt(p.reductionPct, 1)}%</td>
                  <td className="num">
                    {fmt(p.strokeDeg, 0)}°{!p.feasible && ' ⚠'}
                  </td>
                  <td className="num">{fmtEuro(p.cost)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">⚠ = stroke or spring constraint violated at that mass. Costs are order-of-magnitude placeholders.</p>
        </Section>
      )}
    </>
  );
}
