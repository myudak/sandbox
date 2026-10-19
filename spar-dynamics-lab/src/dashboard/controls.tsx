import { ReactNode, useId } from 'react';

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  digits?: number;
  hint?: string;
  onChange: (v: number) => void;
}

export function Slider({ label, value, min, max, step, unit, digits = 1, hint, onChange }: SliderProps) {
  const id = useId();
  return (
    <div className="field" title={hint}>
      <label htmlFor={id}>
        <span>{label}</span>
        <span className="value">
          {value.toFixed(digits)}
          {unit && <small> {unit}</small>}
        </span>
      </label>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
    </div>
  );
}

interface SegProps<T extends string> {
  label?: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}

export function Segmented<T extends string>({ label, value, options, onChange }: SegProps<T>) {
  return (
    <div className="field">
      {label && <div className="field-label">{label}</div>}
      <div className="segmented" role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button key={o.value} role="radio" aria-checked={o.value === value} className={o.value === value ? 'on' : ''} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="section">
      <header>
        <h3>{title}</h3>
        {aside}
      </header>
      {children}
    </section>
  );
}

export function Delta({ pct, lowerIsBetter = true }: { pct: number; lowerIsBetter?: boolean }) {
  if (!Number.isFinite(pct)) return <span className="delta">—</span>;
  const better = lowerIsBetter ? pct < -0.5 : pct > 0.5;
  const worse = lowerIsBetter ? pct > 0.5 : pct < -0.5;
  const cls = better ? 'good' : worse ? 'bad' : 'flat';
  const icon = pct < -0.5 ? '▼' : pct > 0.5 ? '▲' : '•';
  return (
    <span className={`delta ${cls}`} title={better ? 'TMD helps' : worse ? 'TMD hurts' : 'no meaningful change'}>
      <span aria-hidden>{icon}</span> {pct > 0 ? '+' : ''}
      {pct.toFixed(1)}%
    </span>
  );
}

export function Progress({ value, label }: { value: number; label?: string }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div style={{ width: `${(value * 100).toFixed(1)}%` }} />
      {label && <span>{label}</span>}
    </div>
  );
}
