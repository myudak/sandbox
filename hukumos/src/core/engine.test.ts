import { describe, expect, it } from 'vitest';
import fc from 'fast-check';
import { addDays, workingDaysBetween } from './calendar';
import { dueDate, enabledTransitions, fire, type Run, start } from './engine';
import { TIMEOUT } from './ir';
import { type KipCtx, kipModel as m } from '../models/uu-14-2008/model';

const ctx: KipCtx = { perpanjangan: 0, badanPublik: 'negara' };

function must(r: ReturnType<typeof fire<KipCtx>>): Run<KipCtx> {
  if (!r.ok) throw new Error(r.error);
  return r.run;
}

describe('engine on UU 14/2008', () => {
  it('computes the Pasal 22(7) deadline in working days', () => {
    const run = start(m, ctx, '2026-11-13'); // Friday
    expect(dueDate(m, run)).toBe('2026-11-27');
  });

  it('allows one extension and refuses a second', () => {
    let run = must(fire(m, start(m, ctx, '2026-11-13'), 'perpanjang', '2026-11-20'));
    expect(run.ctx.perpanjangan).toBe(1);
    expect(enabledTransitions(m, run).some((t) => t.event === 'PERPANJANG')).toBe(false);
    run = must(fire(m, run, 'beri_2', dueDate(m, run)!));
    expect(run.stateId).toBe('diberikan');
  });

  it('rejects late actions and early timeouts', () => {
    const run = start(m, ctx, '2026-11-13');
    const due = dueDate(m, run)!;
    expect(fire(m, run, 'beri', addDays(due, 1)).ok).toBe(false);
    expect(fire(m, run, 'permohonan_lewat', due).ok).toBe(false);
    const late = must(fire(m, run, 'permohonan_lewat', addDays(due, 5)));
    expect(late.stateId).toBe('tidak_ditanggapi');
    expect(late.enteredAt).toBe(due);
  });

  it('enforces Pasal 47 jurisdiction through guards', () => {
    const non: KipCtx = { ...ctx, badanPublik: 'non_negara' };
    const run: Run<KipCtx> = { ctx: non, stateId: 'putusan_ajudikasi', enteredAt: '2026-11-13', history: [] };
    expect(fire(m, run, 'gugat_ptun', '2026-11-16').ok).toBe(false);
    expect(must(fire(m, run, 'gugat_pn', '2026-11-16')).stateId).toBe('gugatan_pn');
  });

  it('random legal walks always terminate within 219 working days', () => {
    fc.assert(
      fc.property(
        fc.constantFrom<KipCtx['badanPublik']>('negara', 'non_negara'),
        fc.array(fc.nat(), { minLength: 20, maxLength: 20 }),
        fc.array(fc.nat({ max: 30 }), { minLength: 20, maxLength: 20 }),
        (bp, picks, delays) => {
          const t0 = '2026-01-05';
          let run = start(m, { perpanjangan: 0, badanPublik: bp }, t0);
          for (let i = 0; i < 20; i++) {
            const options = enabledTransitions(m, run);
            if (options.length === 0) break;
            const t = options[picks[i] % options.length];
            const due = dueDate(m, run)!;
            // Act somewhere inside the allowed window, or just after it for TIMEOUT.
            const at = t.event === TIMEOUT ? addDays(due, 1 + (delays[i] % 3)) : minDate(addDays(run.enteredAt, delays[i]), due);
            run = must(fire(m, run, t.id, at));
            expect(run.ctx.perpanjangan).toBeLessThanOrEqual(1);
          }
          const final = m.states.find((s) => s.id === run.stateId)!;
          expect(final.terminal).toBe(true);
          expect(workingDaysBetween(t0, run.enteredAt)).toBeLessThanOrEqual(219);
        },
      ),
    );
  });
});

const minDate = (a: string, b: string) => (a < b ? a : b);
