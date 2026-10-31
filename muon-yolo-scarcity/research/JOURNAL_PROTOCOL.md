# Journal development protocol

This protocol was written after the eight-run pilot and before the journal campaign. It is a prospective development plan, not a registered report. The user selected a journal target and authorized at most 43,200 additional Kaggle notebook seconds. No claim of journal readiness or publication follows from that choice.

The machine-readable authority is `JOURNAL_PLAN.json`; submitted plans and their hashes are embedded in each notebook. The ledger `JOURNAL_BUDGET_LEDGER.json` reserves the entire runtime cap before each submission. Failed attempts consume their full reservation conservatively. Prior completed pilot jobs are outside this new authorization. The first preflight reserves 1,200 seconds, leaving at most 42,000 seconds for the campaign. Any additional preflight attempt reduces the main cap. Both installation and data preparation are subject to Kaggle's external notebook timeout.

## Research question and estimand

The question is whether the MuSGD–AdamW difference changes with available training images and missing-box annotations when image exposure and update count are held constant. SGD provides a conventional momentum baseline on the primary dataset. This compares native optimizer recipes in the pinned detector implementation, including parameter groups, internal precision and head learning rates. It does not identify a causal effect of orthogonalization alone.

All primary cells receive 20 exposure blocks of 1,024 images at batch 16: 20,480 presented images, 1,280 optimizer updates, 20 schedule events and 20 validation events. A continuously shuffled cyclic stream revisits scarce images. The term “block” replaces an ordinary full pass through the unique images. A per-run hash of the actual presented image sequence must agree across paired recipes. Augmentations are randomized reproducibly; batch size, accumulation and warmup are fixed. No dataset fraction is changed in response to performance.

The preliminary control compares variable rounded exposure with fixed exposure at the pilot's default learning rates on one development block. Rounding fills batches, so it is a bridge to the original pilot, not an exact reproduction of its 260/1,280 updates. The journal data audit may also remove additional near copies. Do not pool the two phases as identical data.

## Datasets

African Wildlife starts with the pilot's hash-bound reviewed exclusions. Both datasets then receive the same prespecified conservative cross-split screen: dHash distance at most 6, normalized RGB MAE at most 0.025 after resizing to 32×32, and relative aspect difference at most 0.05. Connected components retain the highest-priority split (test, then validation, then training); same-split duplicates can remain. Images and labels in the test split are never removed or modified. This screen is not an exhaustive scene/entity or pretraining-overlap audit.

VOC2007 uses its original train, val and test lists, with 2,501, 2,510 and 4,952 images before filtering. All annotated objects, including `difficult`, are retained. One-based inclusive coordinates become zero-based half-open coordinates before normalization. This controlled all-object task is scored by mAP50–95 and must not be presented as official VOC AP or the usual Ultralytics VOC conversion. A deterministic 512-image validation sample is selected without model outcomes, and all 20 classes must be represented. Full original test membership is retained. Source and retained split fingerprints from a successful preflight are frozen for the main job.

After preflight v1, the private candidate sheets were inspected before main submission. One additional likely same-scene wildlife training image was conservatively excluded via `configs/journal_duplicate_exclusions.json`, bound to both image hashes and the source identity. Its candidate failed the automatic RGB threshold, illustrating the screen's limits. No preflight model score was used in the review. The main wildlife pool is **1,020/223/227** images (1,880/377/375 objects); the original pilot remains unchanged. The VOC sample contains **2,501/512/4,952** images (7,844/1,591/14,976 objects), with all 20 classes represented. `JOURNAL_DATA_FREEZE.json` records final identities and chronology.

## Tuning and confirmation

Each optimizer receives six candidates: three prespecified learning rates × two weight decays, tested at two validation anchors (full/clean and scarce/missing). All candidates use the same development training/subset/corruption block and ten exposure blocks. The highest mean anchor mAP selects one global setting per optimizer; ties favor lower learning rate and then lower decay. Ten-block tuning is a budget constraint: these settings transfer to twenty-block confirmation without retuning. Report search compute, failures, margins and whether the selected learning rate lies at the searched boundary.

If a boundary optimum is observed and estimated time for all mandatory confirmation runs remains, an equal-count extension adds two candidates per optimizer, again at both anchors and ten blocks. The rule is deterministic and recorded in the machine-readable plan. Equal counts do not guarantee equal search-space coverage or equal tuning time.

The primary confirmation uses joint blocks 101–103, all three optimizers and the complete 2×2 condition grid. Training seed is the block ID, subset seed is 3,000 plus that ID, and corruption seed is 4,000 plus that ID. The external task transfers the selected AdamW/MuSGD settings with the same three block IDs and grid; no VOC hyperparameter search is performed. Pairing is within dataset, block and condition. A joint block is an independent randomized realization of all three sources; it is not a training-seed-only replicate.

Only after these mandatory stages can optional longer schedules, the head-LR sensitivity check or additional complete primary blocks run. Time allocation uses runtime, not the direction of performance differences. Optional experiments must be labeled as one-block descriptive checks when appropriate. A 60-block transfer does not demonstrate convergence or use settings tuned specifically for that horizon.

## Freezing and opening the test split

Before any test metric call, all three mandatory blocks on both datasets must be complete, with no attempted incomplete confirmation block. The runner saves a freeze containing checkpoint paths and SHA-256 hashes, variants, hyperparameters, code/plan identity and UTC time. Checkpoint selection uses validation only. Selected complete confirmation checkpoints receive a single fixed-setting test evaluation. Per-image predictions are saved to permit later image-level analyses, but no such analysis is claimed until performed.

If the mandatory grid is incomplete, test scoring remains unopened. If final evaluations run out of time, every attempted and missing test cell is reported; incomplete blocks are not pooled into paired summaries. No test-guided tuning or retry is authorized by this protocol. Failed and budget-stopped training trials remain in the full trial ledger.

## Analysis and interpretation

Report per-condition mean mAP, realized annotation removal, exposure, actual optimizer steps, timing and memory. Within each joint block, compute recipe differences in AP points. The prespecified descriptive interaction is:

`[(MuSGD−AdamW)scarce,missing − (MuSGD−AdamW)scarce,clean] − [(MuSGD−AdamW)full,missing − (MuSGD−AdamW)full,clean]`.

Analogous SGD contrasts are secondary. Approximate Student t intervals use variation across paired joint blocks. At three blocks these intervals are unstable, do not represent an image-level bootstrap and cannot isolate subset/corruption/training variance. Numerous cell contrasts are exploratory, without multiplicity-adjusted significance claims. Report negative or inconclusive findings with the same treatment as positive results.

The eventual journal paper must disclose the post-pilot design, short tuning horizon, chosen checkpoint's MuSGD pretraining lineage, native recipe differences, source-image licensing uncertainty, possible pretraining overlap, limited model/dataset diversity and synthetic independent deletion. A venue decision depends on completed results and a fuller literature review.
