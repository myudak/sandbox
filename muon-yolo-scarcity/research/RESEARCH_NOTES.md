# Results collection — 31 October 2026

The main Kaggle campaign is **completed and audited**: 120 successful training trials, three complete joint blocks on each dataset, and 60 successful frozen-checkpoint test evaluations. The manifest completed on 25 October at 09:01:59 UTC (16:01:59 WIB). No new training job was launched during collection.

Compact transfer: 688 files over six API pages. Checks of identities, all histories, exposure/step counts, pairing, CSV/JSON values and test-freeze links passed. Independent arithmetic recomputed 70 statistical summaries. The executed CPU companion is `notebooks/journal_results_review.ipynb`; current manuscript `paper/main.tex` now contains measured results and interpretation. Read `JOURNAL_INTERPRETATION.md` and `JOURNAL_FINDINGS.md` before drawing conclusions. Lower-bound LR selection, small joint-block count and conditional recipe scope remain central limitations.

The initial transfer hit Windows extended-path prefix handling, which was corrected while preserving containment checks. Report generation was made pandas-independent. These were local evidence/reporting repairs; the submitted training source and results were not changed.

---

# Historical submission entry — 25 October 2026

The user selected a **journal** target and authorized **at most 12 additional Kaggle notebook hours**. Journal preflight v1 completed all six trials on both datasets, with exact exposure/step and paired-order checks. The final input-only review removes one further wildlife training near-scene candidate; main split identities are frozen in `JOURNAL_DATA_FREEZE.json`.

**Current main job:** `myudak/muon-yolo-journal`, version 1, submitted with a 42,000-second external runtime cap. Status at this update: running; no main confirmation/test metrics retrieved. Combined with the 1,200-second preflight reservation, the conservative cap total is exactly 43,200 seconds. Do not launch another notebook without reconciling the budget ledger. The running job is self-contained and performs staged selection, confirmation and gated final evaluation without relying on the laptop remaining online.

Current design: `JOURNAL_PROTOCOL.md` / `JOURNAL_PLAN.json`. Working manuscript: `../paper/main.tex`; confirmation sections explicitly pending. The historical `PROPOSED_RUN_PLAN.json` was not executed and is superseded. The source of truth for the submitted main code is its embedded notebook bundle and the recorded code/notebook hashes, not later working-tree edits.

# Research notes

25 October 2026. Local workspace was initially empty. The supplied ZIP contained a handoff and an unexecuted starter notebook; both are preserved under `handoff/`.

## Verified locally

- Kaggle CLI 2.0.2 is installed and authenticated as `myudak`. A private GPU smoke notebook was submitted successfully as `myudak/muon-yolo-smoke`, version 1.
- Ultralytics 8.4.187 was resolved from PyPI and its wheel source inspected. MuSGD is explicitly supported. In that pinned trainer the hybrid factors are 0.2 for Muon and 1.0 for SGD; selected detection-head groups receive 3× LR. Runtime group manifests are the authority for instantiated behavior.
- 24 training-pipeline tests passed for subset nesting, deterministic/object-level corruption, empty labels, box validity, source immutability, frozen validation/test hashes, cross-split exact duplicate rejection, explicit holdout-priority cleaning, hash-bound reviewed exclusions, stale variant detection, configuration controls and failure serialization. Four additional analysis tests validate the three-way paired contrast and rejection of failed, incomplete, duplicate or unpaired cells: **28 tests passed in total**. Kaggle bundles the 24 training tests.
- Standalone smoke and eight-run pilot notebooks were generated and their notebook format validated.

## Execution status

Kaggle smoke version 1 stopped before training: exact image overlap across official dataset splits. Raw counts match documentation, but the frozen disjoint pool is 1,033 train / 223 validation / 227 test after 19 train and 2 validation exclusions. Test is preserved and retained annotations are unchanged. The policy and every exclusion are documented in `DATA_AUDIT.md` and its JSON manifest. No metric was inspected before choosing the cleaning rule.

Smoke version 2 completed both optimizers on the **superseded exact-hash-only pool**. Each used 52 training images, 2 epochs, 14 optimizer steps and 104 image exposures. Initial model state hashes and variant fingerprints matched exactly. Actual noise was 19/98 objects (19.39%). A local copy of the data reproduced the Kaggle source and smoke variant fingerprints. Saved validation and annotation-overlay figures were visually inspected.

That diagnostic produced validation mAP50–95 of 0.032338 for AdamW and 0.124863 for MuSGD. These are two-epoch, one-seed, untuned observations on a superseded split; **they do not establish optimizer superiority**. Evidence: `outputs/kaggle_smoke_v2/muon_yolo_smoke/EXECUTION_LOG.md` and its CSV/JSON files. Training-call times were 45.48 s / 8.58 s, with peak allocated training VRAM 0.607 / 0.647 GiB (AdamW/MuSGD). Setup, validation and cold-start effects are included; do not infer a speed ranking.

The checkpoint metadata and SHA-256 were downloaded and verified: embedded pretraining optimizer **MuSGD**, checkpoint SHA-256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.

Version 1 verified the Kaggle hardware/software environment: Tesla T4, two GPUs visible but device 0 requested, torch 2.11.0+cu128, CUDA 12.8, Python 3.13.15 and Ultralytics 8.4.187. This is evidence of setup, not completed training.

## Revised split policy and current jobs

A later dHash screen and visual review found 12 further training images overlapping held-out scenes. Current `holdout_priority_reviewed_v2` yields **1,021 train / 223 validation / 227 test**, with **1,881 / 377 / 375 objects**. Its source-bound exclusion manifest is `configs/duplicate_exclusions.json`; all retained annotations are unchanged. See `DATA_AUDIT.md` for chronology and limitations.

The first eight-run pilot was submitted before that review, with positive warmup. It is diagnostic and superseded. Revised pilot configurations use the reviewed pool and zero warmup: the pinned trainer's positive warmup has a 100-iteration minimum that otherwise changes effective epoch warmup by data fraction. Fair schedule/hyperparameter tuning remains future work.

Smoke version **3** completed on the reviewed pool and verified matching data/initialization. Version **4** also completed **2/2** with the final training-loader count/drop checks: 52 actual images, 14 optimizer steps and 104 image exposures for each optimizer. Its evidence is under `outputs/kaggle_smoke_v4/muon_yolo_smoke/`; pairing and the 1,021/223/227 frozen counts were checked.

`notebooks/smoke_results_review.ipynb` was executed locally as a CPU analysis companion: all eight analysis cells executed with no notebook error outputs after adding class AP and loss diagnostics. Its snapshot embeds measured JSON/histories and artifact hashes. The HTML export was generated, but full HTML browser inspection was blocked by the browser's local-URL security policy. The notebook's embedded trajectory figure was extracted and visually inspected directly. Local Jupyter emits a Windows event-loop compatibility warning; it did not prevent execution. No local GPU model training was performed.

The superseded pilot completed **8/8** without failure and used **30.51 minutes** of aggregate training-call wall time. Its 80 evidence files were downloaded with full pagination to `outputs/kaggle_pilot_superseded_v1/`. Those scores remain segregated and are not final research evidence.

The revised private pilot **`myudak/muon-yolo-pilot-reviewed`, version 1**, completed **8/8** on the final reviewed split and zero-warmup configuration. Aggregate training-call time was **28.40 minutes**. Its 81 retrieved evidence files are under `outputs/kaggle_pilot_reviewed_v1/`. Configuration/code/split/checkpoint fingerprints, matching initialization across all eight runs, 20-epoch histories, expected image exposures/optimizer steps and exact CSV/JSON metric serialization were verified. No test metric has been computed.

Current clean-validation mAP50–95 ×100 (AdamW / MuSGD): scarce-clean **69.83 / 70.60**, scarce-noisy **65.91 / 68.23**, full-clean **79.68 / 77.26**, full-noisy **74.80 / 72.53**. The three-way descriptive contrast is **+1.413 AP points**, with no confidence interval. These are one-seed, untuned observations; see `PILOT_FINDINGS.md` for limits. Seven best per-epoch validation values occur at epoch 20 and one at epoch 19, so convergence is not established.

The final pilot review notebook executed all eight CPU analysis cells with no notebook errors. PNG comparison/trajectory and notebook-loss figures were visually inspected; SVG exports were generated. Visual QA found and corrected a shared-axis limit that clipped later panels; plot ranges now use all plotted series. Portable numeric figures are under `research/figures/`. Full HTML browser inspection remains unavailable under the browser's local-URL policy; figures were checked directly.

Browser access was attempted to stop the superseded pilot, but the browser session could not access the private notebook. No cancellation succeeded; the job subsequently completed normally. CLI remains authenticated for status and output retrieval.

Class composition was audited independently against the frozen annotation hashes. `class_balance.csv` / `.json` show 205 images and 385 original objects at 20% scarcity, with 72 removed at target q=0.20 (18.70% realized); the full pool has 1,881 objects with 361 removed (19.19%). These describe one fixed realization, not model results.

## Windows recovery

A Windows BSOD interrupted local artifact generation. A read-only check confirmed bugcheck 0xD1; the protected minidump was inaccessible, so no responsible driver or causal link was established. The user authorized continuing. A scan found NUL corruption in three generated smoke notebook/metadata files; authored Python/configuration/research files passed syntax/JSON checks. Generated files were rebuilt from source. The builder now writes temporary files, flushes/fsyncs and replaces them. This reduces partial-write exposure without guaranteeing recovery from every hardware/OS failure. GPU training remains on Kaggle.

## Engineering corrections to the starter

The new runner hashes actual content instead of equating annotation counts, includes source/code/config/environment/checkpoint in run identity, audits clean validation as well as test, records failures, validates initialized-model pairing and actual optimizer classes, and uses validation-only development evaluation. Warmup is disabled for the two-epoch smoke test. Only missing-box corruption is validated in this implementation.

Kaggle CLI 2.0.2 output retrieval stops after its first page and can fail writing Unicode logs on Windows. `scripts/kaggle_evidence.py` uses the installed authenticated Kaggle client with full pagination and explicit UTF-8 log writing; it omits source images and individual image labels.

## Open research limitations

Equal-budget tuning, repeated seeds, SGD experiments, external-dataset confirmation, near-duplicate scene audit, fixed-time comparisons and a frozen final-test evaluation remain future stages. Dataset image licensing is unspecified in official documentation and must be resolved before redistribution/publication. See `PROTOCOL.md` and `RELATED_WORK.md`.
