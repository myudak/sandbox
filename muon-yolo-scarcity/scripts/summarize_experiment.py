"""Create a measured-only experiment log and convergence figures from outputs.

Usage: python scripts/summarize_experiment.py outputs/kaggle_smoke_v2/muon_yolo_smoke
This does not select hyperparameters or open a test split.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def summarize(root: Path):
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    rows = json.loads((root / "results.json").read_text(encoding="utf-8"))
    split = json.loads((root / "split_audit.json").read_text(encoding="utf-8"))
    lineage = json.loads((root / "checkpoint_lineage.json").read_text(encoding="utf-8"))
    config = manifest["identity"]["config"]
    if len({r["run_id"] for r in rows}) != len(rows):
        raise ValueError("Repeated run IDs in results")
    successful = [r for r in rows if r["status"] == "completed"]
    if any(r.get("test_evaluated") for r in rows):
        raise ValueError("Development report received test-evaluated runs")
    if not successful:
        raise ValueError("No completed runs to summarize")
    for row in successful:
        if not all(0 <= row[key] <= 1 for key in ("val_map50_95", "val_map50", "val_precision", "val_recall")):
            raise ValueError("Accuracy metric outside its expected 0–1 range")
        if row["training_seconds"] <= 0 or row["optimizer_steps"] <= 0 or row["epochs_completed"] != row["epochs_budget"]:
            raise ValueError("Invalid timing, step count or completed epoch budget")
    pairs = []
    for adam in successful:
        if adam["optimizer"] != "AdamW":
            continue
        muon = next((r for r in successful if r["optimizer"] == "MuSGD" and r["seed"] == adam["seed"] and
                     r["variant_fingerprint"] == adam["variant_fingerprint"]), None)
        if muon is None:
            continue
        for field in ("initial_model_state_sha256", "images_seen", "optimizer_steps", "epochs_completed"):
            if adam[field] != muon[field]:
                raise ValueError(f"Pair mismatch for {field}")
        if not all(math.isfinite(r["val_map50_95"]) for r in (adam, muon)):
            raise ValueError("Nonfinite comparison")
        pairs.append({"data_fraction": adam["data_fraction"], "noise_probability": adam["noise_probability"],
                      "seed": adam["seed"], "variant_fingerprint": adam["variant_fingerprint"],
                      "adamw_validation_map50_95": adam["val_map50_95"],
                      "musgd_validation_map50_95": muon["val_map50_95"],
                      "paired_difference_ap_points": 100 * (muon["val_map50_95"] - adam["val_map50_95"]),
                      "images_seen_each": adam["images_seen"], "optimizer_steps_each": adam["optimizer_steps"]})
    (root / "paired_development_results.json").write_text(json.dumps(pairs, indent=2) + "\n", encoding="utf-8")
    if pairs:
        with (root / "paired_development_results.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
            writer.writeheader()
            writer.writerows(pairs)
    environment = manifest["environment"]
    text = [f"# {config['study'].title()} execution log", "",
            f"Evidence: `{root.as_posix()}`. Manifest status: **{manifest['status']}**.", "",
            f"Completed {len(successful)}/{manifest['planned_runs']} planned runs. Test metrics: **not evaluated**. "
            "Learning rates are provisional; all values below are development observations.", "",
            f"Hardware: {environment['gpu']}, device {environment['device_used']}; "
            f"Ultralytics {environment['ultralytics']}, torch {environment['torch']}, CUDA {environment['cuda']}.", "",
            f"Frozen split images: train={split['counts']['train']['images']}, "
            f"validation={split['counts']['val']['images']}, test={split['counts']['test']['images']}. "
            f"Policy: `{split['split_policy']}`. The official test membership is preserved.", "",
            f"Initial checkpoint SHA-256: `{lineage['sha256']}`. "
            f"Embedded pretraining optimizer: `{lineage['pretraining_train_args'].get('optimizer', 'unavailable')}`.", "",
            "| Images | Missing-box probability | Optimizer | Seed | Val mAP50–95 | Epochs | Steps | Training seconds | Peak VRAM GiB |",
            "|---:|---:|---|---:|---:|---:|---:|---:|---:|"]
    for row in sorted(successful, key=lambda r: (r["data_fraction"], r["noise_probability"], r["seed"], r["optimizer"])):
        text.append(f"| {row['train_images']} | {row['noise_probability']:.0%} | {row['optimizer']} | {row['seed']} | "
                    f"{row['val_map50_95']:.5f} | {row['epochs_completed']} | {row['optimizer_steps']} | "
                    f"{row['training_seconds']:.2f} | {row['training_peak_vram_bytes']/2**30:.3f} |")
    text += ["", "mAP is reported on the 0–1 scale. Timing includes training setup, validation and final validation. "
             "Execution order and cold-start overhead can affect these measurements; these are not matched-time or kernel benchmarks.", "",
             "## Paired descriptive comparisons", "",
             "| Train fraction | Missing-box probability | Seed | MuSGD − AdamW (AP points) |",
             "|---:|---:|---:|---:|"]
    for pair in pairs:
        text.append(f"| {pair['data_fraction']:.0%} | {pair['noise_probability']:.0%} | {pair['seed']} | "
                    f"{pair['paired_difference_ap_points']:+.3f} |")
    text += ["", "Pairing checks verified identical initialized parameter hashes, exposure, steps and epochs. "
             "A one-seed comparison has no estimated between-seed uncertainty and does not establish optimizer superiority. "
             "Recipe-specific LR multipliers and the untuned learning rates prevent an algorithm-isolation claim.", "",
             "## Validation trajectories", "", "![Validation trajectories](validation_trajectories.png)", "",
             "The trajectories use per-epoch training validation, which can differ slightly from the independent FP32 "
             "validation of a saved best checkpoint reported above. Preserve both and document the evaluation precision.", "",
             "Warmup is version-specific: in the pinned trainer, a positive warmup duration has a 100-iteration minimum. "
             "Thus nominal three-epoch warmup can occupy more epochs on a scarce subset. The logged LR curves reveal the "
             "actual schedule. Freeze an exposure-based warmup policy for a final interaction study.", "",
             "## Failures", ""]
    failures = [r for r in rows if r["status"] != "completed"]
    text += [f"- `{r['run_id']}`: {r['status']} — {r.get('error', 'see run artifacts')}" for r in failures] or ["No failed rows in this output."]
    (root / "EXECUTION_LOG.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    draw_trajectories(root, successful)
    print(root / "EXECUTION_LOG.md")


def draw_trajectories(root: Path, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conditions = sorted({(r["data_fraction"], r["noise_probability"]) for r in rows})
    columns = min(2, len(conditions))
    count_rows = math.ceil(len(conditions) / columns)
    colors = {"AdamW": "#2166ac", "MuSGD": "#d95f02", "SGD": "#1b9e77"}
    styles = {"AdamW": "-", "MuSGD": "--", "SGD": ":"}
    for variable, ylabel, filename in [
        ("metrics/mAP50-95(B)", "Clean validation mAP50–95", "validation_trajectories.png"),
        ("lr/pg0", "LR of first optimizer group", "learning_rate_trajectories.png"),
        ("train/box_loss", "Training box loss", "training_box_loss.png"),
        ("train/cls_loss", "Training classification loss", "training_classification_loss.png"),
        ("val/cls_loss", "Clean validation classification loss", "validation_classification_loss.png"),
    ]:
        fig, axes = plt.subplots(count_rows, columns, figsize=(6 * columns, 3.6 * count_rows), squeeze=False,
                                 sharex=True, sharey=True)
        for ax, condition in zip(axes.flat, conditions):
            for row in rows:
                if (row["data_fraction"], row["noise_probability"]) != condition:
                    continue
                path = root / "runs" / row["run_id"] / f"attempt-{row['attempt']:03d}" / "train/results.csv"
                with path.open(encoding="utf-8") as stream:
                    history = [{k.strip(): float(v) for k, v in r.items()} for r in csv.DictReader(stream)]
                ax.plot([r["epoch"] for r in history], [r[variable] for r in history],
                        color=colors[row["optimizer"]], linestyle=styles[row["optimizer"]],
                        marker="o" if len(history) <= 3 else None, label=f"{row['optimizer']} seed {row['seed']}")
            ax.set_title(f"{condition[0]:.0%} training images · {condition[1]:.0%} missing boxes")
            ax.set_xlabel("Epoch")
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.2)
            ax.legend(fontsize=9)
        for ax in list(axes.flat)[len(conditions):]:
            ax.set_visible(False)
        # Set the shared range only after every series has been added.
        upper = max((max(line.get_ydata()) for ax in axes.flat for line in ax.lines), default=0) * 1.08
        for ax in axes.flat:
            ax.set_ylim(0, upper or 1)
        fig.suptitle("Development trajectories — untuned settings; no test evaluation", fontsize=13)
        fig.tight_layout()
        fig.savefig(root / filename, dpi=160)
        fig.savefig((root / filename).with_suffix(".svg"))
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    summarize(parser.parse_args().output)
