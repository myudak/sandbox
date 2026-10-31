"""Deterministic subsets, per-object missing labels, and content-hash audits.

No Ultralytics/torch import is needed for testing this module. The initial
benchmark deliberately implements only missing-box noise.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

SCHEMA = 1
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
SPLITS = ("train", "val", "test")


def digest(value) -> str:
    def normalize(item):
        if isinstance(item, dict):
            result = {str(k): normalize(v) for k, v in item.items()}
            if len(result) != len(item):
                raise ValueError("Ambiguous canonical JSON keys")
            return result
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        return item
    return hashlib.sha256(json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def label_for_image(image: Path) -> Path:
    parts = list(image.parts)
    indices = [i for i, part in enumerate(parts) if part == "images"]
    if not indices:
        raise ValueError(f"Cannot map image to label: expected an images directory: {image}")
    parts[indices[-1]] = "labels"
    return Path(*parts).with_suffix(".txt")


def validate_labels(text: str, class_count: int, context="") -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        values = line.split()
        if len(values) != 5:
            raise ValueError(f"Expected class cx cy w h at {context}: {line!r}")
        cls, cx, cy, width, height = map(float, values)
        if not all(math.isfinite(v) for v in (cls, cx, cy, width, height)):
            raise ValueError(f"Nonfinite label at {context}")
        if not cls.is_integer() or not 0 <= cls < class_count:
            raise ValueError(f"Invalid class at {context}: {cls}")
        if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"Invalid normalized box at {context}: {line}")
        if min(cx - width / 2, cy - height / 2) < -1e-5 or max(cx + width / 2, cy + height / 2) > 1 + 1e-5:
            raise ValueError(f"Box exceeds image boundaries at {context}: {line}")
    return lines


def nested_subset(names: list[str], fraction: float, seed: int) -> list[str]:
    if not 0 < fraction <= 1 or len(names) != len(set(names)) or not names:
        raise ValueError("Need unique, nonempty image names and 0 < fraction <= 1")
    ordering = sorted(names, key=lambda name: (digest(["subset", seed, name]), name))
    return sorted(ordering[:max(1, math.ceil(len(names) * fraction))])


def corrupt_missing_boxes(text: str, probability: float, seed: int, image_name: str):
    if not 0 <= probability <= 1:
        raise ValueError("Noise probability must be in [0, 1]")
    kept, events = [], []
    for index, line in enumerate(line for line in text.splitlines() if line.strip()):
        # Separate random score for each object: nested across probabilities,
        # invariant to image iteration order and selected subset size.
        score = int(digest(["missing_box", seed, image_name, index]), 16) / 2**256
        removed = score < probability
        events.append({"object_index": index, "original": line.strip(), "removed": removed})
        if not removed:
            kept.append(line.strip())
    result = text if probability == 0 else "\n".join(kept) + ("\n" if kept else "")
    return result, events


@dataclass
class Dataset:
    images: dict[str, Path]
    names: dict[int, str]
    provenance: dict

    @classmethod
    def from_info(cls, info: dict):
        images = {}
        for split in SPLITS:
            value = info.get(split)
            if not isinstance(value, (str, Path)) or not Path(value).is_dir():
                raise ValueError(f"Expected one image directory for {split}, got {value!r}")
            images[split] = Path(value).resolve()
        names = info["names"]
        names = dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
        if sorted(names) != list(range(len(names))):
            raise ValueError("Class IDs must be contiguous from zero")
        return cls(images, names, {
            "dataset": "Ultralytics African Wildlife",
            "documentation": "https://docs.ultralytics.com/datasets/detect/african-wildlife/",
            "download": "https://github.com/ultralytics/assets/releases/download/v0.0.0/african-wildlife.zip",
            "license": "Unspecified in dataset documentation; do not redistribute source images",
        })


def audit_source(dataset: Dataset, report_path: Path, reject_overlap=True) -> dict:
    records, seen, cross_split_duplicates = {}, {}, []
    for split, folder in dataset.images.items():
        records[split] = []
        images = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
        if not images:
            raise ValueError(f"Empty source split: {split}")
        labels_seen = set()
        for image in images:
            label = label_for_image(image)
            if label in labels_seen:
                raise ValueError(f"Multiple image extensions share a label: {label}")
            labels_seen.add(label)
            if not label.is_file():
                raise FileNotFoundError(f"Missing source label (empty files are allowed): {label}")
            lines = validate_labels(label.read_text(encoding="utf-8"), len(dataset.names), str(label))
            record = {"name": image.relative_to(folder).as_posix(), "image_sha256": file_hash(image),
                      "label_sha256": file_hash(label), "objects": len(lines)}
            records[split].append(record)
            prior = seen.get(record["image_sha256"])
            if prior and prior[0] != split:
                cross_split_duplicates.append({"first": prior, "second": [split, record["name"]]})
            seen.setdefault(record["image_sha256"], [split, record["name"]])
    identity = {"schema": SCHEMA, "names": dataset.names, "records": records}
    report = {**identity, "fingerprint": digest(identity), "provenance": dataset.provenance,
              "counts": {split: {"images": len(rows), "objects": sum(r["objects"] for r in rows),
                                  "empty_labels": sum(r["objects"] == 0 for r in rows)} for split, rows in records.items()},
              "cross_split_exact_duplicates": cross_split_duplicates,
              "near_duplicate_audit": "not performed; exact byte hashes cannot exclude related scenes"}
    save_json(report_path, report)
    if cross_split_duplicates and reject_overlap:
        raise ValueError(f"Exact image leakage across official splits; see {report_path}")
    return report


def disjoint_splits(source: dict, policy: str, reviewed: dict | None = None) -> dict:
    """Keep test intact; exclude overlapping val, then overlapping train images.

    This changes split membership before any training or metric inspection.
    Original files/labels are untouched and every exclusion is recorded.
    """
    if policy not in {"holdout_priority_v1", "holdout_priority_reviewed_v2"}:
        raise ValueError(f"Unknown split policy: {policy}")
    records = {"test": source["records"]["test"], "val": [], "train": []}
    held_out = {r["image_sha256"] for r in records["test"]}
    excluded = []
    for split in ("val", "train"):
        higher_priority = set(held_out)
        for row in source["records"][split]:
            if row["image_sha256"] in higher_priority:
                excluded.append({"split": split, **row, "reason": "exact image also in higher-priority held-out split"})
            else:
                records[split].append(row)
        held_out.update(r["image_sha256"] for r in records[split])
    records = {split: records[split] for split in SPLITS}
    if policy == "holdout_priority_reviewed_v2":
        if not reviewed or reviewed["original_source_fingerprint"] != source["fingerprint"]:
            raise ValueError("Reviewed exclusions do not match the exact source fingerprint")
        for exclusion in reviewed["exclusions"]:
            split, name = exclusion["split"], exclusion["name"]
            if split != "train":
                raise ValueError("Reviewed v2 only excludes training images")
            row = next((r for r in records[split] if r["name"] == name), None)
            peer = next((r for r in records[exclusion["peer_split"]] if r["name"] == exclusion["peer_name"]), None)
            if not row or not peer or row["image_sha256"] != exclusion["image_sha256"] or peer["image_sha256"] != exclusion["peer_sha256"]:
                raise ValueError("Reviewed exclusion/peer content mismatch")
            records[split] = [r for r in records[split] if r["name"] != name]
            excluded.append({"split": split, **row, "reason": "visually reviewed cross-split near duplicate",
                             "peer_split": exclusion["peer_split"], "peer_name": exclusion["peer_name"]})
    if any(not records[split] for split in SPLITS):
        raise ValueError("Split cleaning left an empty split")
    identity = {"schema": SCHEMA, "names": source["names"], "records": records,
                "original_source_fingerprint": source["fingerprint"], "split_policy": policy}
    if reviewed:
        identity["reviewed_exclusions_sha256"] = digest(reviewed)
    return {**identity, "fingerprint": digest(identity), "provenance": source["provenance"],
            "excluded": excluded,
            "counts": {split: {"images": len(rows), "objects": sum(r["objects"] for r in rows),
                                "empty_labels": sum(r["objects"] == 0 for r in rows)} for split, rows in records.items()},
            "within_split_duplicate_policy": "retained; cross-split exclusions follow the recorded policy",
            "test_membership_unchanged": records["test"] == source["records"]["test"],
            "retained_label_bytes_unchanged": True,
            "near_duplicate_audit": ("12 source-bound training exclusions from dHash <=3 screening and visual review; "
                                     "not an exhaustive scene audit" if reviewed else source["near_duplicate_audit"])}


def _link_image(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def verify_variant(root: Path, manifest: dict, dataset: Dataset, source: dict):
    expected_files = set()
    for split, rows in manifest["records"].items():
        for row in rows:
            image = root / "images" / split / row["name"]
            label = root / "labels" / split / Path(row["name"]).with_suffix(".txt")
            expected_files.add(image.relative_to(root).as_posix())
            expected_files.add(label.relative_to(root).as_posix())
            if file_hash(image) != row["image_sha256"] or file_hash(label) != row["label_sha256"]:
                raise ValueError(f"Variant content changed: {image}")
            validate_labels(label.read_text(encoding="utf-8"), len(dataset.names), str(label))
        if split != "train" and rows != source["records"][split]:
            raise ValueError(f"Held-out split changed: {split}")
    actual_files = {p.relative_to(root).as_posix() for base in (root / "images", root / "labels")
                    for p in base.rglob("*") if p.is_file() and p.suffix.lower() != ".cache"}
    if actual_files != expected_files:
        raise ValueError("Unexpected or missing files in variant")


def build_variant(dataset: Dataset, source: dict, output: Path, fraction: float,
                  noise: float, subset_seed: int, corruption_seed: int):
    config = {"schema": SCHEMA, "source_fingerprint": source["fingerprint"], "fraction": fraction,
              "noise": noise, "noise_type": "missing_box", "subset_seed": subset_seed,
              "corruption_seed": corruption_seed}
    variant_id = digest(config)[:16]
    root = output / variant_id
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["config"] != config or manifest["fingerprint"] != digest({"config": config, "records": manifest["records"]}):
            raise ValueError("Variant manifest identity mismatch")
        verify_variant(root, manifest, dataset, source)
        return root / "data.yaml", manifest
    if root.exists():
        raise FileExistsError(f"Incomplete variant: {root}; preserve it for inspection and use a new output directory")
    selected = set(nested_subset([r["name"] for r in source["records"]["train"]], fraction, subset_seed))
    records, events, original_count, removed_count = {}, [], 0, 0
    for split in SPLITS:
        records[split] = []
        for original in source["records"][split]:
            name = original["name"]
            if split == "train" and name not in selected:
                continue
            source_image = dataset.images[split] / name
            source_label = label_for_image(source_image)
            target_image = root / "images" / split / name
            target_label = root / "labels" / split / Path(name).with_suffix(".txt")
            _link_image(source_image, target_image)
            target_label.parent.mkdir(parents=True, exist_ok=True)
            if split == "train" and noise > 0:
                text, image_events = corrupt_missing_boxes(source_label.read_text(encoding="utf-8"), noise, corruption_seed, name)
                target_label.write_text(text, encoding="utf-8", newline="\n")
                events.extend({"image": name, **e} for e in image_events)
                removed_count += sum(e["removed"] for e in image_events)
            else:
                shutil.copy2(source_label, target_label)
            if split == "train":
                original_count += original["objects"]
            lines = validate_labels(target_label.read_text(encoding="utf-8"), len(dataset.names), str(target_label))
            records[split].append({**original, "label_sha256": file_hash(target_label), "objects": len(lines)})
    manifest = {"variant_id": variant_id, "config": config, "records": records,
                "fingerprint": digest({"config": config, "records": records}),
                "train_images": len(records["train"]), "original_train_objects": original_count,
                "removed_objects": removed_count, "realized_noise_rate": removed_count / original_count if original_count else 0,
                "remaining_train_objects": sum(r["objects"] for r in records["train"]),
                "empty_train_labels": sum(r["objects"] == 0 for r in records["train"]),
                "clean_val_and_test_byte_identical_to_frozen_splits": True}
    (root / "data.yaml").write_text(yaml.safe_dump({"path": root.resolve().as_posix(),
        "train": "images/train", "val": "images/val", "test": "images/test", "names": dataset.names}, sort_keys=False), encoding="utf-8")
    save_json(root / "corruption.json", events)
    verify_variant(root, manifest, dataset, source)
    save_json(manifest_path, manifest)
    return root / "data.yaml", manifest


def render_examples(dataset: Dataset, root: Path, manifest: dict, output: Path, limit=3):
    """Side-by-side source/noisy training labels; never sample held-out data."""
    from PIL import Image, ImageDraw
    output.mkdir(parents=True, exist_ok=True)
    rows = sorted(manifest["records"]["train"], key=lambda row: (row["label_sha256"] ==
                  file_hash(label_for_image(dataset.images["train"] / row["name"])), row["name"]))
    for index, row in enumerate(rows[:limit]):
        original_image = dataset.images["train"] / row["name"]
        with Image.open(original_image) as image:
            image = image.convert("RGB")
            image.thumbnail((560, 420))
        canvas = Image.new("RGB", (image.width * 2, image.height + 28), "white")
        for column, label in enumerate([label_for_image(original_image), root / "labels/train" / Path(row["name"]).with_suffix(".txt")]):
            panel = image.copy()
            draw = ImageDraw.Draw(panel)
            for line in validate_labels(label.read_text(encoding="utf-8"), len(dataset.names)):
                cls, cx, cy, width, height = map(float, line.split())
                box = [(cx-width/2)*image.width, (cy-height/2)*image.height,
                       (cx+width/2)*image.width, (cy+height/2)*image.height]
                draw.rectangle(box, outline=(20, 200, 100), width=2)
                draw.text((box[0], box[1]), dataset.names[int(cls)], fill="yellow")
            canvas.paste(panel, (column * image.width, 28))
        draw = ImageDraw.Draw(canvas)
        draw.text((5, 6), "Original training annotation", fill="black")
        draw.text((image.width + 5, 6), "Training annotation after missing-box noise", fill="black")
        canvas.save(output / f"example_{index:02d}.png")
