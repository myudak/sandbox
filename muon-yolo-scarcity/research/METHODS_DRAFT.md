# Methods draft: implemented development stage

This is a draft description of the current smoke/pilot pipeline, not a completed manuscript. Hyperparameter search, repeated-seed confirmation and final test evaluation are not described as completed work.

## Setting and question

We compare the Ultralytics MuSGD and AdamW fine-tuning recipes for YOLO26n under reduced training-image availability and missing bounding-box annotations. The experiment tests an existing implementation rather than proposing a new optimizer. YOLO26 already uses hybrid Muon/SGD updates, while its published detection optimizer ablation concerns training from scratch; our candidate focus is the joint effect of scarcity and annotation missingness during fine-tuning. [YOLO26, sections 3.3.1 and 4.3.2](https://arxiv.org/html/2606.03748v1).

## Source data and split membership

The downloaded African Wildlife source contains 1,052 training, 225 validation and 227 test images, with four classes. SHA-256 auditing identifies exact cross-split image overlap. A fixed priority rule preserves the official test split, removes overlapping validation images and then removes training images overlapping either retained held-out split. A subsequent dHash screen and visual review identifies 12 further training images with held-out scene counterparts. These training exclusions and their peers are bound to exact content hashes and the source fingerprint.

The current pool contains **1,021 training images (1,881 objects), 223 validation images (377 objects), and 227 test images (375 objects)**. All retained label bytes remain unchanged. The validation/training memberships therefore differ from the original official splits; the test membership does not. Both cleaning stages and their development chronology are reported in `DATA_AUDIT.md`. Residual near-duplicate scenes and annotation errors remain possible. “Clean validation” means unchanged retained source annotations, not a verified gold standard. Image provenance and licensing require resolution before redistribution.

## Scarcity and missing-label intervention

For training fraction f, images are ranked by a deterministic SHA-256 score of the subset seed and source-relative path. The first ceil(fN) images are retained, giving nested fractions. The pilot compares f=0.20 and f=1.00, corresponding to 205 and 1,021 images from the current pool. Selection is independent of model outcomes and is not class-stratified. Class composition is reported separately.

For each original annotated object, a deterministic score derived from the corruption seed, image path and object index is compared with missingness probability q. Its label is removed if the score is below q. The pilot compares q=0 and q=0.20. Realized rates use **removed objects / original annotated objects in the selected subset**; they need not equal q exactly. Images with no remaining annotations are retained with empty label files. The mechanism changes only training annotations, and it does not correct or simulate every real-world annotation error. The same object scores are reused across fractions and noise probabilities.

Subset, corruption and training seeds are distinct (2026, 2027 and 42 in development). Every optimizer sees identical selected images and corrupted labels for a condition. Repeating training seeds alone would not measure uncertainty over subset selection or corruption realizations.

## Initialization and training

All runs load the same official `yolo26n.pt` bytes independently, adapt the model to four detection classes with class-row remapping disabled, and verify a matching initialized model-state hash across paired optimizers. Embedded checkpoint arguments identify MuSGD pretraining. This is not an Adam-pretrained optimizer-mismatch experiment. Checkpoint and library source hashes are retained.

The current pilot uses 20 epochs, 512 px images, batch/nominal batch 16, explicit deterministic settings and zero warmup. Zero warmup avoids a library minimum of 100 warmup iterations changing the effective warmup epochs by fraction, but is an untuned development choice. Mosaic and mixing augmentations are disabled; the remaining explicit controls are recorded in `configs/pilot.yaml` and each runtime `args.yaml`. Both recipes share the epoch budget, data condition, schedule and evaluation settings. Across data fractions, fixed epochs imply different image/step exposure.

Development learning rates are 0.001 for AdamW and 0.01 for MuSGD, with momentum/beta1 0.9 and nominal weight decay 0.0005. They are provisional, not matched-budget tuned optima. Ultralytics 8.4.187 also uses selected 3× detection-head learning rates in MuSGD and hybrid coefficients of 0.2/1.0. Actual parameter groups are saved. Forward/backward AMP is disabled, but MuSGD's internal Newton–Schulz implementation still uses bfloat16. AdamW uses the CUDA fused implementation when instantiated by this pinned trainer. These are implementation/recipe comparisons, not isolated orthogonalization ablations.

## Development evaluation and accounting

Best epochs are selected on retained validation data. Saved best weights receive a separate clean-validation evaluation with fixed image size, confidence/IoU settings and detection cap. The primary development metric is validation mAP50–95; mAP50, precision, recall and class AP are retained. Per-epoch histories and independent best-checkpoint validation can differ slightly and are reported separately.

Training-call wall time includes setup, validation and final validation. Peak allocated training VRAM, actual optimizer steps, completed epochs and image exposure are recorded. Loader image counts are checked; automatic batch-size changes or dropped samples invalidate the exposure accounting. These timings do not establish matched-time or optimizer-kernel efficiency. In particular, cold-start behavior and T4 support for internal update dtypes can affect recipe timing.

One paired training seed supports plumbing and feasibility observations, not statistical claims. The planned final study requires equal validation tuning budgets, SGD, repeated training/subset/corruption realizations, external confirmation and prespecified timing/analysis rules. Test labels are audited for integrity but no test metric is computed in development; final test evaluation must follow a frozen protocol.
