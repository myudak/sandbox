/**
 * CLI report: explores the KIP model and every mutant.
 *   npm run verify
 */
import { explore, fmtDays, violations } from '../src/core/explore';
import { citation } from '../src/core/ir';
import { kipModel } from '../src/models/uu-14-2008/model';
import { mutants, mutate } from '../src/models/uu-14-2008/mutants';

const r = explore(kipModel);
const by = (c: string) => r.findings.filter((f) => f.category === c);

console.log(`\n${kipModel.law}: ${kipModel.title}`);
console.log(
  `${r.stats.configurations} konfigurasi, ${r.stats.edges} transisi, ${r.stats.scenarios} skenario, ${r.stats.unverifiedSources} pasal belum diverifikasi\n`,
);

console.log(`Pelanggaran: ${by('violation').length}`);
for (const f of by('violation')) console.log(`  ✗ [${f.check}] ${f.message}`);

console.log(`\nBatas waktu terburuk:`);
for (const b of r.bounds) {
  const ok = b.limit === undefined ? ' ' : b.worstCase !== null && b.worstCase <= b.limit ? '✓' : '✗';
  console.log(`  ${ok} ${b.description}: ${fmtDays(b.worstCase)}${b.limit !== undefined ? ` (batas ${b.limit})` : ''}`);
}

console.log(`\nKandidat celah hukum: ${by('legal_gap_candidate').length}`);
for (const f of by('legal_gap_candidate')) console.log(`  ? ${f.message} [${citation(f.source && kipModel.sources[f.source.id])}]`);

console.log(`\nPilihan interpretasi: ${by('interpretation').length}`);
for (const f of by('interpretation')) console.log(`  ~ ${f.message}`);

console.log(`\nUji mutan (cacat yang disuntikkan):`);
let caught = 0;
for (const m of mutants) {
  const v = violations(explore(mutate(m)));
  const hit = v.filter((f) => m.expectedChecks.includes(f.check));
  if (hit.length) caught++;
  const checks = [...new Set(v.map((f) => f.check))].join(', ') || 'tidak ada';
  console.log(`  ${hit.length ? '✓' : '✗'} ${m.title}  →  ${checks}`);
}
console.log(`\nTertangkap ${caught}/${mutants.length} mutan.\n`);

if (by('violation').length || caught < mutants.length) process.exitCode = 1;
