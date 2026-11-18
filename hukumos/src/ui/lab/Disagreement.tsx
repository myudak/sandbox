import type { PasalResult } from '../../lab/types';
import { argsText, humanize, sampleById } from './util';

export function Disagreement({ r, onReview, onSample }: { r: PasalResult; onReview: () => void; onSample: (id: string) => void }) {
  const total = r.samples.length;
  const failed = r.samples.filter((s) => !s.typechecks);
  const ambiguous = r.pasal.scenarios.filter((s) => s.readings);
  const reps = r.groups.map((g) => sampleById(r, g.members[0]));

  if (r.groups.length <= 1) {
    return (
      <div className="stack narrow">
        <p>
          {r.groups.length === 1 ? `Semua ${r.groups[0].members.length} sampel yang lolos typecheck berperilaku sama pada semua skenario dan ${r.probes.length} input uji.` : 'Tidak ada sampel yang lolos typecheck.'}
        </p>
        {failed.length > 0 && <p className="muted">{failed.length} sampel tidak lolos typecheck dan tidak dibandingkan.</p>}
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <h3 className="h3">
          {total} terjemahan, {r.groups.length} kelompok perilaku
        </h3>
        <p className="muted small">Sampel dikelompokkan menurut hasilnya pada semua skenario dan {r.probes.length} input uji yang dibuat otomatis.</p>
        <div className="groups">
          {r.groups.map((g, i) => {
            const letter = String.fromCharCode(65 + i);
            const reading = Object.values(g.readings)[0];
            return (
              <div key={letter} className="group">
                <div className="group__label">
                  <strong>{letter}</strong>
                  <span>
                    {reading && reading !== 'lain' ? `“${reading}”` : g.consistentWithText ? 'sesuai skenario' : 'salah pada skenario yang jelas'}
                  </span>
                </div>
                <div className="bar" role="img" aria-label={`${g.members.length} dari ${total} sampel`}>
                  <div className="bar__fill" style={{ width: `${(g.members.length / total) * 100}%` }} />
                  <span className="bar__value">
                    {g.members.length}/{total}
                  </span>
                </div>
                <div className="chips">
                  {g.members.map((m) => (
                    <button key={m} className="chip" onClick={() => onSample(m)}>
                      {m.split('#')[1] ? `#${m.split('#')[1]}` : m}
                    </button>
                  ))}
                  {!g.consistentWithText && <span className="small bad">bukan kandidat ambiguitas</span>}
                </div>
              </div>
            );
          })}
          {failed.length > 0 && <p className="muted small">{failed.length} sampel tidak lolos typecheck dan tidak dikelompokkan.</p>}
        </div>
      </section>

      {ambiguous.length > 0 && (
        <section className="card">
          <h3 className="h3">Skenario pembeda</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Skenario</th>
                {reps.map((_, i) => (
                  <th key={i} className="num">
                    Kelompok {String.fromCharCode(65 + i)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ambiguous.map((sc) => (
                <tr key={sc.id}>
                  <td>
                    {sc.desc}
                    <div className="muted small">{argsText(r, sc.args)}</div>
                  </td>
                  {reps.map((s, i) => (
                    <td key={i} className="num">
                      {humanize(r.pasal.returns, s.scenarioOutputs[sc.id])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {r.verdict === 'mungkin_ambigu' && (
            <div className="callout">
              <p>
                Lebih dari satu kelompok sesuai dengan semua skenario yang jelas, tetapi berbeda di sini. Itu tanda <strong>teksnya sendiri</strong> bisa dibaca lebih
                dari satu cara, bukan sekadar kesalahan penerjemah.
              </p>
              <button className="btn btn--primary" onClick={onReview}>
                Kirim ke peninjau hukum →
              </button>
            </div>
          )}
        </section>
      )}

      {r.distinguishingProbes.length > 0 && (
        <section className="card">
          <h3 className="h3">Input uji yang membedakan ({r.distinguishingProbes.length})</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Input</th>
                {reps.map((_, i) => (
                  <th key={i} className="num">
                    {String.fromCharCode(65 + i)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.distinguishingProbes.slice(0, 8).map((pi) => (
                <tr key={pi}>
                  <td className="mono small">{argsText(r, r.probes[pi])}</td>
                  {reps.map((s, i) => (
                    <td key={i} className="num">
                      {humanize(r.pasal.returns, s.probeOutputs[pi])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
