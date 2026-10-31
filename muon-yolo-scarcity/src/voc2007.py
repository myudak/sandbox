"""VOC2007 official membership, explicit inclusive-coordinate conversion.

All annotated objects, including difficult objects, are retained. This produces
a controlled VOC-derived detection task, not the official VOC scoring protocol.
"""
from __future__ import annotations

import os
import math
from pathlib import Path
import shutil
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from .dataset_variants import Dataset, file_hash, save_json, validate_labels

NAMES = ["aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car", "cat", "chair", "cow",
         "diningtable", "dog", "horse", "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"]


def convert_annotation(xml: str):
    if "<!DOCTYPE" in xml.upper():
        raise ValueError("Unexpected XML document type")
    root = ET.fromstring(xml)
    width, height = int(root.findtext("size/width")), int(root.findtext("size/height"))
    if min(width, height) <= 0:
        raise ValueError("Invalid image dimensions")
    lines, clipped, difficult = [], 0, 0
    for obj in root.findall("object"):
        name = obj.findtext("name")
        if name not in NAMES:
            raise ValueError(f"Unknown VOC class: {name}")
        difficult += int(obj.findtext("difficult", "0")) == 1
        box = obj.find("bndbox")
        left, top = float(box.findtext("xmin")) - 1, float(box.findtext("ymin")) - 1
        right, bottom = float(box.findtext("xmax")), float(box.findtext("ymax"))
        if not all(math.isfinite(v) for v in (left,top,right,bottom)):
            raise ValueError("Nonfinite VOC coordinates")
        bounded = max(0, left), max(0, top), min(width, right), min(height, bottom)
        clipped += bounded != (left, top, right, bottom)
        left, top, right, bottom = bounded
        if right <= left or bottom <= top:
            raise ValueError("Degenerate VOC box")
        values = [(left + right) / (2 * width), (top + bottom) / (2 * height),
                  (right - left) / width, (bottom - top) / height]
        lines.append(str(NAMES.index(name)) + " " + " ".join(f"{v:.10f}" for v in values))
    text = "\n".join(lines) + ("\n" if lines else "")
    validate_labels(text, len(NAMES))
    return text, {"width": width, "height": height, "objects": len(lines), "difficult_included": difficult,
                  "boxes_clipped_to_image": clipped}


def prepare_voc2007(scratch: Path, evidence: Path):
    from PIL import Image
    from ultralytics.utils import ASSETS_URL
    root = scratch / "voc2007"
    root.mkdir(parents=True, exist_ok=True)
    archives = []
    for filename in ("VOCtrainval_06-Nov-2007.zip", "VOCtest_06-Nov-2007.zip"):
        path = root / filename
        url = f"{ASSETS_URL}/{filename}"
        if not path.exists():
            temporary = path.with_suffix(".zip.partial")
            print("DOWNLOAD", url, flush=True)
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(path)
        archives.append({"url": url, "filename": filename, "sha256": file_hash(path)})
        marker = root / (filename + ".extracted")
        if not marker.exists():
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    if not (root / member.filename).resolve().is_relative_to(root.resolve()):
                        raise ValueError("Unsafe archive member")
                    if (member.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError("Archive symlink is unsupported")
                archive.extractall(root)
            marker.write_text(archives[-1]["sha256"], encoding="utf-8")
    original = root / "VOCdevkit/VOC2007"
    images, reports = {}, {}
    for split in ("train", "val", "test"):
        ids = (original / f"ImageSets/Main/{split}.txt").read_text().split()
        if len(ids) != len(set(ids)):
            raise ValueError("Repeated official VOC image ID")
        images[split] = root / "converted/images" / split
        images[split].mkdir(parents=True, exist_ok=True)
        (root / "converted/labels" / split).mkdir(parents=True, exist_ok=True)
        reports[split] = {"images": len(ids), "objects": 0, "difficult_included": 0, "boxes_clipped_to_image": 0}
        for image_id in ids:
            source = original / f"JPEGImages/{image_id}.jpg"
            target = images[split] / source.name
            if not target.exists():
                try: os.link(source, target)
                except OSError: shutil.copy2(source, target)
            text, report = convert_annotation((original / f"Annotations/{image_id}.xml").read_text())
            with Image.open(source) as image:
                if image.size != (report["width"], report["height"]):
                    raise ValueError(f"VOC XML/image size mismatch: {source}")
                if image.getexif().get(274, 1) != 1:
                    raise ValueError(f"Unresolved EXIF orientation: {source}")
            label = root / "converted/labels" / split / f"{image_id}.txt"
            label.write_text(text, encoding="utf-8", newline="\n")
            for key in ("objects", "difficult_included", "boxes_clipped_to_image"):
                reports[split][key] += report[key]
    if [reports[s]["images"] for s in ("train", "val", "test")] != [2501, 2510, 4952]:
        raise ValueError("Unexpected official VOC2007 split counts")
    provenance = {"dataset": "VOC2007-derived controlled detection task", "archives": archives,
        "source": "http://host.robots.ox.ac.uk/pascal/VOC/voc2007/",
        "conversion": "one-based inclusive VOC to zero-based half-open bounds; all difficult objects included; normalized YOLO xywh",
        "evaluation": "mAP50-95 on converted all-object annotations, not official VOC AP",
        "license": "Original Flickr image rights/VOC usage terms apply; images not redistributed in source bundle",
        "split_conversion_counts": reports}
    save_json(evidence / "voc_conversion.json", provenance)
    return Dataset(images, dict(enumerate(NAMES)), provenance)
