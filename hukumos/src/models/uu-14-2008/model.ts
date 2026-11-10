/**
 * UU 14/2008 tentang Keterbukaan Informasi Publik: the request → objection →
 * dispute → court procedure as a state machine.
 *
 * Scope: Pasal 22, 35–39, 47–48. Out of scope for now: fees, Perki 1/2013
 * procedural detail, partial fulfilment, withdrawal, appeal to the Mahkamah
 * Agung (Pasal 50), and anything after a lawsuit is filed.
 */
import { type Model, SYSTEM, TIMEOUT } from '../../core/ir';
import { sources } from './sources';

export interface KipCtx {
  /** Number of Pasal 22(8) extensions used for this request. */
  perpanjangan: number;
  /** Determines the court in Pasal 47. */
  badanPublik: 'negara' | 'non_negara';
}

const src = (id: keyof typeof sources) => ({ id });

export const kipModel: Model<KipCtx> = {
  id: 'uu-14-2008-kip',
  title: 'Permohonan Informasi Publik',
  law: 'UU 14/2008 tentang Keterbukaan Informasi Publik',
  disclaimer:
    'Prototipe interpretasi, bukan nasihat hukum. Teks pasal di sini masih parafrase dan belum diverifikasi terhadap teks resmi.',
  actors: {
    pemohon: { label: 'Pemohon' },
    ppid: { label: 'PPID / Badan Publik' },
    atasan: { label: 'Atasan PPID' },
    ki: { label: 'Komisi Informasi' },
    para_pihak: { label: 'Para pihak' },
    [SYSTEM]: { label: 'Sistem (waktu)' },
  },
  sources,
  initial: 'permohonan',
  scenarios: [
    { id: 'negara', label: 'Badan Publik negara', ctx: { perpanjangan: 0, badanPublik: 'negara' } },
    { id: 'non_negara', label: 'Badan Publik non-negara', ctx: { perpanjangan: 0, badanPublik: 'non_negara' } },
  ],

  states: [
    {
      id: 'permohonan',
      label: 'Permohonan diterima',
      description: 'Badan Publik wajib memberi pemberitahuan tertulis.',
      actors: ['ppid'],
      deadline: { workingDays: 10, kind: 'obligation', source: src('P22_7') },
    },
    {
      id: 'diperpanjang',
      label: 'Waktu diperpanjang',
      description: 'Perpanjangan dengan alasan tertulis.',
      actors: ['ppid'],
      deadline: {
        workingDays: 7,
        kind: 'obligation',
        source: src('P22_8'),
        interpretation:
          'Model menghitung 7 hari kerja sejak perpanjangan diberikan. “7 hari kerja berikutnya” juga bisa dibaca sejak 10 hari awal berakhir. Kedua bacaan sama bila perpanjangan diberikan pada hari ke-10; bila lebih awal, bacaan model lebih ketat bagi Badan Publik.',
      },
    },
    {
      id: 'diberikan',
      label: 'Informasi diberikan',
      description: 'Pemohon dapat menerima, atau keberatan (mis. tidak sesuai permintaan, biaya tidak wajar).',
      actors: ['pemohon'],
      deadline: { workingDays: 30, kind: 'window', source: src('P36_1') },
    },
    {
      id: 'ditolak',
      label: 'Permohonan ditolak',
      description: 'Penolakan dengan alasan, mis. informasi dikecualikan (Pasal 17).',
      actors: ['pemohon'],
      deadline: { workingDays: 30, kind: 'window', source: src('P36_1') },
    },
    {
      id: 'tidak_ditanggapi',
      label: 'Tidak ditanggapi',
      description: 'Batas waktu Badan Publik lewat tanpa pemberitahuan.',
      actors: ['pemohon'],
      deadline: {
        workingDays: 30,
        kind: 'window',
        source: src('P36_1'),
        interpretation: '“Ditemukannya alasan” untuk permintaan yang tidak ditanggapi dianggap terjadi saat batas waktu Badan Publik berakhir.',
      },
    },
    {
      id: 'keberatan',
      label: 'Keberatan diajukan',
      description: 'Atasan PPID wajib memberi tanggapan tertulis.',
      actors: ['atasan'],
      deadline: { workingDays: 30, kind: 'obligation', source: src('P36_2') },
    },
    {
      id: 'keberatan_ditanggapi',
      label: 'Keberatan ditanggapi',
      actors: ['pemohon'],
      deadline: { workingDays: 14, kind: 'window', source: src('P37_2') },
    },
    {
      id: 'keberatan_tidak_ditanggapi',
      label: 'Keberatan tidak ditanggapi',
      actors: ['pemohon'],
      deadline: {
        workingDays: 14,
        kind: 'window',
        source: src('P37_2'),
        interpretation:
          'Pasal 37(2) menghitung 14 hari kerja sejak “diterimanya tanggapan tertulis”. Jika atasan tidak menanggapi, tidak ada tanggapan yang diterima; model memakai berakhirnya batas 30 hari kerja sebagai titik mulai.',
      },
    },
    {
      id: 'sengketa',
      label: 'Sengketa di Komisi Informasi',
      description: 'Komisi Informasi wajib mulai mediasi dan/atau ajudikasi.',
      actors: ['ki'],
      deadline: { workingDays: 14, kind: 'obligation', source: src('P38_1') },
      expiryGap:
        'Undang-undang tidak menyebut apa yang terjadi bila Komisi Informasi tidak memulai penyelesaian dalam 14 hari kerja.',
    },
    {
      id: 'penyelesaian',
      label: 'Mediasi / ajudikasi berjalan',
      actors: ['ki'],
      deadline: {
        workingDays: 100,
        kind: 'obligation',
        source: src('P38_2'),
        interpretation: 'Model menghitung 100 hari kerja sejak penyelesaian dimulai, bukan sejak permohonan sengketa diterima.',
      },
      expiryGap:
        'Undang-undang tidak menyebut akibat bila penyelesaian melewati 100 hari kerja (“paling lambat dapat diselesaikan”).',
    },
    {
      id: 'putusan_ajudikasi',
      label: 'Putusan ajudikasi',
      actors: ['para_pihak'],
      deadline: { workingDays: 14, kind: 'window', source: src('P48_1') },
    },

    { id: 'selesai', label: 'Selesai', terminal: true, description: 'Pemohon tidak menempuh upaya lanjutan.' },
    { id: 'selesai_mediasi', label: 'Selesai melalui mediasi', terminal: true, description: 'Final dan mengikat (Pasal 39).' },
    { id: 'putusan_tetap', label: 'Putusan ajudikasi diterima', terminal: true },
    { id: 'gugatan_ptun', label: 'Gugatan ke PTUN', terminal: true, description: 'Di luar cakupan model.' },
    { id: 'gugatan_pn', label: 'Gugatan ke Pengadilan Negeri', terminal: true, description: 'Di luar cakupan model.' },
  ],

  transitions: [
    // Pasal 22: response to the request
    { id: 'beri', from: 'permohonan', to: 'diberikan', event: 'BERI', actor: 'ppid', label: 'Beri informasi', source: src('P22_7') },
    { id: 'tolak', from: 'permohonan', to: 'ditolak', event: 'TOLAK', actor: 'ppid', label: 'Tolak (dengan alasan)', source: src('P22_7') },
    {
      id: 'perpanjang',
      from: 'permohonan',
      to: 'diperpanjang',
      event: 'PERPANJANG',
      actor: 'ppid',
      label: 'Perpanjang waktu',
      source: src('P22_8'),
      guard: { describe: 'belum pernah diperpanjang', test: (c) => c.perpanjangan === 0 },
      effect: { describe: 'perpanjangan + 1', apply: (c) => ({ ...c, perpanjangan: c.perpanjangan + 1 }) },
    },
    { id: 'permohonan_lewat', from: 'permohonan', to: 'tidak_ditanggapi', event: TIMEOUT, actor: SYSTEM, label: '10 hari kerja lewat' },

    { id: 'beri_2', from: 'diperpanjang', to: 'diberikan', event: 'BERI', actor: 'ppid', label: 'Beri informasi', source: src('P22_8') },
    { id: 'tolak_2', from: 'diperpanjang', to: 'ditolak', event: 'TOLAK', actor: 'ppid', label: 'Tolak (dengan alasan)', source: src('P22_8') },
    { id: 'perpanjang_lewat', from: 'diperpanjang', to: 'tidak_ditanggapi', event: TIMEOUT, actor: SYSTEM, label: '7 hari kerja lewat' },

    // Pasal 35–36: objection to the PPID's superior
    { id: 'terima_info', from: 'diberikan', to: 'selesai', event: 'TERIMA', actor: 'pemohon', label: 'Terima', source: src('P35_1') },
    { id: 'keberatan_info', from: 'diberikan', to: 'keberatan', event: 'KEBERATAN', actor: 'pemohon', label: 'Ajukan keberatan', source: src('P35_1') },
    { id: 'diberikan_lewat', from: 'diberikan', to: 'selesai', event: TIMEOUT, actor: SYSTEM, label: '30 hari kerja lewat' },

    { id: 'terima_tolak', from: 'ditolak', to: 'selesai', event: 'TERIMA', actor: 'pemohon', label: 'Terima penolakan', source: src('P35_1') },
    { id: 'keberatan_tolak', from: 'ditolak', to: 'keberatan', event: 'KEBERATAN', actor: 'pemohon', label: 'Ajukan keberatan', source: src('P35_1') },
    { id: 'ditolak_lewat', from: 'ditolak', to: 'selesai', event: TIMEOUT, actor: SYSTEM, label: '30 hari kerja lewat' },

    { id: 'keberatan_diam', from: 'tidak_ditanggapi', to: 'keberatan', event: 'KEBERATAN', actor: 'pemohon', label: 'Ajukan keberatan', source: src('P35_1') },
    { id: 'diam_lewat', from: 'tidak_ditanggapi', to: 'selesai', event: TIMEOUT, actor: SYSTEM, label: '30 hari kerja lewat' },

    { id: 'tanggapi', from: 'keberatan', to: 'keberatan_ditanggapi', event: 'TANGGAPI', actor: 'atasan', label: 'Tanggapi keberatan', source: src('P36_2') },
    { id: 'keberatan_lewat', from: 'keberatan', to: 'keberatan_tidak_ditanggapi', event: TIMEOUT, actor: SYSTEM, label: '30 hari kerja lewat' },

    // Pasal 37–38: dispute at the Komisi Informasi
    { id: 'puas', from: 'keberatan_ditanggapi', to: 'selesai', event: 'TERIMA', actor: 'pemohon', label: 'Terima tanggapan', source: src('P37_1') },
    { id: 'sengketa_1', from: 'keberatan_ditanggapi', to: 'sengketa', event: 'SENGKETA', actor: 'pemohon', label: 'Ajukan sengketa ke KI', source: src('P37_1') },
    { id: 'tanggapan_lewat', from: 'keberatan_ditanggapi', to: 'selesai', event: TIMEOUT, actor: SYSTEM, label: '14 hari kerja lewat' },

    { id: 'sengketa_2', from: 'keberatan_tidak_ditanggapi', to: 'sengketa', event: 'SENGKETA', actor: 'pemohon', label: 'Ajukan sengketa ke KI', source: src('P37_1') },
    { id: 'sengketa_lewat', from: 'keberatan_tidak_ditanggapi', to: 'selesai', event: TIMEOUT, actor: SYSTEM, label: '14 hari kerja lewat' },

    { id: 'mulai', from: 'sengketa', to: 'penyelesaian', event: 'MULAI', actor: 'ki', label: 'Mulai mediasi / ajudikasi', source: src('P38_1') },
    { id: 'mediasi', from: 'penyelesaian', to: 'selesai_mediasi', event: 'MEDIASI_BERHASIL', actor: 'ki', label: 'Mediasi berhasil', source: src('P39') },
    { id: 'putus', from: 'penyelesaian', to: 'putusan_ajudikasi', event: 'PUTUS', actor: 'ki', label: 'Putusan ajudikasi', source: src('P38_2') },

    // Pasal 47–48: lawsuit
    {
      id: 'gugat_ptun',
      from: 'putusan_ajudikasi',
      to: 'gugatan_ptun',
      event: 'GUGAT',
      actor: 'para_pihak',
      label: 'Gugat ke PTUN',
      source: src('P47'),
      guard: { describe: 'Badan Publik negara', test: (c) => c.badanPublik === 'negara' },
    },
    {
      id: 'gugat_pn',
      from: 'putusan_ajudikasi',
      to: 'gugatan_pn',
      event: 'GUGAT',
      actor: 'para_pihak',
      label: 'Gugat ke PN',
      source: src('P47'),
      guard: { describe: 'Badan Publik non-negara', test: (c) => c.badanPublik === 'non_negara' },
    },
    { id: 'terima_putusan', from: 'putusan_ajudikasi', to: 'putusan_tetap', event: 'TERIMA', actor: 'para_pihak', label: 'Terima putusan', source: src('P48_1') },
    { id: 'putusan_lewat', from: 'putusan_ajudikasi', to: 'putusan_tetap', event: TIMEOUT, actor: SYSTEM, label: '14 hari kerja lewat' },
  ],

  properties: [
    {
      kind: 'maxElapsed',
      id: 'tanggapan_17',
      description: 'Badan Publik menanggapi paling lama 10 + 7 hari kerja',
      from: 'permohonan',
      to: ['diberikan', 'ditolak', 'tidak_ditanggapi'],
      maxWorkingDays: 17,
      source: src('P22_8'),
    },
    {
      kind: 'maxElapsed',
      id: 'keberatan_60',
      description: 'Dari penolakan sampai keberatan dijawab (atau lewat) paling lama 30 + 30 hari kerja',
      from: 'ditolak',
      to: ['keberatan_ditanggapi', 'keberatan_tidak_ditanggapi'],
      maxWorkingDays: 60,
      source: src('P36_2'),
    },
    {
      kind: 'maxElapsed',
      id: 'sampai_gugatan',
      description: 'Waktu terlama dari permohonan sampai gugatan ke pengadilan',
      from: 'permohonan',
      to: ['gugatan_ptun', 'gugatan_pn'],
    },
    {
      kind: 'reachable',
      id: 'upaya_hukum',
      description: 'Pemohon yang ditolak, diabaikan, atau tidak puas selalu bisa membawa sengketa ke Komisi Informasi',
      from: ['diberikan', 'ditolak', 'tidak_ditanggapi'],
      target: ['sengketa'],
      source: src('P37_1'),
    },
    {
      kind: 'reachable',
      id: 'jalur_pengadilan',
      description: 'Putusan ajudikasi selalu bisa digugat ke pengadilan yang berwenang',
      from: ['putusan_ajudikasi'],
      target: ['gugatan_ptun', 'gugatan_pn'],
      source: src('P48_1'),
    },
    {
      kind: 'never',
      id: 'satu_perpanjangan',
      description: 'Perpanjangan waktu paling banyak satu kali',
      predicate: (_s, c) => c.perpanjangan > 1,
      source: src('P22_8'),
    },
    {
      kind: 'never',
      id: 'yurisdiksi',
      description: 'Gugatan diajukan ke pengadilan yang berwenang (PTUN untuk Badan Publik negara, PN untuk non-negara)',
      predicate: (s, c) =>
        (s === 'gugatan_ptun' && c.badanPublik !== 'negara') || (s === 'gugatan_pn' && c.badanPublik !== 'non_negara'),
      source: src('P47'),
    },
  ],
};
