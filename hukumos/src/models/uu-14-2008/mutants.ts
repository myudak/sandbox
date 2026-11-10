/**
 * Deliberately broken copies of the KIP model, one injected defect each.
 * They measure whether the explorer catches realistic modelling mistakes:
 * a mutant counts as caught when exploring it yields at least one violation
 * from one of its `expectedChecks`.
 */
import { cloneModel, type Model, SYSTEM, TIMEOUT } from '../../core/ir';
import { type KipCtx, kipModel } from './model';

export interface Mutant {
  id: string;
  title: string;
  /** What kind of real-world mistake this imitates. */
  defect: string;
  expectedChecks: string[];
  apply: (m: Model<KipCtx>) => void;
}

const st = (m: Model<KipCtx>, id: string) => {
  const s = m.states.find((x) => x.id === id);
  if (!s) throw new Error(`mutant: no state ${id}`);
  return s;
};
const tr = (m: Model<KipCtx>, id: string) => {
  const t = m.transitions.find((x) => x.id === id);
  if (!t) throw new Error(`mutant: no transition ${id}`);
  return t;
};
const drop = (m: Model<KipCtx>, id: string) => {
  tr(m, id);
  m.transitions = m.transitions.filter((t) => t.id !== id);
};

export const mutants: Mutant[] = [
  {
    id: 'perpanjangan_14',
    title: 'Perpanjangan 14 hari, bukan 7',
    defect: 'Salah angka batas waktu',
    expectedChecks: ['deadlineText', 'property'],
    apply: (m) => {
      st(m, 'diperpanjang').deadline!.workingDays = 14;
    },
  },
  {
    id: 'keberatan_3',
    title: 'Jendela keberatan 3 hari, bukan 30',
    defect: 'Salah ketik angka (lebih ketat, tidak melanggar batas atas)',
    expectedChecks: ['deadlineText'],
    apply: (m) => {
      st(m, 'ditolak').deadline!.workingDays = 3;
    },
  },
  {
    id: 'perpanjangan_berulang',
    title: 'Perpanjangan boleh berulang',
    defect: 'Syarat (guard) yang terlupa',
    expectedChecks: ['property', 'stateSpace', 'termination'],
    apply: (m) => {
      m.transitions.push({
        id: 'perpanjang_lagi',
        from: 'diperpanjang',
        to: 'diperpanjang',
        event: 'PERPANJANG',
        actor: 'ppid',
        label: 'Perpanjang lagi',
        source: { id: 'P22_8' },
        effect: { describe: 'perpanjangan + 1', apply: (c) => ({ ...c, perpanjangan: c.perpanjangan + 1 }) },
      });
    },
  },
  {
    id: 'tanpa_timeout_awal',
    title: 'Diamnya Badan Publik tidak berakibat',
    defect: 'Akibat lewat waktu terlupa',
    expectedChecks: ['deadlineExpiry'],
    apply: (m) => drop(m, 'permohonan_lewat'),
  },
  {
    id: 'tolak_tanpa_keberatan',
    title: 'Penolakan tidak bisa diajukan keberatan',
    defect: 'Upaya hukum yang hilang',
    expectedChecks: ['property'],
    apply: (m) => drop(m, 'keberatan_tolak'),
  },
  {
    id: 'aktor_salah',
    title: 'PPID menanggapi keberatan atas dirinya sendiri',
    defect: 'Pelaku yang salah',
    expectedChecks: ['actor'],
    apply: (m) => {
      tr(m, 'tanggapi').actor = 'ppid';
    },
  },
  {
    id: 'tanpa_sumber',
    title: 'Pengajuan sengketa tanpa dasar pasal',
    defect: 'Aturan tanpa jejak sumber',
    expectedChecks: ['traceability'],
    apply: (m) => {
      tr(m, 'sengketa_2').source = undefined;
    },
  },
  {
    id: 'diam_dianggap_jawab',
    title: 'Keberatan yang tidak dijawab dianggap sudah dijawab',
    defect: 'Tujuan transisi salah',
    expectedChecks: ['reachability'],
    apply: (m) => {
      tr(m, 'keberatan_lewat').to = 'keberatan_ditanggapi';
    },
  },
  {
    id: 'nondeterministik',
    title: '“Beri informasi” kadang berujung penolakan',
    defect: 'Peristiwa ganda dengan tujuan berbeda',
    expectedChecks: ['determinism'],
    apply: (m) => {
      m.transitions.push({ ...tr(m, 'tolak'), id: 'beri_tolak', event: 'BERI' });
    },
  },
  {
    id: 'yurisdiksi_tertukar',
    title: 'PTUN dan PN tertukar',
    defect: 'Syarat terbalik',
    expectedChecks: ['property'],
    apply: (m) => {
      const ptun = tr(m, 'gugat_ptun');
      const pn = tr(m, 'gugat_pn');
      [ptun.guard, pn.guard] = [pn.guard, ptun.guard];
    },
  },
  {
    id: 'jalan_buntu',
    title: 'Setelah keberatan dijawab, tidak ada langkah apa pun',
    defect: 'Transisi keluar hilang',
    expectedChecks: ['deadEnd', 'deadlineExpiry'],
    apply: (m) => {
      m.transitions = m.transitions.filter((t) => t.from !== 'keberatan_ditanggapi');
    },
  },
  {
    id: 'terminal_bocor',
    title: 'Status “Selesai” bisa dibuka lagi',
    defect: 'Status akhir yang tidak final',
    expectedChecks: ['terminalOutgoing', 'termination'],
    apply: (m) => {
      m.transitions.push({
        id: 'buka_lagi',
        from: 'selesai',
        to: 'permohonan',
        event: TIMEOUT,
        actor: SYSTEM,
        label: 'Buka lagi',
      });
    },
  },
];

export function mutate(m: Mutant, base: Model<KipCtx> = kipModel): Model<KipCtx> {
  const copy = cloneModel(base);
  m.apply(copy);
  return { ...copy, id: `${base.id}~${m.id}` };
}
