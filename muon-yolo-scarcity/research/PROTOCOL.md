# Proposed paper protocol — freeze after development

Working title: **When Does MuSGD Help? Data Scarcity and Missing Annotations in YOLO Fine-Tuning**.

Status: development protocol. The smoke/pilot settings are not yet a frozen confirmatory experiment. No final test evaluation is authorized by this configuration. Revisions before freezing belong in this file and a dated run plan.

## Question and estimands

Does the effect of choosing the Ultralytics MuSGD recipe over AdamW depend on training-image fraction and independent missing-box probability?

The primary per-condition quantity is the **paired difference** in clean held-out mAP50–95, MuSGD minus AdamW, for the same source checkpoint, image subset, deletion pattern and training seed. Include SGD as a reference in the research stage.

Prespecify two interaction contrasts: (1) the change in the optimizer difference between scarce and full data at fixed noise; (2) the change in the optimizer difference from clean to missing annotations at fixed fraction. With all four cells, also estimate the corresponding difference of these contrasts. Interpret intervals and effect magnitudes, not only which mean is larger. An inconclusive interval is an inconclusive finding.

“Clean” denotes unchanged source annotations, not exhaustively verified ground truth. This is fine-tuning from COCO-pretrained weights. Synthetic missing labels are independent by object; real missingness often depends on size, occlusion, crowding and class.

## Development stages and compute gate

1. **Smoke:** 2 runs, 5% training, 20% missing objects, 2 epochs. Validate source counts, hash audits, identical initialization and successful explicit optimizers. Never use these scores to select a winner.
2. **Pilot:** 8 runs, fractions 20%/100%, noise 0%/20%, 20 epochs. Establish runtime, memory, convergence and whether the experiment is feasible. All scores are validation. This stage supports engineering decisions, not a paper-level optimizer conclusion.
3. **Tuning:** freeze an equal, recorded candidate budget per optimizer. A practical initial proposal is 3 optimizer-appropriate learning rates × 2 weight-decay values = 6 candidates, on two prespecified development anchors (100% clean and 20% images with 20% missing boxes). With 3 optimizers this is 36 training jobs. Fix the schedule and choose one setting per optimizer by equal-weight mean validation mAP across the two anchors. Include default candidates and retain failed trials. Choose LR ranges from pilot stability, then freeze them before comparing candidate outcomes. This defines a global recipe, not a per-condition oracle.
4. **Confirmation:** begin with the 2 × 2 fraction/noise grid, 3 optimizers, and preferably 5 paired training seeds: 60 jobs. If only 3 seeds are affordable, say so and emphasize low precision. Expand fraction/noise levels only with an explicit budget. Use more than one corruption seed in a later replication; a single corruption pattern cannot establish robustness over annotation realizations.
5. **External confirmation:** add a second public detection dataset after checking provenance, licensing, split integrity and pretraining overlap. PASCAL VOC is a candidate, not an automatic download or proven independent test. Freeze its smaller confirmatory grid and tuning policy before running.

Stages 3–5 are proposals, not jobs scheduled by this repository. Estimate total GPU hours using the measured pilot before choosing them. Do not launch the full factorial grid by default.

## Controls and important confounds

Start every paired run from the same checkpoint bytes and check initialized model state after the detection head adapts. Fix image/batch size, augmentation, precision, workers, schedule, nominal batch size/accumulation, loss configuration and validation settings. Record actual optimizer groups: the pinned MuSGD implementation has hybrid weighting and selected head LR multipliers. These effects belong to the implemented recipe; isolating orthogonalization requires separate ablations.

A useful later control matches the selected detection-head LR multipliers across optimizers. Without it, differences between library recipes cannot be attributed specifically to orthogonalization. Coupled versus decoupled weight decay and internal bfloat16 MuSGD arithmetic also remain implementation differences even when the same nominal decay coefficient and forward/backward AMP setting are used.

Equal epochs match images/steps **within a fraction**, but fractions have different exposure. If asking whether extra data itself helps, separately consider a matched-step or matched-image budget and explain the repetition rate. Run fixed-budget training without performance-based early stopping. Pick best epochs using validation only, consistently across optimizers. Compare repeated seeds with matched conditions; check out-of-memory or NaN rates as outcomes.

Elapsed training-call time includes setup and validation. A separate matched-time experiment must freeze the timing boundary, GPU type, validation cadence and stopping/checkpoint policy, and report actual overshoot. It cannot be inferred by dividing the fixed-epoch accuracy by seconds. Per-optimizer kernel timing is optional and must be measured separately if used to explain overhead.

Official pretraining used MuSGD. Record embedded training arguments and code lineage. COCO class familiarity and possible image-source overlap limit the claims. The primary dataset has only four classes and a small held-out sample. Audit exact duplicate images now and scene/near-duplicate overlap before the final study. Resolve the dataset license before release; downloadable does not establish redistribution rights.

The initial audit already found exact cross-split image duplication. Before any training or score inspection, `holdout_priority_v1` was defined to preserve test and exclude overlapping validation, then training images. The frozen pool is 1,033 train / 223 validation / 227 test, instead of 1,052 / 225 / 227. Report this split-membership deviation and its exclusion manifest; unchanged labels alone do not imply unchanged validation membership. See `DATA_AUDIT.md`.

Development revision: a later perceptual screen and visual review found 12 additional training near duplicates. Current `holdout_priority_reviewed_v2` uses **1,021 / 223 / 227** images and a source-hash-bound exclusion manifest. Earlier exact-cleaned results are diagnostic and superseded. Current pilot warmup is zero to avoid the library's minimum-iteration warmup confound. These revisions precede confirmation; they are not claimed to have preceded every development score.

## Statistical reporting and test policy

Publish all paired seed values, mean differences and clearly defined uncertainty intervals. With few seeds, seed-level intervals are unstable; report that limitation. If using a t interval over paired differences, state the independent unit and assumptions. Multiple corruption seeds add a second variability source and should be analyzed as such, not pooled as independent images. Image-level uncertainty for mAP requires resampling detections and recomputing mAP; it is not the mean of per-image AP.

Subset randomness is a further source of variation: several training seeds on one nested subset do not estimate variability over which images were labeled. Report the subset-conditioned estimand, describe class composition and add subset replications where the budget permits. Preserve pairing within each subset/corruption/training-seed block.

Use validation for candidate and epoch selection, and archive a machine-readable frozen run plan with selected settings, primary contrasts, seeds and hashes. The final evaluator should accept only that frozen plan and should write a test-access log. Open the test set once after tuning and debugging are complete. Do not change settings in response to final test outcomes. Record any unavoidable protocol deviation and treat subsequent results as exploratory.

## Paper structure and evidence required

- **Introduction:** practical question, existing MuSGD support, and the narrow candidate contribution. No claim that we invented Muon for detection.
- **Related work:** optimizer geometry/hybrids, detection annotation missingness, transfer/pretraining lineage, and fair optimizer evaluation.
- **Methods:** source splits/hashes, nested subsets, deletion mechanism and realized rates, model lineage, explicit recipes, tuning budgets, timing boundaries, seed pairing and final-test freeze.
- **Results:** per-condition paired differences and interactions; convergence; actual time/memory; failure counts; separate fixed-data and fixed-time evidence. Fill only from executed final runs.
- **Discussion:** positive/null/negative findings, uncertainty, dataset limitations, source annotation errors, synthetic noise and limits of generalization.
- **Reproducibility appendix:** versions/hardware, configuration and checkpoint hashes, all tuning trials, manifests and failure/resume policy.

Do not draft a results-bearing abstract, claim significance, or invent mechanism explanations before those experiments exist. Venue and submission format can be chosen once the pilot establishes the study's scale and strength.
