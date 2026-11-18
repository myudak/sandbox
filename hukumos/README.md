# HukumOS

Law as code for Indonesia. Two experiments on **UU 14/2008 tentang Keterbukaan Informasi Publik**:

1. **Lab (the main one): from pasal to Lean, and how faithful is it?** An LLM translates each pasal into Lean 4. Lean typechecks it, runs it on legal scenarios, and tries to *prove* it equivalent to a hand-written baseline and to satisfy stated properties. Faithfulness is measured with checks that need no lawyer: scenario tests, "change the text" tests, and agreement between several independent translations. When translations disagree but each fits the text, that flags the **text itself** as possibly ambiguous.
2. **Prosedur:** the whole request → objection → dispute → court procedure as an explorable state machine (the earlier prototype, kept as a tab).

> Prototype interpretation, not legal advice. **The pasal texts here are paraphrases written from memory and are not yet verified against the official text**, and expected answers are the modeller's, not yet reviewed by a legal expert. The committed `src/data/results.json` uses **hand-written example translations**, not LLM output (the UI says so); the Lean checks on them are real.

## Lab

```
benchmark/kip.json        10 pasal: text, fixed Lean signature, scenarios (ambiguous ones marked),
                          "change the text" perturbations, properties
lean/HukumOS/Prelude.lean the legal vocabulary translations are written against (HariKerja, Pihak,
                          Catala-style default/exception combinator, deadline lemmas)
lean/HukumOS/Kip/Baku.lean hand-written baseline translations + proved theorems
                          (e.g. worst case request → lawsuit = 219 hari kerja)
pipeline/                 translate (Claude or fixtures) → typecheck → run scenarios/probes →
                          prove properties & equivalence → group by behaviour → verdict
src/ui/lab/               Pasal workspace · Ringkasan (dashboard) · Tinjauan (lawyer review mode)
```

For each pasal and each translation the pipeline reports:

| Check | How | What it catches |
|---|---|---|
| Typecheck | Lean, with a filter for `sorry`, `axiom`, `IO`, `#eval`, attributes… | broken or unsound code |
| Scenarios | `lean --run` on concrete inputs with known answers | wrong numbers, wrong cases |
| Change the text | translate an edited pasal (30 → 3 days, delete a ground, swap courts) and check the code changes accordingly | translations that ignore the text |
| Agreement | group N translations by their outputs on scenarios + generated probes | instability; and **ambiguity** when ≥2 groups all fit the clear scenarios |
| Equivalence | Lean proof attempt against the baseline (tactic battery: `simp`, `omega`, `cases`, `decide`) | proved same / shown different by counterexample / unknown |
| Properties | Lean proof attempt of statements written from the text independently | violations of what the text clearly requires |
| Quote links | every line carries `-- dari: "<quote>"`; quotes not found in the text are flagged | invented justifications |

Verdicts: **setia** (majority fits everything), **mungkin ambigu** (several groups fit the clear scenarios but differ on an ambiguous one), **bermasalah**, **gagal**.

### Run it

Lean 4.15 is needed for the pipeline (not for the UI). Install [elan](https://github.com/leanprover/elan), then:

```bash
npm install
(cd lean && lake build)           # builds the library and checks the baseline proofs
npm run lab                       # example translations, no API key → src/data/results.json
npm run lab -- --llm              # Claude translations (ANTHROPIC_API_KEY or `ant auth login`)
npm run lab -- --llm --samples 8 --only P37_2,P38_2
npm run dev                       # UI
```

With `--llm` the pipeline calls `claude-opus-5-5` (effort `high`) once per sample and once per perturbation: 10 pasal × (5 + 1) = 60 requests by default. Server-side refusal fallback (`fallbacks: "default"`) is enabled.

### Honest limits

- The checks can only catch what scenarios, perturbations and properties cover. A wrong translation that passes all of them is invisible here; only expert review (the Tinjauan tab, which exports answers as JSON) measures that.
- Signatures are fixed per pasal, which makes translations comparable but also hands the translator part of the structure.
- 10 pasal is a pilot, not a benchmark yet.

## Prosedur (earlier prototype)

### Why not just Catala?

[Catala](https://github.com/CatalaLang/catala) is great at **computations**: facts in, a value out (tax owed, benefit amount), with exceptions as first-class. Much Indonesian administrative law is **procedure**: who must act, by when, what happens when they don't, and which remedy comes next. HukumOS models that part:

| | Catala | HukumOS |
|---|---|---|
| Models | inputs → value | states, deadlines, actors over time |
| Checks | types, tests | every reachable path: dead ends, termination, deadline bounds, remedies |
| Traceability | literate code next to the law | every deadline and transition cites a pasal; the explorer checks the numbers match the text |

Borrowed from Catala: the literate style (the **Pasal & Aturan** tab puts each provision next to the rules that encode it).

### Run it

```bash
npm test          # unit + property tests
npm run verify    # CLI report: findings, worst-case deadlines, mutation score
```

### What's here

```
src/core/ir.ts          Legal IR: states, transitions, deadlines, actors, provisions, properties
src/core/calendar.ts    hari kerja arithmetic (weekends; holidays passed in)
src/core/engine.ts      run the model on concrete dates (late actions and early timeouts are rejected)
src/core/explore.ts     exhaustive explorer + checks + counterexample traces
src/models/uu-14-2008/  the KIP model, its provisions, and 12 injected-defect mutants
src/ui/ProcedureApp.tsx  Vite + React + React Flow: Simulator · Pasal & Aturan · Verifikasi
scripts/verify.ts       CLI report
```

#### Scope of the model

Pasal 22 (response, one extension) → 35–36 (keberatan to atasan PPID) → 37–38 (sengketa at Komisi Informasi, mediasi/ajudikasi) → 39 (mediation is final) → 47–48 (gugatan to PTUN or PN). Not yet: fees, Perki 1/2013 procedure details, partial fulfilment, withdrawal, kasasi (Pasal 50).

### What the explorer checks

Structural: valid references, terminal states have no exits, every deadline has an expiry transition, `TIMEOUT` only from states with deadlines, the acting party is allowed to act in that state, every rule cites a provision, every deadline's number appears in its provision's text.

Behavioural (over every reachable `(state, context)` for each scenario): all states reachable, no dead ends, determinism, termination (no cycles), bounded state space, plus the model's own legal properties:

- the agency answers within 10 + 7 working days (Pasal 22)
- refusal → objection answered within 30 + 30 working days (Pasal 36)
- a refused, ignored or unsatisfied requester can always reach the Komisi Informasi (Pasal 37)
- at most one extension (Pasal 22(8))
- lawsuits go to the right court (Pasal 47)

Findings are split into the three categories a human reviewer needs:

| Category | Meaning |
|---|---|
| **violation** | the model breaks a rule. A model bug *or* an interpretation disagreement: a person decides which |
| **legal_gap_candidate** | the model follows the text faithfully, and the text leaves something open |
| **interpretation** | a choice the modeller made where the text is not explicit |

### Current results (`npm run verify`)

- 56 configurations, 2 scenarios (Badan Publik negara / non-negara), **0 violations**.
- Worst case from request to lawsuit: **219 hari kerja** (10 + 7 + 30 + 30 + 14 + 14 + 100 + 14), with the path as a replayable trace.
- **2 candidate legal gaps**: Pasal 38(1) and 38(2) set deadlines for the Komisi Informasi but (in our reading) state no consequence if they are missed.
- **4 recorded interpretations**, e.g. Pasal 37(2) counts 14 days from *receiving the atasan's response*, which does not exist when the atasan never responds.
- **12/12 injected defects caught**: wrong numbers, a forgotten guard, a missing remedy, wrong actor, missing source, wrong target, nondeterminism, swapped jurisdiction, dead end, a reopenable terminal state.

Honest caveat: the mutants were written by the same people who wrote the checks, so 12/12 is an upper bound. A real evaluation needs defects from people who didn't write the explorer, and models written by others.

### Roadmap

1. **Verify the sources** against the official text; flip `verified: true` one provision at a time.
2. Expert review of the model, the 4 interpretations and the 2 gap candidates.
3. Exceptions in the IR (Catala-style "base rule unless…", e.g. Pasal 17 exemptions).
4. A second law, to see whether the IR generalises beyond KIP.
5. Research evaluation: LLM-only vs hand-coded rules vs HukumOS on scenario correctness, defect detection precision/recall, and review effort.
6. Later: AI-assisted drafting of models from text (always reviewed), Lexifina/JDIH ingestion, a public site.
