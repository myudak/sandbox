/**
 * Hand-written example translations, standing in for LLM output so the
 * pipeline can run without an API key. They deliberately include the kinds of
 * variation and mistakes the checks are meant to find:
 *
 * - P22_8, P37_2, P38_2: samples split between two readings of unclear text
 * - P35_1: one sample treats the list of grounds as open-ended
 * - P36_2: one sample uses the wrong number (14 instead of 30)
 * - P48_1: one sample does not typecheck
 * - P36_1: the translation of the perturbed text ignores the change
 *
 * Results produced from these are marked illustrative in results.json and the UI.
 */

type Fixture = { samples: string[]; perturbations: Record<string, string> };

const q = (s: string) => `-- dari: "${s}"`;

const deadline = (fn: string, param: string, n: number, quote: string, style: 'plus' | 'fn' = 'plus') =>
  `def ${fn} (${param} : HariKerja) : HariKerja :=\n  ${style === 'plus' ? `${param} + ${n}` : `batasWaktu ${param} ${n}`} ${q(quote)}`;

const FIXTURES: Record<string, Fixture> = {
  P22_7: {
    samples: [
      deadline('batasPemberitahuan', 'diterima', 10, 'Paling lambat 10 (sepuluh) hari kerja sejak diterimanya permintaan'),
      deadline('batasPemberitahuan', 'diterima', 10, 'Paling lambat 10 (sepuluh) hari kerja', 'fn'),
      deadline('batasPemberitahuan', 'diterima', 10, '10 (sepuluh) hari kerja sejak diterimanya permintaan'),
      `-- Batas waktu pemberitahuan tertulis
def batasPemberitahuan (diterima : HariKerja) : HariKerja :=
  let lama := 10 ${q('10 (sepuluh) hari kerja')}
  diterima + lama ${q('sejak diterimanya permintaan')}`,
      deadline('batasPemberitahuan', 'diterima', 10, 'Paling lambat 10 (sepuluh) hari kerja sejak diterimanya permintaan', 'fn'),
    ],
    perturbations: {
      angka: deadline('batasPemberitahuan', 'diterima', 3, 'Paling lambat 3 (tiga) hari kerja sejak diterimanya permintaan'),
    },
  },

  P22_8: {
    samples: [
      `def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  -- "berikutnya" dibaca: setelah periode 10 hari pada ayat (7) berakhir
  diterima + 10 + 7 ${q('paling lambat 7 (tujuh) hari kerja berikutnya')}`,
      `def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  -- dihitung sejak perpanjangan diberitahukan
  perpanjangPada + 7 ${q('paling lambat 7 (tujuh) hari kerja berikutnya')}`,
      `def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  batasWaktu (batasWaktu diterima 10) 7 ${q('memperpanjang waktu untuk mengirimkan pemberitahuan sebagaimana dimaksud pada ayat (7), paling lambat 7 (tujuh) hari kerja berikutnya')}`,
      `def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  batasWaktu perpanjangPada 7 ${q('7 (tujuh) hari kerja berikutnya')}`,
      `def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  let akhirAwal := diterima + 10 ${q('sebagaimana dimaksud pada ayat (7)')}
  akhirAwal + 7 ${q('paling lambat 7 (tujuh) hari kerja berikutnya')}`,
    ],
    perturbations: {
      angka: `def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  diterima + 10 + 14 ${q('paling lambat 14 (empat belas) hari kerja berikutnya')}`,
    },
  },

  P35_1: {
    samples: [
      `def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  match a with
  | .penolakanPasal17 => true ${q('penolakan atas permintaan informasi berdasarkan alasan pengecualian')}
  | .informasiBerkalaTidakDisediakan => true ${q('tidak disediakannya informasi berkala')}
  | .tidakDitanggapi => true ${q('tidak ditanggapinya permintaan informasi')}
  | .tidakSesuaiPermintaan => true ${q('permintaan informasi ditanggapi tidak sebagaimana yang diminta')}
  | .tidakDipenuhi => true ${q('tidak dipenuhinya permintaan informasi')}
  | .biayaTidakWajar => true ${q('pengenaan biaya yang tidak wajar')}
  | .melebihiWaktu => true ${q('penyampaian informasi yang melebihi waktu yang diatur')}
  | .lainnya => false`,
      `def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  a != .lainnya ${q('berdasarkan alasan berikut')}`,
      `def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  match a with
  | .lainnya => false
  | _ => true ${q('dapat mengajukan keberatan secara tertulis kepada atasan Pejabat Pengelola Informasi dan Dokumentasi berdasarkan alasan berikut')}`,
      `-- Daftar alasan dibaca sebagai contoh, bukan daftar tertutup
def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  let _ := a
  true ${q('Setiap Pemohon Informasi Publik dapat mengajukan keberatan')}`,
      `def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  match a with
  | .lainnya => false
  | _ => true ${q('berdasarkan alasan berikut')}`,
    ],
    perturbations: {
      hapus_butir: `def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  match a with
  | .biayaTidakWajar => false
  | .lainnya => false
  | _ => true ${q('berdasarkan alasan berikut')}`,
    },
  },

  P36_1: {
    samples: [
      deadline('batasKeberatan', 'alasanDitemukan', 30, 'paling lambat 30 (tiga puluh) hari kerja setelah ditemukannya alasan'),
      deadline('batasKeberatan', 'alasanDitemukan', 30, '30 (tiga puluh) hari kerja', 'fn'),
      deadline('batasKeberatan', 'alasanDitemukan', 30, 'paling lambat 30 (tiga puluh) hari kerja setelah ditemukannya alasan', 'fn'),
      deadline('batasKeberatan', 'alasanDitemukan', 30, 'dalam jangka waktu paling lambat 30 (tiga puluh) hari kerja'),
      deadline('batasKeberatan', 'alasanDitemukan', 30, '30 (tiga puluh) hari kerja setelah ditemukannya alasan'),
    ],
    perturbations: {
      // The text now says 3 days; this translation still says 30.
      angka: deadline('batasKeberatan', 'alasanDitemukan', 30, 'paling lambat 3 (tiga) hari kerja setelah ditemukannya alasan'),
    },
  },

  P36_2: {
    samples: [
      deadline('batasTanggapanAtasan', 'keberatanDiterima', 30, 'paling lambat 30 (tiga puluh) hari kerja sejak diterimanya keberatan'),
      deadline('batasTanggapanAtasan', 'keberatanDiterima', 30, '30 (tiga puluh) hari kerja sejak diterimanya keberatan', 'fn'),
      deadline('batasTanggapanAtasan', 'keberatanDiterima', 14, 'memberikan tanggapan atas keberatan'),
      deadline('batasTanggapanAtasan', 'keberatanDiterima', 30, 'paling lambat 30 (tiga puluh) hari kerja'),
      deadline('batasTanggapanAtasan', 'keberatanDiterima', 30, 'dalam jangka waktu paling lambat 30 (tiga puluh) hari kerja sejak diterimanya keberatan secara tertulis', 'fn'),
    ],
    perturbations: {
      angka: deadline('batasTanggapanAtasan', 'keberatanDiterima', 14, 'paling lambat 14 (empat belas) hari kerja sejak diterimanya keberatan'),
    },
  },

  P37_2: {
    samples: [
      `def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  match tanggapanDiterima with
  | some t => some (t + 14) ${q('paling lambat 14 (empat belas) hari kerja setelah diterimanya tanggapan tertulis')}
  -- Tanpa tanggapan: dihitung dari berakhirnya batas 30 hari atasan
  | none => some (keberatanDiterima + 30 + 14)`,
      `def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  let _ := keberatanDiterima
  -- Tanpa tanggapan tertulis, titik mulai dalam teks tidak pernah terjadi
  tanggapanDiterima.map (· + 14) ${q('14 (empat belas) hari kerja setelah diterimanya tanggapan tertulis')}`,
      `def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  match tanggapanDiterima with
  | some t => some (batasWaktu t 14) ${q('setelah diterimanya tanggapan tertulis dari atasan pejabat')}
  | none => some (batasWaktu (batasWaktu keberatanDiterima 30) 14)`,
      `def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  match tanggapanDiterima with
  | some t => some (t + 14) ${q('paling lambat 14 (empat belas) hari kerja setelah diterimanya tanggapan tertulis')}
  | none => none`,
      `def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  match tanggapanDiterima with
  | some t => some (t + 14) ${q('14 (empat belas) hari kerja setelah diterimanya tanggapan tertulis')}
  | none => some (keberatanDiterima + 44)`,
    ],
    perturbations: {
      angka: `def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  match tanggapanDiterima with
  | some t => some (t + 30) ${q('paling lambat 30 (tiga puluh) hari kerja setelah diterimanya tanggapan tertulis')}
  | none => some (keberatanDiterima + 30 + 30)`,
    },
  },

  P38_1: {
    samples: [
      deadline('batasMulaiPenyelesaian', 'permohonanDiterima', 14, 'paling lambat 14 (empat belas) hari kerja setelah menerima permohonan'),
      deadline('batasMulaiPenyelesaian', 'permohonanDiterima', 14, '14 (empat belas) hari kerja', 'fn'),
      deadline('batasMulaiPenyelesaian', 'permohonanDiterima', 14, 'harus mulai mengupayakan penyelesaian'),
      deadline('batasMulaiPenyelesaian', 'permohonanDiterima', 14, 'paling lambat 14 (empat belas) hari kerja setelah menerima permohonan penyelesaian', 'fn'),
      deadline('batasMulaiPenyelesaian', 'permohonanDiterima', 14, '14 (empat belas) hari kerja setelah menerima permohonan'),
    ],
    perturbations: {
      angka: deadline('batasMulaiPenyelesaian', 'permohonanDiterima', 7, 'paling lambat 7 (tujuh) hari kerja setelah menerima permohonan'),
    },
  },

  P38_2: {
    samples: [
      `def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := permohonanDiterima
  mulaiPenyelesaian + 100 ${q('Proses penyelesaian sengketa')} ${q('dalam waktu 100 (seratus) hari kerja')}`,
      `def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := mulaiPenyelesaian
  -- dihitung sejak permohonan diterima, sama seperti ayat (1)
  permohonanDiterima + 100 ${q('paling lambat dapat diselesaikan dalam waktu 100 (seratus) hari kerja')}`,
      `def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := permohonanDiterima
  batasWaktu mulaiPenyelesaian 100 ${q('dapat diselesaikan dalam waktu 100 (seratus) hari kerja')}`,
      `def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := mulaiPenyelesaian
  batasWaktu permohonanDiterima 100 ${q('100 (seratus) hari kerja')}`,
      `def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := permohonanDiterima
  mulaiPenyelesaian + 100 ${q('paling lambat dapat diselesaikan dalam waktu 100 (seratus) hari kerja')}`,
    ],
    perturbations: {
      angka: `def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := permohonanDiterima
  mulaiPenyelesaian + 60 ${q('paling lambat dapat diselesaikan dalam waktu 60 (enam puluh) hari kerja')}`,
    },
  },

  P47: {
    samples: Array.from(
      { length: 5 },
      () => `def pengadilanBerwenang (b : JenisBadanPublik) : Pengadilan :=
  match b with
  | .negara => .ptun ${q('pengadilan tata usaha negara apabila yang digugat adalah Badan Publik negara')}
  | .nonNegara => .pn ${q('pengadilan negeri apabila yang digugat adalah Badan Publik selain Badan Publik negara')}`,
    ),
    perturbations: {
      tukar: `def pengadilanBerwenang (b : JenisBadanPublik) : Pengadilan :=
  match b with
  | .negara => .pn ${q('pengadilan negeri apabila yang digugat adalah Badan Publik negara')}
  | .nonNegara => .ptun ${q('pengadilan tata usaha negara apabila yang digugat adalah Badan Publik selain Badan Publik negara')}`,
    },
  },

  P48_1: {
    samples: [
      deadline('batasMenolakPutusan', 'putusanDiterima', 14, 'paling lambat 14 (empat belas) hari kerja setelah diterimanya putusan tersebut'),
      deadline('batasMenolakPutusan', 'putusanDiterima', 14, '14 (empat belas) hari kerja', 'fn'),
      `def batasMenolakPutusan (putusanDiterima : HariKerja) : HariKerja :=
  putusanDiterima + 14 hariKerja ${q('paling lambat 14 (empat belas) hari kerja')}`,
      deadline('batasMenolakPutusan', 'putusanDiterima', 14, 'setelah diterimanya putusan tersebut', 'fn'),
      deadline('batasMenolakPutusan', 'putusanDiterima', 14, 'paling lambat 14 (empat belas) hari kerja setelah diterimanya putusan'),
    ],
    perturbations: {
      angka: deadline('batasMenolakPutusan', 'putusanDiterima', 30, 'paling lambat 30 (tiga puluh) hari kerja setelah diterimanya putusan tersebut'),
    },
  },
};

export function fixtureFor(pasalId: string, sample: number | { perturbation: string }): string {
  const f = FIXTURES[pasalId];
  if (!f) throw new Error(`No fixture for ${pasalId}`);
  if (typeof sample === 'number') return f.samples[sample % f.samples.length];
  const p = f.perturbations[sample.perturbation];
  if (!p) throw new Error(`No fixture for ${pasalId} perturbation ${sample.perturbation}`);
  return p;
}
