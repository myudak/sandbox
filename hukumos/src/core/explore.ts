/**
 * Exhaustive explorer: enumerates every reachable (state, context)
 * configuration of a model for each scenario, then checks structural rules,
 * invariants and deadline bounds. Each violation comes with a counterexample
 * trace that can be replayed and drawn on the graph.
 *
 * Findings fall into three categories, matching how a human should triage them:
 * - violation: the model breaks a rule. Either a model bug or an
 *   interpretation disagreement; a reviewer decides which.
 * - legal_gap_candidate: the model follows the text faithfully, and the text
 *   itself leaves something open (e.g. a deadline with no stated consequence).
 * - interpretation: a choice the modeller made where the text was not explicit.
 */
import {
  type Model,
  type SourceRef,
  type StateDef,
  type StateId,
  SYSTEM,
  TIMEOUT,
  type TransitionDef,
} from './ir';

export type Category = 'violation' | 'legal_gap_candidate' | 'interpretation';

export interface TraceStep {
  transitionId: string;
  from: StateId;
  to: StateId;
}

export interface Trace {
  scenario: string;
  steps: TraceStep[];
}

export interface Finding {
  check: string;
  category: Category;
  message: string;
  states?: StateId[];
  transitions?: string[];
  trace?: Trace;
  source?: SourceRef;
}

export interface Bound {
  propertyId: string;
  description: string;
  /** Worst case in working days; Infinity when some wait has no deadline. */
  worstCase: number | null;
  limit?: number;
  trace?: Trace;
}

export interface Report {
  modelId: string;
  findings: Finding[];
  bounds: Bound[];
  reachedStates: StateId[];
  stats: {
    scenarios: number;
    configurations: number;
    edges: number;
    truncated: boolean;
    unverifiedSources: number;
  };
}

export interface ExploreOptions {
  /** Per-scenario cap on configurations; hitting it means a likely unbounded loop. */
  maxConfigs?: number;
}

interface Edge {
  t: string;
  to: string;
}

interface Config<C> {
  key: string;
  state: StateId;
  ctx: C;
}

export const CHECKS = {
  structure: 'Struktur model valid',
  reachability: 'Semua status dapat dicapai',
  terminalOutgoing: 'Status akhir tidak punya transisi keluar',
  deadEnd: 'Tidak ada jalan buntu',
  determinism: 'Satu peristiwa, satu tujuan',
  deadlineExpiry: 'Setiap batas waktu punya akibat',
  timeoutWithoutDeadline: 'TIMEOUT hanya dari status berbatas waktu',
  actor: 'Pelaku berwenang',
  traceability: 'Setiap aturan punya sumber',
  deadlineText: 'Angka batas waktu cocok dengan teks pasal',
  termination: 'Prosedur selalu berakhir',
  stateSpace: 'Ruang status terbatas',
  property: 'Properti hukum',
  interpretation: 'Pilihan interpretasi',
} as const;

export function explore<C>(model: Model<C>, opts: ExploreOptions = {}): Report {
  const maxConfigs = opts.maxConfigs ?? 5000;
  const findings: Finding[] = [];
  const bounds: Bound[] = [];
  const reached = new Set<StateId>();
  const stats = {
    scenarios: model.scenarios.length,
    configurations: 0,
    edges: 0,
    truncated: false,
    unverifiedSources: Object.values(model.sources).filter((p) => !p.verified).length,
  };

  const states = new Map(model.states.map((s) => [s.id, s]));
  const add = (f: Finding) => findings.push(f);

  staticChecks(model, states, add);

  // Static checks found broken references: exploring would only repeat them.
  const structurallyBroken = findings.some((f) => f.check === 'structure');
  if (!structurallyBroken) {
    const seen = new Set<string>(); // dedupe "check|state|property"
    const once = (k: string, f: Finding) => {
      if (seen.has(k)) return;
      seen.add(k);
      add(f);
    };
    const boundAgg = new Map<string, Bound>();

    for (const sc of model.scenarios) {
      const r = bfs(model, states, sc.ctx, maxConfigs);
      stats.configurations += r.configs.size;
      stats.edges += r.edgeCount;
      for (const c of r.configs.values()) reached.add(c.state);

      const trace = (key: string, extra: TraceStep[] = []): Trace => ({
        scenario: sc.id,
        steps: [...r.traceTo(key), ...extra],
      });

      if (r.truncated) {
        stats.truncated = true;
        once(`stateSpace|${sc.id}`, {
          check: 'stateSpace',
          category: 'violation',
          message: `Lebih dari ${maxConfigs} konfigurasi pada skenario “${sc.label}”: kemungkinan ada perulangan tak terbatas (mis. konteks terus berubah).`,
          trace: r.lastKey ? trace(r.lastKey) : undefined,
        });
      }

      for (const c of r.configs.values()) {
        const s = states.get(c.state)!;
        const out = r.edges.get(c.key) ?? [];

        if (!s.terminal && out.length === 0 && !r.frontier.has(c.key)) {
          once(`deadEnd|${s.id}`, {
            check: 'deadEnd',
            category: 'violation',
            message: `Jalan buntu: “${s.label}” bukan status akhir tetapi tidak ada transisi yang dapat terjadi.`,
            states: [s.id],
            trace: trace(c.key),
          });
        }

        const byEvent = new Map<string, string[]>();
        for (const e of out) {
          const ev = model.transitions.find((t) => t.id === e.t)!.event;
          byEvent.set(ev, [...(byEvent.get(ev) ?? []), e.t]);
        }
        for (const [ev, ts] of byEvent) {
          if (ts.length > 1) {
            once(`determinism|${s.id}|${ev}`, {
              check: 'determinism',
              category: 'violation',
              message: `Peristiwa ${ev} pada “${s.label}” dapat menuju lebih dari satu status (${ts.join(', ')}).`,
              states: [s.id],
              transitions: ts,
              trace: trace(c.key),
            });
          }
        }

        for (const p of model.properties) {
          if (p.kind === 'never' && p.predicate(c.state, c.ctx)) {
            once(`property|${p.id}`, {
              check: 'property',
              category: 'violation',
              message: `Properti “${p.description}” dilanggar pada “${s.label}”.`,
              states: [s.id],
              trace: trace(c.key),
              source: p.source,
            });
          }
        }
      }

      if (r.truncated) continue; // graph is incomplete; cycle and bound results would be wrong

      const cycle = findCycle(r.configs, r.edges);
      if (cycle) {
        const cycleSteps = cycle.loop.map((e) => stepOf(model, e.t));
        once(`termination|${sc.id}`, {
          check: 'termination',
          category: 'violation',
          message: `Prosedur dapat berputar tanpa akhir: ${cycleSteps.map((s) => s.from).join(' → ')} → ${cycleSteps[0].from}.`,
          states: cycleSteps.map((s) => s.from),
          transitions: cycle.loop.map((e) => e.t),
          trace: trace(cycle.entry, cycleSteps),
        });
      }

      for (const p of model.properties) {
        if (p.kind === 'reachable') {
          const targets = new Set(p.target);
          for (const c of r.configs.values()) {
            if (!p.from.includes(c.state)) continue;
            if (!canReach(c.key, r.edges, (k) => targets.has(r.configs.get(k)!.state))) {
              once(`property|${p.id}`, {
                check: 'property',
                category: 'violation',
                message: `Properti “${p.description}” dilanggar: dari “${states.get(c.state)!.label}” tidak ada jalan ke ${p.target.join(' / ')}.`,
                states: [c.state],
                trace: trace(c.key),
                source: p.source,
              });
            }
          }
        }

        if (p.kind === 'maxElapsed' && !cycle) {
          const targets = new Set(p.to);
          const lp = longestPaths(states, r.configs, r.edges, (k) => targets.has(r.configs.get(k)!.state));
          let best: { days: number; key: string } | null = null;
          for (const c of r.configs.values()) {
            if (c.state !== p.from) continue;
            const v = lp.value(c.key);
            if (v !== null && (best === null || v > best.days)) best = { days: v, key: c.key };
          }
          const prev = boundAgg.get(p.id);
          if (best && (!prev || prev.worstCase === null || best.days > prev.worstCase)) {
            boundAgg.set(p.id, {
              propertyId: p.id,
              description: p.description,
              worstCase: best.days,
              limit: p.maxWorkingDays,
              trace: trace(best.key, lp.path(best.key).map((t) => stepOf(model, t))),
            });
          } else if (!prev) {
            boundAgg.set(p.id, { propertyId: p.id, description: p.description, worstCase: null, limit: p.maxWorkingDays });
          }
        }
      }
    }

    for (const b of boundAgg.values()) {
      bounds.push(b);
      if (b.limit !== undefined && b.worstCase !== null && b.worstCase > b.limit) {
        const p = model.properties.find((x) => x.id === b.propertyId);
        add({
          check: 'property',
          category: 'violation',
          message: `Properti “${b.description}” dilanggar: kasus terburuk ${fmtDays(b.worstCase)}, batas ${b.limit} hari kerja.`,
          trace: b.trace,
          states: b.trace?.steps.map((s) => s.from),
          source: p?.source,
        });
      }
    }

    for (const s of model.states) {
      if (!reached.has(s.id) && !stats.truncated) {
        add({
          check: 'reachability',
          category: 'violation',
          message: `“${s.label}” tidak dapat dicapai dari status awal pada skenario mana pun.`,
          states: [s.id],
        });
      }
    }
  }

  return { modelId: model.id, findings, bounds, reachedStates: [...reached], stats };
}

export function fmtDays(d: number | null): string {
  if (d === null) return 'tidak tercapai';
  if (!Number.isFinite(d)) return 'tak terbatas';
  return `${d} hari kerja`;
}

export function violations(r: Report): Finding[] {
  return r.findings.filter((f) => f.category === 'violation');
}

// ---------------------------------------------------------------------------

function staticChecks<C>(model: Model<C>, states: Map<StateId, StateDef>, add: (f: Finding) => void) {
  const dup = <T extends { id: string }>(xs: T[], what: string) => {
    const seen = new Set<string>();
    for (const x of xs) {
      if (seen.has(x.id)) add({ check: 'structure', category: 'violation', message: `${what} ganda: ${x.id}` });
      seen.add(x.id);
    }
  };
  dup(model.states, 'ID status');
  dup(model.transitions, 'ID transisi');

  if (!states.has(model.initial)) {
    add({ check: 'structure', category: 'violation', message: `Status awal tidak dikenal: ${model.initial}` });
  }
  for (const t of model.transitions) {
    for (const end of [t.from, t.to]) {
      if (!states.has(end)) {
        add({
          check: 'structure',
          category: 'violation',
          message: `Transisi ${t.id} merujuk status tidak dikenal: ${end}`,
          transitions: [t.id],
        });
      }
    }
  }

  const sourceOk = (ref: SourceRef | undefined) => !!ref && !!model.sources[ref.id];

  for (const s of model.states) {
    const out = model.transitions.filter((t) => t.from === s.id);

    if (s.terminal && out.length > 0) {
      add({
        check: 'terminalOutgoing',
        category: 'violation',
        message: `Status akhir “${s.label}” memiliki transisi keluar (${out.map((t) => t.id).join(', ')}).`,
        states: [s.id],
        transitions: out.map((t) => t.id),
      });
    }

    if (s.deadline) {
      const hasTimeout = out.some((t) => t.event === TIMEOUT);
      if (!hasTimeout && s.expiryGap) {
        add({
          check: 'deadlineExpiry',
          category: 'legal_gap_candidate',
          message: `“${s.label}”: batas ${s.deadline.workingDays} hari kerja tanpa akibat hukum dalam teks. ${s.expiryGap}`,
          states: [s.id],
          source: s.deadline.source,
        });
      } else if (!hasTimeout) {
        add({
          check: 'deadlineExpiry',
          category: 'violation',
          message: `“${s.label}” memiliki batas waktu ${s.deadline.workingDays} hari kerja tetapi tidak ada transisi saat batas waktu lewat.`,
          states: [s.id],
          source: s.deadline.source,
        });
      }

      if (!sourceOk(s.deadline.source)) {
        add({
          check: 'traceability',
          category: 'violation',
          message: `Batas waktu pada “${s.label}” tidak menunjuk ke pasal yang ada.`,
          states: [s.id],
        });
      } else {
        const text = model.sources[s.deadline.source.id].excerpt;
        const n = s.deadline.workingDays;
        if (!new RegExp(`(^|\\D)${n}(\\D|$)`).test(text)) {
          add({
            check: 'deadlineText',
            category: 'violation',
            message: `Batas waktu “${s.label}” = ${n} hari kerja, tetapi angka ${n} tidak ada di teks ${citeId(model, s.deadline.source)}.`,
            states: [s.id],
            source: s.deadline.source,
          });
        }
      }

      if (s.deadline.interpretation) {
        add({
          check: 'interpretation',
          category: 'interpretation',
          message: `“${s.label}”: ${s.deadline.interpretation}`,
          states: [s.id],
          source: s.deadline.source,
        });
      }
    }
  }

  for (const t of model.transitions) {
    const from = states.get(t.from);
    if (t.event === TIMEOUT) {
      if (from && !from.deadline) {
        add({
          check: 'timeoutWithoutDeadline',
          category: 'violation',
          message: `Transisi ${t.id} adalah TIMEOUT dari “${from.label}”, yang tidak memiliki batas waktu.`,
          transitions: [t.id],
          states: [t.from],
        });
      }
      if (t.actor !== SYSTEM) {
        add({
          check: 'actor',
          category: 'violation',
          message: `TIMEOUT ${t.id} harus dijalankan oleh sistem, bukan ${t.actor}.`,
          transitions: [t.id],
        });
      }
    } else {
      if (from && !(from.actors ?? []).includes(t.actor)) {
        const who = model.actors[t.actor]?.label ?? t.actor;
        add({
          check: 'actor',
          category: 'violation',
          message: `“${t.label}” dilakukan oleh ${who}, padahal pada “${from.label}” yang berwenang adalah ${(from.actors ?? []).map((a) => model.actors[a]?.label ?? a).join(', ') || 'tidak ada'}.`,
          transitions: [t.id],
          states: [t.from],
        });
      }
      if (!sourceOk(t.source)) {
        add({
          check: 'traceability',
          category: 'violation',
          message: `Transisi “${t.label}” (${t.id}) tidak menunjuk ke pasal mana pun.`,
          transitions: [t.id],
          states: [t.from],
        });
      }
    }
    if (t.interpretation) {
      add({
        check: 'interpretation',
        category: 'interpretation',
        message: `“${t.label}”: ${t.interpretation}`,
        transitions: [t.id],
        source: t.source,
      });
    }
  }
}

function citeId<C>(model: Model<C>, ref: SourceRef): string {
  const p = model.sources[ref.id];
  return p ? `Pasal ${p.pasal}${p.ayat ? ` ayat (${p.ayat})` : ''}` : ref.id;
}

function stepOf<C>(model: Model<C>, tid: string): TraceStep {
  const t = model.transitions.find((x) => x.id === tid)!;
  return { transitionId: t.id, from: t.from, to: t.to };
}

function keyOf(state: StateId, ctx: unknown): string {
  return `${state}|${JSON.stringify(ctx)}`;
}

function bfs<C>(model: Model<C>, states: Map<StateId, StateDef>, ctx0: C, maxConfigs: number) {
  const configs = new Map<string, Config<C>>();
  const edges = new Map<string, Edge[]>();
  const parent = new Map<string, { from: string; t: string } | null>();
  const frontier = new Set<string>(); // configs never expanded because of truncation
  let edgeCount = 0;
  let truncated = false;
  let lastKey: string | null = null;

  const k0 = keyOf(model.initial, ctx0);
  configs.set(k0, { key: k0, state: model.initial, ctx: ctx0 });
  parent.set(k0, null);
  const queue = [k0];

  while (queue.length) {
    const key = queue.shift()!;
    if (truncated) {
      frontier.add(key);
      continue;
    }
    const c = configs.get(key)!;
    const out: Edge[] = [];
    for (const t of model.transitions as TransitionDef<C>[]) {
      if (t.from !== c.state || !states.has(t.to)) continue;
      if (t.guard && !t.guard.test(c.ctx)) continue;
      const ctx = t.effect ? t.effect.apply(c.ctx) : c.ctx;
      const nk = keyOf(t.to, ctx);
      out.push({ t: t.id, to: nk });
      edgeCount++;
      if (!configs.has(nk)) {
        if (configs.size >= maxConfigs) {
          truncated = true;
          lastKey = key;
          frontier.add(key);
          continue;
        }
        configs.set(nk, { key: nk, state: t.to, ctx });
        parent.set(nk, { from: key, t: t.id });
        queue.push(nk);
      }
    }
    // Drop edges to configs we refused to create.
    edges.set(key, out.filter((e) => configs.has(e.to)));
  }

  const traceTo = (key: string): TraceStep[] => {
    const steps: TraceStep[] = [];
    let k: string | undefined = key;
    while (k) {
      const p = parent.get(k);
      if (!p) break;
      steps.unshift(stepOf(model, p.t));
      k = p.from;
    }
    return steps;
  };

  return { configs, edges, edgeCount, truncated, lastKey, frontier, traceTo };
}

function findCycle<C>(configs: Map<string, Config<C>>, edges: Map<string, Edge[]>) {
  const color = new Map<string, 0 | 1 | 2>();
  const stack: { key: string; via?: Edge }[] = [];

  const visit = (key: string): { entry: string; loop: Edge[] } | null => {
    color.set(key, 1);
    for (const e of edges.get(key) ?? []) {
      const c = color.get(e.to) ?? 0;
      if (c === 1) {
        // Back edge: the loop runs from e.to along the stack to key, then e.
        const i = stack.findIndex((s) => s.key === e.to);
        const loop = [...stack.slice(i + 1).map((s) => s.via!), e];
        return { entry: e.to, loop };
      }
      if (c === 0) {
        stack.push({ key: e.to, via: e });
        const r = visit(e.to);
        if (r) return r;
        stack.pop();
      }
    }
    color.set(key, 2);
    return null;
  };

  for (const key of configs.keys()) {
    if ((color.get(key) ?? 0) === 0) {
      stack.length = 0;
      stack.push({ key });
      const r = visit(key);
      if (r) return r;
    }
  }
  return null;
}

function canReach(start: string, edges: Map<string, Edge[]>, isTarget: (k: string) => boolean): boolean {
  const seen = new Set([start]);
  const q = [start];
  while (q.length) {
    const k = q.shift()!;
    if (isTarget(k)) return true;
    for (const e of edges.get(k) ?? []) {
      if (!seen.has(e.to)) {
        seen.add(e.to);
        q.push(e.to);
      }
    }
  }
  return false;
}

/**
 * Worst-case working days from a configuration until first arriving in a
 * target. Leaving a state can take up to its full deadline (acting on the last
 * day, or letting it expire). A non-terminal state with no deadline can last
 * forever. Requires an acyclic configuration graph.
 */
function longestPaths<C>(
  states: Map<StateId, StateDef>,
  configs: Map<string, Config<C>>,
  edges: Map<string, Edge[]>,
  isTarget: (k: string) => boolean,
) {
  const memo = new Map<string, { v: number | null; next?: Edge }>();
  const go = (k: string): number | null => {
    const m = memo.get(k);
    if (m) return m.v;
    if (isTarget(k)) {
      memo.set(k, { v: 0 });
      return 0;
    }
    const s = states.get(configs.get(k)!.state)!;
    const wait = s.deadline ? s.deadline.workingDays : Infinity;
    let best: number | null = null;
    let next: Edge | undefined;
    for (const e of edges.get(k) ?? []) {
      const sub = go(e.to);
      if (sub === null) continue;
      const v = wait + sub;
      if (best === null || v > best) {
        best = v;
        next = e;
      }
    }
    memo.set(k, { v: best, next });
    return best;
  };
  return {
    value: go,
    path: (k: string): string[] => {
      const out: string[] = [];
      let cur = k;
      for (;;) {
        go(cur);
        const m = memo.get(cur)!;
        if (!m.next) break;
        out.push(m.next.t);
        cur = m.next.to;
      }
      return out;
    },
  };
}
