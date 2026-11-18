/** Shared between the pipeline (pipeline/) and the UI (src/ui/). */

export interface Param {
  name: string;
  type: string; // Lean type, e.g. "HariKerja", "Option HariKerja"
}

export interface Scenario {
  id: string;
  desc: string;
  /** Lean expressions, one per parameter. */
  args: string[];
  /** Expected rendered output. Absent when the text allows several readings. */
  expect?: string;
  /** Ambiguous scenario: reading label → rendered output under that reading. */
  readings?: Record<string, string>;
}

export interface Perturbation {
  id: string;
  label: string;
  find: string;
  replace: string;
  /** Expected rendered outputs for (some of) the scenarios under the changed text. */
  expect: Record<string, string>;
}

export interface Property {
  id: string;
  desc: string;
  /** Lean proposition; `F` stands for the translated function. */
  statement: string;
}

export interface BenchPasal {
  id: string;
  cite: string;
  text: string;
  context?: string;
  verified: boolean;
  fn: string;
  params: Param[];
  returns: string;
  scenarios: Scenario[];
  perturbations: Perturbation[];
  properties: Property[];
}

export interface Benchmark {
  id: string;
  law: string;
  note: string;
  pasal: BenchPasal[];
}

// ---------------------------------------------------------------------------

export type ProofStatus = 'terbukti' | 'berbeda' | 'tidak_diketahui';

export interface Sample {
  id: string;
  code: string;
  /** Lean accepted the code (and it contains no forbidden constructs). */
  typechecks: boolean;
  error?: string;
  scenarioOutputs: Record<string, string>;
  /** Outputs on the generated probe inputs, in probe order. */
  probeOutputs: string[];
  /** Equivalence with the hand-written baseline. */
  equivalence: ProofStatus;
  properties: Record<string, ProofStatus>;
  /** Scenario ids whose output contradicts a non-ambiguous expectation. */
  failedScenarios: string[];
  /** For ambiguous scenarios: which reading this sample chose (label), or "lain". */
  readingsChosen: Record<string, string>;
  errorKinds: ErrorKind[];
}

export type ErrorKind =
  | 'tidak_typecheck'
  | 'konstruksi_terlarang'
  | 'skenario_gagal'
  | 'properti_gagal'
  | 'perubahan_diabaikan'
  | 'perubahan_salah';

export interface Group {
  members: string[];
  /** True when every member passes all non-ambiguous scenarios. */
  consistentWithText: boolean;
  readings: Record<string, string>;
}

export interface PerturbationResult {
  id: string;
  label: string;
  textAfter: string;
  sample: Sample;
  expect: Record<string, string>;
  /** Outputs match the expectation for the changed text. */
  pass: boolean;
  /** Outputs differ from the translation of the original text. */
  changed: boolean;
}

export type Verdict = 'setia' | 'mungkin_ambigu' | 'bermasalah' | 'gagal';

export interface PasalResult {
  pasal: BenchPasal;
  baselineCode: string;
  baselineScenarioOutputs: Record<string, string>;
  probes: string[][];
  samples: Sample[];
  groups: Group[];
  /** Index into `probes` of inputs where the groups disagree. */
  distinguishingProbes: number[];
  representative: string;
  perturbations: PerturbationResult[];
  metrics: {
    typecheck: [number, number];
    scenarios: [number, number];
    perturbations: [number, number];
    agreement: [number, number];
    equivalent: [number, number];
    properties: [number, number];
  };
  verdict: Verdict;
  verdictReason: string;
}

export interface Results {
  generatedAt: string;
  translator: string;
  /** True when the translations are hand-written examples, not LLM output. */
  illustrative: boolean;
  samplesPerPasal: number;
  leanVersion: string;
  benchmark: { id: string; law: string; note: string };
  pasal: PasalResult[];
}
