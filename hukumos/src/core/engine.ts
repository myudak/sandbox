/**
 * Executes a model step by step on concrete dates.
 *
 * Rules the engine enforces:
 * - an action must happen on or after the day the current state was entered;
 * - an action by a party must happen on or before the state's deadline;
 * - TIMEOUT can only fire after the deadline has passed;
 * - a transition's guard must hold for the current context.
 */
import { addWorkingDays, type Calendar, type IsoDate, WEEKENDS_ONLY } from './calendar';
import { type Model, type StateDef, type StateId, TIMEOUT, type TransitionDef, stateById } from './ir';

export interface HistoryEntry {
  transitionId: string;
  from: StateId;
  to: StateId;
  at: IsoDate;
  /** Deadline of the state that was left, if it had one. */
  due?: IsoDate;
}

export interface Run<C> {
  ctx: C;
  stateId: StateId;
  enteredAt: IsoDate;
  history: HistoryEntry[];
}

export type FireResult<C> = { ok: true; run: Run<C> } | { ok: false; error: string };

export function start<C>(model: Model<C>, ctx: C, at: IsoDate): Run<C> {
  return { ctx, stateId: model.initial, enteredAt: at, history: [] };
}

export function currentState<C>(model: Model<C>, run: Run<C>): StateDef {
  const s = stateById(model, run.stateId);
  if (!s) throw new Error(`Status tidak dikenal: ${run.stateId}`);
  return s;
}

export function dueDate<C>(model: Model<C>, run: Run<C>, cal: Calendar = WEEKENDS_ONLY): IsoDate | undefined {
  const d = currentState(model, run).deadline;
  return d ? addWorkingDays(run.enteredAt, d.workingDays, cal) : undefined;
}

/** Transitions out of the current state whose guards hold, regardless of date. */
export function enabledTransitions<C>(model: Model<C>, run: Run<C>): TransitionDef<C>[] {
  return model.transitions.filter((t) => t.from === run.stateId && (!t.guard || t.guard.test(run.ctx)));
}

export function fire<C>(
  model: Model<C>,
  run: Run<C>,
  transitionId: string,
  at: IsoDate,
  cal: Calendar = WEEKENDS_ONLY,
): FireResult<C> {
  const t = model.transitions.find((x) => x.id === transitionId);
  if (!t) return { ok: false, error: `Transisi tidak dikenal: ${transitionId}` };
  if (t.from !== run.stateId) return { ok: false, error: `“${t.label}” tidak tersedia pada status ini.` };
  if (t.guard && !t.guard.test(run.ctx)) return { ok: false, error: `Syarat tidak terpenuhi: ${t.guard.describe}` };
  if (!stateById(model, t.to)) return { ok: false, error: `Status tujuan tidak dikenal: ${t.to}` };
  if (at < run.enteredAt) return { ok: false, error: `Tanggal ${at} sebelum status ini dimulai (${run.enteredAt}).` };

  const due = dueDate(model, run, cal);
  if (t.event === TIMEOUT) {
    if (!due) return { ok: false, error: 'Status ini tidak memiliki batas waktu.' };
    if (at <= due) return { ok: false, error: `Batas waktu belum lewat (berakhir ${due}).` };
  } else if (due && at > due) {
    return { ok: false, error: `Terlambat: batas waktu berakhir ${due}.` };
  }

  const ctx = t.effect ? t.effect.apply(run.ctx) : run.ctx;
  // After a timeout the next period counts from the day the deadline ended,
  // not from whenever someone noticed it had passed.
  const effective = t.event === TIMEOUT && due ? due : at;
  return {
    ok: true,
    run: {
      ctx,
      stateId: t.to,
      enteredAt: effective,
      history: [...run.history, { transitionId: t.id, from: t.from, to: t.to, at: effective, due }],
    },
  };
}
