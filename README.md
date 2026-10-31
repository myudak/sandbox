# sandbox monorepo
for sandbox,, soo experiments etc,, inside is multiple disconnected projects

## Projects

- [`spar-dynamics-lab/`](spar-dynamics-lab/): interactive SPAR floating wind turbine simulation with a rotary tuned mass damper (Vite + React + three.js). Asks when the damper helps and when it hurts.
- [`chatdna/`](chatdna/): local experiments in LLM fine-tuning with LoRA and building a decoder-only GPT from scratch in PyTorch. Includes data preparation, training, evaluation, a sentence finisher, and learning notes fromm my own whatsapp dataset
- [`muon-yolo-scarcity/`](muon-yolo-scarcity/): research manuscript, reproducible code, numeric experiment evidence, and interactive results for MuSGD–YOLO26 fine-tuning under image scarcity and missing annotations.

## Research

### Separating Training Exposure from Data Scarcity in MuSGD–YOLO Fine-Tuning under Missing Annotations

**Muchammad Yuda Tri Ananda · Research manuscript · 2026**

Compares existing MuSGD, AdamW, and momentum-SGD recipes while matching image exposure and optimizer updates. Includes 120 training trials, 60 frozen-checkpoint test evaluations, and three paired joint blocks across African Wildlife and a VOC2007-derived task. Results show dataset-dependent recipe behavior; the primary scarcity × missingness interaction remains unresolved.

[Paper (PDF)](muon-yolo-scarcity/output/pdf/muon_yolo_scarcity.pdf) · [Source & reproducibility](muon-yolo-scarcity/) · [Interactive Kaggle results](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=364100382)
