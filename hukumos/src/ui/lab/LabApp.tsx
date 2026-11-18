import { useEffect, useState } from 'react';
import { ProcedureApp } from '../ProcedureApp';
import { Dashboard } from './Dashboard';
import { PasalView } from './PasalView';
import { Review } from './Review';
import { VERDICT, results } from './util';

type View = 'pasal' | 'ringkasan' | 'tinjauan' | 'prosedur';

function readHash(): { view: View; pasal: string } {
  const [view, pasal] = window.location.hash.replace(/^#\/?/, '').split('/');
  const views: View[] = ['pasal', 'ringkasan', 'tinjauan', 'prosedur'];
  return {
    view: views.includes(view as View) ? (view as View) : 'pasal',
    pasal: results.pasal.some((p) => p.pasal.id === pasal) ? pasal : results.pasal[0].pasal.id,
  };
}

export function LabApp() {
  const [{ view, pasal }, setRoute] = useState(readHash);
  useEffect(() => {
    const on = () => setRoute(readHash());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const go = (v: View, p = pasal) => {
    window.location.hash = `/${v}/${p}`;
  };

  const r = results.pasal.find((x) => x.pasal.id === pasal)!;

  return (
    <div className="lab">
      <header className="topbar">
        <div className="brand">
          <strong>HukumOS</strong>
          <span className="muted">Dari pasal ke Lean, dan seberapa setia hasilnya</span>
        </div>
        <nav className="tabs" role="tablist">
          {(
            [
              ['pasal', 'Pasal'],
              ['ringkasan', 'Ringkasan'],
              ['tinjauan', 'Tinjauan'],
              ['prosedur', 'Prosedur'],
            ] as [View, string][]
          ).map(([id, label]) => (
            <button key={id} role="tab" aria-selected={view === id} className="tab" onClick={() => go(id)}>
              {label}
            </button>
          ))}
        </nav>
      </header>

      {results.illustrative && view !== 'prosedur' && (
        <div className="banner banner--warn">
          <strong>Data contoh.</strong> Terjemahan di sini ditulis tangan untuk mendemokan alur, bukan keluaran LLM. Pemeriksaan Lean-nya nyata. Jalankan{' '}
          <code>npm run lab -- --llm</code> untuk terjemahan Claude.
        </div>
      )}

      {view === 'prosedur' ? (
        <div className="procedure-host">
          <ProcedureApp />
        </div>
      ) : (
        <div className="lab__body">
          {view === 'pasal' && (
            <div className="workspace">
              <aside className="sidebar" aria-label="Daftar pasal">
                <div className="pane__title">UU 14/2008 · {results.pasal.length} pasal</div>
                {results.pasal.map((p) => {
                  const v = VERDICT[p.verdict];
                  return (
                    <button key={p.pasal.id} className={`side__item ${p.pasal.id === pasal ? 'side__item--on' : ''}`} onClick={() => go('pasal', p.pasal.id)}>
                      <span>{p.pasal.cite}</span>
                      <small className={`tone--${v.tone}`}>
                        {v.icon} {v.label}
                      </small>
                    </button>
                  );
                })}
              </aside>
              <main className="workspace__main">
                <PasalView key={r.pasal.id} r={r} onReview={() => go('tinjauan', r.pasal.id)} />
              </main>
            </div>
          )}
          {view === 'ringkasan' && (
            <main className="page">
              <Dashboard onPasal={(id) => go('pasal', id)} />
            </main>
          )}
          {view === 'tinjauan' && (
            <main className="page">
              <Review pasalId={pasal} onPasal={(id) => go('tinjauan', id)} />
            </main>
          )}
          <footer className="foot">
            {results.translator} · {results.samplesPerPasal} sampel per pasal · {results.leanVersion} · dibuat {results.generatedAt.slice(0, 10)}. {results.benchmark.note}
          </footer>
        </div>
      )}
    </div>
  );
}
