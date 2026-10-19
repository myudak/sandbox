import { useEffect, useState } from 'react';
import { analysisWorker, proxy } from '../workers/client';
import type { Check } from '../physics/validation';
import { Progress, Section } from './controls';

export function ValidationPanel() {
  const [checks, setChecks] = useState<Check[] | null>(null);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    setProgress(0);
    setChecks(await analysisWorker().validate(proxy(setProgress)));
    setBusy(false);
  };
  useEffect(() => {
    run();
  }, []);
  const groups = checks ? [...new Set(checks.map((c) => c.group))] : [];
  const passed = checks?.filter((c) => c.pass).length ?? 0;
  return (
    <>
      <Section
        title="Validation suite"
        aside={
          <button disabled={busy} onClick={run}>
            Re-run
          </button>
        }
      >
        <p className="muted small">
          Runs in your browser against the same code that drives the simulation. The same checks run as unit tests (<code>npm test</code>).
        </p>
        {busy && <Progress value={progress} label="Running checks…" />}
        {checks && (
          <p className={passed === checks.length ? 'good-text' : 'bad-text'}>
            {passed === checks.length ? '✔' : '✖'} {passed} / {checks.length} checks pass
          </p>
        )}
      </Section>
      {groups.map((g) => (
        <Section key={g} title={g}>
          <ul className="checks">
            {checks!
              .filter((c) => c.group === g)
              .map((c) => (
                <li key={c.id}>
                  <div className="check-head">
                    <span>{c.name}</span>
                    <span className={c.pass ? 'good-text' : 'bad-text'}>{c.pass ? '✔ pass' : '✖ fail'}</span>
                  </div>
                  <div className="check-vals">
                    <span>
                      Model <b>{c.value}</b>
                    </span>
                    <span>
                      Reference <b>{c.reference}</b>
                    </span>
                  </div>
                  {c.note && <div className="muted small">{c.note}</div>}
                </li>
              ))}
          </ul>
        </Section>
      ))}
      <Section title="Not yet validated">
        <ul className="small list">
          <li>Comparison against OpenFAST OC3-Hywind runs (RAOs and time series): planned for v2.</li>
          <li>Thrust curve and turbulence spectra are approximate digitisations; aero damping assumes a detuned controller.</li>
          <li>Second-order (slow-drift) wave loads, which also excite the pitch resonance, are not modelled.</li>
        </ul>
      </Section>
    </>
  );
}
