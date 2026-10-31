from pathlib import Path

import pytest

from src.dataset_variants import (
    Dataset, audit_source, build_variant, corrupt_missing_boxes, disjoint_splits, file_hash,
    label_for_image, nested_subset, validate_labels,
)


@pytest.fixture
def source_dataset(tmp_path):
    images = {}
    for split, count in (("train", 10), ("val", 2), ("test", 2)):
        folder = tmp_path / "source" / "images" / split
        folder.mkdir(parents=True)
        images[split] = folder
        for index in range(count):
            image = folder / f"nested_{index % 2}" / f"image_{index}.jpg"
            image.parent.mkdir(exist_ok=True)
            image.write_bytes(f"unique image bytes {split} {index}".encode())
            label = label_for_image(image)
            label.parent.mkdir(parents=True, exist_ok=True)
            label.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n", encoding="utf-8")
    dataset = Dataset(images, {0: "a", 1: "b"}, {"dataset": "synthetic unit test only"})
    audit = audit_source(dataset, tmp_path / "audit.json")
    return dataset, audit


def test_subsets_are_nested_and_independent_of_input_order():
    names = [f"image_{i}.jpg" for i in range(101)]
    small = nested_subset(names, 0.2, 123)
    assert len(small) == 21
    assert set(small) < set(nested_subset(names, 0.5, 123))
    assert small == nested_subset(list(reversed(names)), 0.2, 123)
    assert small != nested_subset(names, 0.2, 124)


@pytest.mark.parametrize("fraction", [0, -0.1, 1.1])
def test_invalid_fraction_rejected(fraction):
    with pytest.raises(ValueError):
        nested_subset(["a"], fraction, 0)


def test_noise_endpoints_and_empty_negative():
    text = "0 0.5 0.5 0.2 0.2\r\n1 0.4 0.4 0.1 0.1\r\n"
    assert corrupt_missing_boxes(text, 0, 9, "a")[0] == text
    assert corrupt_missing_boxes(text, 1, 9, "a")[0] == ""
    assert corrupt_missing_boxes("", 0.2, 9, "a") == ("", [])


def test_noise_is_per_object_reproducible_and_nested():
    text = "0 0.5 0.5 0.2 0.2\n" * 10000
    low = corrupt_missing_boxes(text, 0.2, 2027, "a.jpg")
    assert low == corrupt_missing_boxes(text, 0.2, 2027, "a.jpg")
    high = corrupt_missing_boxes(text, 0.4, 2027, "a.jpg")
    low_removed = {e["object_index"] for e in low[1] if e["removed"]}
    high_removed = {e["object_index"] for e in high[1] if e["removed"]}
    assert low_removed < high_removed
    assert 0.18 < len(low_removed) / 10000 < 0.22


@pytest.mark.parametrize("line", ["0 nan .5 .2 .2", "2 .5 .5 .2 .2", "0 .1 .5 .8 .2",
                                  "0 .5 .5 0 .2", "0.5 .5 .5 .2 .2", "0 .5 .5"])
def test_invalid_labels_rejected(line):
    with pytest.raises(ValueError):
        validate_labels(line, 2)


def test_empty_label_is_valid():
    assert validate_labels("\n", 2) == []


def test_variants_preserve_clean_data_and_object_denominators(source_dataset, tmp_path):
    dataset, source = source_dataset
    path, variant = build_variant(dataset, source, tmp_path / "variants", 0.2, 1, 5, 6)
    assert variant["train_images"] == 2
    assert variant["original_train_objects"] == 4
    assert variant["removed_objects"] == 4
    assert variant["realized_noise_rate"] == 1
    assert variant["empty_train_labels"] == 2
    for split in ("val", "test"):
        assert variant["records"][split] == source["records"][split]
        for row in source["records"][split]:
            label = path.parent / "labels" / split / Path(row["name"]).with_suffix(".txt")
            assert file_hash(label) == row["label_sha256"]
    # Original annotations are still intact after all training boxes were removed.
    assert all(file_hash(label_for_image(dataset.images["train"] / r["name"])) == r["label_sha256"]
               for r in source["records"]["train"])


def test_changed_seed_has_different_identity_and_reuse_detects_tampering(source_dataset, tmp_path):
    dataset, source = source_dataset
    first, manifest = build_variant(dataset, source, tmp_path / "variants", 0.5, 0.2, 5, 6)
    second, _ = build_variant(dataset, source, tmp_path / "variants", 0.5, 0.2, 5, 7)
    assert first != second
    assert build_variant(dataset, source, tmp_path / "variants", 0.5, 0.2, 5, 6)[1] == manifest
    label = next((first.parent / "labels/val").rglob("*.txt"))
    label.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="content changed"):
        build_variant(dataset, source, tmp_path / "variants", 0.5, 0.2, 5, 6)


def test_shared_images_receive_identical_noise_across_fractions(source_dataset, tmp_path):
    dataset, source = source_dataset
    _, small = build_variant(dataset, source, tmp_path / "variants", 0.2, 0.3, 5, 6)
    _, large = build_variant(dataset, source, tmp_path / "variants", 1, 0.3, 5, 6)
    large_labels = {r["name"]: r["label_sha256"] for r in large["records"]["train"]}
    assert all(large_labels[r["name"]] == r["label_sha256"] for r in small["records"]["train"])


def test_source_leakage_is_reported_and_rejected(source_dataset, tmp_path):
    dataset, _ = source_dataset
    first = next(dataset.images["train"].rglob("*.jpg"))
    second = next(dataset.images["test"].rglob("*.jpg"))
    second.write_bytes(first.read_bytes())
    report = tmp_path / "leakage.json"
    with pytest.raises(ValueError, match="leakage"):
        audit_source(dataset, report)
    assert report.is_file()


def test_missing_label_is_not_silently_treated_as_negative(source_dataset, tmp_path):
    dataset, _ = source_dataset
    image = next(dataset.images["train"].rglob("*.jpg"))
    label_for_image(image).unlink()
    with pytest.raises(FileNotFoundError):
        audit_source(dataset, tmp_path / "missing.json")


def test_holdout_priority_preserves_test_and_all_retained_labels(source_dataset, tmp_path):
    dataset, _ = source_dataset
    train = sorted(dataset.images["train"].rglob("*.jpg"))
    val = sorted(dataset.images["val"].rglob("*.jpg"))
    test = sorted(dataset.images["test"].rglob("*.jpg"))
    train[0].write_bytes(val[0].read_bytes())
    val[1].write_bytes(test[0].read_bytes())
    train[1].write_bytes(test[0].read_bytes())
    raw = audit_source(dataset, tmp_path / "raw.json", reject_overlap=False)
    clean = disjoint_splits(raw, "holdout_priority_v1")
    assert clean["records"]["test"] == raw["records"]["test"]
    assert clean["counts"]["train"]["images"] == 8
    assert clean["counts"]["val"]["images"] == 1
    assert len(clean["excluded"]) == 3
    sets = [{r["image_sha256"] for r in clean["records"][s]} for s in ("train", "val", "test")]
    assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
    for split in ("train", "val", "test"):
        original = {r["name"]: r for r in raw["records"][split]}
        assert all(original[r["name"]] == r for r in clean["records"][split])
    assert clean["fingerprint"] != raw["fingerprint"]


def test_reviewed_exclusions_are_hash_bound_and_preserve_held_out(source_dataset):
    _, source = source_dataset
    row = source["records"]["train"][0]
    peer = source["records"]["val"][0]
    review = {"original_source_fingerprint": source["fingerprint"], "exclusions": [
        {"split": "train", "name": row["name"], "image_sha256": row["image_sha256"],
         "peer_split": "val", "peer_name": peer["name"], "peer_sha256": peer["image_sha256"]}]}
    cleaned = disjoint_splits(source, "holdout_priority_reviewed_v2", review)
    assert cleaned["counts"]["train"]["images"] == 9
    assert cleaned["records"]["val"] == source["records"]["val"]
    assert cleaned["records"]["test"] == source["records"]["test"]
    review["exclusions"][0]["image_sha256"] = "wrong"
    with pytest.raises(ValueError, match="content mismatch"):
        disjoint_splits(source, "holdout_priority_reviewed_v2", review)
