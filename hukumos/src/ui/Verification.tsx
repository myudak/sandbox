import { useMemo } from 'react';
import { CHECKS, type Category, type Finding, type Report, type Trace, fmtDays, explore, violations } from '../core/explore';
import { type Model, citation, provision } from '../core/ir';
import type { KipCtx } from '../models/uu-14-2008/model';
import { mutants, mutate } from '../models/uu-14-2008/mutants';
import type { Highlight } from './Graph';

const CATEGORY: Record<Category, { title: string; hint: string }> = {
  violation: {
    title: 'Pelanggaran',
    hint: 'Model melanggar aturan. Bisa bug model, bisa beda interpretasi; perlu ditinjau manusia.',
  },
  legal_gap_candidate: {
    title: 'Kandidat celah hukum',
    hint: 'Model setia pada teks, dan teks itu sendiri tidak mengatur sesuatu.',
  },
  interpretation: {
    title: 'Pilihan interpretasi',
    hint: 'Tempat teks tidak eksplisit dan pembuat model memilih satu bacaan.',
  },
};

export function highlightOf(f: { states?: string[]; transitions?: string[]; trace?: Trace }, tone: Highlight['tone']): Highlight {
  return {
    states: new Set([...(f.states ?? []), ...(f.trace?.steps.flatMap((s) => [s.from, s.to]) ?? [])]),
    transitions: new Set([...(f.transitions ?? []), ...(f.trace?.steps.map((s) => s.transitionId) ?? [])]),
    tone,
  };
}

export function Verification(props: {
  base: Model<KipCtx>;
  model: Model<KipCtx>;
  report: Report;
  mutantId: string | null;
  onMutant: (id: string | null) => void;
  onHighlight: (h: Highlight) => void;
  onCite: (sourceId: string) => void;
}) {
  const { base, model, report, mutantId, onMutant, onHighlight, onCite } = props;

  const score = useMemo(
    () =>
      mutants.map((m) => {
        const v = violations(explore(mutate(m, base)));
        return { m, caught: v.some((f) => m.expectedChecks.includes(f.check)), checks: [...new Set(v.map((f) => f.check))] };
      }),
    [base],
  );
  const caught = score.filter((s) => s.caught).length;
  const active = mutants.find((m) => m.id === mutantId);

  return (
    <div className="stack">
      <section className="card">
        <label className="field">
          <span>Model yang diperiksa</span>
          <select value={mutantId ?? ''} onChange={(e) => onMutant(e.target.value || null)}>
            <option value="">Model acuan (UU 14/2008)</option>
            <optgroup label="Mutan: cacat yang sengaja disuntikkan">
              {mutants.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        {active && (
          <p className="muted small">
            Cacat: {active.defect}. Diharapkan tertangkap oleh: {active.expectedChecks.map((c) => CHECKS[c as keyof typeof CHECKS] ?? c).join(' / ')}.
          </p>
        )}
        <p className="muted small">
          {report.stats.configurations} konfigurasi dan {report.stats.edges} transisi dijelajahi pada {report.stats.scenarios} skenario
          {report.stats.truncated ? ' (dihentikan: melewati batas ruang status)' : ''}.
        </p>
      </section>

      <section className="card">
        <h3>Batas waktu terburuk</h3>
        <table className="bounds">
          <tbody>
            {report.bounds.map((b) => {
              const ok = b.limit === undefined ? null : b.worstCase !== null && b.worstCase <= b.limit;
              return (
                <tr key={b.propertyId} onClick={() => b.trace && onHighlight(highlightOf({ trace: b.trace }, ok === false ? 'problem' : 'trace'))}>
                  <td>{ok === null ? '·' : ok ? '✓' : '✗'}</td>
                  <td>{b.description}</td>
                  <td className="num">
                    {fmtDays(b.worstCase)}
                    {b.limit !== undefined && <div className="muted small">batas {b.limit}</div>}
                  </td>
                </tr>
              );
            })}
            {report.bounds.length === 0 && (
              <tr>
                <td colSpan={3} className="muted">
                  Tidak dihitung (model memiliki siklus atau ruang status tak terbatas).
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <p className="muted small">Klik baris untuk melihat jalur kasus terburuk pada graf.</p>
      </section>

      {(Object.keys(CATEGORY) as Category[]).map((cat) => {
        const fs = report.findings.filter((f) => f.category === cat);
        return (
          <section key={cat} className={`card findings findings--${cat}`}>
            <h3>
              {CATEGORY[cat].title} <span className="count">{fs.length}</span>
            </h3>
            <p className="muted small">{CATEGORY[cat].hint}</p>
            {fs.length === 0 && <p className="muted">{cat === 'violation' ? '✓ Tidak ada.' : 'Tidak ada.'}</p>}
            <ul>
              {fs.map((f, i) => (
                <FindingItem key={i} f={f} model={model} onHighlight={onHighlight} onCite={onCite} />
              ))}
            </ul>
          </section>
        );
      })}

      <section className="card">
        <h3>
          Uji mutan <span className="count">{caught}/{mutants.length}</span>
        </h3>
        <p className="muted small">
          Setiap mutan adalah salinan model dengan satu cacat yang disengaja. Mutan tertangkap jika penjelajah melaporkan pelanggaran yang diharapkan.
        </p>
        <ul className="mutants">
          {score.map(({ m, caught, checks }) => (
            <li key={m.id}>
              <button className={`link ${m.id === mutantId ? 'active' : ''}`} onClick={() => onMutant(m.id)}>
                {caught ? '✓' : '✗'} {m.title}
              </button>
              <span className="muted small"> {checks.map((c) => CHECKS[c as keyof typeof CHECKS] ?? c).join(', ')}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function FindingItem(props: {
  f: Finding;
  model: Model<KipCtx>;
  onHighlight: (h: Highlight) => void;
  onCite: (id: string) => void;
}) {
  const { f, model, onHighlight, onCite } = props;
  const p = provision(model, f.source);
  const label = (id: string) => model.states.find((s) => s.id === id)?.label ?? id;
  return (
    <li className="finding">
      <button className="link finding__msg" onClick={() => onHighlight(highlightOf(f, f.category === 'violation' ? 'problem' : 'trace'))}>
        <span className="finding__check">{CHECKS[f.check as keyof typeof CHECKS] ?? f.check}</span>
        {f.message}
      </button>
      {p && (
        <button className="link small" onClick={() => onCite(p.id)}>
          {citation(p)}
        </button>
      )}
      {f.trace && f.trace.steps.length > 0 && (
        <details>
          <summary className="small">Contoh jalur ({f.trace.steps.length} langkah, skenario {f.trace.scenario})</summary>
          <ol className="trace small">
            <li>{label(f.trace.steps[0].from)}</li>
            {f.trace.steps.map((s, i) => (
              <li key={i}>
                → {model.transitions.find((t) => t.id === s.transitionId)?.label ?? s.transitionId} → {label(s.to)}
              </li>
            ))}
          </ol>
        </details>
      )}
    </li>
  );
}
