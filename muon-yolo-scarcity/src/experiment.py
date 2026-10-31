"""Run a bounded, validation-only study with explicit optimizers and manifests."""
from __future__ import annotations

import argparse
import gc
import hashlib
import inspect
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .dataset_variants import Dataset, audit_source, build_variant, digest, disjoint_splits, file_hash, render_examples, save_json
from .metrics import plot_results, read_history, write_results

ROOT = Path(__file__).resolve().parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path):
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    parent = config.pop("extends", None)
    if parent:
        base = load_config(path.parent / parent)
        for key, value in config.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key].update(value)
            else:
                base[key] = value
        config = base
    if config["evaluation"]["split"] != "val":
        raise ValueError("Development runner only evaluates validation. Freeze a final protocol before opening test.")
    if config["noise_type"] != "missing_box":
        raise ValueError("This implementation validates missing_box only")
    if not set(config["optimizers"]).issubset({"AdamW", "MuSGD", "SGD"}):
        raise ValueError("Explicit AdamW, MuSGD, or SGD required; auto is prohibited")
    for fraction in config["fractions"]:
        if not 0 < fraction <= 1:
            raise ValueError("Invalid training fraction")
    for probability in config["noise_levels"]:
        if not 0 <= probability <= 1:
            raise ValueError("Invalid noise probability")
    if not config["training_seeds"] or len(config["training_seeds"]) != len(set(config["training_seeds"])):
        raise ValueError("Need unique training seeds")
    if config["train"]["batch"] <= 0 or config["train"]["epochs"] < 1:
        raise ValueError("Fixed positive batch and epoch budget required")
    return config


def planned_runs(config):
    return len(config["fractions"]) * len(config["noise_levels"]) * len(config["optimizers"]) * len(config["training_seeds"])


def code_fingerprint():
    return digest({p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted((ROOT / "src").glob("*.py"))})


def state_hash(model):
    h = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        array = tensor.detach().cpu().contiguous().numpy()
        h.update(name.encode())
        h.update(str(array.dtype).encode())
        h.update(str(array.shape).encode())
        h.update(array.tobytes())
    return h.hexdigest()


def optimizer_details(optimizer):
    groups = []
    for group in optimizer.param_groups:
        groups.append({"parameters": sum(p.numel() for p in group["params"]),
                       **{key: value for key, value in group.items() if key != "params" and
                          isinstance(value, (str, int, float, bool, tuple, type(None)))}})
    return {"class": type(optimizer).__name__, "groups": groups,
            "muon_factor": getattr(optimizer, "muon", None), "sgd_factor": getattr(optimizer, "sgd", None)}


def run_study(config_path: Path, output: Path, max_runs=8):
    config = load_config(config_path)
    if planned_runs(config) > max_runs:
        raise ValueError(f"Planned {planned_runs(config)} runs exceeds explicit max_runs={max_runs}")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    identity = {"config": config, "code_sha256": code_fingerprint()}
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous["identity"] != identity:
            raise ValueError("Configuration/code changed: select a new output directory to preserve previous results")
    manifest = {"identity": identity, "status": "preflight", "updated_utc": utc_now(),
                "planned_runs": planned_runs(config), "test_evaluated": False,
                "purpose": "Pipeline smoke/pilot; learning rates are provisional and untuned"}
    save_json(manifest_path, manifest)
    try:
        return _execute(config, output, manifest, manifest_path)
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}", updated_utc=utc_now())
        save_json(manifest_path, manifest)
        (output / "failure_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise


def _execute(config, output, manifest, manifest_path):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("WANDB_MODE", "disabled")
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    import torch
    import ultralytics
    from ultralytics import YOLO, settings
    from ultralytics.data.utils import check_det_dataset
    from ultralytics.engine.trainer import BaseTrainer
    from ultralytics.optim.muon import MuSGD

    settings.update({key: False for key in ("wandb", "mlflow", "comet", "tensorboard", "clearml", "neptune", "hub", "sync") if key in settings})
    if ultralytics.__version__ != str(config["ultralytics_version"]):
        raise RuntimeError(f"Expected Ultralytics {config['ultralytics_version']}, found {ultralytics.__version__}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU unavailable. Kaggle: enable GPU accelerator; no training has run.")
    hardware = {"python": sys.version, "platform": platform.platform(), "torch": torch.__version__,
                "cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
                "ultralytics": ultralytics.__version__, "gpu": torch.cuda.get_device_name(0),
                "gpu_count_visible": torch.cuda.device_count(), "device_used": config["train"]["device"],
                "gpu_total_bytes": torch.cuda.get_device_properties(0).total_memory,
                "musgd_source_sha256": file_hash(Path(inspect.getfile(MuSGD))),
                "trainer_source_sha256": file_hash(Path(inspect.getfile(BaseTrainer)))}
    manifest.update(environment=hardware, status="auditing", updated_utc=utc_now())
    save_json(manifest_path, manifest)
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True)
    (output / "environment-lock.txt").write_text(freeze.stdout, encoding="utf-8")
    dataset = Dataset.from_info(check_det_dataset(config["dataset"]))
    raw_source = audit_source(dataset, output / "source_audit.json", reject_overlap=False)
    reviewed_file = config.get("reviewed_exclusions_file")
    reviewed = json.loads((ROOT / "configs" / reviewed_file).read_text(encoding="utf-8")) if reviewed_file else None
    source = disjoint_splits(raw_source, config["split_policy"], reviewed)
    save_json(output / "split_audit.json", source)
    variants = []
    for fraction in config["fractions"]:
        for probability in config["noise_levels"]:
            path, variant = build_variant(dataset, source, output / "variants", fraction, probability,
                                          config["subset_seed"], config["corruption_seed"])
            if not variant["remaining_train_objects"]:
                raise ValueError("No training boxes remain; select a larger subset or lower corruption")
            variants.append((path, variant))
            render_examples(dataset, path.parent, variant, output / "annotation_examples" / variant["variant_id"])
    save_json(output / "variant_audit.json", [{k: v for k, v in variant.items() if k != "records"} for _, variant in variants])

    weights_dir = output / "initial_weights"
    weights_dir.mkdir(exist_ok=True)
    checkpoint = weights_dir / Path(config["checkpoint"]).name
    initial = YOLO(str(checkpoint))
    ckpt = initial.ckpt or {}
    lineage = {"checkpoint": checkpoint.name, "sha256": file_hash(checkpoint),
               "pretraining_train_args": ckpt.get("train_args", {}), "git": ckpt.get("git"),
               "source": "Official Ultralytics pretrained asset; recipe uses MuSGD",
               "note": "COCO category overlap and possible source-image overlap need discussion"}
    save_json(output / "checkpoint_lineage.json", lineage)
    del initial, ckpt
    gc.collect()
    torch.cuda.empty_cache()
    experiment_identity = {"environment": hardware, "checkpoint_sha256": lineage["sha256"],
                           "source_fingerprint": source["fingerprint"]}
    if "experiment_identity" in manifest and manifest["experiment_identity"] != experiment_identity:
        raise ValueError("Environment/checkpoint/source changed: use a new output directory")
    # The saved previous manifest also guards resuming against an environment change.
    previous_identity_file = output / "experiment_identity.json"
    if previous_identity_file.exists() and json.loads(previous_identity_file.read_text(encoding="utf-8")) != experiment_identity:
        raise ValueError("Environment/checkpoint/source changed: use a new output directory")
    save_json(previous_identity_file, experiment_identity)
    manifest.update(experiment_identity=experiment_identity, status="running", updated_utc=utc_now())
    save_json(manifest_path, manifest)
    rows_path = output / "results.json"
    rows = json.loads(rows_path.read_text(encoding="utf-8")) if rows_path.exists() else []
    # Alternate run order by condition to reduce a systematic optimizer-order confound.
    for condition_index, (data_yaml, variant) in enumerate(variants):
        optimizers = list(config["optimizers"])
        if condition_index % 2:
            optimizers.reverse()
        for seed in config["training_seeds"]:
            for optimizer in optimizers:
                spec = {"study": config, "code_sha256": manifest["identity"]["code_sha256"],
                        **experiment_identity, "variant_fingerprint": variant["fingerprint"],
                        "optimizer": optimizer, "seed": seed}
                run_id = f"{config['study']}-{optimizer}-s{seed}-{digest(spec)[:12]}"
                previous = next((r for r in rows if r["run_id"] == run_id), None)
                if previous and previous["status"] == "completed":
                    if file_hash(Path(previous["best_weights"])) != previous["best_weights_sha256"]:
                        raise ValueError(f"Completed run checkpoint changed: {run_id}")
                    print("SKIP completed", run_id, flush=True)
                    continue
                row = _train_one(YOLO, torch, config, output, data_yaml, variant, seed, optimizer, run_id, spec, rows)
                rows = [r for r in rows if r["run_id"] != run_id] + [row]
                write_results(output, rows)
                print("RESULT", json.dumps({k: row.get(k) for k in ("run_id", "status", "val_map50_95", "training_seconds", "error")}), flush=True)
    plot_results(output, rows)
    manifest.update(status="completed" if all(r["status"] == "completed" for r in rows) else "completed_with_failures",
                    completed_runs=sum(r["status"] == "completed" for r in rows), updated_utc=utc_now())
    save_json(manifest_path, manifest)
    if any(r["status"] != "completed" for r in rows):
        raise RuntimeError("One or more training runs failed; see results.csv and per-attempt tracebacks")
    return rows


def _train_one(YOLO, torch, config, output, data_yaml, variant, seed, optimizer, run_id, spec, previous_rows, deadline=None):
    run_root = output / "runs" / run_id
    attempt_number = len(list(run_root.glob("attempt-*"))) + 1
    attempt = run_root / f"attempt-{attempt_number:03d}"
    attempt.mkdir(parents=True, exist_ok=False)
    row = {"run_id": run_id, "attempt": attempt_number, "status": "running", "started_utc": utc_now(),
           "optimizer": optimizer, "seed": seed, "data_fraction": variant["config"]["fraction"],
           "noise_probability": variant["config"]["noise"], "realized_noise_rate": variant["realized_noise_rate"],
           "variant_fingerprint": variant["fingerprint"], "train_images": variant["train_images"],
           "epochs_budget": config["train"]["epochs"], "test_evaluated": False, "spec_sha256": digest(spec)}
    save_json(attempt / "run_spec.json", spec)
    save_json(attempt / "result.json", row)
    steps = {"count": 0}
    hook = None
    model = evaluator = None
    print("TRAIN", run_id, flush=True)
    start = time.perf_counter()
    call_start = start
    try:
        checkpoint = output / "initial_weights" / Path(config["checkpoint"]).name
        if file_hash(checkpoint) != spec["checkpoint_sha256"]:
            raise ValueError("Initial checkpoint changed")
        model = YOLO(str(checkpoint))

        def on_start(trainer):
            nonlocal hook
            actual_images = len(trainer.train_loader.dataset)
            if actual_images != variant["train_images"]:
                raise RuntimeError(f"Training loader retained {actual_images}/{variant['train_images']} audited images")
            if trainer.train_loader.drop_last and actual_images % trainer.train_loader.batch_size:
                raise RuntimeError("Training loader drops images; fixed exposure accounting rejected")
            row["actual_train_images"] = actual_images
            details = optimizer_details(trainer.optimizer)
            if details["class"] != optimizer:
                raise RuntimeError(f"Wrong optimizer instantiated: {details['class']}")
            row["optimizer_details"] = details
            row["initial_model_state_sha256"] = state_hash(trainer.model)
            for other in previous_rows:
                if (other["status"] == "completed" and other["seed"] == seed and
                        other["variant_fingerprint"] == variant["fingerprint"] and
                        other["initial_model_state_sha256"] != row["initial_model_state_sha256"]):
                    raise ValueError("Paired optimizers did not start from identical initialized parameters")
            def after_step(*_):
                steps["count"] += 1
            hook = trainer.optimizer.register_step_post_hook(after_step)
            save_json(attempt / "optimizer.json", details)
            save_json(attempt / "result.json", row)

        def check_batch(trainer):
            if trainer.batch_size != config["train"]["batch"]:
                raise RuntimeError("Ultralytics changed batch size after OOM; comparison rejected")

        def check_deadline(trainer):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Campaign training budget exhausted")

        model.add_callback("on_train_start", on_start)
        model.add_callback("on_train_epoch_start", check_batch)
        model.add_callback("on_train_batch_end", check_deadline)
        trainer_option = {}
        if config.get("sampling"):
            from .exposure import make_exposure_trainer
            trainer_option["trainer"] = make_exposure_trainer(config["sampling"])
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        model.train(data=str(data_yaml), **config["train"], **config["optimizers"][optimizer],
                    optimizer=optimizer, seed=seed, project=str(attempt), name="train", exist_ok=False,
                    verbose=False, resume=False, **trainer_option)
        torch.cuda.synchronize()
        row["training_seconds"] = time.perf_counter() - start
        row["training_peak_vram_bytes"] = torch.cuda.max_memory_allocated()
        row["optimizer_steps"] = steps["count"]
        trainer = model.trainer
        check_batch(trainer)
        history = read_history(Path(trainer.save_dir) / "results.csv")
        if len(history) != config["train"]["epochs"] or not all(math.isfinite(v) for r in history for v in r.values()):
            raise RuntimeError("Incomplete epoch budget or nonfinite training history")
        row["epochs_completed"] = len(history)
        row["images_seen"] = getattr(trainer, "exposure_images", variant["train_images"] * len(history))
        if config.get("sampling"):
            expected = trainer.exposure_samples_per_epoch * len(history)
            if row["images_seen"] != expected or steps["count"] != expected // config["train"]["batch"]:
                raise RuntimeError("Exposure or optimizer-step budget mismatch")
            row.update(sampling=config["sampling"], samples_per_epoch=trainer.exposure_samples_per_epoch,
                       exposure_order_sha256=trainer.exposure_hash.hexdigest())
        best_epoch = max(history, key=lambda r: r["metrics/mAP50-95(B)"])
        row["best_validation_epoch"] = int(best_epoch["epoch"])
        row["best_validation_map50_95"] = best_epoch["metrics/mAP50-95(B)"]
        best = Path(trainer.best)
        row["best_weights"] = str(best)
        row["best_weights_sha256"] = file_hash(best)
        evaluator = YOLO(str(best))
        validation_start = time.perf_counter()
        metrics = evaluator.val(data=str(data_yaml), **config["evaluation"], imgsz=config["train"]["imgsz"],
                                batch=config["train"]["batch"], device=config["train"]["device"],
                                workers=config["train"]["workers"], plots=False, verbose=False,
                                project=str(attempt), name="validation", exist_ok=False)
        row["validation_seconds"] = time.perf_counter() - validation_start
        row.update(val_map50_95=float(metrics.box.map), val_map50=float(metrics.box.map50),
                   val_precision=float(metrics.box.mp), val_recall=float(metrics.box.mr),
                   val_per_class_map50_95=[float(v) for v in metrics.box.maps],
                   lr0=config["optimizers"][optimizer]["lr0"], status="completed")
        if not all(math.isfinite(row[k]) for k in ("val_map50_95", "val_map50", "val_precision", "val_recall")):
            raise RuntimeError("Nonfinite validation metrics")
    except Exception as error:
        row.update(status="budget_exhausted" if isinstance(error, TimeoutError) else "oom" if "out of memory" in str(error).lower() else "failed",
                   error=f"{type(error).__name__}: {error}", elapsed_seconds=time.perf_counter() - start,
                   optimizer_steps=steps["count"])
        (attempt / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        if hook:
            hook.remove()
        row["finished_utc"] = utc_now()
        row["run_call_seconds"] = time.perf_counter() - call_start
        save_json(attempt / "result.json", row)
        del model, evaluator
        gc.collect()
        torch.cuda.empty_cache()
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/smoke.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/smoke")
    parser.add_argument("--max-runs", type=int, default=8)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    if args.plan:
        config = load_config(args.config)
        print(json.dumps({"planned_runs": planned_runs(config), "config": config}, indent=2))
    else:
        run_study(args.config, args.output, args.max_runs)


if __name__ == "__main__":
    main()
