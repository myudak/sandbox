import HukumOS.Prelude

/-!
# Baseline translations of UU 14/2008 (hand-written)

The reference the LLM translations are compared against. Each definition has
the fixed signature from `benchmark/kip.json`, and each line that comes from
the text says where with a `-- dari: "..."` comment.

Where the text allows more than one reading, the baseline picks one and says
so; the benchmark marks those scenarios as ambiguous rather than scoring them.

The pasal texts are still unverified paraphrases (see sources/uu-14-2008).
-/

namespace HukumOS.Kip.Baku
open HukumOS

/-- Pasal 22 ayat (7) -/
def batasPemberitahuan (diterima : HariKerja) : HariKerja :=
  batasWaktu diterima 10 -- dari: "Paling lambat 10 (sepuluh) hari kerja sejak diterimanya permintaan"

/-- Pasal 22 ayat (8). Reading: the 7 days follow the original 10-day period
("7 hari kerja berikutnya"). Alternative: 7 days from the extension notice. -/
def batasPerpanjangan (diterima perpanjangPada : HariKerja) : HariKerja :=
  let _ := perpanjangPada
  batasWaktu (batasWaktu diterima 10) 7 -- dari: "paling lambat 7 (tujuh) hari kerja berikutnya"

/-- Pasal 35 ayat (1): the listed grounds, and nothing else. -/
def bolehKeberatan (a : AlasanKeberatan) : Bool :=
  match a with
  | .penolakanPasal17 => true -- dari: "penolakan atas permintaan informasi berdasarkan alasan pengecualian sebagaimana dimaksud dalam Pasal 17"
  | .informasiBerkalaTidakDisediakan => true -- dari: "tidak disediakannya informasi berkala"
  | .tidakDitanggapi => true -- dari: "tidak ditanggapinya permintaan informasi"
  | .tidakSesuaiPermintaan => true -- dari: "permintaan informasi ditanggapi tidak sebagaimana yang diminta"
  | .tidakDipenuhi => true -- dari: "tidak dipenuhinya permintaan informasi"
  | .biayaTidakWajar => true -- dari: "pengenaan biaya yang tidak wajar"
  | .melebihiWaktu => true -- dari: "penyampaian informasi yang melebihi waktu yang diatur"
  | .lainnya => false

/-- Pasal 36 ayat (1) -/
def batasKeberatan (alasanDitemukan : HariKerja) : HariKerja :=
  batasWaktu alasanDitemukan 30 -- dari: "paling lambat 30 (tiga puluh) hari kerja setelah ditemukannya alasan"

/-- Pasal 36 ayat (2) -/
def batasTanggapanAtasan (keberatanDiterima : HariKerja) : HariKerja :=
  batasWaktu keberatanDiterima 30 -- dari: "paling lambat 30 (tiga puluh) hari kerja sejak diterimanya keberatan"

/-- Pasal 37 ayat (2). Reading when the superior never responds: the 14 days
run from the end of the superior's 30-day period. Alternative: they never start. -/
def batasSengketa (keberatanDiterima : HariKerja) (tanggapanDiterima : Option HariKerja) : Option HariKerja :=
  match tanggapanDiterima with
  | some t => some (batasWaktu t 14) -- dari: "paling lambat 14 (empat belas) hari kerja setelah diterimanya tanggapan tertulis"
  | none => some (batasWaktu (batasWaktu keberatanDiterima 30) 14)

/-- Pasal 38 ayat (1) -/
def batasMulaiPenyelesaian (permohonanDiterima : HariKerja) : HariKerja :=
  batasWaktu permohonanDiterima 14 -- dari: "paling lambat 14 (empat belas) hari kerja setelah menerima permohonan"

/-- Pasal 38 ayat (2). Reading: 100 days from when the process starts.
Alternative: from when the dispute request was received. -/
def batasPenyelesaian (permohonanDiterima mulaiPenyelesaian : HariKerja) : HariKerja :=
  let _ := permohonanDiterima
  batasWaktu mulaiPenyelesaian 100 -- dari: "dapat diselesaikan dalam waktu 100 (seratus) hari kerja"

/-- Pasal 47 -/
def pengadilanBerwenang (b : JenisBadanPublik) : Pengadilan :=
  match b with
  | .negara => .ptun -- dari: "pengadilan tata usaha negara apabila yang digugat adalah Badan Publik negara"
  | .nonNegara => .pn -- dari: "pengadilan negeri apabila yang digugat adalah Badan Publik selain Badan Publik negara"

/-- Pasal 48 ayat (1) -/
def batasMenolakPutusan (putusanDiterima : HariKerja) : HariKerja :=
  batasWaktu putusanDiterima 14 -- dari: "paling lambat 14 (empat belas) hari kerja setelah diterimanya putusan"

/-! ## Properties of the baseline, proved -/

theorem perpanjangan_paling_lama_17 (d p : HariKerja) : batasPerpanjangan d p ≤ d + 17 := by
  simp [batasPerpanjangan, batasWaktu]

theorem sengketa_setelah_tanggapan (k t : HariKerja) : batasSengketa k (some t) = some (t + 14) := by
  simp [batasSengketa, batasWaktu]

theorem pengadilan_negara : pengadilanBerwenang .negara = .ptun := rfl

/-- Worst case from request to the last day to reject an adjudication decision,
chaining every deadline with its maximum (10 + 7 + 30 + 30 + 14 + 14 + 100 + 14). -/
theorem total_paling_lama (d : HariKerja) :
    batasMenolakPutusan
      (batasPenyelesaian 0 (batasMulaiPenyelesaian
        ((batasSengketa (batasKeberatan (batasPerpanjangan d d)) none).getD 0)))
    = d + 219 := by
  simp [batasMenolakPutusan, batasPenyelesaian, batasMulaiPenyelesaian, batasSengketa,
    batasKeberatan, batasPerpanjangan, batasWaktu]

end HukumOS.Kip.Baku
