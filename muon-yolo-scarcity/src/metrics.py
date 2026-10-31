"""Serialize measured runs and draw development-only comparisons."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .dataset_variants import save_json


def write_results(output: Path, rows: list[dict]):
    save_json(output / "results.json", rows)
    if not rows:
        return
    columns = sorted({key for row in rows for key in row})
    temporary = output / "results.csv.tmp"
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    temporary.replace(output / "results.csv")


def plot_results(output: Path, rows: list[dict]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    successful = [row for row in rows if row["status"] == "completed"]
    if not successful:
        return
    conditions = sorted({(r["data_fraction"], r["noise_probability"]) for r in successful})
    optimizers = sorted({r["optimizer"] for r in successful})
    colors = {"AdamW": "#2166ac", "MuSGD": "#d95f02", "SGD": "#1b9e77"}
    for key, ylabel, filename in [
        ("val_map50_95", "Clean validation mAP50–95", "validation_map.png"),
        ("training_seconds", "Training call wall time (seconds)", "training_time.png"),
    ]:
        fig, ax = plt.subplots(figsize=(max(7, len(conditions) * 1.6), 4.5))
        width = 0.75 / len(optimizers)
        for j, optimizer in enumerate(optimizers):
            for i, condition in enumerate(conditions):
                values = [r[key] for r in successful if r["optimizer"] == optimizer and
                          (r["data_fraction"], r["noise_probability"]) == condition]
                if not values:
                    continue
                x = i + (j - (len(optimizers) - 1) / 2) * width
                ax.bar(x, sum(values) / len(values), width=width, color=colors.get(optimizer),
                       label=optimizer if i == 0 else None)
                ax.scatter([x] * len(values), values, color="black", s=12, zorder=3)
        ax.set_xticks(range(len(conditions)), [f"{f:.0%} images\n{n:.0%} missing boxes" for f, n in conditions])
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.set_title("Development run — provisional learning rates; no test evaluation")
        ax.legend()
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        fig.tight_layout()
        fig.savefig(output / filename, dpi=160)
        plt.close(fig)


def read_history(path: Path):
    with path.open(encoding="utf-8") as stream:
        return [{k.strip(): float(v) for k, v in row.items()} for row in csv.DictReader(stream)]
