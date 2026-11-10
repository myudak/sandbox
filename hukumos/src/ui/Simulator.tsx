import { useState } from 'react';
import { addDays, workingDaysBetween } from '../core/calendar';
import { currentState, dueDate, enabledTransitions, fire, type Run } from '../core/engine';
import { type Model, TIMEOUT, citation, provision } from '../core/ir';
import type { KipCtx } from '../models/uu-14-2008/model';
import { fmtDate } from './format';

export function Simulator(props: {
  model: Model<KipCtx>;
  run: Run<KipCtx>;
  scenarioId: string;
  startDate: string;
  onRun: (r: Run<KipCtx>) => void;
  onReset: (scenarioId: string, startDate: string) => void;
  onCite: (sourceId: string) => void;
}) {
  const { model, run, scenarioId, startDate, onRun, onReset, onCite } = props;
  const [actDate, setActDate] = useState<string>(run.enteredAt);
  const [error, setError] = useState<string | null>(null);

  let state;
  try {
    state = currentState(model, run);
  } catch {
    return <p className="error">Status saat ini tidak ada di model ini. Mulai ulang simulasi.</p>;
  }
  const due = dueDate(model, run);
  const options = enabledTransitions(model, run);
  const actions = options.filter((t) => t.event !== TIMEOUT);
  const timeouts = options.filter((t) => t.event === TIMEOUT);
  const deadlineSrc = provision(model, state.deadline?.source);
  const date = actDate < run.enteredAt ? run.enteredAt : actDate;

  const go = (tid: string, at: string) => {
    const r = fire(model, run, tid, at);
    if (r.ok) {
      setError(null);
      setActDate(r.run.enteredAt);
      onRun(r.run);
    } else setError(r.error);
  };

  const remaining = due ? workingDaysBetween(date, due) : null;

  return (
    <div className="stack">
      <section className="card">
        <div className="row">
          <label className="field">
            <span>Skenario</span>
            <select value={scenarioId} onChange={(e) => onReset(e.target.value, startDate)}>
              {model.scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Permohonan diterima</span>
            <input type="date" value={startDate} onChange={(e) => e.target.value && onReset(scenarioId, e.target.value)} />
          </label>
        </div>
      </section>

      <section className={`card current ${state.terminal ? 'current--done' : ''}`}>
        <div className="eyebrow">{state.terminal ? 'Status akhir' : 'Status saat ini'}</div>
        <h2>{state.label}</h2>
        {state.description && <p className="muted">{state.description}</p>}
        {!state.terminal && (
          <dl className="facts">
            <dt>Yang bertindak</dt>
            <dd>{state.actors?.map((a) => model.actors[a]?.label ?? a).join(', ') || '—'}</dd>
            <dt>Mulai dihitung</dt>
            <dd>{fmtDate(run.enteredAt)}</dd>
            {state.deadline && due && (
              <>
                <dt>{state.deadline.kind === 'obligation' ? 'Wajib bertindak paling lambat' : 'Dapat bertindak sampai'}</dt>
                <dd>
                  <strong>{fmtDate(due)}</strong> ({state.deadline.workingDays} hari kerja)
                  {deadlineSrc && (
                    <>
                      {' · '}
                      <button className="link" onClick={() => onCite(deadlineSrc.id)}>
                        {citation(deadlineSrc)}
                      </button>
                    </>
                  )}
                </dd>
              </>
            )}
          </dl>
        )}
        {state.expiryGap && <p className="note note--gap">⚠ {state.expiryGap}</p>}
        {state.deadline?.interpretation && <p className="note note--interp">~ Interpretasi: {state.deadline.interpretation}</p>}
      </section>

      {!state.terminal && (
        <section className="card">
          <label className="field">
            <span>Tanggal tindakan</span>
            <input type="date" value={date} min={run.enteredAt} onChange={(e) => e.target.value && setActDate(e.target.value)} />
          </label>
          {remaining !== null && due && (
            <p className={`muted small ${date > due ? 'late' : ''}`}>
              {date > due ? `Batas waktu sudah lewat pada ${fmtDate(due)}.` : `Sisa ${remaining} hari kerja sampai batas waktu.`}
            </p>
          )}
          <div className="actions">
            {actions.map((t) => (
              <button key={t.id} className="btn" onClick={() => go(t.id, date)}>
                <span>{t.label}</span>
                <small>{model.actors[t.actor]?.label ?? t.actor}</small>
              </button>
            ))}
            {timeouts.map((t) => (
              <button key={t.id} className="btn btn--ghost" onClick={() => due && go(t.id, addDays(due, 1))}>
                <span>⏱ Biarkan batas waktu lewat</span>
                <small>{t.label}</small>
              </button>
            ))}
          </div>
          {actions.length === 0 && timeouts.length === 0 && <p className="error">Jalan buntu: tidak ada tindakan yang mungkin.</p>}
          {error && <p className="error">{error}</p>}
        </section>
      )}

      <section className="card">
        <div className="row row--between">
          <h3>Riwayat</h3>
          <button className="link" onClick={() => onReset(scenarioId, startDate)}>
            Mulai ulang
          </button>
        </div>
        <ol className="timeline">
          <li>
            <span className="timeline__date">{fmtDate(startDate)}</span>
            <span>Permohonan diterima</span>
          </li>
          {run.history.map((h, i) => {
            const t = model.transitions.find((x) => x.id === h.transitionId);
            const p = provision(model, t?.source);
            const to = model.states.find((s) => s.id === h.to);
            return (
              <li key={i}>
                <span className="timeline__date">{fmtDate(h.at)}</span>
                <span>
                  {t?.event === TIMEOUT ? '⏱ ' : ''}
                  {t?.label ?? h.transitionId} → <strong>{to?.label ?? h.to}</strong>
                  {p && (
                    <>
                      {' '}
                      <button className="link small" onClick={() => onCite(p.id)}>
                        {citation(p)}
                      </button>
                    </>
                  )}
                </span>
              </li>
            );
          })}
        </ol>
        {run.history.length > 0 && (
          <p className="muted small">Total {workingDaysBetween(startDate, run.enteredAt)} hari kerja sejak permohonan.</p>
        )}
      </section>
    </div>
  );
}
