import { useEffect, useRef } from 'react';
import { Scene } from './scene/Scene';
import { CameraPreset, Tab, useApp } from './state/store';
import { engine } from './sim/engine';
import { useEngineVersion, useTicker } from './sim/useEngine';
import { ControlPanel, LiveChart, MetricsTable } from './dashboard/LivePanel';
import { SpectraPanel } from './dashboard/SpectraPanel';
import { OptimizerPanel } from './dashboard/OptimizerPanel';
import { RobustnessPanel } from './dashboard/RobustnessPanel';
import { ValidationPanel } from './dashboard/ValidationPanel';
import { ModelPanel } from './dashboard/ModelPanel';
import { COLORS } from './dashboard/Chart';
import { DEG, fmt } from './dashboard/format';

const TABS: { id: Tab; label: string }[] = [
  { id: 'live', label: 'Simulate' },
  { id: 'spectra', label: 'Spectra' },
  { id: 'optimize', label: 'Optimise' },
  { id: 'robustness', label: 'Robustness' },
  { id: 'validation', label: 'Validation' },
  { id: 'model', label: 'Model' },
];

const CAMERAS: { id: CameraPreset; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'waterline', label: 'Waterline' },
  { id: 'underwater', label: 'Underwater' },
  { id: 'nacelle', label: 'Damper' },
];

/** Rebuild the simulation when the environment or damper changes (debounced). */
function useEngineConfig() {
  const sea = useApp((s) => s.sea);
  const wind = useApp((s) => s.wind);
  const tmd = useApp((s) => s.tmd);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      engine.configure(sea, wind, tmd);
      return;
    }
    const id = setTimeout(() => engine.configure(sea, wind, tmd), 160);
    return () => clearTimeout(id);
  }, [sea, wind, tmd]);
}

function ViewportOverlay() {
  const s = useApp();
  useEngineVersion();
  useTicker(200);
  const b = engine.base;
  const t = engine.tmd;
  const solidLabel = s.primary === 'tmd' ? 'With TMD' : 'Without TMD';
  const ghostLabel = s.primary === 'tmd' ? 'Without TMD' : 'With TMD';
  return (
    <>
      <div className="overlay top-left">
        <div className="pill">
          <span className="sw" style={{ background: s.primary === 'tmd' ? COLORS.withTmd : COLORS.without }} />
          Solid: {solidLabel}
          {s.ghost && (
            <>
              <span className="sw ghost" style={{ borderColor: COLORS.without }} /> Ghost: {ghostLabel}
            </>
          )}
        </div>
        {b && t && (
          <div className="pill mono">
            t {fmt(engine.t, 0)} s · pitch {fmt(b.last.pitch * DEG, 2)}° → {fmt(t.last.pitch * DEG, 2)}° · β {fmt(t.last.damper * DEG, 1)}°
          </div>
        )}
        {s.exaggeration > 1 && <div className="pill muted">Motion ×{s.exaggeration} (visual only)</div>}
      </div>
      <div className="overlay bottom-left">
        <div className="segmented small">
          {CAMERAS.map((c) => (
            <button key={c.id} className={s.camera === c.id ? 'on' : ''} onClick={() => s.goCamera(c.id)}>
              {c.label}
            </button>
          ))}
        </div>
        <button className="ghost-btn" onClick={() => s.set({ paused: !s.paused })} aria-label={s.paused ? 'Play' : 'Pause'}>
          {s.paused ? '▶ Play' : '❚❚ Pause'}
        </button>
        <button className="ghost-btn" onClick={() => engine.configure(s.sea, s.wind, s.tmd)} title="Restart both simulations">
          ↺ Restart
        </button>
      </div>
    </>
  );
}

export default function App() {
  useEngineConfig();
  const tab = useApp((s) => s.tab);
  const set = useApp((s) => s.set);
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden>
            <path d="M12 2v9M12 11l-6 3M12 11l6 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" fill="none" />
            <rect x="10.6" y="11" width="2.8" height="11" rx="1" fill="currentColor" />
            <path d="M2 16c2 1.5 4 1.5 6 0s4-1.5 6 0 4 1.5 6 0" stroke="#3987e5" strokeWidth="1.6" fill="none" />
          </svg>
          <div>
            <h1>SPAR Dynamics Lab</h1>
            <p>Floating offshore wind turbine · rotary tuned mass damper</p>
          </div>
        </div>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? 'on' : ''} onClick={() => set({ tab: t.id })}>
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="layout">
        <div className="left">
          <div className="viewport">
            <Scene />
            <ViewportOverlay />
          </div>
          <div className="results">
            <MetricsTable />
            <LiveChart />
          </div>
        </div>
        <aside className="panel">
          {tab === 'live' && <ControlPanel />}
          {tab === 'spectra' && <SpectraPanel />}
          {tab === 'optimize' && <OptimizerPanel />}
          {tab === 'robustness' && <RobustnessPanel />}
          {tab === 'validation' && <ValidationPanel />}
          {tab === 'model' && <ModelPanel />}
        </aside>
      </main>
    </div>
  );
}
