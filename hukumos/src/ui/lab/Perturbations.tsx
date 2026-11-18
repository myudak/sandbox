import type { PasalResult } from '../../lab/types';
import { humanize, lineDiff, sampleById } from './util';

export function Perturbations({ r }: { r: PasalResult }) {
  const base = sampleById(r, r.representative);
  return (
    <div className="stack">
      <p className="muted narrow">
        Teks pasal diubah sedikit, lalu diterjemahkan ulang. Terjemahan yang setia harus ikut berubah, dan berubah dengan benar. Kiri: perubahan teks. Kanan: perubahan
        kode dibanding terjemahan teks asli (sampel {r.representative}).
      </p>
      {r.perturbations.map((p) => {
        // Compare code without comments: a changed quote alone is not a changed translation.
        const diff = p.sample.typechecks ? lineDiff(stripComments(base.code), stripComments(p.sample.code)) : [];
        const sameCode = diff.length > 0 && diff.every((d) => d.kind === 'same');
        const t = findText(r.pasal.text, p.textAfter);
        const tone = p.pass ? 'good' : 'bad';
        const message = p.pass
          ? 'Terjemahan berubah sesuai perubahan teks.'
          : !p.sample.typechecks
            ? 'Terjemahan teks yang diubah tidak lolos typecheck.'
            : p.changed
              ? 'Terjemahan berubah, tetapi tidak sesuai perubahan teks.'
              : 'Teks berubah, terjemahan tidak berubah: tidak setia.';
        return (
          <section key={p.id} className="card">
            <div className="row row--between">
              <h3 className="h3">{p.label}</h3>
              <span className={`verdict verdict--${tone} verdict--sm`}>
                <span className="verdict__label">
                  {p.pass ? '✓' : '✗'} {message}
                </span>
              </span>
            </div>
            <div className="diffs">
              <div>
                <div className="pane__title">Teks diubah</div>
                <div className="diff">
                  <div className="diff__line diff__line--del">
                    <span>−</span>
                    {t.before}
                  </div>
                  <div className="diff__line diff__line--add">
                    <span>+</span>
                    {t.after || '(dihapus)'}
                  </div>
                </div>
              </div>
              <div>
                <div className="pane__title">Lean berubah? (tanpa komentar)</div>
                <pre className="diff diff--code">
                  {diff.length === 0 && <div className="diff__line">{p.sample.error ?? '—'}</div>}
                  {sameCode && <div className="diff__line diff__line--del"><span>=</span>Kode identik dengan terjemahan teks asli</div>}
                  {diff.map((d, i) => (
                    <div key={i} className={`diff__line diff__line--${d.kind}`}>
                      <span>{d.kind === 'add' ? '+' : d.kind === 'del' ? '−' : ' '}</span>
                      {d.text}
                    </div>
                  ))}
                </pre>
              </div>
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th />
                  <th>Skenario</th>
                  <th className="num">Harus</th>
                  <th className="num">Hasil</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(p.expect).map(([sid, want]) => {
                  const sc = r.pasal.scenarios.find((x) => x.id === sid);
                  const got = p.sample.scenarioOutputs[sid];
                  return (
                    <tr key={sid}>
                      <td className={got === want ? 'ok' : 'bad'}>{got === want ? '✓' : '✗'}</td>
                      <td>{sc?.desc ?? sid}</td>
                      <td className="num">{humanize(r.pasal.returns, want)}</td>
                      <td className="num">{humanize(r.pasal.returns, got)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        );
      })}
    </div>
  );
}

function stripComments(code: string): string {
  return code
    .split('\n')
    .map((l) => l.replace(/\s*--.*$/, ''))
    .filter((l) => l.trim() !== '')
    .join('\n');
}

/** The differing middle part of two strings. */
function findText(a: string, b: string): { before: string; after: string } {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  let j = 0;
  while (j < a.length - i && j < b.length - i && a[a.length - 1 - j] === b[b.length - 1 - j]) j++;
  // Widen to word boundaries so the diff reads naturally.
  const start = Math.max(0, a.lastIndexOf(' ', i - 1) + 1);
  const pad = (s: string, from: number, to: number) => s.slice(from, Math.min(s.length, to)).trim();
  const endA = a.indexOf(' ', a.length - j);
  const endB = b.indexOf(' ', b.length - j);
  return {
    before: pad(a, start, endA < 0 ? a.length : endA),
    after: pad(b, start, endB < 0 ? b.length : endB),
  };
}
