"""Build a standalone notebook with an inspectable, hashed source bundle."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]


def atomic_text(path, text):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def build(profile="smoke"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        paths = sorted([*(ROOT / "src").glob("*.py"), *(ROOT / "configs").glob("*.yaml"), *(ROOT / "configs").glob("*.json"),
                        *(ROOT / "tests").glob("test_*.py"), ROOT / "requirements.txt"])
        for path in paths:
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    bundle = buffer.getvalue()
    encoded = base64.b64encode(bundle).decode()
    cells = [
        nbf.v4.new_markdown_cell(f"""# MuSGD × YOLO26: {profile} experiment log

Research question: how does the MuSGD/AdamW fine-tuning comparison change with scarce images and missing training boxes?

This notebook runs **{2 if profile == 'smoke' else 8} development runs** with provisional learning rates. It evaluates clean **validation only**. Test data are audited for integrity but never used for configuration selection or scoring here. No paper-level performance claim follows from this run.

Enable a Kaggle GPU and Internet. Source code, tests and configuration are embedded below, with a SHA-256 integrity check. Source images are downloaded from the official dataset location and are not redistributed in this notebook.

The frozen split policy preserves test, excludes exact overlaps from validation/training, and excludes 12 visually reviewed training near duplicates. All retained labels are unchanged; source membership differs from the official splits. Inspect `split_audit.json` and `configs/duplicate_exclusions.json`.
"""),
        nbf.v4.new_markdown_cell("## 1. Install the fixed training library\nKaggle's existing CUDA-compatible PyTorch is retained; the complete environment is saved after import."),
        nbf.v4.new_code_cell('%pip install -q "ultralytics==8.4.187" "PyYAML==6.0.3" "matplotlib>=3.8,<4" "Pillow>=10" "pytest>=8,<10"'),
        nbf.v4.new_markdown_cell("## 2. Restore the experiment source\nThe bundle contains src/, tests/, and configs/. Inspect the restored files before changing a study."),
        nbf.v4.new_code_cell(f'''from pathlib import Path
import base64, hashlib, io, os, sys, zipfile

WORKING = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path.cwd() / "work"
PROJECT = WORKING / "muon_yolo_project"
PROJECT.mkdir(parents=True, exist_ok=True)
bundle = base64.b64decode({encoded!r})
assert hashlib.sha256(bundle).hexdigest() == {hashlib.sha256(bundle).hexdigest()!r}
with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
    for member in archive.namelist():
        destination = (PROJECT / member).resolve()
        assert destination.is_relative_to(PROJECT.resolve())
    archive.extractall(PROJECT)
sys.path.insert(0, str(PROJECT))
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
print("Restored source:", PROJECT)
'''),
        nbf.v4.new_markdown_cell("## 3. Verify corruption and leakage safeguards\nThese tests use synthetic fixture files, not scientific training data."),
        nbf.v4.new_code_cell('''import subprocess
subprocess.run([sys.executable, "-m", "pytest", "-q", str(PROJECT / "tests")], cwd=PROJECT, check=True)
'''),
        nbf.v4.new_markdown_cell("## 4. Review the bounded run plan\nThe smoke mode uses 5% of training images, 20% per-object missing boxes, two epochs, and two explicit optimizers. Validation remains full size. All runs start from identical checkpoint bytes and the initialized parameters are checked for pairing."),
        nbf.v4.new_code_cell(f'''import json
from src.experiment import load_config, planned_runs, run_study
PROFILE = {profile!r}
CONFIG = PROJECT / "configs" / f"{{PROFILE}}.yaml"
OUTPUT = WORKING / f"muon_yolo_{{PROFILE}}"
config = load_config(CONFIG)
print(json.dumps(config, indent=2))
print("Planned runs:", planned_runs(config))
'''),
        nbf.v4.new_markdown_cell("## 5. Audit data, train, and evaluate clean validation\nOutputs include SHA-256 audits, corruption examples, checkpoint lineage, actual optimizer groups, initialized-model hashes, optimizer step counts, histories, timings, peak training VRAM and failure records. A changed code/config/environment requires a new output directory; failed runs get a new attempt directory."),
        nbf.v4.new_code_cell('rows = run_study(CONFIG, OUTPUT, max_runs=8)\n'),
        nbf.v4.new_markdown_cell("## 6. Inspect measured development results\nSingle-seed smoke scores verify plumbing. They do not rank optimizers or establish a scarcity/noise interaction."),
        nbf.v4.new_code_cell('''import pandas as pd
from IPython.display import display, Image
results = pd.read_csv(OUTPUT / "results.csv")
display(results[["optimizer", "status", "train_images", "realized_noise_rate", "val_map50_95", "training_seconds", "optimizer_steps"]])
display(Image(filename=str(OUTPUT / "validation_map.png")))
display(Image(filename=str(OUTPUT / "training_time.png")))
'''),
        nbf.v4.new_markdown_cell("## 7. Retrieve evidence and plan the paper\nDownload the notebook outputs through Kaggle or `kaggle kernels output OWNER/SLUG -p outputs/PROFILE`. Keep results.csv, manifest.json, source_audit.json, variant_audit.json, checkpoint_lineage.json, environment-lock.txt and run histories. Preserve all tried settings. Before a final paper: equal validation tuning budgets, SGD baseline, repeated paired seeds and corruption seeds, a second public dataset, and a frozen one-shot test protocol. Dataset licensing and possible pretrained-image overlap remain unresolved."),
    ]
    notebook = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}})
    nbf.validate(notebook)
    destination = ROOT / "notebooks" / f"muon_yolo_{profile}.ipynb"
    atomic_text(destination, nbf.writes(notebook))
    kaggle = ROOT / "kaggle" / profile
    kaggle.mkdir(parents=True, exist_ok=True)
    atomic_text(kaggle / destination.name, nbf.writes(notebook))
    slug = f"muon-yolo-{profile}"
    title = f"Muon YOLO {profile.title()}"
    if profile == "pilot":
        slug += "-reviewed"
        title += " Reviewed"
    atomic_text(kaggle / "kernel-metadata.json", json.dumps({
        "id": f"myudak/{slug}", "title": title,
        "code_file": destination.name, "language": "python", "kernel_type": "notebook",
        "is_private": True, "enable_gpu": True, "enable_internet": True,
        "machine_shape": "NvidiaTeslaT4", "dataset_sources": [], "competition_sources": [],
        "kernel_sources": [], "model_sources": [],
    }, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["smoke", "pilot"], default="smoke")
    build(parser.parse_args().profile)
