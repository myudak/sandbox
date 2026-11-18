/-!
# HukumOS Prelude

The small legal vocabulary every translation is written against: so that
translations by different people (or different LLM samples) of the same pasal
have the same shape and can be run on the same scenarios and compared.

Kept to core Lean (no Mathlib) so the project builds in seconds.
-/

namespace HukumOS

/-- A point in time, counted in *hari kerja* (working days) from an arbitrary
origin. Deadlines in UU 14/2008 are all in working days, so the calendar
(weekends, holidays, cuti bersama) stays outside the formal model: it maps real
dates to this index. -/
abbrev HariKerja := Nat

/-- Amounts of money in whole rupiah. -/
abbrev Rupiah := Nat

/-- Parties that appear in procedures. -/
inductive Pihak where
  | pemohon
  | badanPublik
  | ppid
  | atasanPpid
  | komisiInformasi
  | pengadilan
  deriving Repr, DecidableEq, Inhabited

/-- Whether a public body is a state body (Pasal 47 picks the court by this). -/
inductive JenisBadanPublik where
  | negara
  | nonNegara
  deriving Repr, DecidableEq, Inhabited

inductive Pengadilan where
  | ptun   -- Pengadilan Tata Usaha Negara
  | pn     -- Pengadilan Negeri
  deriving Repr, DecidableEq, Inhabited

/-- Grounds for an objection (keberatan). `lainnya` stands for any ground the
article does not list. -/
inductive AlasanKeberatan where
  | penolakanPasal17
  | informasiBerkalaTidakDisediakan
  | tidakDitanggapi
  | tidakSesuaiPermintaan
  | tidakDipenuhi
  | biayaTidakWajar
  | melebihiWaktu
  | lainnya
  deriving Repr, DecidableEq, Inhabited

instance : ToString Pengadilan := ⟨fun | .ptun => "ptun" | .pn => "pn"⟩
instance : ToString JenisBadanPublik := ⟨fun | .negara => "negara" | .nonNegara => "nonNegara"⟩

/-- Rendering used by the scenario harness: `none`, `some 12`, `true`, `ptun`... -/
class Tampil (α : Type) where
  tampil : α → String

instance : Tampil Nat := ⟨toString⟩
instance : Tampil Bool := ⟨toString⟩
instance : Tampil Pengadilan := ⟨toString⟩
instance [Tampil α] : Tampil (Option α) := ⟨fun | none => "none" | some a => s!"some {Tampil.tampil a}"⟩

/-!
## Default logic, Catala style

Laws are written as a base rule plus exceptions that sit in other pasal.
`Bawaan.nilai` applies the base rule unless exactly one exception applies; if
two exceptions apply at once, that is a conflict the text must resolve, and we
surface it instead of picking one silently.
-/

/-- A conditional rule: applies to some inputs, and gives a value when it does. -/
abbrev Pengecualian (α β : Type) := α → Option β

inductive Hasil (β : Type) where
  | ok (v : β)
  | konflik (vs : List β)
  deriving Repr

def Bawaan.nilai (pengecualian : List (Pengecualian α β)) (dasar : α → β) (x : α) : Hasil β :=
  match pengecualian.filterMap (· x) with
  | [] => .ok (dasar x)
  | [v] => .ok v
  | vs => .konflik vs

/-- Deadline arithmetic: the last working day of a period of `n` working days
counted from (and not including) `mulai`. -/
def batasWaktu (mulai : HariKerja) (n : Nat) : HariKerja := mulai + n

theorem batasWaktu_mono {a b : HariKerja} (n : Nat) (h : a ≤ b) : batasWaktu a n ≤ batasWaktu b n :=
  Nat.add_le_add_right h n

theorem batasWaktu_tambah (a m n : Nat) : batasWaktu (batasWaktu a m) n = batasWaktu a (m + n) :=
  Nat.add_assoc a m n

end HukumOS
