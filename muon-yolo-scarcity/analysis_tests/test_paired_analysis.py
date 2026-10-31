"""Artificial algebra fixtures, not experimental results."""
import copy

import pytest

from scripts.paired_analysis import analyze


def grid(seeds=(1,)):
    rows = []
    for seed in seeds:
        for fraction in (0.2, 1.0):
            for noise in (0.0, 0.2):
                scarce, noisy = fraction == 0.2, noise == 0.2
                for optimizer in ("AdamW", "MuSGD"):
                    score = 0.2
                    if optimizer == "MuSGD":
                        score += 0.03 + 0.04 * scarce + 0.02 * noisy + 0.01 * seed * scarce * noisy
                    rows.append({"optimizer": optimizer, "data_fraction": fraction, "noise_probability": noise,
                        "seed": seed, "status": "completed", "val_map50_95": score,
                        "variant_fingerprint": f"{fraction}-{noise}", "initial_model_state_sha256": f"seed-{seed}",
                        "images_seen": 100, "optimizer_steps": 10, "epochs_completed": 2})
    return rows


def test_three_way_contrast_and_training_seed_sd():
    result = analyze(grid((1, 2, 3)))
    assert [r["optimizer_scarcity_noise_interaction_ap_points"] for r in result["per_seed"]] == pytest.approx([1, 2, 3])
    assert result["mean_interaction_ap_points"] == pytest.approx(2)
    assert result["seed_sd_ap_points"] == pytest.approx(1)
    assert result["confidence_interval"] is None


def test_single_seed_has_no_uncertainty_estimate():
    result = analyze(grid())
    assert result["training_seeds"] == 1
    assert result["seed_sd_ap_points"] is None
    assert result["confidence_interval"] is None


def test_incomplete_or_failed_seed_is_not_silently_dropped():
    rows = grid()
    with pytest.raises(ValueError, match="Incomplete"):
        analyze(rows[:-1])
    rows[-1]["status"] = "failed"
    with pytest.raises(ValueError, match="failed/unfinished"):
        analyze(rows)


def test_tuning_duplicates_and_unpaired_initialization_rejected():
    rows = grid()
    with pytest.raises(ValueError, match="Multiple runs"):
        analyze(rows + [copy.deepcopy(rows[0])])
    rows[1]["initial_model_state_sha256"] = "different"
    with pytest.raises(ValueError, match="Unpaired"):
        analyze(rows)
