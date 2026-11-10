import { useMemo } from 'react';
import {
  Background,
  Controls,
  type Edge,
  Handle,
  MarkerType,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { type Model, type StateDef, type StateId, TIMEOUT, provision } from '../core/ir';

export interface Highlight {
  states: Set<StateId>;
  transitions: Set<string>;
  tone: 'trace' | 'problem';
}

export const NO_HIGHLIGHT: Highlight = { states: new Set(), transitions: new Set(), tone: 'trace' };

export type Selection = { kind: 'state'; id: StateId } | { kind: 'transition'; id: string } | null;

type LawNodeData = {
  state: StateDef;
  actor?: string;
  cite?: string;
  current: boolean;
  visited: boolean;
  flagged: boolean;
  tone: Highlight['tone'];
  unreached: boolean;
  gap: boolean;
};
type LawNode = Node<LawNodeData, 'law'>;

function LawNodeView({ data }: NodeProps<LawNode>) {
  const s = data.state;
  const cls = [
    'node',
    s.terminal && 'node--terminal',
    data.visited && 'node--visited',
    data.current && 'node--current',
    data.flagged && `node--${data.tone}`,
    data.unreached && 'node--unreached',
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <div className={cls}>
      <Handle type="target" position={Position.Top} />
      <div className="node__label">{s.label}</div>
      {(data.actor || s.deadline) && (
        <div className="node__meta">
          {data.actor && <span>{data.actor}</span>}
          {s.deadline && (
            <span className="node__deadline">
              {s.deadline.workingDays} hk{data.cite ? ` · ${data.cite}` : ''}
            </span>
          )}
        </div>
      )}
      {data.gap && <div className="node__gap" title="Kandidat celah hukum">⚠ celah?</div>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { law: LawNodeView };

/** Longest-path ranks from the initial state; terminals after active states within a rank. */
function layout<C>(model: Model<C>): Map<StateId, { x: number; y: number }> {
  const ids = model.states.map((s) => s.id);
  const rank = new Map<StateId, number>([[model.initial, 0]]);
  for (let i = 0; i < ids.length; i++) {
    for (const t of model.transitions) {
      const r = rank.get(t.from);
      if (r === undefined || t.from === t.to || r + 1 >= ids.length) continue;
      if ((rank.get(t.to) ?? -1) < r + 1) rank.set(t.to, r + 1);
    }
  }
  const maxRank = Math.max(0, ...rank.values());
  const rows = new Map<number, StateDef[]>();
  for (const s of model.states) {
    const r = rank.get(s.id) ?? maxRank + 1; // unreachable states go to a final row
    rows.set(r, [...(rows.get(r) ?? []), s]);
  }
  const pos = new Map<StateId, { x: number; y: number }>();
  for (const [r, row] of rows) {
    row.sort((a, b) => Number(!!a.terminal) - Number(!!b.terminal));
    row.forEach((s, i) => pos.set(s.id, { x: (i - (row.length - 1) / 2) * 230, y: r * 120 }));
  }
  return pos;
}

export function Graph<C>(props: {
  model: Model<C>;
  current?: StateId;
  visitedStates: Set<StateId>;
  visitedTransitions: Set<string>;
  highlight: Highlight;
  unreached: Set<StateId>;
  gaps: Set<StateId>;
  showLabels: boolean;
  onSelect: (s: Selection) => void;
}) {
  const { model, current, visitedStates, visitedTransitions, highlight, unreached, gaps, showLabels, onSelect } = props;
  const pos = useMemo(() => layout(model), [model]);

  const nodes: LawNode[] = model.states.map((s) => {
    const p = provision(model, s.deadline?.source);
    return {
      id: s.id,
      type: 'law',
      position: pos.get(s.id) ?? { x: 0, y: 0 },
      data: {
        state: s,
        actor: s.actors?.map((a) => model.actors[a]?.label ?? a).join(', '),
        cite: p ? `P${p.pasal}${p.ayat ? `(${p.ayat})` : ''}` : undefined,
        current: s.id === current,
        visited: visitedStates.has(s.id),
        flagged: highlight.states.has(s.id),
        tone: highlight.tone,
        unreached: unreached.has(s.id),
        gap: gaps.has(s.id),
      },
    };
  });

  const edges: Edge[] = model.transitions
    .filter((t) => pos.has(t.from) && pos.has(t.to))
    .map((t) => {
      const flagged = highlight.transitions.has(t.id);
      const visited = visitedTransitions.has(t.id);
      const cls = ['edge', t.event === TIMEOUT && 'edge--timeout', visited && 'edge--visited', flagged && `edge--${highlight.tone}`]
        .filter(Boolean)
        .join(' ');
      return {
        id: t.id,
        source: t.from,
        target: t.to,
        className: cls,
        label: showLabels || flagged || visited ? (t.event === TIMEOUT ? `⏱ ${t.label}` : t.label) : undefined,
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 4,
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
        animated: flagged,
        zIndex: flagged || visited ? 10 : 0,
      };
    });

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      minZoom={0.2}
      nodesDraggable={false}
      nodesConnectable={false}
      colorMode="system"
      proOptions={{ hideAttribution: false }}
      onNodeClick={(_, n) => onSelect({ kind: 'state', id: n.id })}
      onEdgeClick={(_, e) => onSelect({ kind: 'transition', id: e.id })}
      onPaneClick={() => onSelect(null)}
    >
      <Background gap={24} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
