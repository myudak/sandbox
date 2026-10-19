import { useEffect, useRef, useState } from 'react';
import { COLORS } from './Chart';

const NEG = hex(COLORS.helps);
const POS = hex(COLORS.hurts);
const MID = hex(COLORS.neutral);

function hex(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Diverging blue ← grey → red; saturates at ±limit. */
export function divergingColor(v: number, limit: number): string {
  const t = Math.max(-1, Math.min(1, v / limit));
  const end = t < 0 ? NEG : POS;
  const a = Math.abs(t) ** 0.8;
  const c = MID.map((m, i) => Math.round(m + (end[i] - m) * a));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

interface Props {
  rows: number[];
  cols: number[];
  values: number[][];
  rowLabel: string;
  colLabel: string;
  limit: number;
  tooltip: (i: number, j: number) => string;
}

/** Hs × Tp grid of signed % change; hover shows the underlying numbers. */
export function Heatmap({ rows, cols, values, rowLabel, colLabel, limit, tooltip }: Props) {
  const [hover, setHover] = useState<{ i: number; j: number; x: number; y: number } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => setHover(null), [values]);
  return (
    <div className="heatmap" ref={box}>
      <div className="hm-ylabel">{rowLabel}</div>
      <div className="hm-grid" style={{ gridTemplateColumns: `36px repeat(${cols.length}, 1fr)` }} onMouseLeave={() => setHover(null)}>
        {[...rows].reverse().map((r, ri) => {
          const i = rows.length - 1 - ri;
          return [
            <div key={`l${i}`} className="hm-rowlab">
              {r}
            </div>,
            ...cols.map((_, j) => {
              const v = values[i][j];
              return (
                <div
                  key={`${i}-${j}`}
                  className={hover && hover.i === i && hover.j === j ? 'hm-cell on' : 'hm-cell'}
                  style={{ background: divergingColor(v, limit) }}
                  onMouseEnter={(e) => {
                    const rect = box.current!.getBoundingClientRect();
                    const c = (e.target as HTMLElement).getBoundingClientRect();
                    setHover({ i, j, x: c.left - rect.left + c.width / 2, y: c.top - rect.top });
                  }}
                  aria-label={tooltip(i, j)}
                >
                  <span>{Math.abs(v) >= 0.5 ? `${v > 0 ? '+' : ''}${v.toFixed(0)}` : '0'}</span>
                </div>
              );
            }),
          ];
        })}
        <div />
        {cols.map((c) => (
          <div key={`c${c}`} className="hm-collab">
            {c}
          </div>
        ))}
      </div>
      <div className="hm-xlabel">{colLabel}</div>
      <div className="hm-legend">
        <span>TMD helps</span>
        <div
          className="hm-bar"
          style={{
            background: `linear-gradient(90deg, ${divergingColor(-limit, limit)}, ${divergingColor(0, limit)}, ${divergingColor(limit, limit)})`,
          }}
        />
        <span>TMD hurts</span>
        <small className="muted">
          ±{limit}% · {'cells show % change'}
        </small>
      </div>
      {hover && (
        <div className="tooltip" style={{ left: hover.x, top: hover.y }}>
          {tooltip(hover.i, hover.j)
            .split('\n')
            .map((l) => (
              <div key={l}>{l}</div>
            ))}
        </div>
      )}
    </div>
  );
}
