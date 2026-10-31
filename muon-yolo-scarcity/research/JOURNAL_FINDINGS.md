# Bounded journal campaign evidence

Status: **completed**. Attempted runs: 120. Failed/budget-stopped runs: 0.

Frozen test status: `completed`. Validation and test summaries are separate.

All intervals describe variation across joint randomization blocks. They are not image-bootstrap confidence intervals or evidence of optimizer causality.

## wildlife: validation

Joint blocks: [101, 102, 103]. Units: AP points.

| Contrast | Images | Missing boxes | Mean paired difference | Approximate 95% interval |
|---|---:|---:|---:|---|
| MuSGD minus AdamW | 20% | 0% | -0.709 | [-4.216, 2.797] |
| SGD minus AdamW | 20% | 0% | +0.721 | [-2.962, 4.403] |
| MuSGD minus AdamW | 20% | 20% | -1.367 | [-3.324, 0.590] |
| SGD minus AdamW | 20% | 20% | +0.007 | [-2.036, 2.049] |
| MuSGD minus AdamW | 100% | 0% | -0.175 | [-1.119, 0.769] |
| SGD minus AdamW | 100% | 0% | +0.664 | [-1.357, 2.685] |
| MuSGD minus AdamW | 100% | 20% | +0.618 | [0.065, 1.171] |
| SGD minus AdamW | 100% | 20% | +0.989 | [-0.722, 2.699] |

## voc2007: validation

Joint blocks: [101, 102, 103]. Units: AP points.

| Contrast | Images | Missing boxes | Mean paired difference | Approximate 95% interval |
|---|---:|---:|---:|---|
| MuSGD minus AdamW | 20% | 0% | +1.785 | [-0.045, 3.615] |
| MuSGD minus AdamW | 20% | 20% | +1.481 | [0.311, 2.650] |
| MuSGD minus AdamW | 100% | 0% | +0.744 | [-0.892, 2.381] |
| MuSGD minus AdamW | 100% | 20% | +1.639 | [-0.987, 4.264] |

## wildlife: frozen_test

Joint blocks: [101, 102, 103]. Units: AP points.

| Contrast | Images | Missing boxes | Mean paired difference | Approximate 95% interval |
|---|---:|---:|---:|---|
| MuSGD minus AdamW | 20% | 0% | +0.785 | [-0.655, 2.225] |
| SGD minus AdamW | 20% | 0% | +0.870 | [-0.671, 2.412] |
| MuSGD minus AdamW | 20% | 20% | +0.259 | [-0.441, 0.959] |
| SGD minus AdamW | 20% | 20% | +2.730 | [0.605, 4.855] |
| MuSGD minus AdamW | 100% | 0% | +0.745 | [-1.850, 3.339] |
| SGD minus AdamW | 100% | 0% | +0.276 | [-2.583, 3.136] |
| MuSGD minus AdamW | 100% | 20% | -0.251 | [-4.753, 4.251] |
| SGD minus AdamW | 100% | 20% | +0.077 | [-5.037, 5.191] |

## voc2007: frozen_test

Joint blocks: [101, 102, 103]. Units: AP points.

| Contrast | Images | Missing boxes | Mean paired difference | Approximate 95% interval |
|---|---:|---:|---:|---|
| MuSGD minus AdamW | 20% | 0% | +1.554 | [-0.214, 3.322] |
| MuSGD minus AdamW | 20% | 20% | +1.671 | [0.434, 2.908] |
| MuSGD minus AdamW | 100% | 0% | +1.102 | [0.668, 1.536] |
| MuSGD minus AdamW | 100% | 20% | +0.731 | [-0.659, 2.120] |

## Limits

- Short-budget fine-tuning recipes, not isolated orthogonalization effects or convergence results.
- Joint blocks vary training, subset and annotation deletion seeds together; intervals do not isolate these variance sources.
- Approximate t intervals at n=3 are unstable. Cell contrasts are exploratory; no multiple-comparison claims.
- One checkpoint lineage, uncertain pretrained-image overlap, and unresolved source-image rights limit generalization.
- VOC-derived all-object mAP50-95 is not official VOC AP; validation uses a frozen 512-image sample.
- Hyperparameters selected at 10 exposure blocks and transferred to 20/60-block schedules; tuning is not convergence-based.
