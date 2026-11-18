import { useEffect, useState } from 'react';
import type { PasalResult } from '../../lab/types';
import { VERDICT, humanize, results, sampleById, storageGet, storageSet } from './util';

type Answers = Record<string, { choice: string; note?: string }>;
const KEY = 'hukumos.review.v1';

/** Reviewer mode for lawyers: no Lean, only the text and what the translation concludes. */
export function Review({ pasalId, onPasal }: { pasalId: string; onPasal: (id: string) => void }) {
  const [answers, setAnswers] = useState<Answers>(() => storageGet<Answers>(KEY, {}));
  useEffect(() => storageSet(KEY, answers), [answers]);

  const r = results.pasal.find((p) => p.pasal.id === pasalId) ?? results.pasal[0];
  const queue = [...results.pasal].sort((a, b) => rank(a) - rank(b));
  const set = (k: string, choice: string) => setAnswers((a) => ({ ...a, [k]: { ...a[k], choice } }));
  const note = (k: string, text: string) => setAnswers((a) => ({ ...a, [k]: { choice: a[k]?.choice ?? '', note: text } }));
  const done = Object.values(answers).filter((a) => a.choice).length;

  const download = () => {
    const blob = new Blob([JSON.stringify({ benchmark: results.benchmark.id, answeredAt: new Date().toISOString(), answers }, null, 2)], {
      type: 'application/json',
    });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'tinjauan-hukumos.json';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const rep = sampleById(r, r.representative);
  const reps = r.groups.filter((g) => g.consistentWithText).map((g) => sampleById(r, g.members[0]));

  return (
    <div className="review">
      <aside className="review__queue">
        <div className="pane__title">Antrian tinjauan</div>
        {queue.map((p) => (
          <button key={p.pasal.id} className={`queue__item ${p.pasal.id === r.pasal.id ? 'queue__item--on' : ''}`} onClick={() => onPasal(p.pasal.id)}>
            <span>{p.pasal.cite}</span>
            <small className={`tone--${VERDICT[p.verdict].tone}`}>
              {VERDICT[p.verdict].icon} {VERDICT[p.verdict].label}
            </small>
          </button>
        ))}
        <p className="muted small">{done} jawaban tersimpan di peramban ini.</p>
        <button className="btn" onClick={download} disabled={done === 0}>
          Unduh jawaban (JSON)
        </button>
      </aside>

      <div className="review__main stack">
        <p className="muted small">
          Mode peninjau: tanpa kode. Bacalah pasal, lalu nilai apakah kesimpulan terjemahan sesuai. Jawaban hanya disimpan di peramban ini; unduh dan kirimkan ke
          tim.
        </p>
        <section className="card">
          <div className="eyebrow">UU 14/2008</div>
          <h2>{r.pasal.cite}</h2>
          <p className="lawtext">{r.pasal.text}</p>
          {r.pasal.context && <p className="context">Konteks: {r.pasal.context}</p>}
        </section>

        {r.pasal.scenarios.map((sc) => {
          const k = `${r.pasal.id}/${sc.id}`;
          const a = answers[k];
          if (sc.readings) {
            const options = [...Object.keys(sc.readings), 'Keduanya mungkin: teks ambigu', 'Tidak tahu'];
            return (
              <section key={sc.id} className="card question">
                <div className="eyebrow">Penerjemah tidak sepakat</div>
                <h3 className="h3">{sc.desc}</h3>
                <ul className="readings">
                  {reps.map((s, i) => (
                    <li key={i}>
                      Bacaan {String.fromCharCode(65 + i)}: <strong>{humanize(r.pasal.returns, s.scenarioOutputs[sc.id])}</strong>
                      {s.readingsChosen[sc.id] && s.readingsChosen[sc.id] !== 'lain' ? ` (${s.readingsChosen[sc.id]})` : ''}
                    </li>
                  ))}
                </ul>
                <p>Bacaan mana yang benar menurut Anda?</p>
                <Choices options={options} value={a?.choice} onChange={(c) => set(k, c)} />
                <textarea placeholder="Catatan (opsional): dasar hukum, putusan, peraturan pelaksana…" value={a?.note ?? ''} onChange={(e) => note(k, e.target.value)} />
              </section>
            );
          }
          return (
            <section key={sc.id} className="card question">
              <h3 className="h3">{sc.desc}</h3>
              <p>
                Menurut terjemahan: <strong>{humanize(r.pasal.returns, rep.scenarioOutputs[sc.id])}</strong>
              </p>
              <p>Apakah ini sesuai dengan pasal?</p>
              <Choices options={['Sesuai', 'Tidak sesuai', 'Tergantung tafsir']} value={a?.choice} onChange={(c) => set(k, c)} />
              {a?.choice && a.choice !== 'Sesuai' && (
                <textarea placeholder="Apa jawaban yang benar, dan mengapa?" value={a?.note ?? ''} onChange={(e) => note(k, e.target.value)} />
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function Choices({ options, value, onChange }: { options: string[]; value?: string; onChange: (v: string) => void }) {
  return (
    <div className="choices" role="radiogroup">
      {options.map((o) => (
        <button key={o} role="radio" aria-checked={value === o} className={`choice ${value === o ? 'choice--on' : ''}`} onClick={() => onChange(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

function rank(p: PasalResult): number {
  return { mungkin_ambigu: 0, bermasalah: 1, gagal: 2, setia: 3 }[p.verdict];
}
