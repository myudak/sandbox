import type { Provision } from '../../core/ir';

/**
 * Provisions of UU 14/2008 tentang Keterbukaan Informasi Publik used by the model.
 *
 * WARNING: these excerpts are PARAPHRASES written from memory, not the official
 * text. Every entry is `verified: false` until someone compares it with the
 * official publication (JDIH / Lembaran Negara 2008 No. 61) and replaces the
 * excerpt with the exact wording. See sources/uu-14-2008/README.md.
 *
 * The explorer checks that every deadline's number appears in its excerpt, so
 * keep the numbers when replacing the text.
 */
const LAW = 'UU 14/2008';

export const sources: Record<string, Provision> = {
  P22_7: {
    id: 'P22_7',
    law: LAW,
    pasal: '22',
    ayat: '7',
    excerpt:
      '[Parafrase] Paling lambat 10 (sepuluh) hari kerja sejak diterimanya permintaan, Badan Publik wajib menyampaikan pemberitahuan tertulis yang berisi, antara lain, apakah informasi berada di bawah penguasaannya dan apakah permintaan diterima atau ditolak beserta alasannya.',
    verified: false,
  },
  P22_8: {
    id: 'P22_8',
    law: LAW,
    pasal: '22',
    ayat: '8',
    excerpt:
      '[Parafrase] Badan Publik dapat memperpanjang waktu pemberitahuan paling lambat 7 (tujuh) hari kerja berikutnya dengan memberikan alasan secara tertulis.',
    verified: false,
  },
  P17: {
    id: 'P17',
    law: LAW,
    pasal: '17',
    excerpt:
      '[Parafrase] Mengatur informasi publik yang dikecualikan, yaitu informasi yang apabila dibuka dapat menimbulkan akibat tertentu (antara lain menghambat penegakan hukum, mengganggu perlindungan HAKI, membahayakan pertahanan negara, mengungkap rahasia pribadi).',
    verified: false,
  },
  P35_1: {
    id: 'P35_1',
    law: LAW,
    pasal: '35',
    ayat: '1',
    excerpt:
      '[Parafrase] Pemohon dapat mengajukan keberatan secara tertulis kepada atasan PPID berdasarkan alasan, antara lain: penolakan berdasarkan pengecualian Pasal 17; informasi berkala tidak disediakan; permintaan tidak ditanggapi; permintaan ditanggapi tidak sebagaimana yang diminta; permintaan tidak dipenuhi; pengenaan biaya yang tidak wajar; atau penyampaian informasi melebihi waktu yang diatur.',
    verified: false,
  },
  P36_1: {
    id: 'P36_1',
    law: LAW,
    pasal: '36',
    ayat: '1',
    excerpt:
      '[Parafrase] Keberatan diajukan dalam jangka waktu paling lambat 30 (tiga puluh) hari kerja setelah ditemukannya alasan sebagaimana dimaksud dalam Pasal 35 ayat (1).',
    verified: false,
  },
  P36_2: {
    id: 'P36_2',
    law: LAW,
    pasal: '36',
    ayat: '2',
    excerpt:
      '[Parafrase] Atasan pejabat memberikan tanggapan atas keberatan secara tertulis dalam jangka waktu paling lambat 30 (tiga puluh) hari kerja sejak diterimanya keberatan.',
    verified: false,
  },
  P37_1: {
    id: 'P37_1',
    law: LAW,
    pasal: '37',
    ayat: '1',
    excerpt:
      '[Parafrase] Upaya penyelesaian sengketa informasi publik diajukan kepada Komisi Informasi apabila tanggapan atasan PPID dalam proses keberatan tidak memuaskan pemohon.',
    verified: false,
  },
  P37_2: {
    id: 'P37_2',
    law: LAW,
    pasal: '37',
    ayat: '2',
    excerpt:
      '[Parafrase] Upaya penyelesaian sengketa informasi publik diajukan dalam waktu paling lambat 14 (empat belas) hari kerja setelah diterimanya tanggapan tertulis dari atasan pejabat sebagaimana dimaksud dalam Pasal 36 ayat (2).',
    verified: false,
  },
  P38_1: {
    id: 'P38_1',
    law: LAW,
    pasal: '38',
    ayat: '1',
    excerpt:
      '[Parafrase] Komisi Informasi harus mulai mengupayakan penyelesaian sengketa melalui mediasi dan/atau ajudikasi nonlitigasi paling lambat 14 (empat belas) hari kerja setelah menerima permohonan penyelesaian sengketa.',
    verified: false,
  },
  P38_2: {
    id: 'P38_2',
    law: LAW,
    pasal: '38',
    ayat: '2',
    excerpt:
      '[Parafrase] Proses penyelesaian sengketa sebagaimana dimaksud pada ayat (1) paling lambat dapat diselesaikan dalam waktu 100 (seratus) hari kerja.',
    verified: false,
  },
  P39: {
    id: 'P39',
    law: LAW,
    pasal: '39',
    excerpt: '[Parafrase] Putusan Komisi Informasi yang berasal dari kesepakatan melalui mediasi bersifat final dan mengikat.',
    verified: false,
  },
  P47: {
    id: 'P47',
    law: LAW,
    pasal: '47',
    excerpt:
      '[Parafrase] Pengajuan gugatan dilakukan melalui pengadilan tata usaha negara apabila yang digugat adalah Badan Publik negara, dan melalui pengadilan negeri apabila yang digugat adalah Badan Publik selain Badan Publik negara.',
    verified: false,
  },
  P48_1: {
    id: 'P48_1',
    law: LAW,
    pasal: '48',
    ayat: '1',
    excerpt:
      '[Parafrase] Pengajuan gugatan hanya dapat ditempuh apabila salah satu atau para pihak yang bersengketa secara tertulis menyatakan tidak menerima putusan ajudikasi Komisi Informasi paling lambat 14 (empat belas) hari kerja setelah diterimanya putusan tersebut.',
    verified: false,
  },
};
