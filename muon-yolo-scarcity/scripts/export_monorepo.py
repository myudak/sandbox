"""Copy the public research release into a new sandbox monorepo project folder."""
import argparse
import base64
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TITLE='Separating Training Exposure from Data Scarcity in MuSGD–YOLO Fine-Tuning under Missing Annotations'
PUBLIC_README='''# MuSGD × YOLO26 under data scarcity and missing annotations

## Research manuscript

**Separating Training Exposure from Data Scarcity in MuSGD–YOLO Fine-Tuning under Missing Annotations**  
**Muchammad Yuda Tri Ananda** · [yuda@myudak.com](mailto:yuda@myudak.com) · October 2026

[**Read the paper (PDF)**](output/pdf/muon_yolo_scarcity.pdf) · [LaTeX source](paper/main.tex) · [Interactive Kaggle report](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=364100382) · [Original experiment and outputs](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=361947826)

An empirical comparison of existing MuSGD, AdamW and momentum-SGD fine-tuning recipes in pretrained YOLO26n. The study controls actual training exposure while varying available images and missing training boxes. This is a research manuscript; no journal acceptance or new optimizer is claimed.

## Findings

- **120 completed training trials** and **60 frozen-checkpoint test evaluations**, with no recorded failed or incomplete confirmation block.
- Primary runs each receive **20,480 image presentations and 1,280 optimizer updates**. Three paired joint blocks vary training, image-subset and annotation-deletion seeds together.
- MuSGD–AdamW test differences range from **−0.25 to +0.79 AP points on African Wildlife**, and **+0.73 to +1.67 on VOC-derived data**. SGD is a substantive wildlife comparator.
- The primary scarcity × missingness interaction is **+0.470 [−6.383, 7.322] AP points** on wildlife and **+0.488 [−0.660, 1.637]** on VOC-derived data. Both approximate 95% paired intervals include zero.
- **All selected learning rates are at the lower search boundary.** The prospective runtime rule skipped the planned extension. These are finite-grid-selected recipes, with three-block uncertainty; they do not establish universal optimizer superiority.

The VOC2007-derived task retains difficult objects and reports all-object **mAP50–95, not official VOC AP**. Validation and final test estimates are separate; the earlier untuned pilot is not pooled with journal confirmation.

![Paired frozen-test differences](paper/images/journal_test_contrasts.png)

See the [measured interpretation](research/JOURNAL_INTERPRETATION.md), [full paired estimates](research/JOURNAL_FINDINGS.md), and [frozen protocol](research/JOURNAL_PROTOCOL.md).

## Explore the results

The [public Kaggle report](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=364100382) has five interactive charts: paired differences, absolute scores, the primary interaction, validation search and learning trajectories. Dropdowns select datasets, validation/test views, recipes, conditions and trajectory metrics. Hover reveals exact values and legend entries isolate series or blocks. It renders archived evidence on CPU; it does not rerun training.

For an offline copy, download [the interactive HTML explorer](output/kaggle_report/muon_yolo_results_explorer.html) and open the downloaded file in a browser. GitHub's file preview displays HTML source. The explorer includes its own plotting runtime and needs no Python session. Individual chart HTML files use the adjacent `plotly.min.js` bundle.

## What's in this directory?

| Path | Contents |
| --- | --- |
| [`output/pdf/`](output/pdf/) | The checked, ten-page manuscript PDF |
| [`paper/`](paper/) | Editable LaTeX, tables and numeric figures |
| [`src/`](src/) | Dataset variants, exposure control, training recipes and statistics |
| [`configs/`](configs/) | Pinned study settings and hash-bound duplicate exclusions |
| [`tests/`](tests/), [`analysis_tests/`](analysis_tests/) | CPU checks for data handling, pairing and analysis |
| [`research/`](research/) | Protocol, plan, run registry, findings and audit records |
| [`outputs/kaggle_journal_v1/muon_yolo_journal/`](outputs/kaggle_journal_v1/muon_yolo_journal/) | Frozen numeric evidence, data/variant manifests and per-run histories |
| [`kaggle/journal_public_report/`](kaggle/journal_public_report/) | Executed public report notebook and CPU publication metadata |
| [`notebooks/`](notebooks/) | Analysis companions and archived training notebooks |
| [`output/kaggle_report/`](output/kaggle_report/) | CSV/JSON exports and interactive HTML charts |
| [`release_manifest.json`](release_manifest.json) | SHA-256 identities of released files |

The evidence includes numeric records, source-image hashes and paths, rather than source photographs, individual image-label files or model weights. Private duplicate-review contact sheets and workstation tooling are omitted. Original checkpoints and predictions remain in the linked Kaggle version 1 outputs.

## Validate without training

From the monorepo root:

```bash
cd muon-yolo-scarcity
python -m pip install -r requirements-report.txt
python -m pytest -q tests analysis_tests
python scripts/audit_journal_evidence.py outputs/kaggle_journal_v1/muon_yolo_journal
python scripts/audit_journal_statistics.py outputs/kaggle_journal_v1/muon_yolo_journal
```

The evidence audit checks recorded plan/spec/data identities, actual exposure, finite histories, paired initialization/order and test-freeze linkage. The arithmetic audit independently recalculates 70 summaries and reconciles CSV/JSON metrics. These checks do not independently rehash omitted source-image or checkpoint bytes. Source files retain their frozen byte identities across Git checkouts.

To regenerate the CPU-only interactive report:

```bash
python scripts/build_public_journal.py
```

This writes an executed notebook under `kaggle/journal_public_report/` and regenerates `output/kaggle_report/`. It makes no Kaggle submission. Publishing scripts require separate explicit execution and authenticated credentials; credentials are not included.

## Training provenance

All GPU training ran on Kaggle. The preflight and original campaign had external caps totaling 12 hours; the original campaign's runner clock was 10.24 hours, excluding notebook installation and output persistence. Publication saves only render existing numeric results.

The [original version 1](https://www.kaggle.com/code/myudak/muon-yolo-journal?scriptVersionId=361947826) preserves executable training source and artifacts. The original plan and checkpoint/configuration freeze are included here. Test access has occurred; a new search must not be presented as a continuation of an untouched confirmatory test. The default launch helper refuses another campaign when the existing reserved cap is exhausted.

## Build the paper

The existing `paper/main.tex` is the manuscript entry point. For a local Tectonic installation:

```bash
tectonic --outdir output/pdf paper/main.tex
```

Tectonic writes `main.pdf`; the checked release is named `muon_yolo_scarcity.pdf`. The saved release was also compiled successfully in the desktop editor and all ten rendered pages were inspected. No journal-specific template has been selected.

## Attribution and data terms

African Wildlife and VOC images remain subject to upstream terms. The report contains numeric figures, and the release omits source photographs and weights. Upstream dependencies and models retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Publication of this directory does not relicense the datasets or model.

## Cite this manuscript

```bibtex
@unpublished{ananda2026musgdscarcity,
  author = {{Muchammad Yuda Tri Ananda}},
  title = {Separating Training Exposure from Data Scarcity in MuSGD--YOLO Fine-Tuning under Missing Annotations},
  year = {2026},
  note = {Research manuscript},
  url = {https://github.com/myudak/sandbox/blob/main/muon-yolo-scarcity/output/pdf/muon_yolo_scarcity.pdf}
}
```
'''


def export(destination):
    destination=destination.resolve()
    assert destination.parent.name=='sandbox' and (destination.parent/'.git').is_dir()
    assert destination.name=='muon-yolo-scarcity'
    if destination.exists():raise ValueError('Destination exists; review changes before exporting again')
    destination.mkdir()
    omitted=[]
    def copy(path):
        relative=path.relative_to(ROOT)
        if '__pycache__' in relative.parts or path.suffix in {'.pyc','.pt','.tmp'} or path.name.startswith('private_'):
            omitted.append(relative.as_posix());return
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for directory in ('src','scripts','tests','analysis_tests','configs','research','paper','notebooks','kaggle'):
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file() and 'bundle' not in path.relative_to(ROOT).parts:copy(path)
    for name in ('requirements.txt','requirements-dev.txt','requirements-report.txt'):
        copy(ROOT/name)
    for directory in ('outputs/kaggle_journal_v1/muon_yolo_journal','output/pdf','output/kaggle_report'):
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file():copy(path)
    # Keep historical local context separately from the public overview.
    shutil.copyfile(ROOT/'README.md',destination/'research/DEVELOPMENT_README.md')
    (destination/'README.md').write_text(PUBLIC_README,encoding='utf-8')
    (destination/'.gitattributes').write_text('# Preserve byte hashes in frozen source and evidence.\n* -text\n*.pdf binary\n*.png binary\n*.jpg binary\n',encoding='utf-8')
    (destination/'.gitignore').write_text('''/.venv/
**/__pycache__/
/.pytest_cache/
/work/
/datasets/
/tmp/
/tools/
/deliverables/
*.pt
*.cache
*.pyc
**/private_*
kaggle/*/bundle/
/outputs/*
!/outputs/kaggle_journal_v1/
/outputs/kaggle_journal_v1/*
!/outputs/kaggle_journal_v1/muon_yolo_journal/
/output/*
!/output/pdf/
!/output/kaggle_report/
''',encoding='utf-8')
    notices='''# Third-party notices

`output/kaggle_report/plotly.min.js` and the plotting runtime embedded in the offline explorer are Plotly.js v2.35.2, distributed with Plotly.py 5.24.1. Copyright 2012–2024 Plotly, Inc.; MIT license. The upstream license is retained at `third_party/plotly/LICENSE.txt`; the JavaScript bundle retains its own notices. Upstream project: https://github.com/plotly/plotly.js.

Training imports Ultralytics 8.4.187 and other pinned dependencies. This release does not include the Ultralytics package or pretrained weights. Their licenses and dataset terms remain with their upstream providers. Wildlife/VOC source photographs and private duplicate-review sheets are not distributed here.
'''
    (destination/'THIRD_PARTY_NOTICES.md').write_text(notices,encoding='utf-8')
    distribution=importlib.metadata.distribution('plotly')
    license_path=next(p for p in distribution.files if p.name=='LICENSE.txt')
    target=destination/'third_party/plotly/LICENSE.txt';target.parent.mkdir(parents=True)
    shutil.copyfile(distribution.locate_file(license_path),target)
    files=[p for p in destination.rglob('*') if p.is_file()]
    assert not any(p.name.startswith('private_') or p.suffix in {'.pt','.zip','.exe','.pyc'} for p in files)
    patterns=[rb'gh[pousr]_[A-Za-z0-9]{25,}',rb'github_pat_[A-Za-z0-9_]{30,}',rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',rb'KGAT_[A-Za-z0-9_\-]{20,}']
    for path in files:
        if any(re.search(pattern,path.read_bytes()) for pattern in patterns):raise ValueError(f'Credential-like content in {path.relative_to(destination)}')
    manifest={'title':TITLE,'author':'Muchammad Yuda Tri Ananda','email':'yuda@myudak.com','date':'2026-10-31',
        'repository':'https://github.com/myudak/sandbox','project':'muon-yolo-scarcity','paper_status':'research manuscript',
        'source_images_included':False,'model_weights_included':False,'private_contact_sheets_included':False,
        'original_training_code_sha256':'217520ec98348e5a74500ac4efb9a3c1188580e76a8a48ff0c16d0bc12889d46',
        'files':{p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    (destination/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'destination':str(destination),'files':len(files)+1,'MiB':round(sum(p.stat().st_size for p in files)/1024**2,2),
        'omitted_private_sheets':[name for name in omitted if 'private_' in name]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path)
    export(parser.parse_args().destination)
