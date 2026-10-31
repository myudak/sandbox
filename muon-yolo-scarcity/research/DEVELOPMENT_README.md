# MuSGD × YOLO under data scarcity and missing annotations

A reproducible empirical study of **when the Ultralytics MuSGD fine-tuning recipe helps or hurts relative to AdamW**. The completed campaign stayed within a maximum **12 additional Kaggle notebook hours**. The manuscript reports existing optimizer recipes and their limitations.

## Publication release — 31 October 2026

**Muchammad Yuda Tri Ananda** · **yuda@myudak.com**

- [Publication PDF](output/pdf/muon_yolo_scarcity.pdf): 10 pages, compiled and visually reviewed, with embedded fonts and checked links.
- [Editable LaTeX source](paper/main.tex), maintained in place.
- [Interactive public Kaggle report, version 5](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=364100382) and [original version 1 experiment with outputs](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=361947826).
- [Publication record](research/PUBLICATION_STATUS.json) and [PDF release checks](research/PDF_RELEASE_QA.json).

Version 5 is a successful 22.4-second CPU-only results report. It presents five interactive charts: paired recipe differences, absolute scores, the primary interaction, validation search and learning trajectories. Dropdowns select datasets, validation/test views, optimizer searches, conditions and trajectory metrics; hover and legends expose exact values and individual blocks. Reading-view code is collapsed. The Output tab contains CSV/JSON evidence, chart files and a self-contained offline HTML explorer. Version 2 was the initial publication save; versions 3–4 were superseded presentation iterations. No model training was rerun. The original experiment and its outputs remain in version 1. No journal-specific template has been selected.

The report source is [muon_yolo_results_explorer.ipynb](kaggle/journal_public_report/muon_yolo_results_explorer.ipynb). Install `requirements-report.txt` for local report work. `scripts/build_public_journal.py` regenerates it from preserved local evidence and executes analysis only. `scripts/publish_public_journal.py` uploads the reviewed CPU report; `scripts/verify_public_report.py` compares downloaded Kaggle evidence, chart values and controls with the local version. See [report status](research/INTERACTIVE_REPORT_STATUS.json) and [round-trip audit](research/INTERACTIVE_REPORT_AUDIT.json).

The journal campaign completed **120/120 training trials and 60/60 frozen test evaluations**. The full compact-evidence and independent arithmetic audits passed. See [the measured interpretation](research/JOURNAL_INTERPRETATION.md), [full paired estimates](research/JOURNAL_FINDINGS.md), and [the updated paper](paper/main.tex). Effects are dataset-dependent, with unresolved three-way interactions and all selected learning rates at the lower search boundary.

The earlier reviewed pilot completed **8/8** Kaggle runs. See [the measured findings](research/PILOT_FINDINGS.md) and [the executed results notebook](notebooks/pilot_results_review.ipynb). The observed ranking reverses between scarce and full data under the provisional settings; one seed and untuned learning rates do not establish superiority.

The archived prospective design is [JOURNAL_PROTOCOL.md](research/JOURNAL_PROTOCOL.md), with an executable [plan](research/JOURNAL_PLAN.json) and [runtime-cap ledger](research/JOURNAL_BUDGET_LEDGER.json). The [manuscript](paper/main.tex) contains measured confirmation results and a separate pilot appendix. The supplied handoff and starter notebook are preserved in `handoff/` as historical input; their instructions are context and their numbers are configurations, not findings.

The journal runner adds a continuous deterministic sampling stream with fixed 20,480 image presentations / 1,280 updates per primary cell, short-horizon equal-count validation tuning, SGD, paired joint seed blocks, an audited VOC2007-derived transfer task, and a one-shot test evaluator gated on complete confirmation plus a checkpoint freeze. Model training runs only on Kaggle. Do not pool journal results with the pilot's different exposure and split policy.

Use `python scripts/launch_journal.py --mode campaign` only after the preflight passes and its dataset fingerprints are frozen into the main plan. This command reserves the full cap before submission and rejects any total above 43,200 seconds. Every additional preflight attempt reduces the campaign allowance. See the ledger for current submission status; building a notebook does not launch it.

Journal main version 1 has completed and its results have been collected. **Do not submit it again.** After the version 2 presentation save, `scripts/collect_journal.py` refuses to retrieve latest-version outputs into the frozen version 1 evidence directory. Inspect the version-specific evidence link above for original outputs. Recheck the preserved local evidence with `python scripts/audit_journal_evidence.py outputs/kaggle_journal_v1/muon_yolo_journal`. Generated manuscript includes were curated for publication; rerunning the older results builder would overwrite that formatting. The compact downloader omits large per-image predictions by default; checkpoints remain retrievable from Kaggle separately.

## Paper working files

| File | Purpose |
|---|---|
| [Pilot findings](research/PILOT_FINDINGS.md) | Executed results, descriptive comparisons and convergence caveats |
| [Methods draft](research/METHODS_DRAFT.md) | Description of the implemented development study, with explicit limitations |
| [Protocol](research/PROTOCOL.md) | Estimands, tuning, replication, compute controls and final-test policy |
| [Related work](research/RELATED_WORK.md) | Primary sources, focused section checks and conditional novelty assessment |
| [Data audit](research/DATA_AUDIT.md) | Exact/near-duplicate exclusions and the current 1,021/223/227 split |
| [Run registry](research/RUN_REGISTRY.json) | Kaggle notebook versions and segregation of superseded runs |
| [Earlier proposed run plan](research/PROPOSED_RUN_PLAN.json) | Historical unfrozen proposal; superseded by JOURNAL_PLAN.json |
| [References](research/references.bib) | Verified bibliographic starting points |

## What is implemented

- Pinned Ultralytics **8.4.187**, YOLO26n pretrained checkpoint, explicit AdamW/MuSGD, and optional explicit SGD through configuration.
- Nested training-image fractions and deterministic per-object missing-box noise. Separate subset, corruption, and training seeds. Original source labels are never edited.
- SHA-256 audits of all source/variant images and labels. The current `holdout_priority_reviewed_v2` policy keeps test intact, excludes exact overlaps from validation and training, and excludes 12 visually reviewed training near duplicates using a source-hash-bound manifest. All retained annotations remain byte-identical and frozen across variants. The perceptual screen is not an exhaustive scene audit.
- Shared checkpoint hash and verification of identical initialized model state across optimizers for each paired condition/seed.
- Unique IDs include configuration, code, data, checkpoint and environment. Completed results are verified before reuse; failures get separate attempt directories. Changed studies must use a new output directory.
- Actual optimizer groups, LR multipliers, optimizer steps, images seen, epochs, histories, training wall time, peak training VRAM, CSV/JSON results and PNGs.
- **Pilot runner scores validation only.** The journal runner has a separate final-test evaluator that requires complete confirmation and saves a checkpoint/configuration freeze before scoring.

Only missing-box corruption is implemented. The starter's unvalidated class-flip/jitter options are deliberately deferred. Images with empty label files are retained as no-annotation targets; visible objects may still be present after label deletion. Missing source label files are an error.

## Run on Kaggle

The CLI is available and authenticated on the owner's machine. Credentials are never embedded in source or notebooks.

```powershell
python -m pytest -q
python scripts/build_notebook.py --profile smoke
kaggle kernels push -p kaggle/smoke -t 1800
kaggle kernels status myudak/muon-yolo-smoke
kaggle kernels output myudak/muon-yolo-smoke -p outputs/kaggle_smoke
```

The notebook is **private**, requests a T4 GPU, enables Internet, installs the fixed training library, runs the tests, and executes two smoke runs. It embeds a checked source bundle so no separate source dataset upload or repository publishing is required. The actual GPU and software versions come from the resulting manifest, not the requested hardware name.

Open `notebooks/muon_yolo_smoke.ipynb` to inspect the notebook. Generated copies and Kaggle metadata live in `kaggle/smoke/`. After editing Python/configuration/test files, rebuild before pushing; the embedded bundle does not update itself. Change the metadata owner when using another Kaggle account.

The eight-run pilot is prepared separately and should run only after smoke evidence is checked:

```powershell
python scripts/build_notebook.py --profile pilot
kaggle kernels push -p kaggle/pilot -t 5400
kaggle kernels status myudak/muon-yolo-pilot-reviewed
python scripts/kaggle_evidence.py --kernel myudak/muon-yolo-pilot-reviewed --output outputs/kaggle_pilot_reviewed
python scripts/paired_analysis.py outputs/kaggle_pilot_reviewed/muon_yolo_pilot/results.json
```

Use a selective evidence download to avoid copying dataset images and checkpoints when only logs/metrics are needed:

```powershell
kaggle kernels output myudak/muon-yolo-smoke -p outputs/kaggle_smoke --file-pattern '.*(\.json|\.csv|\.png|\.txt|\.log|\.ipynb)$'
```

This regex includes per-image label TXT files, and CLI 2.0.2 does not follow later output pages. Use the helper below for a complete compact transfer; it follows pagination and excludes image-label directories.

```powershell
python scripts/kaggle_evidence.py --kernel myudak/muon-yolo-smoke --output outputs/kaggle_smoke
python scripts/summarize_experiment.py outputs/kaggle_smoke/muon_yolo_smoke
```

Outputs are under `/kaggle/working/muon_yolo_smoke/` or `/kaggle/working/muon_yolo_pilot/`. Preserve `manifest.json`, `source_audit.json`, `split_audit.json`, `variant_audit.json`, `checkpoint_lineage.json`, `experiment_identity.json`, `environment-lock.txt`, `results.csv`, `results.json`, per-attempt `run_spec.json`, `optimizer.json`, `result.json`, `train/args.yaml`, `train/results.csv`, and failure tracebacks. The environment lock records the exact execution environment; GPU/PyTorch are not assumed reproducible merely from requirements.txt.

Retain `initial_weights/yolo26n.pt` for exact checkpoint reproduction. The checked checkpoint SHA-256 is `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`; a future asset with the same filename may differ. The runner records and compares actual checkpoint hashes within each study. The compact evidence helper intentionally omits `.pt` weights; retrieve those separately from Kaggle outputs when needed.

## Local checks and execution

Python 3.10+ is supported. Dataset tests run on the installed local Python 3.14 without torch or CUDA:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m src.experiment --config configs/pilot.yaml --plan
```

After downloading a completed job, create an executed, self-contained CPU analysis companion:

```powershell
python scripts/summarize_experiment.py outputs/kaggle_smoke_v4/muon_yolo_smoke
python scripts/build_results_notebook.py outputs/kaggle_smoke_v4/muon_yolo_smoke --name smoke_results_review
```

This writes `notebooks/smoke_results_review.ipynb` with saved table/figure outputs and a readable HTML export. It embeds measured JSON/history snapshots and artifact hashes; it does not run model training or require Kaggle credentials. The exact evidence directory depends on where outputs were downloaded.

`scripts/paired_analysis.py` requires a complete paired 2×2 pilot grid and deliberately supplies no confidence interval for the one-block pilot. The journal summarizer computes separate validation/test paired joint-block contrasts, approximate t intervals, incomplete-block records and three-way interactions. The current local suite has 42 passing tests (37 core plus five analysis tests). All six journal preflight GPU trials completed, with exact update/exposure and paired-order checks on both datasets.

Create a portable source/evidence handoff with `python scripts/package_project.py --with-evidence outputs/kaggle_pilot_reviewed/muon_yolo_pilot`. The ZIP excludes dataset images, individual image labels, example photos and model weights. It verifies every packaged file against a SHA-256 manifest.

On a separate environment with CUDA-compatible PyTorch already installed:

```powershell
python -m pip install -r requirements.txt
python -m src.experiment --config configs/smoke.yaml --output outputs/local_smoke --max-runs 2
```

The runner requires CUDA and never silently switches to CPU or changes batch size after OOM. It restarts a failed attempt from the shared initial checkpoint rather than resuming partially trained optimizer state. Deterministic settings improve repeatability but do not guarantee identical floating-point behavior across GPUs/software versions.

## Interpretation and provenance

Smoke uses 5% of training images, 20% object missingness, two epochs, batch 8, 320 px. Pilot uses 20%/100%, 0%/20% missingness, 20 epochs, batch 16, 512 px. Learning rates (`AdamW=0.001`, `MuSGD=0.01`) are **untuned plumbing defaults**. Current smoke and pilot both disable warmup. This avoids Ultralytics' 100-iteration warmup minimum creating different warmup durations by data fraction; zero warmup is itself a development choice that requires tuning later. Augmentation is controlled, with mosaic disabled in both modes.

The comparison is between **Ultralytics recipes**. In version 8.4.187, MuSGD uses Muon factor 0.2, SGD factor 1.0, and 3× LR for selected detection-head groups. AdamW also uses a different weight-decay formulation. Forward/backward AMP is disabled, but MuSGD's internal orthogonalization still uses bfloat16. Actual group settings are saved. An algorithm-isolation study would require separate, validated ablations. See [official optimizer documentation](https://docs.ultralytics.com/reference/optim/muon/) and [training documentation](https://docs.ultralytics.com/modes/train/).

All models start from the same COCO-pretrained YOLO26n checkpoint. Official pretraining used MuSGD; this is not an Adam-pretrained model mismatch experiment. The class remapping feature is disabled consistently in these configurations; model initialization is verified after the detection head is adapted. Checkpoint metadata are retained for lineage. [Official recipe](https://docs.ultralytics.com/guides/yolo26-training-recipe/).

The African Wildlife documentation states 1,052/225/227 train/validation/test images and four classes. The downloaded data match these raw counts. Pilot overlap cleaning yields **1,021/223/227** images and **1,881/377/375** objects; the frozen journal campaign additionally excludes one reviewed training image, giving **1,020/223/227** images and **1,880/377/375** objects. The earlier exact-hash-only pool (1,033/223/227) is superseded. See [the data audit](research/DATA_AUDIT.md). Original image provenance and licensing scope remain those of the upstream providers. The manuscript contains numerical figures, and the companion source bundle omits source photographs and model weights. Source images are downloaded by the notebook. [Dataset documentation](https://docs.ultralytics.com/datasets/detect/african-wildlife/).

Equal epochs within a condition give matched examples/updates across optimizers. Across fractions, equal epochs give different data/step budgets. `training_seconds` measures the complete training call including setup, validation and final validation; it is **not** optimizer-kernel time or a matched-time benchmark. No superiority, statistical significance or SOTA claim is supported by a single-seed pilot.
