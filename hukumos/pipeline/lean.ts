/**
 * Runs candidate Lean code against the HukumOS library: typecheck, evaluate on
 * scenarios and probes, and try to prove properties and equivalence with the
 * baseline. Every check is a separate `lake env lean` invocation so one failed
 * proof doesn't hide the others.
 */
import { execFile } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { BenchPasal, ProofStatus } from '../src/lab/types';

const here = path.dirname(fileURLToPath(import.meta.url));
export const LEAN_DIR = path.resolve(here, '../lean');
const WORK = path.join(LEAN_DIR, 'work');

/** Constructs a translation may not use: unsound escapes and anything that runs code. */
const FORBIDDEN = /\b(sorry|admit|axiom|unsafe|partial|IO|run_cmd|run_tac|initialize|implemented_by|extern|macro|syntax|elab|macro_rules|native_decide)\b|#eval|#print|#exit|@\[/;

export function stripComments(code: string): string {
  return code.replace(/\/-[\s\S]*?-\//g, '').replace(/--.*$/gm, '');
}

export function forbiddenIn(code: string): string | null {
  const m = stripComments(code).match(FORBIDDEN);
  return m ? m[0] : null;
}

/** Drop lines the harness provides itself. */
export function sanitize(code: string): string {
  return code
    .split('\n')
    .filter((l) => !/^\s*(import|namespace|end\s+\w|open\s+HukumOS\s*$|set_option)\b/.test(l))
    .join('\n')
    .trim();
}

let counter = 0;

function run(cmd: string, args: string[], timeoutMs: number): Promise<{ code: number; out: string }> {
  return new Promise((resolve) => {
    execFile(cmd, args, { cwd: LEAN_DIR, timeout: timeoutMs, maxBuffer: 4 << 20 }, (err, stdout, stderr) => {
      resolve({ code: err ? 1 : 0, out: `${stdout}${stderr}${err && !stdout && !stderr ? String(err) : ''}` });
    });
  });
}

async function leanFile(source: string, mode: 'check' | 'run'): Promise<{ ok: boolean; out: string }> {
  await mkdir(WORK, { recursive: true });
  const file = path.join(WORK, `c${process.pid}_${counter++}.lean`);
  await writeFile(file, source);
  const args = mode === 'run' ? ['env', 'lean', '--run', file] : ['env', 'lean', file];
  const r = await run('lake', args, 120_000);
  const errored = r.code !== 0 || /\berror\b:/.test(r.out);
  return { ok: !errored, out: r.out.replaceAll(file, '<kandidat>.lean') };
}

const HEADER = 'import HukumOS\nopen HukumOS\n';

function wrap(code: string): string {
  return `${HEADER}\nnamespace Kandidat\n${code}\nend Kandidat\n`;
}

const call = (target: string, args: string[]) => (args.length ? `(${target} ${args.join(' ')})` : target);

/** Typecheck only. */
export async function typecheck(code: string): Promise<{ ok: boolean; error?: string }> {
  const bad = forbiddenIn(code);
  if (bad) return { ok: false, error: `Konstruksi terlarang: ${bad}` };
  const r = await leanFile(wrap(code), 'check');
  if (!r.ok) return { ok: false, error: firstError(r.out) };
  if (/declaration uses 'sorry'/.test(r.out)) return { ok: false, error: "Memakai 'sorry'" };
  return { ok: true };
}

function firstError(out: string): string {
  const lines = out.split('\n');
  const i = lines.findIndex((l) => /error:/.test(l));
  return (i >= 0 ? lines.slice(i, i + 6) : lines.slice(0, 6)).join('\n').trim().slice(0, 800);
}

/**
 * Evaluate `target` (a function name, e.g. "Kandidat.f" or the baseline's) on
 * scenarios and probes. `code` may be empty when the target is the baseline.
 */
export async function evaluate(
  code: string,
  target: string,
  scenarios: { id: string; args: string[] }[],
  probes: string[][],
): Promise<{ ok: boolean; error?: string; scenarios: Record<string, string>; probes: string[] }> {
  const lines = [
    ...scenarios.map((s) => `  IO.println s!"S\\t${s.id}\\t{Tampil.tampil ${call(target, s.args)}}"`),
    ...probes.map((p, i) => `  IO.println s!"P\\t${i}\\t{Tampil.tampil ${call(target, p)}}"`),
  ];
  const src = `${code ? wrap(code) : HEADER}\ndef main : IO Unit := do\n${lines.join('\n')}\n  pure ()\n`;
  const r = await leanFile(src, 'run');
  const out = { scenarios: {} as Record<string, string>, probes: [] as string[] };
  if (!r.ok) return { ok: false, error: firstError(r.out), ...out };
  for (const line of r.out.split('\n')) {
    const [kind, key, ...rest] = line.split('\t');
    const value = rest.join('\t').trim();
    if (kind === 'S') out.scenarios[key] = value;
    if (kind === 'P') out.probes[Number(key)] = value;
  }
  return { ok: true, ...out };
}

const tactic = (unfold: string[]) => {
  const u = [...unfold, 'HukumOS.batasWaktu'].join(', ');
  return `by
  first
  | rfl
  | decide
  | (intros; rfl)
  | (intros; simp [${u}]; done)
  | (intros; simp [${u}] <;> omega)
  | (intro a; cases a <;> rfl)
  | (intro a; cases a <;> simp [${u}]; done)
  | (intro a b; cases b <;> simp [${u}] <;> omega)
  | (intro a b; cases b <;> simp [${u}]; done)
  | (intros; simp_all [${u}]; done)
  | (intros; simp_all [${u}] <;> omega)`;
};

/** Try to prove a property of the candidate. `F` in the statement is replaced by the candidate. */
export async function proveProperty(code: string, fn: string, statement: string): Promise<boolean> {
  const stmt = statement.replace(/\bF\b/g, `Kandidat.${fn}`);
  const src = `${wrap(code)}\ntheorem cek : ${stmt} := ${tactic([`Kandidat.${fn}`])}\n`;
  return (await leanFile(src, 'check')).ok;
}

/** Try to prove the candidate equal to the baseline on all inputs. */
export async function proveEquivalent(code: string, p: BenchPasal): Promise<boolean> {
  const vars = p.params.map((x, i) => `(x${i} : ${x.type})`).join(' ');
  const xs = p.params.map((_, i) => `x${i}`).join(' ');
  const base = `HukumOS.Kip.Baku.${p.fn}`;
  const stmt = `∀ ${vars}, Kandidat.${p.fn} ${xs} = ${base} ${xs}`;
  const src = `${wrap(code)}\ntheorem setara : ${stmt} := ${tactic([`Kandidat.${p.fn}`, base])}\n`;
  return (await leanFile(src, 'check')).ok;
}

export function proofStatus(proved: boolean, counterexample: boolean): ProofStatus {
  if (proved) return 'terbukti';
  return counterexample ? 'berbeda' : 'tidak_diketahui';
}

export async function leanVersion(): Promise<string> {
  const r = await run('lake', ['env', 'lean', '--version'], 30_000);
  return r.out.trim().split('\n')[0];
}

/** Sample values per Lean type, used to build probe inputs. */
const PROBE_VALUES: Record<string, string[]> = {
  HariKerja: ['0', '3', '10', '14', '30'],
  'Option HariKerja': ['none', '(some 0)', '(some 20)'],
  JenisBadanPublik: ['.negara', '.nonNegara'],
  AlasanKeberatan: [
    '.penolakanPasal17',
    '.informasiBerkalaTidakDisediakan',
    '.tidakDitanggapi',
    '.tidakSesuaiPermintaan',
    '.tidakDipenuhi',
    '.biayaTidakWajar',
    '.melebihiWaktu',
    '.lainnya',
  ],
  Bool: ['true', 'false'],
};

export function probesFor(p: BenchPasal): string[][] {
  let acc: string[][] = [[]];
  for (const param of p.params) {
    const vals = PROBE_VALUES[param.type];
    if (!vals) throw new Error(`No probe values for type ${param.type}`);
    acc = acc.flatMap((prefix) => vals.map((v) => [...prefix, v]));
  }
  return acc;
}

/** Run async jobs with bounded concurrency, preserving order. */
export async function pool<T, R>(items: T[], n: number, f: (x: T, i: number) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(n, items.length) }, async () => {
      while (next < items.length) {
        const i = next++;
        out[i] = await f(items[i], i);
      }
    }),
  );
  return out;
}
