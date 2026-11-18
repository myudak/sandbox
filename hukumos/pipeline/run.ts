/**
 * Translate every pasal in the benchmark N times, check each translation with
 * Lean, and write src/data/results.json for the UI.
 *
 *   npm run lab                     # hand-written example translations (no API key)
 *   npm run lab -- --llm            # Claude translations (needs ANTHROPIC_API_KEY)
 *   npm run lab -- --llm --samples 8 --only P37_2
 */
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type {
  BenchPasal,
  Benchmark,
  Group,
  PasalResult,
  PerturbationResult,
  Results,
  Sample,
  Verdict,
} from '../src/lab/types';
import {
  LEAN_DIR,
  evaluate,
  leanVersion,
  pool,
  probesFor,
  proofStatus,
  proveEquivalent,
  proveProperty,
  sanitize,
  typecheck,
} from './lean';
import { type Translator, anthropicTranslator, fixtureTranslator } from './translators';

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(here, '..');

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

async function main() {
  const bench: Benchmark = JSON.parse(await readFile(path.join(ROOT, 'benchmark/kip.json'), 'utf8'));
  const llm = process.argv.includes('--llm');
  const translator = llm ? await anthropicTranslator() : fixtureTranslator;
  const n = Number(arg('samples') ?? 5);
  const only = arg('only')?.split(',');
  const out = arg('out') ?? path.join(ROOT, 'src/data/results.json');
  const pasal = bench.pasal.filter((p) => !only || only.includes(p.id));

  console.log(`Translator: ${translator.name}, ${n} samples × ${pasal.length} pasal, Lean dir ${LEAN_DIR}`);
  const baselineSource = await readFile(path.join(LEAN_DIR, 'HukumOS/Kip/Baku.lean'), 'utf8');

  const results: PasalResult[] = [];
  for (const p of pasal) {
    const t0 = Date.now();
    results.push(await runPasal(p, translator, n, baselineSource));
    const r = results.at(-1)!;
    console.log(`  ${p.id.padEnd(6)} ${r.verdict.padEnd(15)} ${r.verdictReason}  (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  }

  const doc: Results = {
    generatedAt: new Date().toISOString(),
    translator: translator.name,
    illustrative: translator.illustrative,
    samplesPerPasal: n,
    leanVersion: await leanVersion(),
    benchmark: { id: bench.id, law: bench.law, note: bench.note },
    pasal: results,
  };
  await writeFile(out, `${JSON.stringify(doc, null, 2)}\n`);
  console.log(`Wrote ${path.relative(process.cwd(), out)}`);
}

async function runPasal(p: BenchPasal, tr: Translator, n: number, baselineSource: string): Promise<PasalResult> {
  const probes = probesFor(p);
  const base = await evaluate('', `HukumOS.Kip.Baku.${p.fn}`, p.scenarios, probes);
  if (!base.ok) throw new Error(`Baseline ${p.fn} failed to evaluate:\n${base.error}`);

  const codes = await pool(Array.from({ length: n }, (_, i) => i), 3, async (i) => {
    try {
      return sanitize(await tr.translate({ pasal: p, text: p.text, sample: i }));
    } catch (e) {
      return `-- penerjemah gagal: ${(e as Error).message.replaceAll('\n', ' ')}`;
    }
  });
  const samples = await pool(codes, 4, (code, i) => checkSample(`${p.id}#${i + 1}`, code, p, probes, base.probes));

  // Group typechecked samples by behaviour on scenarios + probes.
  const byKey = new Map<string, Sample[]>();
  for (const s of samples.filter((x) => x.typechecks)) {
    const key = JSON.stringify([p.scenarios.map((sc) => s.scenarioOutputs[sc.id]), s.probeOutputs]);
    byKey.set(key, [...(byKey.get(key) ?? []), s]);
  }
  const groups: Group[] = [...byKey.values()]
    .sort((a, b) => b.length - a.length)
    .map((ms) => ({
      members: ms.map((m) => m.id),
      consistentWithText: ms[0].failedScenarios.length === 0,
      readings: ms[0].readingsChosen,
    }));
  const groupSamples = groups.map((g) => samples.find((s) => s.id === g.members[0])!);
  const distinguishingProbes = probes
    .map((_, i) => i)
    .filter((i) => new Set(groupSamples.map((s) => s.probeOutputs[i])).size > 1);

  const representative = groups[0]?.members[0] ?? samples[0].id;
  const rep = samples.find((s) => s.id === representative)!;

  const perturbations: PerturbationResult[] = [];
  for (const pert of p.perturbations) {
    const textAfter = p.text.replace(pert.find, pert.replace);
    if (textAfter === p.text) throw new Error(`${p.id}/${pert.id}: find text not found in the pasal`);
    let code: string;
    try {
      code = sanitize(await tr.translate({ pasal: p, text: textAfter, sample: { perturbation: pert.id } }));
    } catch (e) {
      code = `-- penerjemah gagal: ${(e as Error).message}`;
    }
    const s = await checkSample(`${p.id}~${pert.id}`, code, p, probes, null);
    const ids = Object.keys(pert.expect);
    const pass = s.typechecks && ids.every((id) => s.scenarioOutputs[id] === pert.expect[id]);
    const changed = s.typechecks && rep.typechecks && ids.some((id) => s.scenarioOutputs[id] !== rep.scenarioOutputs[id]);
    if (s.typechecks && !pass) s.errorKinds.push(changed ? 'perubahan_salah' : 'perubahan_diabaikan');
    perturbations.push({ id: pert.id, label: pert.label, textAfter, sample: s, expect: pert.expect, pass, changed });
  }

  const ok = samples.filter((s) => s.typechecks);
  const scenarioChecks = ok.flatMap((s) => p.scenarios.filter((sc) => sc.expect !== undefined).map((sc) => !s.failedScenarios.includes(sc.id)));
  const propChecks = ok.flatMap((s) => Object.values(s.properties).map((v) => v === 'terbukti'));
  const metrics: PasalResult['metrics'] = {
    typecheck: [ok.length, samples.length],
    scenarios: [scenarioChecks.filter(Boolean).length, scenarioChecks.length],
    perturbations: [perturbations.filter((x) => x.pass).length, perturbations.length],
    agreement: [groups[0]?.members.length ?? 0, ok.length],
    equivalent: [ok.filter((s) => s.equivalence === 'terbukti').length, ok.length],
    properties: [propChecks.filter(Boolean).length, propChecks.length],
  };

  const [verdict, verdictReason] = decide(p, samples, groups, perturbations);
  return {
    pasal: p,
    baselineCode: extractBaseline(baselineSource, p.fn),
    baselineScenarioOutputs: base.scenarios,
    probes,
    samples,
    groups,
    distinguishingProbes,
    representative,
    perturbations,
    metrics,
    verdict,
    verdictReason,
  };
}

async function checkSample(
  id: string,
  code: string,
  p: BenchPasal,
  probes: string[][],
  baselineProbes: string[] | null,
): Promise<Sample> {
  const s: Sample = {
    id,
    code,
    typechecks: false,
    scenarioOutputs: {},
    probeOutputs: [],
    equivalence: 'tidak_diketahui',
    properties: {},
    failedScenarios: [],
    readingsChosen: {},
    errorKinds: [],
  };
  const tc = await typecheck(code);
  if (!tc.ok) {
    s.error = tc.error;
    s.errorKinds.push(tc.error?.startsWith('Konstruksi terlarang') || tc.error?.includes('sorry') ? 'konstruksi_terlarang' : 'tidak_typecheck');
    return s;
  }
  const ev = await evaluate(code, `Kandidat.${p.fn}`, p.scenarios, probes);
  if (!ev.ok) {
    s.error = ev.error;
    s.errorKinds.push('tidak_typecheck');
    return s;
  }
  s.typechecks = true;
  s.scenarioOutputs = ev.scenarios;
  s.probeOutputs = ev.probes;

  for (const sc of p.scenarios) {
    const got = ev.scenarios[sc.id];
    if (sc.expect !== undefined && got !== sc.expect) s.failedScenarios.push(sc.id);
    if (sc.readings) {
      s.readingsChosen[sc.id] = Object.entries(sc.readings).find(([, v]) => v === got)?.[0] ?? 'lain';
      if (s.readingsChosen[sc.id] === 'lain') s.failedScenarios.push(sc.id);
    }
  }
  // A translation of perturbed text is judged only by the perturbation's own expectations.
  if (!baselineProbes) {
    s.failedScenarios = [];
    s.readingsChosen = {};
    return s;
  }
  if (s.failedScenarios.length) s.errorKinds.push('skenario_gagal');

  const [props, equiv] = await Promise.all([
    Promise.all(p.properties.map(async (pr) => [pr.id, await proveProperty(code, p.fn, pr.statement)] as const)),
    proveEquivalent(code, p),
  ]);
  for (const [pid, proved] of props) s.properties[pid] = proved ? 'terbukti' : 'tidak_diketahui';
  if (props.some(([, proved]) => !proved)) s.errorKinds.push('properti_gagal');
  const differs = baselineProbes.some((v, i) => v !== s.probeOutputs[i]);
  s.equivalence = proofStatus(equiv, differs);
  return s;
}

function decide(p: BenchPasal, samples: Sample[], groups: Group[], perts: PerturbationResult[]): [Verdict, string] {
  const total = samples.length;
  if (groups.length === 0) return ['gagal', `Tidak ada terjemahan yang lolos typecheck (0/${total}).`];

  const plausible = groups.filter((g) => g.consistentWithText);
  const ambiguous = p.scenarios.filter((s) => s.readings);
  if (plausible.length >= 2 && ambiguous.length > 0) {
    const sizes = plausible.map((g) => g.members.length).join(' vs ');
    return ['mungkin_ambigu', `Terjemahan terbagi ${sizes} pada bacaan yang sama-sama sesuai teks.`];
  }

  const top = groups[0];
  const majority = top.members.length * 2 > total;
  const pertFails = perts.filter((x) => !x.pass);
  if (!top.consistentWithText) return ['bermasalah', 'Kelompok terbesar gagal pada skenario yang jelas.'];
  if (!majority) return ['bermasalah', `Tidak ada mayoritas: kelompok terbesar ${top.members.length}/${total}.`];
  if (pertFails.length) return ['bermasalah', `Uji ubah teks gagal: ${pertFails.map((x) => x.label).join(', ')}.`];

  const dissent = total - top.members.length;
  return ['setia', dissent ? `Mayoritas ${top.members.length}/${total} sesuai; ${dissent} sampel menyimpang.` : `Semua ${total} sampel sepakat dan sesuai skenario.`];
}

/** The baseline definition for one function, with its doc comment. */
function extractBaseline(src: string, fn: string): string {
  const lines = src.split('\n');
  const at = lines.findIndex((l) => l.startsWith(`def ${fn} `));
  if (at < 0) return '';
  let a = at;
  while (a > 0 && lines[a - 1].trim() !== '') a--;
  let b = at;
  while (b + 1 < lines.length && lines[b + 1].trim() !== '') b++;
  return lines.slice(a, b + 1).join('\n');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
