"""Balanced paired optimizer contrasts; no significance claims from pilot seeds."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def analyze(rows, small=0.2, full=1.0, clean=0.0, noisy=0.2, left="MuSGD", right="AdamW"):
    cells = [(small, clean), (small, noisy), (full, clean), (full, noisy)]
    if len(set(cells)) != 4:
        raise ValueError("Need distinct scarcity and noise levels")
    selected = [r for r in rows if r["optimizer"] in {left, right} and
                (r["data_fraction"], r["noise_probability"]) in cells]
    if not selected or any(r["status"] != "completed" for r in selected):
        raise ValueError("No complete balanced study, or failed/unfinished runs in selected grid")
    index = {}
    for row in selected:
        key = (row["seed"], row["data_fraction"], row["noise_probability"], row["optimizer"])
        if key in index:
            raise ValueError("Multiple runs for one cell: freeze configurations before analysis")
        if not math.isfinite(row["val_map50_95"]) or not 0 <= row["val_map50_95"] <= 1:
            raise ValueError("Invalid accuracy metric")
        index[key] = row
    per_seed, paired_cells = [], []
    for seed in sorted({r["seed"] for r in selected}):
        differences = {}
        for fraction, noise in cells:
            try:
                a = index[seed, fraction, noise, left]
                b = index[seed, fraction, noise, right]
            except KeyError as error:
                raise ValueError(f"Incomplete seed block: {seed}") from error
            for field in ("variant_fingerprint", "initial_model_state_sha256", "images_seen", "optimizer_steps", "epochs_completed"):
                if a[field] != b[field]:
                    raise ValueError(f"Unpaired {field} in seed {seed}")
            difference = a["val_map50_95"] - b["val_map50_95"]
            differences[fraction, noise] = difference
            paired_cells.append({"seed": seed, "fraction": fraction, "noise": noise,
                                 "left_map": a["val_map50_95"], "right_map": b["val_map50_95"],
                                 "left_minus_right_ap_points": 100 * difference})
        noise_effect_small = differences[small, noisy] - differences[small, clean]
        noise_effect_full = differences[full, noisy] - differences[full, clean]
        per_seed.append({"seed": seed, "noise_interaction_small_ap_points": 100 * noise_effect_small,
                         "noise_interaction_full_ap_points": 100 * noise_effect_full,
                         "optimizer_scarcity_noise_interaction_ap_points": 100 * (noise_effect_small - noise_effect_full)})
    estimates = [r["optimizer_scarcity_noise_interaction_ap_points"] for r in per_seed]
    return {"status": "descriptive_development_analysis", "left_optimizer": left, "right_optimizer": right,
            "fractions": [small, full], "noise_levels": [clean, noisy], "training_seeds": len(per_seed),
            "definition": "[(left-right)small,noisy - (left-right)small,clean] - [(left-right)full,noisy - (left-right)full,clean]",
            "units": "AP points (100 times the difference on the 0–1 mAP scale)",
            "paired_cells": paired_cells, "per_seed": per_seed,
            "mean_interaction_ap_points": statistics.mean(estimates),
            "seed_sd_ap_points": statistics.stdev(estimates) if len(estimates) > 1 else None,
            "confidence_interval": None,
            "uncertainty_note": "No confidence interval or significance test in this development helper. Seed SD is not a confidence interval. A frozen confirmatory analysis is still required.",
            "scope": "Conditional on the fixed subset, corruption realization, checkpoint, recipes and development horizon; no test access"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--left", default="MuSGD")
    parser.add_argument("--right", default="AdamW")
    args = parser.parse_args()
    result = analyze(json.loads(args.results.read_text(encoding="utf-8")), left=args.left, right=args.right)
    result["input_results_sha256"] = hashlib.sha256(args.results.read_bytes()).hexdigest()
    output = args.output or args.results.with_name("paired_interactions.json")
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
