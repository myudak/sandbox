import { useMemo, useState } from 'react';
import type { PasalResult, Sample } from '../../lab/types';
import { Disagreement } from './Disagreement';
import { Perturbations } from './Perturbations';
import {
  VERDICT,
  argsText,
  codeLines,
  groupOf,
  humanize,
  locateQuotes,
  sampleById,
  segments,
} from './util';

type Sub = 'terjemahan' | 'ubah' | 'beda' | 'baseline';

export function PasalView({ r, onReview }: { r: PasalResult; onReview: () => void }) {
  const [sub, setSub] = useState<Sub>('terjemahan');
  const [sampleId, setSampleId] = useState(r.representative);
  const v = VERDICT[r.verdict];
  const pertFails = r.perturbations.filter((p) => !p.pass).length;

  return (
    <div className="pasal">
      <header className="pasal__head">
        <div>
          <div className="eyebrow">UU 14/2008</div>
          <h1>{r.pasal.cite}</h1>
        </div>
        <div className={`verdict verdict--${v.tone}`}>
          <span className="verdict__label">
            {v.icon} {v.label}
          </span>
          <span className="verdict__reason">{r.verdictReason}</span>
        </div>
      </header>

      <nav className="subtabs" role="tablist">
        {(
          [
            ['terjemahan', 'Terjemahan'],
            ['ubah', `Uji ubah teks${pertFails ? ` · ${pertFails} gagal` : ''}`],
            ['beda', `Perbedaan · ${r.groups.length} kelompok`],
            ['baseline', 'Baseline'],
          ] as [Sub, string][]
        ).map(([id, label]) => (
          <button key={id} role="tab" aria-selected={sub === id} className="subtab" onClick={() => setSub(id)}>
            {label}
          </button>
        ))}
      </nav>

      {sub === 'terjemahan' && <Translation r={r} sampleId={sampleId} onSample={setSampleId} />}
      {sub === 'ubah' && <Perturbations r={r} />}
      {sub === 'beda' && <Disagreement r={r} onReview={onReview} onSample={(id) => (setSampleId(id), setSub('terjemahan'))} />}
      {sub === 'baseline' && <Baseline r={r} />}
    </div>
  );
}

function Translation({ r, sampleId, onSample }: { r: PasalResult; sampleId: string; onSample: (id: string) => void }) {
  const s = sampleById(r, sampleId);
  const lines = useMemo(() => codeLines(s.code), [s.code]);
  const { ranges, missing } = useMemo(() => locateQuotes(r.pasal.text, lines.flatMap((l) => l.quotes)), [r.pasal.text, lines]);
  const [hover, setHover] = useState<string[]>([]);
  const lit = (qs: string[]) => qs.some((q) => hover.includes(q));

  return (
    <div className="triptych">
      <section className="pane pane--text">
        <div className="pane__title">Teks pasal</div>
        <p className="lawtext">
          {segments(r.pasal.text, ranges).map((seg, i) =>
            seg.quotes.length ? (
              <mark
                key={i}
                className={`span ${lit(seg.quotes) ? 'span--lit' : ''}`}
                onMouseEnter={() => setHover(seg.quotes)}
                onMouseLeave={() => setHover([])}
              >
                {seg.text}
              </mark>
            ) : (
              <span key={i}>{seg.text}</span>
            ),
          )}
        </p>
        {r.pasal.context && <p className="context">Konteks: {r.pasal.context}</p>}
        {!r.pasal.verified && <p className="note note--gap small">Teks masih parafrase, belum dicocokkan dengan teks resmi.</p>}
        {missing.length > 0 && (
          <div className="note note--bad small">
            Kutipan di kode yang tidak ada di teks:
            <ul>
              {missing.map((q) => (
                <li key={q}>“{q}”</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="pane pane--code">
        <div className="pane__title row row--between">
          <span>Lean</span>
          <SamplePicker r={r} current={s.id} onPick={onSample} />
        </div>
        <pre className="code">
          {lines.map((l) => (
            <div
              key={l.n}
              className={`code__line ${l.quotes.length ? 'code__line--linked' : ''} ${lit(l.quotes) ? 'code__line--lit' : ''}`}
              onMouseEnter={() => l.quotes.length && setHover(l.quotes)}
              onMouseLeave={() => setHover([])}
            >
              <span className="code__n">{l.n}</span>
              <code>{l.text || ' '}</code>
            </div>
          ))}
        </pre>
        {!s.typechecks && <pre className="code code--error">{s.error}</pre>}
        <p className="muted small">Arahkan kursor ke frasa yang disorot atau baris kode untuk melihat pasangannya.</p>
      </section>

      <section className="pane pane--result">
        <div className="pane__title">Hasil</div>
        <Metrics r={r} />
        <SampleChecks r={r} s={s} />
      </section>
    </div>
  );
}

function SamplePicker({ r, current, onPick }: { r: PasalResult; current: string; onPick: (id: string) => void }) {
  return (
    <div className="chips" role="group" aria-label="Pilih sampel terjemahan">
      {r.samples.map((s, i) => {
        const g = groupOf(r, s.id);
        return (
          <button
            key={s.id}
            className={`chip ${s.id === current ? 'chip--on' : ''} ${!s.typechecks ? 'chip--bad' : ''}`}
            onClick={() => onPick(s.id)}
            title={g ? `Sampel ${i + 1}, kelompok ${g}` : `Sampel ${i + 1}, tidak lolos typecheck`}
          >
            #{i + 1}
            <small>{g ?? '✗'}</small>
          </button>
        );
      })}
    </div>
  );
}

function Metrics({ r }: { r: PasalResult }) {
  const rows: [string, [number, number], string][] = [
    ['Typecheck', r.metrics.typecheck, 'Lean menerima kode'],
    ['Skenario', r.metrics.scenarios, 'Hasil sama dengan jawaban yang diharapkan'],
    ['Uji ubah teks', r.metrics.perturbations, 'Terjemahan ikut berubah saat teks diubah'],
    ['Kesepakatan', r.metrics.agreement, 'Sampel dalam kelompok terbesar'],
    ['Setara baseline', r.metrics.equivalent, 'Dibuktikan Lean untuk semua input'],
    ['Properti', r.metrics.properties, 'Properti terbukti di Lean'],
  ];
  return (
    <dl className="metrics">
      {rows.map(([label, [a, b], hint]) => (
        <div key={label} className="metric" title={hint}>
          <dt>{label}</dt>
          <dd className={a === b ? 'ok' : 'warnc'}>
            {a}/{b}
          </dd>
        </div>
      ))}
    </dl>
  );
}

const PROOF = { terbukti: '✓ terbukti', berbeda: '✗ berbeda', tidak_diketahui: '? tidak terbukti' };

function SampleChecks({ r, s }: { r: PasalResult; s: Sample }) {
  if (!s.typechecks) return <p className="note note--bad small">Sampel ini tidak lolos typecheck, jadi tidak dijalankan.</p>;
  return (
    <>
      <h3 className="h3">Skenario (sampel ini)</h3>
      <table className="table">
        <tbody>
          {r.pasal.scenarios.map((sc) => {
            const got = s.scenarioOutputs[sc.id];
            const ok = !s.failedScenarios.includes(sc.id);
            return (
              <tr key={sc.id}>
                <td className={ok ? 'ok' : 'bad'}>{sc.readings ? '◐' : ok ? '✓' : '✗'}</td>
                <td>
                  {sc.desc}
                  <div className="muted small">{argsText(r, sc.args)}</div>
                  {sc.readings && <div className="small warnc">Ambigu: memilih “{s.readingsChosen[sc.id]}”</div>}
                </td>
                <td className="num">
                  {humanize(r.pasal.returns, got)}
                  {sc.expect !== undefined && !ok && <div className="small muted">harap: {humanize(r.pasal.returns, sc.expect)}</div>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h3 className="h3">Bukti Lean</h3>
      <table className="table">
        <tbody>
          <tr>
            <td>Setara dengan baseline</td>
            <td className="num">{PROOF[s.equivalence]}</td>
          </tr>
          {r.pasal.properties.map((p) => (
            <tr key={p.id}>
              <td>
                {p.desc}
                <div className="muted small mono">{p.statement}</div>
              </td>
              <td className="num">{PROOF[s.properties[p.id] ?? 'tidak_diketahui']}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Baseline({ r }: { r: PasalResult }) {
  return (
    <div className="stack narrow">
      <p className="muted">
        Terjemahan acuan yang ditulis tangan (<code>lean/HukumOS/Kip/Baku.lean</code>). Kesetaraan setiap sampel dengan definisi ini dicoba dibuktikan oleh Lean.
        Untuk skenario yang ambigu, baseline memilih satu bacaan, dan bacaan itu tidak dinilai.
      </p>
      <pre className="code code--block">{r.baselineCode}</pre>
    </div>
  );
}
