import { describe, expect, it } from 'vitest';
import { explore, violations } from './explore';
import { kipModel } from '../models/uu-14-2008/model';
import { mutants, mutate } from '../models/uu-14-2008/mutants';

describe('explorer on the KIP model', () => {
  const report = explore(kipModel);

  it('finds no violations in the reference model', () => {
    expect(violations(report)).toEqual([]);
  });

  it('reaches every state', () => {
    expect(new Set(report.reachedStates)).toEqual(new Set(kipModel.states.map((s) => s.id)));
  });

  it('computes worst-case deadlines', () => {
    const b = Object.fromEntries(report.bounds.map((x) => [x.propertyId, x.worstCase]));
    expect(b).toEqual({ tanggapan_17: 17, keberatan_60: 60, sampai_gugatan: 219 });
  });

  it('reports Pasal 38 deadlines without consequences as candidate legal gaps', () => {
    const gaps = report.findings.filter((f) => f.category === 'legal_gap_candidate');
    expect(gaps.flatMap((g) => g.states)).toEqual(['sengketa', 'penyelesaian']);
  });

  it('gives a replayable counterexample for the worst case', () => {
    const t = report.bounds.find((x) => x.propertyId === 'sampai_gugatan')!.trace!;
    expect(t.steps[0].from).toBe(kipModel.initial);
    for (let i = 1; i < t.steps.length; i++) expect(t.steps[i].from).toBe(t.steps[i - 1].to);
    expect(['gugatan_ptun', 'gugatan_pn']).toContain(t.steps.at(-1)!.to);
  });
});

describe('injected defects', () => {
  for (const m of mutants) {
    it(`catches: ${m.title}`, () => {
      const v = violations(explore(mutate(m)));
      const hits = v.filter((f) => m.expectedChecks.includes(f.check));
      expect(hits.length, `found: ${v.map((f) => f.check).join(', ') || 'nothing'}`).toBeGreaterThan(0);
    });
  }

  it('leaves the reference model untouched', () => {
    for (const m of mutants) mutate(m);
    expect(violations(explore(kipModel))).toEqual([]);
  });
});
