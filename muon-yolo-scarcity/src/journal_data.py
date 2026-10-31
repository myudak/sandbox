"""Scratch-only images, frozen held-out references, compact provenance artifacts."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile

import yaml

from .dataset_variants import (Dataset, SPLITS, audit_source, corrupt_missing_boxes, digest,
    disjoint_splits, file_hash, label_for_image, nested_subset, save_json, validate_labels)
from .voc2007 import prepare_voc2007


def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists(): return
    try: os.link(source, target)
    except OSError: shutil.copy2(source, target)


def apply_review(records, raw_fingerprint, base_fingerprint, review):
    if review['schema']!='journal-reviewed-exclusions-v1' or review['raw_source_fingerprint']!=raw_fingerprint or review['base_fingerprint']!=base_fingerprint:
        raise ValueError('Journal visual review does not match source identity')
    result={split:list(rows) for split,rows in records.items()};excluded=[]
    for item in review['exclusions']:
        if item['split']!='train' or item['peer_split'] not in ('val','test'):
            raise ValueError('Journal visual review may exclude training only')
        row=next((r for r in result['train'] if r['name']==item['name']),None)
        peer=next((r for r in result[item['peer_split']] if r['name']==item['peer_name']),None)
        if not row or not peer or row['image_sha256']!=item['image_sha256'] or peer['image_sha256']!=item['peer_sha256']:
            raise ValueError('Journal visual review image/peer changed')
        result['train'].remove(row);excluded.append({**row,**item})
    return result,excluded


def wildlife(scratch):
    root = scratch / "wildlife"
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "african-wildlife.zip"
    url = "https://github.com/ultralytics/assets/releases/download/v0.0.0/african-wildlife.zip"
    if not archive_path.exists():
        temporary = archive_path.with_suffix(".zip.partial")
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(archive_path)
    if not (root / "images/train").exists():
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if not (root / member.filename).resolve().is_relative_to(root.resolve()):
                    raise ValueError("Unsafe dataset archive path")
            archive.extractall(root)
    dataset = Dataset.from_info({**{s: root / "images" / s for s in SPLITS},
                                 "names": ["buffalo", "elephant", "rhino", "zebra"]})
    dataset.provenance["archive_sha256"] = file_hash(archive_path)
    return dataset


def near_duplicate_filter(dataset, source, evidence, distance=6, max_error=0.025):
    """Prespecified conservative image-only rule; no model outcomes are read."""
    from PIL import Image, ImageOps
    signatures = {}
    for split, records in source["records"].items():
        signatures[split] = []
        for row in records:
            with Image.open(dataset.images[split] / row["name"]) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                ratio = image.width / image.height
                pixels = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).tobytes()
                bits = 0
                for y in range(8):
                    for x in range(8): bits = (bits << 1) | (pixels[y*9+x] > pixels[y*9+x+1])
                rgb = image.resize((32, 32), Image.Resampling.LANCZOS).tobytes()
            signatures[split].append((row["name"], bits, ratio, rgb))
    parent = {}
    def find(value):
        parent.setdefault(value, value)
        if parent[value] != value: parent[value] = find(parent[value])
        return parent[value]
    def union(a, b): parent[find(a)] = find(b)
    candidates = []
    for first, second in (("train", "val"), ("train", "test"), ("val", "test")):
        for a in signatures[first]:
            for b in signatures[second]:
                delta = (a[1] ^ b[1]).bit_count()
                if delta > distance: continue
                error = sum(abs(x-y) for x,y in zip(a[3],b[3])) / (255 * len(a[3]))
                accepted = error <= max_error and abs(a[2] / b[2] - 1) <= 0.05
                row = {"first_split":first,"first_name":a[0],"second_split":second,"second_name":b[0],
                       "dhash_distance":delta,"normalized_rgb_mae":error,"excluded_by_rule":accepted}
                candidates.append(row)
                if accepted: union((first,a[0]),(second,b[0]))
    groups = {}
    for node in parent: groups.setdefault(find(node), []).append(node)
    excluded = set()
    for nodes in groups.values():
        retained_split = "test" if any(s=="test" for s,_ in nodes) else "val"
        excluded.update(node for node in nodes if node[0] != retained_split)
    records = {s:[r for r in source["records"][s] if (s,r["name"]) not in excluded] for s in SPLITS}
    save_json(evidence / "near_duplicate_screen.json", {
        "rule":{"max_dhash_distance":distance,"max_normalized_rgb_mae":max_error,"max_relative_aspect_change":0.05},
        "candidates":candidates,"excluded":[{"split":s,"name":n} for s,n in sorted(excluded)],
        "limitation":"Conservative deterministic screen, not an exhaustive scene or pretraining-overlap audit"})
    # Private visual-review sheet; not included in distributable project bundles.
    from PIL import ImageDraw
    shown = sorted(candidates,key=lambda r:(not r["excluded_by_rule"],r["normalized_rgb_mae"]))[:24]
    if shown:
        canvas=Image.new("RGB",(800,220*len(shown)),"white");draw=ImageDraw.Draw(canvas)
        for i,row in enumerate(shown):
            for col,prefix in enumerate(("first","second")):
                with Image.open(dataset.images[row[f"{prefix}_split"]]/row[f"{prefix}_name"]) as im:
                    im=ImageOps.exif_transpose(im).convert("RGB");im.thumbnail((390,190))
                draw.text((400*col+3,220*i+3),f"{row[f'{prefix}_split']} {row[f'{prefix}_name']} MAE={row['normalized_rgb_mae']:.3f}",fill="black")
                canvas.paste(im,(400*col,220*i+25))
        canvas.save(evidence / "private_near_duplicate_contact_sheet.png")
    return records, [{"split":s,"name":n,"reason":"prespecified perceptual screen"} for s,n in sorted(excluded)]


def prepare_context(name, scratch, evidence, project, val_limit=None):
    evidence.mkdir(parents=True, exist_ok=True)
    dataset = wildlife(scratch) if name == "wildlife" else prepare_voc2007(scratch, evidence)
    raw = audit_source(dataset, evidence / "source_audit.json", reject_overlap=False)
    reviewed = json.loads((project / "configs/duplicate_exclusions.json").read_text()) if name=="wildlife" else None
    base = disjoint_splits(raw,"holdout_priority_reviewed_v2" if reviewed else "holdout_priority_v1",reviewed)
    records, exclusions = near_duplicate_filter(dataset, base, evidence)
    review_path=project/'configs/journal_duplicate_exclusions.json'
    journal_review=json.loads(review_path.read_text()) if name=='wildlife' and review_path.exists() else None
    if journal_review:
        records,additional=apply_review(records,raw['fingerprint'],base['fingerprint'],journal_review)
        exclusions+=additional
        save_json(evidence/'additional_visual_review.json',journal_review)
    if val_limit and len(records["val"]) > val_limit:
        ranked=sorted(records["val"],key=lambda r:digest(["journal-validation-v1",5200,r["name"]]))[:val_limit]
        records["val"]=sorted(ranked,key=lambda r:r["name"])
    identity={"schema":"journal-data-v1","names":dataset.names,"records":records,
              "raw_source_fingerprint":raw["fingerprint"],"base_fingerprint":base["fingerprint"],
              "near_rule":{"dhash":6,"rgb_mae":0.025,"aspect":0.05},"validation_limit":val_limit,"validation_seed":5200}
    if journal_review:identity['additional_visual_review_sha256']=digest(journal_review)
    source={**identity,"fingerprint":digest(identity),"provenance":dataset.provenance,
            "excluded":base["excluded"]+exclusions,
            "counts":{s:{"images":len(rows),"objects":sum(r["objects"] for r in rows)} for s,rows in records.items()},
            "test_membership_unchanged":records["test"]==raw["records"]["test"]}
    coverage={}
    for split,rows in records.items():
        counts=[0]*len(dataset.names)
        for row in rows:
            for line in validate_labels(label_for_image(dataset.images[split]/row['name']).read_text(),len(dataset.names)):
                counts[int(line.split()[0])]+=1
        if any(n==0 for n in counts):raise ValueError(f"Missing class in clean {name}/{split} split")
        coverage[split]=counts
    source['class_object_counts']=coverage
    if not source["test_membership_unchanged"]:raise ValueError("Test membership changed")
    save_json(evidence/"split_audit.json",source)
    evaluation=scratch/"evaluation"/name
    for row in records["val"]:
        image=dataset.images["val"]/row["name"]
        link(image,evaluation/"images/val"/row["name"])
        label=evaluation/"labels/val"/Path(row["name"]).with_suffix(".txt")
        label.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(label_for_image(image),label)
    return {"name":name,"dataset":dataset,"source":source,"evidence":evidence,"scratch":scratch,
            "validation":evaluation/"images/val","test":dataset.images["test"],"variants":{}}


def variant(context, fraction, noise, subset_seed, corruption_seed):
    key=(fraction,noise,subset_seed,corruption_seed)
    if key in context["variants"]:return context["variants"][key]
    source=context["source"];dataset=context["dataset"]
    config={"source_fingerprint":source["fingerprint"],"fraction":fraction,"noise":noise,
            "noise_type":"missing_box","subset_seed":subset_seed,"corruption_seed":corruption_seed}
    variant_id=digest(config)[:16]
    root=context["scratch"]/"variants"/context["name"]/variant_id
    selected=set(nested_subset([r["name"] for r in source["records"]["train"]],fraction,subset_seed))
    rows=[];original=removed=empty=0
    for row in source["records"]["train"]:
        if row["name"] not in selected:continue
        image=dataset.images["train"]/row["name"]
        link(image,root/"images/train"/row["name"])
        original_label=label_for_image(image)
        text=original_label.read_text(encoding="utf-8")
        changed,events=corrupt_missing_boxes(text,noise,corruption_seed,row["name"])
        label=root/"labels/train"/Path(row["name"]).with_suffix(".txt")
        label.parent.mkdir(parents=True,exist_ok=True)
        if noise:label.write_text(changed,encoding="utf-8",newline="\n")
        else:shutil.copy2(original_label,label)
        count=len(validate_labels(label.read_text(),len(dataset.names)))
        original+=row["objects"];removed+=sum(e["removed"] for e in events);empty+=count==0
        rows.append({**row,"label_sha256":file_hash(label),"objects":count})
    manifest={"variant_id":variant_id,"config":config,"fingerprint":digest({"config":config,"train":rows}),
              "train_images":len(rows),"original_train_objects":original,"removed_objects":removed,
              "remaining_train_objects":original-removed,"realized_noise_rate":removed/original if original else 0,
              "empty_train_labels":empty,"records":{"train":rows},
              "held_out_reference_fingerprint":source["fingerprint"],"clean_validation_and_test":True}
    if not manifest["remaining_train_objects"]:raise ValueError("No training annotations remain")
    data={"path":root.resolve().as_posix(),"train":"images/train","val":str(context["validation"]),
          "test":str(context["test"]),"names":dataset.names}
    path=root/"data.yaml";path.write_text(yaml.safe_dump(data,sort_keys=False),encoding="utf-8")
    evidence=context["evidence"]/"variants"/variant_id
    save_json(evidence/"manifest.json",manifest)
    (evidence/"data.yaml").write_text(yaml.safe_dump(data,sort_keys=False),encoding="utf-8")
    context["variants"][key]=(path,manifest)
    return path,manifest
