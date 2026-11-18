import { describe, expect, it } from 'vitest';
import { forbiddenIn, probesFor, sanitize } from '../../pipeline/lean';
import { lineDiff, locateQuotes, segments } from '../ui/lab/util';
import bench from '../../benchmark/kip.json';
import type { Benchmark } from './types';

const b = bench as Benchmark;

describe('pipeline helpers', () => {
  it('rejects unsound or effectful Lean, ignoring comments', () => {
    expect(forbiddenIn('def f := sorry')).toBe('sorry');
    expect(forbiddenIn('#eval IO.println "x"')).not.toBeNull();
    expect(forbiddenIn('def f (n : Nat) := n + 1 -- sorry, no IO here')).toBeNull();
  });

  it('strips lines the harness provides', () => {
    expect(sanitize('import Foo\nnamespace X\ndef f := 1\nend X')).toBe('def f := 1');
  });

  it('builds probes as the cartesian product of parameter values', () => {
    const p37 = b.pasal.find((p) => p.id === 'P37_2')!;
    expect(probesFor(p37)).toHaveLength(5 * 3);
  });

  it('every perturbation edits its pasal and every scenario has a known answer or readings', () => {
    for (const p of b.pasal) {
      for (const x of p.perturbations) expect(p.text.includes(x.find), `${p.id}/${x.id}`).toBe(true);
      for (const s of p.scenarios) {
        expect(s.args).toHaveLength(p.params.length);
        expect(s.expect !== undefined || s.readings !== undefined).toBe(true);
      }
    }
  });
});

describe('UI helpers', () => {
  it('links quotes to text and reports quotes not in the text', () => {
    const { ranges, missing } = locateQuotes('Paling lambat 10 (sepuluh) hari kerja', ['10 (sepuluh) hari', 'tidak ada']);
    expect(ranges).toEqual([{ start: 14, end: 31, quote: '10 (sepuluh) hari' }]);
    expect(missing).toEqual(['tidak ada']);
    expect(segments('Paling lambat 10 (sepuluh) hari kerja', ranges).map((s) => s.quotes.length)).toEqual([0, 1, 0]);
  });

  it('diffs lines', () => {
    expect(lineDiff('a\nb\nc', 'a\nx\nc').map((d) => d.kind)).toEqual(['same', 'del', 'add', 'same']);
  });
});
