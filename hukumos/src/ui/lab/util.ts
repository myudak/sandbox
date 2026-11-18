import type { ErrorKind, PasalResult, Results, Sample, Verdict } from '../../lab/types';
import raw from '../../data/results.json';

export const results = raw as unknown as Results;

export const VERDICT: Record<Verdict, { label: string; icon: string; tone: 'good' | 'warn' | 'bad' }> = {
  setia: { label: 'Setia', icon: '✓', tone: 'good' },
  mungkin_ambigu: { label: 'Mungkin ambigu', icon: '◐', tone: 'warn' },
  bermasalah: { label: 'Bermasalah', icon: '✗', tone: 'bad' },
  gagal: { label: 'Gagal', icon: '✗', tone: 'bad' },
};

export const ERROR_KIND: Record<ErrorKind, { label: string; caughtBy: string }> = {
  tidak_typecheck: { label: 'Tidak lolos typecheck', caughtBy: 'Lean' },
  konstruksi_terlarang: { label: 'Konstruksi terlarang (sorry, IO, …)', caughtBy: 'Filter' },
  skenario_gagal: { label: 'Salah pada skenario', caughtBy: 'Skenario' },
  properti_gagal: { label: 'Properti tidak terbukti', caughtBy: 'Lean (bukti)' },
  perubahan_diabaikan: { label: 'Perubahan teks diabaikan', caughtBy: 'Uji ubah teks' },
  perubahan_salah: { label: 'Perubahan teks diterjemahkan salah', caughtBy: 'Uji ubah teks' },
};

/** Group letter (A, B, …) of a sample, or null if it did not typecheck. */
export function groupOf(r: PasalResult, sampleId: string): string | null {
  const i = r.groups.findIndex((g) => g.members.includes(sampleId));
  return i < 0 ? null : String.fromCharCode(65 + i);
}

export function sampleById(r: PasalResult, id: string): Sample {
  return r.samples.find((s) => s.id === id) ?? r.samples[0];
}

// --- Quote linking -----------------------------------------------------------

export interface CodeLine {
  n: number;
  text: string;
  quotes: string[];
}

export function codeLines(code: string): CodeLine[] {
  return code.split('\n').map((text, i) => ({
    n: i + 1,
    text,
    quotes: [...text.matchAll(/--\s*dari:\s*"([^"]+)"/g)].map((m) => m[1]),
  }));
}

export interface Range {
  start: number;
  end: number;
  quote: string;
}

/** Where each quote occurs in the text (case-insensitive), plus quotes that don't occur at all. */
export function locateQuotes(text: string, quotes: string[]): { ranges: Range[]; missing: string[] } {
  const lower = text.toLowerCase();
  const ranges: Range[] = [];
  const missing: string[] = [];
  for (const q of new Set(quotes)) {
    const i = lower.indexOf(q.toLowerCase());
    if (i < 0) missing.push(q);
    else ranges.push({ start: i, end: i + q.length, quote: q });
  }
  return { ranges: ranges.sort((a, b) => a.start - b.start || b.end - a.end), missing };
}

/** Split text into segments, each tagged with every quote covering it. */
export function segments(text: string, ranges: Range[]): { text: string; quotes: string[] }[] {
  const cuts = new Set([0, text.length]);
  for (const r of ranges) {
    cuts.add(r.start);
    cuts.add(r.end);
  }
  const pts = [...cuts].sort((a, b) => a - b);
  const out: { text: string; quotes: string[] }[] = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const [a, b] = [pts[i], pts[i + 1]];
    out.push({ text: text.slice(a, b), quotes: ranges.filter((r) => r.start <= a && r.end >= b).map((r) => r.quote) });
  }
  return out;
}

// --- Rendering values for people ---------------------------------------------

export function humanize(returns: string, v: string | undefined): string {
  if (v === undefined) return '—';
  if (returns === 'HariKerja') return `hari kerja ke-${v}`;
  if (returns === 'Option HariKerja') return v === 'none' ? 'tidak ada batas (tidak pernah mulai)' : `hari kerja ke-${v.replace('some ', '')}`;
  if (returns === 'Bool') return v === 'true' ? 'boleh' : 'tidak boleh';
  if (returns === 'Pengadilan') return v === 'ptun' ? 'PTUN' : v === 'pn' ? 'Pengadilan Negeri' : v;
  return v;
}

export function argsText(r: PasalResult, args: string[]): string {
  return r.pasal.params.map((p, i) => `${p.name} = ${args[i]}`).join(', ');
}

// --- Line diff (LCS) ---------------------------------------------------------

export type DiffLine = { kind: 'same' | 'add' | 'del'; text: string };

export function lineDiff(a: string, b: string): DiffLine[] {
  const x = a.split('\n');
  const y = b.split('\n');
  const dp = Array.from({ length: x.length + 1 }, () => new Array<number>(y.length + 1).fill(0));
  for (let i = x.length - 1; i >= 0; i--)
    for (let j = y.length - 1; j >= 0; j--) dp[i][j] = x[i] === y[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < x.length && j < y.length) {
    if (x[i] === y[j]) {
      out.push({ kind: 'same', text: x[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ kind: 'del', text: x[i++] });
    else out.push({ kind: 'add', text: y[j++] });
  }
  while (i < x.length) out.push({ kind: 'del', text: x[i++] });
  while (j < y.length) out.push({ kind: 'add', text: y[j++] });
  return out;
}

export function storageGet<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function storageSet(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode or blocked storage: answers just won't persist */
  }
}
