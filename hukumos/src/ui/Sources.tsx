import { useEffect, useRef } from 'react';
import { type Model, TIMEOUT, citation } from '../core/ir';
import type { Highlight } from './Graph';

/** Literate view: each provision next to the rules that encode it. */
export function Sources<C>(props: {
  model: Model<C>;
  focus: string | null;
  onHighlight: (h: Highlight) => void;
}) {
  const { model, focus, onHighlight } = props;
  const refs = useRef(new Map<string, HTMLElement>());

  useEffect(() => {
    if (focus) refs.current.get(focus)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [focus]);

  const provisions = Object.values(model.sources).sort(
    (a, b) => Number(a.pasal) - Number(b.pasal) || Number(a.ayat ?? 0) - Number(b.ayat ?? 0),
  );
  const unverified = provisions.filter((p) => !p.verified).length;

  return (
    <div className="stack">
      {unverified > 0 && (
        <p className="note note--gap">
          {unverified} dari {provisions.length} kutipan masih parafrase dan belum dicocokkan dengan teks resmi.
        </p>
      )}
      {provisions.map((p) => {
        const deadlines = model.states.filter((s) => s.deadline?.source.id === p.id);
        const transitions = model.transitions.filter((t) => t.source?.id === p.id && t.event !== TIMEOUT);
        const properties = model.properties.filter((x) => x.source?.id === p.id);
        const all = {
          states: new Set(deadlines.map((s) => s.id)),
          transitions: new Set(transitions.map((t) => t.id)),
          tone: 'trace' as const,
        };
        return (
          <section
            key={p.id}
            ref={(el) => {
              if (el) refs.current.set(p.id, el);
            }}
            className={`card source ${focus === p.id ? 'source--focus' : ''}`}
          >
            <div className="row row--between">
              <button className="link" onClick={() => onHighlight(all)}>
                <h3>{citation(p)}</h3>
              </button>
              <span className={`badge ${p.verified ? 'badge--ok' : 'badge--warn'}`}>
                {p.verified ? 'terverifikasi' : 'belum diverifikasi'}
              </span>
            </div>
            <blockquote>{p.excerpt}</blockquote>
            <ul className="rules">
              {deadlines.map((s) => (
                <li key={s.id}>
                  <button
                    className="link"
                    onClick={() => onHighlight({ states: new Set([s.id]), transitions: new Set(), tone: 'trace' })}
                  >
                    Batas waktu {s.deadline!.workingDays} hari kerja pada “{s.label}”
                  </button>
                </li>
              ))}
              {transitions.map((t) => (
                <li key={t.id}>
                  <button
                    className="link"
                    onClick={() => onHighlight({ states: new Set(), transitions: new Set([t.id]), tone: 'trace' })}
                  >
                    {model.actors[t.actor]?.label ?? t.actor}: {t.label}
                    {t.guard ? ` (jika ${t.guard.describe})` : ''}
                  </button>
                </li>
              ))}
              {properties.map((x) => (
                <li key={x.id} className="muted">
                  Properti: {x.description}
                </li>
              ))}
              {deadlines.length + transitions.length + properties.length === 0 && (
                <li className="muted">Belum ada aturan yang merujuk pasal ini.</li>
              )}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
