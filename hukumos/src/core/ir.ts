/**
 * Legal Intermediate Representation (IR) for procedural law.
 *
 * A procedure is a finite state machine over (state, context) configurations.
 * Every deadline and every transition points back to the provision it encodes,
 * so a reviewer can check the model against the law side by side.
 *
 * The law stays the authority. A model is a transparent, testable
 * *interpretation* of it, so interpretive choices are recorded explicitly.
 */

export type StateId = string;
export type ActorId = string;
export const SYSTEM: ActorId = 'sistem';

/** Pointer from a rule to the provision it encodes. */
export interface SourceRef {
  /** Key into the model's `sources` table, e.g. "P22_7". */
  id: string;
}

/** One provision of the law, as quoted (or paraphrased) in the model. */
export interface Provision {
  id: string;
  law: string; // "UU 14/2008"
  pasal: string; // "22"
  ayat?: string; // "7"
  /** Text of the provision. Must contain any number a deadline cites. */
  excerpt: string;
  /** False until someone checks `excerpt` against the official text. */
  verified: boolean;
  url?: string;
}

export interface Deadline {
  workingDays: number;
  /**
   * obligation: the actor must act; expiry is a failure by that actor.
   * window: the actor may act; expiry closes the option.
   */
  kind: 'obligation' | 'window';
  source: SourceRef;
  /** Interpretive choice made to encode this deadline, if any. */
  interpretation?: string;
}

export interface StateDef {
  id: StateId;
  label: string;
  description?: string;
  terminal?: boolean;
  /** Who may act while in this state. */
  actors?: ActorId[];
  /** Deadline counted from the working day after entering the state. */
  deadline?: Deadline;
  /**
   * Set when the text imposes a deadline but states no consequence on expiry.
   * Reported as a candidate legal gap instead of a model bug.
   */
  expiryGap?: string;
}

export interface Guard<C> {
  describe: string;
  test: (ctx: C) => boolean;
}

export interface Effect<C> {
  describe: string;
  apply: (ctx: C) => C;
}

export interface TransitionDef<C> {
  id: string;
  from: StateId;
  to: StateId;
  /** Event name. `TIMEOUT` is fired by the system when the deadline passes. */
  event: string;
  actor: ActorId;
  label: string;
  guard?: Guard<C>;
  effect?: Effect<C>;
  source?: SourceRef;
  interpretation?: string;
}

export const TIMEOUT = 'TIMEOUT';

export type Property<C> =
  | {
      kind: 'maxElapsed';
      id: string;
      description: string;
      from: StateId;
      to: StateId[];
      /** Omit to only report the computed worst case. */
      maxWorkingDays?: number;
      source?: SourceRef;
    }
  | {
      kind: 'reachable';
      id: string;
      description: string;
      /** From every reachable configuration in these states... */
      from: StateId[];
      /** ...some configuration in one of these states must be reachable. */
      target: StateId[];
      source?: SourceRef;
    }
  | {
      kind: 'never';
      id: string;
      description: string;
      predicate: (state: StateId, ctx: C) => boolean;
      source?: SourceRef;
    };

export interface Scenario<C> {
  id: string;
  label: string;
  ctx: C;
}

export interface Model<C> {
  id: string;
  title: string;
  law: string;
  disclaimer: string;
  actors: Record<ActorId, { label: string }>;
  sources: Record<string, Provision>;
  initial: StateId;
  /** Initial contexts. The explorer checks every one. */
  scenarios: Scenario<C>[];
  states: StateDef[];
  transitions: TransitionDef<C>[];
  properties: Property<C>[];
}

/** A copy whose arrays and records can be edited without touching the original. */
export function cloneModel<C>(m: Model<C>): Model<C> {
  return {
    ...m,
    actors: { ...m.actors },
    sources: Object.fromEntries(Object.entries(m.sources).map(([k, v]) => [k, { ...v }])),
    scenarios: m.scenarios.map((s) => ({ ...s })),
    states: m.states.map((s) => ({ ...s, deadline: s.deadline ? { ...s.deadline } : undefined })),
    transitions: m.transitions.map((t) => ({ ...t })),
    properties: m.properties.map((p) => ({ ...p })),
  };
}

export function stateById<C>(m: Model<C>, id: StateId): StateDef | undefined {
  return m.states.find((s) => s.id === id);
}

export function provision<C>(m: Model<C>, ref: SourceRef | undefined): Provision | undefined {
  return ref ? m.sources[ref.id] : undefined;
}

export function citation(p: Provision | undefined): string {
  if (!p) return 'tanpa sumber';
  return `${p.law} Pasal ${p.pasal}${p.ayat ? ` ayat (${p.ayat})` : ''}`;
}
