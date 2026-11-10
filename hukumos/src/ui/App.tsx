import { useMemo, useState } from 'react';
import { start, type Run } from '../core/engine';
import { explore } from '../core/explore';
import { TIMEOUT, citation, provision } from '../core/ir';
import { type KipCtx, kipModel } from '../models/uu-14-2008/model';
import { mutants, mutate } from '../models/uu-14-2008/mutants';
import { Graph, type Highlight, NO_HIGHLIGHT, type Selection } from './Graph';
import { Simulator } from './Simulator';
import { Sources } from './Sources';
import { Verification } from './Verification';

type Tab = 'sim' | 'pasal' | 'verif';

const today = () => new Date().toISOString().slice(0, 10);

export function App() {
  const [tab, setTab] = useState<Tab>('sim');
  const [mutantId, setMutantId] = useState<string | null>(null);
  const model = useMemo(() => {
    const m = mutants.find((x) => x.id === mutantId);
    return m ? mutate(m, kipModel) : kipModel;
  }, [mutantId]);
  const report = useMemo(() => explore(model), [model]);

  const [scenarioId, setScenarioId] = useState(kipModel.scenarios[0].id);
  const [startDate, setStartDate] = useState(today());
  const [epoch, setEpoch] = useState(0);
  const newRun = (sid: string, d: string): Run<KipCtx> =>
    start(model, (model.scenarios.find((s) => s.id === sid) ?? model.scenarios[0]).ctx, d);
  const [run, setRun] = useState<Run<KipCtx>>(() => newRun(scenarioId, startDate));

  const [highlight, setHighlight] = useState<Highlight>(NO_HIGHLIGHT);
  const [selection, setSelection] = useState<Selection>(null);
  const [focusSource, setFocusSource] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(false);

  const reset = (sid: string, d: string, m = model) => {
    setScenarioId(sid);
    setStartDate(d);
    setRun(start(m, (m.scenarios.find((s) => s.id === sid) ?? m.scenarios[0]).ctx, d));
    setEpoch((e) => e + 1);
    setHighlight(NO_HIGHLIGHT);
  };

  const chooseMutant = (id: string | null) => {
    setMutantId(id);
    const m = mutants.find((x) => x.id === id);
    reset(scenarioId, startDate, m ? mutate(m, kipModel) : kipModel);
  };

  const cite = (id: string) => {
    setFocusSource(id);
    setTab('pasal');
  };

  const visitedStates = new Set([kipModel.initial, ...run.history.map((h) => h.to)]);
  const visitedTransitions = new Set(run.history.map((h) => h.transitionId));
  const unreached = new Set(report.stats.truncated ? [] : model.states.map((s) => s.id).filter((id) => !report.reachedStates.includes(id)));
  const gaps = new Set(report.findings.filter((f) => f.category === 'legal_gap_candidate').flatMap((f) => f.states ?? []));
  const violationCount = report.findings.filter((f) => f.category === 'violation').length;

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <strong>HukumOS</strong>
          <span className="muted">{kipModel.law}</span>
        </div>
        <nav className="tabs" role="tablist">
          <TabButton id="sim" tab={tab} onClick={setTab}>
            Simulator
          </TabButton>
          <TabButton id="pasal" tab={tab} onClick={setTab}>
            Pasal & Aturan
          </TabButton>
          <TabButton id="verif" tab={tab} onClick={setTab}>
            Verifikasi <span className={`count ${violationCount ? 'count--bad' : 'count--ok'}`}>{violationCount || '✓'}</span>
          </TabButton>
        </nav>
      </header>

      {mutantId && (
        <div className="banner">
          Sedang melihat mutan: <strong>{mutants.find((m) => m.id === mutantId)?.title}</strong>.{' '}
          <button className="link" onClick={() => chooseMutant(null)}>
            Kembali ke model acuan
          </button>
        </div>
      )}

      <main className="main">
        <div className="graph">
          <Graph
            model={model}
            current={run.stateId}
            visitedStates={visitedStates}
            visitedTransitions={visitedTransitions}
            highlight={highlight}
            unreached={unreached}
            gaps={gaps}
            showLabels={showLabels}
            onSelect={setSelection}
          />
          <div className="graph__tools">
            <label className="small">
              <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> Label transisi
            </label>
            {highlight !== NO_HIGHLIGHT && (
              <button className="link small" onClick={() => setHighlight(NO_HIGHLIGHT)}>
                Hapus sorotan
              </button>
            )}
          </div>
          <Legend />
          {selection && <Details selection={selection} onClose={() => setSelection(null)} onCite={cite} model={model} />}
        </div>

        <aside className="panel">
          {tab === 'sim' && (
            <Simulator
              key={`${model.id}-${epoch}`}
              model={model}
              run={run}
              scenarioId={scenarioId}
              startDate={startDate}
              onRun={setRun}
              onReset={reset}
              onCite={cite}
            />
          )}
          {tab === 'pasal' && <Sources model={model} focus={focusSource} onHighlight={setHighlight} />}
          {tab === 'verif' && (
            <Verification
              base={kipModel}
              model={model}
              report={report}
              mutantId={mutantId}
              onMutant={chooseMutant}
              onHighlight={setHighlight}
              onCite={cite}
            />
          )}
          <p className="disclaimer">{kipModel.disclaimer}</p>
        </aside>
      </main>
    </div>
  );
}

function TabButton(props: { id: Tab; tab: Tab; onClick: (t: Tab) => void; children: React.ReactNode }) {
  return (
    <button role="tab" aria-selected={props.tab === props.id} className="tab" onClick={() => props.onClick(props.id)}>
      {props.children}
    </button>
  );
}

function Legend() {
  return (
    <div className="legend small">
      <span>
        <i className="sw sw--current" /> saat ini
      </span>
      <span>
        <i className="sw sw--visited" /> dilalui
      </span>
      <span>
        <i className="sw sw--problem" /> masalah
      </span>
      <span>
        <i className="sw sw--terminal" /> akhir
      </span>
      <span>⏱ = batas waktu lewat · hk = hari kerja</span>
    </div>
  );
}

function Details(props: { selection: NonNullable<Selection>; model: typeof kipModel; onClose: () => void; onCite: (id: string) => void }) {
  const { selection, model, onClose, onCite } = props;
  const actor = (a: string) => model.actors[a]?.label ?? a;

  let body: React.ReactNode = null;
  let src;
  if (selection.kind === 'state') {
    const s = model.states.find((x) => x.id === selection.id);
    if (!s) return null;
    src = provision(model, s.deadline?.source);
    body = (
      <>
        <h3>{s.label}</h3>
        {s.description && <p className="muted">{s.description}</p>}
        {s.actors && <p className="small">Yang bertindak: {s.actors.map(actor).join(', ')}</p>}
        {s.deadline && (
          <p className="small">
            Batas waktu: {s.deadline.workingDays} hari kerja ({s.deadline.kind === 'obligation' ? 'kewajiban' : 'kesempatan'})
          </p>
        )}
        {s.expiryGap && <p className="note note--gap">⚠ {s.expiryGap}</p>}
        {s.deadline?.interpretation && <p className="note note--interp">~ {s.deadline.interpretation}</p>}
      </>
    );
  } else {
    const t = model.transitions.find((x) => x.id === selection.id);
    if (!t) return null;
    src = provision(model, t.source ?? (t.event === TIMEOUT ? model.states.find((s) => s.id === t.from)?.deadline?.source : undefined));
    body = (
      <>
        <h3>{t.label}</h3>
        <p className="small">
          {actor(t.actor)} · peristiwa <code>{t.event}</code>
        </p>
        {t.guard && <p className="small">Syarat: {t.guard.describe}</p>}
        {t.effect && <p className="small">Akibat: {t.effect.describe}</p>}
        {t.interpretation && <p className="note note--interp">~ {t.interpretation}</p>}
      </>
    );
  }
  return (
    <div className="details card">
      <button className="details__close link" onClick={onClose} aria-label="Tutup">
        ×
      </button>
      {body}
      {src ? (
        <>
          <button className="link small" onClick={() => onCite(src.id)}>
            {citation(src)}
          </button>
          <blockquote className="small">{src.excerpt}</blockquote>
        </>
      ) : (
        <p className="error small">Tanpa sumber pasal.</p>
      )}
    </div>
  );
}
