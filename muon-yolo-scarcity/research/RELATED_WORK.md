# Related work and novelty assessment

Checked 25 October 2026. This is a targeted initial search, **not** an exhaustive systematic review. Abstracts and official documentation establish the distinctions below; full experimental sections require deeper review before submission. Searches included `Muon MuSGD object detection annotation noise data scarcity optimizer benchmark`, `object detection missing annotations benchmark label noise optimizer Muon`, `site:arxiv.org MuSGD "noise"` and `site:arxiv.org Muon "data scarcity" detection`. The latter searches produced little relevant evidence; this is not proof of absence.

| Primary source | Relevant overlap | Consequence for this project |
|---|---|---|
| [Jordan, Muon: An optimizer for hidden layers in neural networks (2024)](https://kellerjordan.github.io/posts/muon/) | Matrix updates and Newton–Schulz orthogonalization; discusses use on convolutional weights. | Muon beyond language models is established. Attribute the optimizer and distinguish pure Muon from MuSGD. |
| [Jocher et al., Ultralytics YOLO26 (2026)](https://arxiv.org/abs/2606.03748) | Introduces the YOLO26 architecture/training family with hybrid Muon/SGD. | Applying an existing optimizer option to YOLO26 is not the contribution. |
| [Huang et al., MiMuon (2026)](https://arxiv.org/abs/2605.19619) | Another mixed Muon/SGD method; includes YOLO26m experiments. | Mixed matrix/SGD updates in detection are already studied. MiMuon is not interchangeable with Ultralytics MuSGD. |
| [Ruan et al., Muon Learns More Robust and Transferable Features than Adam (2026)](https://arxiv.org/abs/2606.09658) | Robustness to corrupted inputs and transfer of pretrained features. | Our manipulated variable is missing **training annotations**, not image corruption at evaluation. Their result does not predict ours. |
| [Qu et al., Can Muon Fine-tune Adam-Pretrained Models? (ICML 2026)](https://proceedings.mlr.press/v306/qu26e.html) | Full fine-tuning and optimizer-pretraining mismatch. | Record pretraining optimizer; official YOLO26 weights use MuSGD. Avoid directly importing an Adam-pretraining explanation. |
| [Akhtar et al., When Does Muon Actually Win? (2026)](https://arxiv.org/abs/2610.21555) | Matched data, elapsed time and tuning budgets for small language models/vision transformers. | Fairness of budget matching is existing methodology. Our candidate gap is detection fine-tuning with scarcity × missing labels. |
| [Yang et al., Object Detection as a Positive-Unlabeled Problem (BMVC 2020)](https://arxiv.org/abs/2002.04672) | Training with missing object labels and the false-background issue. | Missing boxes are an established detection problem; use existing terminology and avoid claiming a new noise model. |
| [Schubert et al., Identifying Label Errors in Object Detection Datasets by Loss Inspection (WACV 2024)](https://openaccess.thecvf.com/content/WACV2024/papers/Schubert_Identifying_Label_Errors_in_Object_Detection_Datasets_by_Loss_Inspection_WACV_2024_paper.pdf) | Detection label-error benchmark and loss-based diagnosis. | Distinguish optimizer robustness from label-error detection/correction. |
| [Llerena et al., Noise-Aware Evaluation of Object Detectors (WACV 2025)](https://openaccess.thecvf.com/content/WACV2025/papers/Llerena_Noise-Aware_Evaluation_of_Object_Detectors_WACV_2025_paper.pdf) | Evaluation sensitivity to annotation discrepancies. | “Clean” held-out data means unmodified source annotations, not verified annotation perfection. |
| [Penquitt et al., Object Detection Benchmarks are Incomplete (2026)](https://arxiv.org/abs/2609.21822) | Missing annotations, annotation uncertainty and real label errors. | Synthetic independent deletion is a controlled intervention with limited external validity. |

Candidate contribution, conditional on experiments: **a paired, reproducible study of the interaction between optimizer recipe, labeled-image count and missing-box probability in pretrained YOLO26 fine-tuning, with separate data/compute budgets and equal validation tuning budgets.** This is a plausible research direction, not established novelty or a promised result.

Before writing a novelty claim, inspect the full MiMuon/YOLO26 experiments and the citations of the budget benchmark, search OpenReview/CVF/arXiv for optimizer × missing-label detection studies, and add the closest directly comparable work. Report null/negative effects and release the configuration and per-seed evidence rather than framing this as proof that MuSGD wins.

Implementation authority: [training docs](https://docs.ultralytics.com/modes/train/), [MuSGD reference](https://docs.ultralytics.com/reference/optim/muon/), [pretraining recipe](https://docs.ultralytics.com/guides/yolo26-training-recipe/), and the actual pinned **8.4.187** wheel source hashes saved during execution. Mutable `main` source is not a substitute for the version actually run.

## Focused experimental-section review

- [YOLO26, section 4.3.2](https://arxiv.org/html/2606.03748v1) compares MuSGD and SGD in COCO training from scratch using different epoch budgets. This supports the relevance of MuSGD to detection, but does not resolve AdamW fine-tuning under scarce/noisy annotations. Our fixed-budget controls and fine-tuning setting must be stated explicitly.
- [MiMuon, section 6.2](https://arxiv.org/html/2605.19619v1) trains YOLO26m from scratch on Pascal VOC at 640 px and batch 32, with multiple optimizer baselines on an A100. The reviewed detection experiment does not manipulate training-image fraction or missing-box probability. It is a direct detection-optimizer precedent, with a different training regime from our proposal.
- [Akhtar et al., sections 2.2 and 4](https://arxiv.org/pdf/2610.21555) distinguish matched-data and matched-time measurements and note that equal candidate counts need not equal search-space coverage or tuning time. Our planned equal-count search must also report candidate ranges, compute and failures. Our current full training-call timings include validation/I/O, unlike their narrower training clock.

These are targeted section checks, not a complete critical review of theoretical claims, source code or every ablation. No independent reproduction of prior work has been performed. Bibliographic starting points are in `references.bib`.

## Additional label-noise precedents

Further searches for `"MuSGD" "annotation"`, `"Muon" "label noise"`, `"Muon" "object detection" "scarcity"`, and `"optimizer" "missing annotations" object detection AdamW` found broader Muon/noisy-data work. Do **not** describe this project as the first study of Muon under label noise.

- [Li et al., Muon in Associative Memory Learning: Training Dynamics and Scaling Laws](https://arxiv.org/abs/2602.05725) analyzes noisy labels in a structured associative-memory model and reports synthetic/LM experiments. Its assumptions and comparators do not directly establish detector annotation-missingness behavior.
- [Wu et al., DynMuon: A Dynamic Spectral Shaping View of Muon](https://arxiv.org/abs/2605.17109) connects spectral shaping to curvature, noise and training stage. This is conceptual context; we have not reproduced its theory or experiments.
- [Mastromichalakis, EchoMuon (preprint)](https://www.preprints.org/manuscript/202608.2150) includes vision classification with symmetric training-label noise, paired seeds and LR-selection audits. It is not peer reviewed on the inspected page. The distinction here is missing object annotations in pretrained detection, not noisy labels in general. Its LR-confound discussion reinforces the need for tuned baselines; no reported numerical advantage is transplanted into our study.

This search has not established an identical detector-fine-tuning factorial benchmark, but search absence does not prove novelty. The candidate contribution remains conditional on a careful final literature review and sufficient executed evidence.
