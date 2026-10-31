# Journal results status — 31 October 2026

**Completed and audited:** 120/120 unique training trials and 60/60 frozen-checkpoint test evaluations, with no recorded failure or incomplete confirmation block. The main manifest completed on 25 October 2026 at 09:01:59 UTC, approximately **16:02 WIB**. No additional training was launched during collection.

The now-public [main Kaggle notebook](https://www.kaggle.com/code/myudak/muon-yolo-journal), [original version 1](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=361947826), ran on one T4 device. The runner clock covered 36,859.9 seconds (10.24 hours), excluding initial notebook installation and subsequent output persistence. Its external cap was 42,000 seconds. Combined with the preflight's 1,200-second cap, the conservative total reservation remained 43,200 seconds. All GPU training was remote. The version 2 publication save completed as an 8.3-second Quick Version. The final [version 5 interactive report](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=364100382) completed in 22.4 seconds on CPU; no full training campaign was rerun.

The public reading view contains five interactive charts, methods, interpretation, limitations, exact frozen-test values and provenance links. Dataset/split, search recipe, condition and trajectory metric controls are available without a live Python kernel. Inputs are collapsed in reading view. The downloaded Kaggle CSV, numeric snapshot, chart data and control specifications match the local reviewed report; all 70 summaries were recalculated. Chart rendering and dataset switching were verified against Kaggle's generated HTML, and the owner confirmed the main notebook works on a phone. The Output tab includes an offline HTML explorer and numeric exports. Versions 3–4 are superseded presentation iterations.

Completed stages: 16 unique default/exposure-control trials, 36 tuning trials, 36 wildlife confirmation trials, 24 VOC-derived transfer trials, four longer-schedule trials and four head-LR trials. Four identical full-data default runs are shared across control roles. Confirmation uses blocks 101–103. The boundary extension and optional blocks 104/105 were skipped by the runtime-reservation rule.

The compact transfer contains 688 files across six API pages. The local evidence audit passed for plan/code/source/variant identities, finite histories, actual exposure/step counts, paired initialization and image order, and test-freeze linkage. A separate arithmetic audit recalculated 70 summaries from raw metrics and checked CSV/JSON equality. This does not independently rehash source photographs or checkpoint bytes, which were omitted from the compact transfer.

Working artifacts:

- `JOURNAL_INTERPRETATION.md`: central results, search boundaries, controls and interpretation.
- `JOURNAL_FINDINGS.md`: separate validation/test paired estimates and intervals.
- `JOURNAL_NUMERIC_AUDIT.json`: raw-metric recalculation checks.
- `../notebooks/journal_results_review.ipynb` and `.html`: executed portable CPU analysis with embedded evidence and figures.
- `../paper/main.tex`: the existing manuscript, updated in place with measured abstract, results, discussion and conclusion.

MuSGD test point differences are positive in all VOC-derived cells and small/mixed on wildlife. Both prespecified scarcity × missingness interaction intervals include zero. All selected learning rates are at the lower search boundary. The paper reports conditional recipe behavior and uncertainty, rather than general optimizer superiority.

The publication manuscript names Muchammad Yuda Tri Ananda (yuda@myudak.com). Its ten-page PDF is exported at `../output/pdf/muon_yolo_scarcity.pdf`; the saved source compiles in the desktop editor, and every PDF page was visually reviewed after rendering. Font embedding, author metadata, A4 geometry and links passed automated checks. The paper includes verified primary references and explicit upstream-data terms; no affiliation was invented. Venue-specific formatting remains dependent on journal selection. No background monitor, scheduled task or notification was created.
