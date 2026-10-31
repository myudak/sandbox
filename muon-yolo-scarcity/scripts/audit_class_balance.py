"""Describe class composition for the frozen subsets and missing-box patterns."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dataset_variants import corrupt_missing_boxes, nested_subset, validate_labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--split-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.split_audit.read_text(encoding="utf-8"))
    names = {int(k): v for k, v in source["names"].items()}
    annotations = {}
    for split, records in source["records"].items():
        annotations[split] = {}
        for record in records:
            path = args.dataset_root / "labels" / split / Path(record["name"]).with_suffix(".txt")
            blob = path.read_bytes()
            if hashlib.sha256(blob).hexdigest() != record["label_sha256"]:
                raise ValueError(f"Label differs from frozen source: {path}")
            text = blob.decode("utf-8")
            validate_labels(text, len(names))
            annotations[split][record["name"]] = text
    rows = []
    for fraction in (0.05, 0.20, 1.0):
        selected = nested_subset(list(annotations["train"]), fraction, 2026)
        original = Counter()
        for image in selected:
            original.update(int(line.split()[0]) for line in annotations["train"][image].splitlines() if line.strip())
        for noise in (0, 0.20):
            retained = Counter()
            for image in selected:
                text, _ = corrupt_missing_boxes(annotations["train"][image], noise, 2027, image)
                retained.update(int(line.split()[0]) for line in text.splitlines() if line.strip())
            for cls, name in names.items():
                rows.append({"split": "train", "fraction": fraction, "images": len(selected),
                    "noise_probability": noise, "class": name, "original_objects": original[cls],
                    "retained_objects": retained[cls], "removed_objects": original[cls] - retained[cls]})
    for split in ("val", "test"):
        counts = Counter()
        for text in annotations[split].values():
            counts.update(int(line.split()[0]) for line in text.splitlines() if line.strip())
        for cls, name in names.items():
            rows.append({"split": split, "fraction": 1.0, "images": len(annotations[split]),
                "noise_probability": 0, "class": name, "original_objects": counts[cls],
                "retained_objects": counts[cls], "removed_objects": 0})
        assert sum(counts.values()) == source["counts"][split]["objects"]
    full = [r for r in rows if r["split"] == "train" and r["fraction"] == 1 and r["noise_probability"] == 0]
    assert sum(r["original_objects"] for r in full) == source["counts"]["train"]["objects"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.output.with_suffix(".json").write_text(json.dumps({"source_fingerprint": source["fingerprint"],
        "subset_seed": 2026, "corruption_seed": 2027, "rows": rows,
        "note": "Descriptive composition of this frozen subset/corruption realization; no new training"}, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
