# Measured journal campaign: interpretation — 31 October 2026

The Kaggle campaign completed **120/120 unique training trials and 60/60 frozen test evaluations**, with no recorded failure or incomplete confirmation block. Its manifest completed at 2026-10-25 09:01:59 UTC, approximately **16:02 WIB on 25 October**. The runner clock covered **10.24 hours**, including dataset preparation, training and final evaluation, but excluding initial notebook installation and output persistence. The external cap remained 11 hours 40 minutes; together with the preflight cap it respected the 12-hour authorization. No further training was launched.

The compact transfer contains 688 files across six API pages. Local checks passed for frozen plan/code/data/variant identities, all per-run finite histories, actual image exposure and optimizer steps, initialized model and presentation-order pairing, CSV/JSON metrics and linkage of all test results to the 60-checkpoint freeze. An independent arithmetic audit recalculated 70 summaries from raw rows, including the three-way contrasts and approximate three-block t intervals. This validates recorded evidence and internal consistency; source-image and checkpoint bytes were not independently downloaded and rehashed in this compact collection.

## What the test results support

Values are means across three paired joint training/subset/deletion blocks. Units are mAP50–95 multiplied by 100; differences are AP points.

| Dataset | Images | Target missing boxes | AdamW | MuSGD | SGD | MuSGD − AdamW |
|---|---:|---:|---:|---:|---:|---:|
| Wildlife | 20% | 0% | 80.30 | 81.08 | 81.17 | +0.79 |
| Wildlife | 20% | 20% | 74.86 | 75.12 | 77.59 | +0.26 |
| Wildlife | 100% | 0% | 84.32 | 85.06 | 84.59 | +0.74 |
| Wildlife | 100% | 20% | 82.78 | 82.53 | 82.86 | −0.25 |
| VOC-derived | 20% | 0% | 46.59 | 48.14 | — | +1.55 |
| VOC-derived | 20% | 20% | 42.18 | 43.85 | — | +1.67 |
| VOC-derived | 100% | 0% | 54.15 | 55.25 | — | +1.10 |
| VOC-derived | 100% | 20% | 52.24 | 52.97 | — | +0.73 |

MuSGD has positive point differences in all four VOC-derived test cells and smaller, mixed differences on wildlife. All wildlife MuSGD–AdamW paired cell intervals include zero. Two VOC cell intervals exclude zero before multiplicity correction; these are exploratory comparisons with only three blocks. This is not evidence of a universal ranking.

The prespecified MuSGD–AdamW scarcity × missingness interaction is **+0.470 AP points, approximate 95% interval [−6.383, 7.322] on wildlife**, and **+0.488 [−0.660, 1.637] on VOC-derived data**. Both intervals include zero. The joint interaction is unresolved. The primary estimate should not be replaced by whichever individual cell looks most favorable.

SGD is an important secondary baseline: on wildlife with scarce images and missing boxes it exceeds AdamW by +2.73 points and has the highest recipe point estimate in that cell. Its unadjusted paired interval is [0.61, 4.85]. The remaining SGD–AdamW cell intervals include zero.

## Search boundaries are a central limitation

All three recipes selected their **lowest searched learning rate**: AdamW 0.0003 (decay 0.0005), MuSGD 0.003 (decay 0.0005), and SGD 0.003 (zero decay). All six candidates per optimizer completed on both validation anchors. The planned equal-count boundary extension was skipped by the prospective runtime-reservation rule. Its omission must be disclosed even though the eventual job finished below its external cap.

These results concern finite-grid-selected recipes, not globally optimized baselines. Settings were selected at ten exposure blocks on one development realization and transferred to twenty-block confirmation; VOC settings were transferred without VOC tuning. Test access has already occurred. A new search prompted by these test results would be exploratory or require a new prospective evaluation design; it must not be presented as a continuation of an untouched confirmatory test.

## Controls and sensitivity

The original pilot's ranking reversal was absent even in the new variable-exposure bridge. That bridge changed one training image, sampling and batch rounding, so a cross-phase causal attribution to exposure alone is unsupported. The fixed-exposure primary comparisons do control actual image presentations and updates within the journal phase.

Four 60-block transfer checks completed on block 101 at 20% missing boxes. Each produced lower best-checkpoint validation AP than its paired twenty-block run, by 0.65–3.51 points. These are schedule-transfer observations, not convergence or optimal-horizon results.

The block-101 MuSGD head-LR 1× check changed validation AP by +1.56/+1.41/+0.08/−0.04 across scarce-clean/scarce-missing/full-clean/full-missing cells relative to native 3×. Actual optimizer group LRs confirm the change. There was no separate retuning or additional test evaluation. Optional confirmation blocks 104/105 were skipped; all reported confirmation intervals use three blocks.

## Paper state

The existing `paper/main.tex` now contains measured confirmation/test results, the selection-boundary limitation, descriptive controls and sensitivity checks, and an updated abstract/discussion/conclusion. Its generated test table derives from the archived numeric summary. Figures show paired means, all three block differences and approximate intervals. The source compiles in the desktop LaTeX editor; final PDF page layout has not been visually reviewed.

The results notebook executes locally without CUDA, network access or pandas and independently checks reported interval arithmetic. Full literature review, image-rights statements, author information and venue selection remain necessary before submission. The evidence supports a conditional empirical recipe study; journal acceptance and broad novelty are not established by execution success.
