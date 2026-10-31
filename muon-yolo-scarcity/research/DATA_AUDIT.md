# African Wildlife split audit — 25 October 2026

**Current policy: `holdout_priority_reviewed_v2`**, superseding exact-hash-only cleaning. The table below documents the initial exact-hash stage; the subsequent review is recorded afterward.

The first private Kaggle smoke job (version 1) stopped before model training because the official source has exact image overlap across splits. The source was downloaded by Ultralytics 8.4.187; the evidence is `outputs/kaggle_smoke_v1/muon_yolo_smoke/source_audit.json`. This is an observed data-integrity issue, not a model result.

| Split | Downloaded images | Downloaded objects | Frozen images | Frozen objects |
|---|---:|---:|---:|---:|
| Train | 1,052 | 1,931 | 1,033 | 1,900 |
| Validation | 225 | 379 | 223 | 377 |
| Test | 227 | 375 | 227 | 375 |

The audit found 20 cross-split duplicate occurrences relative to each hash's first-seen image. A hash can occur in more than two splits, so that list is not an exhaustive pair list. The cleaning policy excludes **21 files: 19 training images and 2 validation images**. No model was trained and no validation/test metric was inspected before freezing this rule.

`holdout_priority_v1` keeps every official test image. It excludes validation images whose image SHA-256 occurs in test, then excludes training images whose SHA-256 occurs in either retained held-out split. Within-split duplicates are retained in this initial policy. Source files and all retained label bytes remain unchanged. The clean validation/test memberships are then frozen across all training fractions, noise levels and optimizers.

This is a **modified training/validation membership**, not the original official split. The paper must state that deviation and report both raw and effective counts. The cleaned training pool defines the denominator for scarcity fractions. It is inappropriate to claim byte-identical original validation membership after these exclusions.

[source_split_audit_2026-10-25.json](source_split_audit_2026-10-25.json) contains effective records, original source fingerprint, policy, counts and every exclusion with image/annotation hashes. The runtime also writes `source_audit.json` for the raw source and `split_audit.json` for the frozen pool. Variants verify their retained validation/test records against that frozen pool.

Limitations: SHA-256 detects identical bytes, not resized/recompressed copies, related frames or shared scenes. Within-split duplicate weighting and near-duplicate overlap need inspection before the final study. “Clean labels” means unchanged source annotations, not a human-verified gold standard.

## Reviewed near duplicates and current frozen pool

A 64-bit horizontal dHash screen of the exact-cleaned pool found **12 cross-split candidate pairs** at Hamming distance <=3. Visual review of all 12 pairs on `outputs/near_duplicate_audit/candidate_contact_sheet.png` showed matching scenes with different image bytes. All first images were training images, and 12 distinct training images were excluded. The dHash threshold alone never edits the data.

The reviewed manifest is `configs/duplicate_exclusions.json`. It binds every exclusion and its held-out peer to exact image SHA-256 and binds the complete decision list to the original source fingerprint. If source content changes, the runner rejects the reviewed list. The reviewed pairs may differ in crops/resolution/encoding; this review establishes scene overlap, not byte equality.

| Split | Current images | Current objects | Removed images from raw split |
|---|---:|---:|---:|
| Train | 1,021 | 1,881 | 31 |
| Validation | 223 | 377 | 2 |
| Test | 227 | 375 | 0 |

[source_split_audit_reviewed_v2.json](source_split_audit_reviewed_v2.json) records the current pool and all 33 exclusions. Fractions are computed from 1,021 training images. Validation membership remains the same as the exact-cleaned stage, and test membership remains the entire official split.

This additional review happened after inspecting the two-epoch smoke outputs and after submitting the initial pilot. Consequently, the initial smoke/pilot remain **development diagnostics**, and their scores must not be mixed with runs from the revised pool. The exclusions were chosen from image similarity and visual review, not model errors or per-image scores. The revised pilot also disables warmup to remove a data-fraction-dependent 100-iteration floor. Both changes are protocol revisions before confirmation, not a frozen confirmatory study.

The dHash screen can miss crops, flipped images and related frames. Within-split duplicates are retained. This small web-image dataset remains an engineering benchmark with unresolved provenance and scene-overlap limitations; a paper should add a carefully audited, licensed external dataset before making general claims.


## Journal preflight review and frozen inputs

The journal preflight used the pilot pool and an additional prespecified conservative cross-split dHash/RGB screen. It completed six GPU trials, with 128 image presentations and eight optimizer updates each. No additional image met the automatic exclusion threshold.

Before main submission, the candidate sheets were reviewed as input evidence. The wildlife pair `train/1 (81).jpg` and `test/1 (41).jpg` shows a likely same-scene buffalo/bird subject at different framing. It had dHash distance 6 and normalized RGB MAE 0.0732, above the automatic 0.025 threshold. The training image was conservatively excluded through a separate source/peer-hash-bound manifest, `configs/journal_duplicate_exclusions.json`. This decision used input images, not preflight performance; it does not assert byte identity. It also shows why the prior pilot's near-scene screen must be described as incomplete.

The journal pool is now **1,020/223/227 images and 1,880/377/375 objects**. Pilot results remain attached to their original 1,021-image training pool. Do not compare the phases as though split membership were identical. All test images and annotations remain unchanged.

VOC2007 official membership was converted with difficult objects retained, with a frozen 512-image validation sample. The main counts are **2,501/512/4,952 images and 7,844/1,591/14,976 objects**, with all 20 classes represented in each clean split. The 23 dHash candidate pairs in the contact sheet showed no apparent same-scene counterpart; no extra visual exclusion was applied. This is a limited candidate review, not proof of complete scene independence.

Final input hashes and the preflight-to-main chronology are in `JOURNAL_DATA_FREEZE.json`. The main runner verifies these identities before training. Source photographs and private review sheets are excluded from the distributable project package.
