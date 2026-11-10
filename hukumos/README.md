# HukumOS

Law as code for Indonesia. The first experiment: **UU 14/2008 tentang Keterbukaan Informasi Publik** (public information requests) as an executable, explorable and verifiable state machine.

> Prototype interpretation, not legal advice. The law stays the authority; the model is a transparent, testable reading of it. **The pasal excerpts in this repo are paraphrases written from memory and are not yet verified against the official text** (see [`sources/uu-14-2008/`](sources/uu-14-2008/)).

## Why not just Catala?

[Catala](https://github.com/CatalaLang/catala) is great at **computations**: facts in, a value out (tax owed, benefit amount), with exceptions as first-class. Much Indonesian administrative law is **procedure**: who must act, by when, what happens when they don't, and which remedy comes next. HukumOS models that part:

| | Catala | HukumOS |
|---|---|---|
| Models | inputs → value | states, deadlines, actors over time |
| Checks | types, tests | every reachable path: dead ends, termination, deadline bounds, remedies |
| Traceability | literate code next to the law | every deadline and transition cites a pasal; the explorer checks the numbers match the text |

Borrowed from Catala: the literate style (the **Pasal & Aturan** tab puts each provision next to the rules that encode it).

## Run it

```bash
npm install
npm run dev       # UI on http://localhost:5173
npm test          # unit + property tests
npm run verify    # CLI report: findings, worst-case deadlines, mutation score
```

## What's here

```
src/core/ir.ts          Legal IR: states, transitions, deadlines, actors, provisions, properties
src/core/calendar.ts    hari kerja arithmetic (weekends; holidays passed in)
src/core/engine.ts      run the model on concrete dates (late actions and early timeouts are rejected)
src/core/explore.ts     exhaustive explorer + checks + counterexample traces
src/models/uu-14-2008/  the KIP model, its provisions, and 12 injected-defect mutants
src/ui/                 Vite + React + React Flow: Simulator · Pasal & Aturan · Verifikasi
scripts/verify.ts       CLI report
```

### Scope of the model

Pasal 22 (response, one extension) → 35–36 (keberatan to atasan PPID) → 37–38 (sengketa at Komisi Informasi, mediasi/ajudikasi) → 39 (mediation is final) → 47–48 (gugatan to PTUN or PN). Not yet: fees, Perki 1/2013 procedure details, partial fulfilment, withdrawal, kasasi (Pasal 50).

## What the explorer checks

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

## Current results (`npm run verify`)

- 56 configurations, 2 scenarios (Badan Publik negara / non-negara), **0 violations**.
- Worst case from request to lawsuit: **219 hari kerja** (10 + 7 + 30 + 30 + 14 + 14 + 100 + 14), with the path as a replayable trace.
- **2 candidate legal gaps**: Pasal 38(1) and 38(2) set deadlines for the Komisi Informasi but (in our reading) state no consequence if they are missed.
- **4 recorded interpretations**, e.g. Pasal 37(2) counts 14 days from *receiving the atasan's response*, which does not exist when the atasan never responds.
- **12/12 injected defects caught**: wrong numbers, a forgotten guard, a missing remedy, wrong actor, missing source, wrong target, nondeterminism, swapped jurisdiction, dead end, a reopenable terminal state.

Honest caveat: the mutants were written by the same people who wrote the checks, so 12/12 is an upper bound. A real evaluation needs defects from people who didn't write the explorer, and models written by others.

## Roadmap

1. **Verify the sources** against the official text; flip `verified: true` one provision at a time.
2. Expert review of the model, the 4 interpretations and the 2 gap candidates.
3. Exceptions in the IR (Catala-style "base rule unless…", e.g. Pasal 17 exemptions).
4. A second law, to see whether the IR generalises beyond KIP.
5. Research evaluation: LLM-only vs hand-coded rules vs HukumOS on scenario correctness, defect detection precision/recall, and review effort.
6. Later: AI-assisted drafting of models from text (always reviewed), Lexifina/JDIH ingestion, a public site.
