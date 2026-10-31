"""Screen frozen cross-split images with dHash; candidates require visual review.

This diagnostic never changes split membership or training configuration.
"""
import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def dhash(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(image.tobytes())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return bits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--split-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--distance", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    audit = json.loads(args.split_audit.read_text(encoding="utf-8"))
    images = {split: [{**r, "dhash": dhash(args.dataset_root / "images" / split / r["name"])}
                      for r in records] for split, records in audit["records"].items()}
    candidates = []
    for first, second in (("train", "val"), ("train", "test"), ("val", "test")):
        for a in images[first]:
            for b in images[second]:
                distance = (a["dhash"] ^ b["dhash"]).bit_count()
                if distance <= args.distance:
                    candidates.append({"first_split": first, "first_name": a["name"],
                        "second_split": second, "second_name": b["name"], "dhash_distance": distance,
                        "exact_bytes_equal": a["image_sha256"] == b["image_sha256"]})
    candidates.sort(key=lambda r: (r["dhash_distance"], r["first_split"], r["first_name"]))
    fields = ["first_split", "first_name", "second_split", "second_name", "dhash_distance", "exact_bytes_equal"]
    with (args.output / "candidates.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)
    summary = {"source_fingerprint": audit["fingerprint"], "method": "64-bit horizontal dHash on EXIF-oriented grayscale",
        "max_hamming_distance": args.distance, "candidate_pairs": len(candidates),
        "meaning": "screening candidates, not verified duplicates; no split changes",
        "limitations": "May miss transformed/cropped scenes and flag unrelated compositions"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    shown = candidates[:12]
    if shown:
        canvas = Image.new("RGB", (800, len(shown) * 220), "white")
        draw = ImageDraw.Draw(canvas)
        for index, row in enumerate(shown):
            for column, prefix in enumerate(("first", "second")):
                path = args.dataset_root / "images" / row[f"{prefix}_split"] / row[f"{prefix}_name"]
                with Image.open(path) as image:
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    image.thumbnail((390, 190))
                x, y = column * 400, index * 220
                draw.text((x + 4, y + 4), f"{row[f'{prefix}_split']}: {row[f'{prefix}_name']}  d={row['dhash_distance']}", fill="black")
                canvas.paste(image, (x, y + 25))
        canvas.save(args.output / "candidate_contact_sheet.png")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
