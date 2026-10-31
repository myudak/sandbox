"""Build and execute a public results narrative from immutable version-1 evidence."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

import nbformat as nbf
from nbclient import NotebookClient

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'outputs/kaggle_journal_v1/muon_yolo_journal'
PUBLIC_URL='https://www.kaggle.com/code/myudak/muon-yolo-journal'
ORIGINAL_URL=PUBLIC_URL+'?scriptVersionId=361947826'


def snapshot():
    summary=json.loads((EVIDENCE/'campaign_summary.json').read_text())
    raw=json.loads((EVIDENCE/'results.json').read_text())
    selection=json.loads((EVIDENCE/'selected_hyperparameters.json').read_text())
    fields=('run_id','dataset','optimizer','seed','data_fraction','noise_probability','realized_noise_rate',
        'lr0','train_images','images_seen','optimizer_steps','epochs_completed','training_seconds','val_map50_95')
    trials=[{**{k:r[k] for k in fields},'roles':' | '.join(r['roles'])} for r in raw]
    histories=[]
    for row in raw:
        if not any('_confirmation_' in role for role in row['roles']):continue
        path=EVIDENCE/'runs'/row['run_id']/f"attempt-{row['attempt']:03}"/'train/results.csv'
        records=list(csv.DictReader(path.open(newline='',encoding='utf-8')))
        histories.append({'dataset':row['dataset'],'optimizer':row['optimizer'],'block':row['seed'],
            'fraction':row['data_fraction'],'missing':row['noise_probability'],
            'exposure':[int(float(r['epoch']))*1024 for r in records],
            'ap':[100*float(r['metrics/mAP50-95(B)']) for r in records],
            'box_loss':[float(r['train/box_loss']) for r in records]})
    assert len(histories)==60
    # Independent arithmetic check before putting any reviewed estimate in the public narrative.
    checked=0
    for split in ('frozen_test','validation'):
        for group in summary[split].values():
            for family in ('conditions','paired_optimizer_contrasts','three_way_interactions'):
                for row in group[family]:
                    values=row['values'];assert len(values)==3
                    mean=statistics.mean(values);half=4.302652729696142*statistics.stdev(values)/math.sqrt(3)
                    assert math.isclose(mean,row['mean'],abs_tol=1e-9)
                    assert all(math.isclose(a,b,abs_tol=1e-6) for a,b in zip(row['ci95'],(mean-half,mean+half)))
                    checked+=1
    assert checked==70
    identities={name:hashlib.sha256((EVIDENCE/name).read_bytes()).hexdigest() for name in
        ('campaign_summary.json','results.json','final_test_results.json','frozen_final_test_plan.json','selected_hyperparameters.json')}
    return {'summary':summary,'selection':selection,'histories':histories,'trials':trials,
        'provenance':{'original_version':1,'script_version_id':361947826,'url':ORIGINAL_URL,
            'file_sha256':identities,'independently_checked_summaries':checked,'author':'Muchammad Yuda Tri Ananda','email':'yuda@myudak.com'}}


INTRO='''# MuSGD × YOLO26: When Data and Annotations Are Scarce

### An interactive results explorer

**Muchammad Yuda Tri Ananda** · [yuda@myudak.com](mailto:yuda@myudak.com)  
Completed study · 25 October 2026 · Public report updated 31 October 2026

**120 training trials · 60 frozen test evaluations · 2 datasets · 3 paired joint blocks**

Does MuSGD fine-tuning behave differently when there are fewer images and some object boxes are missing? This study compares existing YOLO26n training recipes while matching actual image exposure and optimizer updates.

> **What we found:** MuSGD has modest positive test point differences on VOC-derived data, and smaller, mixed differences on wildlife. The primary scarcity × missingness interaction remains unresolved on both datasets. All selected learning rates are at the lowest tested boundary.

**Start here:** use the dropdown above each chart, hover for exact numbers, click legend entries to isolate a recipe or block, and drag to zoom. Double-click the plot to reset. These controls work in the saved report without starting a Python session.

This is a results presentation of the [completed version 1 experiment]('''+ORIGINAL_URL+'''). That version retains the original training code, checkpoints, predictions and output evidence. This report only renders archived metrics.
'''

METHODS='''## 2. What was actually held constant?

| Design choice | What it means |
|:--|:--|
| Model | Same pinned pretrained YOLO26n checkpoint; Ultralytics 8.4.187 |
| Image availability | 20% or 100% of the training-image pool |
| Annotation intervention | Independently remove training boxes with target probability 0% or 20%; retain images, including those left without boxes |
| Equal exposure | 20,480 actual image presentations and 1,280 optimizer updates per primary run |
| Replication | Three paired joint blocks (101–103), varying training, subset and deletion seeds together |
| Selection | Six candidates per optimizer, two wildlife validation anchors, ten exposure blocks; no test-driven tuning |
| Transfer | Wildlife-selected AdamW/MuSGD settings transferred to VOC-derived data without VOC tuning |
| Evaluation | Clean validation; one final evaluation of each of 60 frozen validation-selected checkpoints |

African Wildlife uses **1,020/223/227 train/validation/test images** after the recorded cross-split audit. The VOC2007-derived task uses **2,501/512/4,952** images. It retains difficult objects and reports all-object mAP50–95, **not official VOC AP**. SGD was evaluated only on wildlife; an absent VOC SGD score is not zero.

**Why match exposure?** At fixed ordinary epochs, fewer images also mean fewer optimizer steps. Here the scarce image pool is revisited, so primary comparisons keep presentations and updates fixed. This controls one confound; it does not isolate Muon's matrix update from other native recipe differences.
'''


def build():
    data=snapshot();cells=[];sections=[]
    def markdown(value):cells.append(nbf.v4.new_markdown_cell(value))
    def code(value):
        cells.append(nbf.v4.new_code_cell(value,metadata={'_kg_hide-input':True,'_kg_hide-output':False,
            'jupyter':{'source_hidden':True},'tags':['hide-input']}))
    markdown(INTRO)
    markdown('''## 1. Explore paired recipe differences

The default view is **African Wildlife · frozen test**. Switch datasets or inspect validation separately. Large markers are mean paired differences; small markers show the three individual blocks. Horizontal bars are approximate unadjusted 95% Student *t* intervals. Positive values favor the named recipe over AdamW.

Wildlife MuSGD differences range from **−0.25 to +0.79 AP points**, with all four intervals including zero. VOC-derived differences range from **+0.73 to +1.67**; two cell intervals exclude zero before multiplicity adjustment. These are exploratory cell comparisons with only three blocks.
''')
    # Numeric evidence and renderer are hidden in the reading view but inspectable via Show code.
    payload=json.dumps(data,separators=(',',':'),allow_nan=False)
    module=(ROOT/'scripts/journal_report_charts.py').read_text(encoding='utf-8')
    code('''# Reviewed numeric snapshots from the immutable version 1 run.
# Expand this cell to inspect inputs; no source-code ZIP, model weights or training are loaded.
import hashlib, json
'''+f"evidence_json={payload!r}\nassert hashlib.sha256(evidence_json.encode()).hexdigest()=={hashlib.sha256(payload.encode()).hexdigest()!r}\nsnapshot=json.loads(evidence_json)\n"+module+"\nshow('paired-effects',effects(snapshot))")
    sections.append(('', '<h1>MuSGD × YOLO26: Results Explorer</h1><p>Muchammad Yuda Tri Ananda · <a href="mailto:yuda@myudak.com">yuda@myudak.com</a></p><p>120 training trials · 60 frozen test evaluations · two datasets · three joint blocks.</p><p class="note">Positive VOC-derived point differences and smaller, mixed wildlife differences; the primary interaction remains unresolved. Hover for exact values, choose a view above each chart, and use the legend to select series.</p><p>Original evidence: <a href="'+ORIGINAL_URL+'">completed version 1 experiment</a>.</p>',None))
    sections.append(('1. Paired differences','<p>Means and approximate unadjusted 95% paired t intervals across three joint blocks. Positive values favor the named recipe over AdamW. Small points are block differences; cells are exploratory.</p>','paired-effects'))
    markdown('''### Exact frozen test values

Means are mAP50–95 × 100 (AP). The final two columns concern the paired MuSGD–AdamW comparison, so the interval is computed from block differences, not from subtracting the endpoints of marginal score intervals.
''')
    code('display(HTML(exact_table(snapshot)))')
    markdown(METHODS)
    sections.append(('2. Study design','<p>Same pretrained YOLO26n checkpoint; primary runs each receive 20,480 image presentations and 1,280 updates. Image availability is 20%/100%, target missing-box probability 0%/20%. All comparisons pair training/subset/deletion seeds across blocks 101–103. VOC2007-derived scores retain difficult objects and use all-object mAP50–95, not official VOC AP.</p>'+ '<h3>Exact frozen test values</h3>',None))
    code("sections="+repr(sections)+"\nsections[-1]=(sections[-1][0],sections[-1][1]+exact_table(snapshot),None)")
    markdown('''## 3. Compare absolute detection scores

Use this view to see the practical score scale. The y-axis starts at zero. Bars show mean AP and approximate marginal 95% intervals; use the paired-difference chart above for direct recipe comparisons. Scores from different datasets describe different tasks and should not be treated as a shared leaderboard.

With 20% wildlife images and 20% target missing boxes, **AdamW / MuSGD / SGD score 74.86 / 75.12 / 77.59 AP**, respectively. SGD is a substantive comparator here.
''')
    code("show('absolute-scores',scores(snapshot))\nsections.append(('3. Absolute scores','<p>Mean mAP50–95 × 100 across three blocks. Error bars are marginal approximate 95% intervals, not paired recipe-difference intervals. Compare recipes within each dataset; SGD was not evaluated on VOC-derived data.</p>','absolute-scores'))")
    markdown('''## 4. The primary question: does scarcity change sensitivity to missing boxes?

For each block, let **D** be MuSGD minus AdamW in AP points. The primary interaction is:

**[D(20% images, 20% missing) − D(20% images, clean)] − [D(100% images, 20% missing) − D(100% images, clean)].**

The frozen test estimates are **+0.470 [−6.383, 7.322]** on wildlife and **+0.488 [−0.660, 1.637]** on VOC-derived data. Both intervals include zero. The current evidence does not resolve this interaction; the attractive individual cells do not replace the primary estimate. The SGD interaction is secondary.
''')
    code("show('primary-interaction',interaction(snapshot))\nsections.append(('4. Primary interaction','<p>Difference of recipe differences across image fractions and missing-box conditions. Both primary MuSGD–AdamW test intervals include zero: +0.470 [−6.383, 7.322] on wildlife and +0.488 [−0.660, 1.637] on VOC-derived data. SGD is secondary.</p>','primary-interaction'))")
    markdown('''## 5. Open the validation search, including its boundary

Choose a recipe to inspect all six candidates. Each point averages the two wildlife validation anchors at ten exposure blocks; it is a selection score, not a final test score. The star marks the selected candidate.

| Recipe | Selected base LR | Weight decay |
|:--|--:|--:|
| AdamW | 0.0003 | 0.0005 |
| MuSGD | 0.003 | 0.0005 |
| SGD | 0.003 | 0 |

**All three selected the lowest searched learning rate.** The planned equal-count boundary extension was skipped by the prospective runtime-reservation rule. Equal candidate counts therefore do not imply equally complete optimization. No new lower-rate search followed test access.
''')
    code("show('validation-search',search(snapshot))\nsections.append(('5. Validation search','<p>Six candidates per recipe; two validation anchors; ten exposure blocks. All selected LRs are the lower boundary of the tested grid. The extension was skipped by the prospective runtime-reservation rule. These settings are finite-grid selections, not established global optima.</p>','validation-search'))")
    markdown('''## 6. Inspect learning trajectories

Choose a dataset and condition, then switch between **validation AP** and **training box loss**. Colors identify optimizers; line styles identify joint blocks. Legend entries let you isolate individual curves.

The x-axis is actual presented-image count: 20 exposure blocks × 1,024 images = 20,480 presentations. Validation trajectories are the per-block history values; the reported final test scores use frozen validation-best checkpoints and are not the last points in these curves. These short runs do not establish convergence.
''')
    code("show('learning-curves',curves(snapshot))\nsections.append(('6. Learning trajectories','<p>Primary confirmation histories only. Choose dataset/condition and validation AP or training box loss. Curves show per-block histories, not final test scores; final evaluation uses frozen validation-best checkpoints. Training is not rerun.</p>','learning-curves'))")
    markdown('''## 7. Controls, sensitivity and interpretation

**Exposure controls.** The earlier pilot's ranking reversal was absent even in the new variable-exposure bridge. On scarce wildlife images, its MuSGD–AdamW validation differences were −0.16 AP (clean) and −2.16 AP (missing boxes); the fixed-exposure controls gave −2.84 and −3.12. Source membership, cyclic sampling and batch rounding also changed, so the phase difference cannot be attributed solely to update matching.

**Longer schedules.** Four one-block 60-exposure-block transfer checks lowered best-checkpoint validation AP by 0.65–3.51 points relative to their corresponding 20-block runs. The horizon and schedule changed together; this does not identify an optimal horizon.

**Head learning rate.** Replacing MuSGD's native 3× selected-head LR with 1× changed block-101 validation AP by +1.56 / +1.41 / +0.08 / −0.04 across scarce-clean / scarce-missing / full-clean / full-missing conditions. This is a sensitivity check, not an independently retuned test comparison.

**What to take away.** This is a conditional comparison of existing library recipes. It provides measured, paired evidence under controlled exposure, while leaving the primary interaction unresolved. It does not establish a universally superior optimizer or isolate the orthogonalization mechanism.
''')
    markdown('''## 8. Evidence, limits and reproducibility

- **Completed:** 120 unique training trials and 60 final frozen-checkpoint evaluations; zero recorded failures or incomplete confirmation blocks. Four full-data control trials are shared between roles and counted once.
- **Test freeze:** all 60 checkpoint hashes and configurations were frozen before first test access. No test-driven retuning or further training followed.
- **Compute:** the original runner clock was 10.24 hours on one T4. Preflight plus campaign had external caps totaling 12 hours. This page is a CPU-only rendering of the archived results.
- **Audit:** all 70 means/intervals were independently recalculated. Compact evidence checks cover recorded identities, exposure, pairing and freeze linkage; independent rehashing of source-image/checkpoint bytes requires the larger original artifacts.
- **Limits:** three joint blocks; unstable approximate unadjusted intervals; one tuning realization; lower-bound LR selection; shorter tuning horizon; synthetic independent label deletion; possible residual scene/pretraining overlap; one small detector and two datasets. Joint blocks do not separate training/subset/deletion variance components.
- **Data rights:** source photographs remain under upstream terms. This report embeds numeric evidence rather than source photographs or weights. [Wildlife dataset documentation](https://docs.ultralytics.com/datasets/detect/african-wildlife/) · [VOC reference](https://doi.org/10.1007/s11263-009-0275-4).

### Trace the original evidence

Open the [original version 1 notebook and outputs]('''+ORIGINAL_URL+'''). Principal files under `muon_yolo_journal/` are `results.json`, `campaign_summary.json`, `selected_hyperparameters.json`, `frozen_final_test_plan.json`, and `final_test_results.json`. The original version retains training source and checkpoint/prediction artifacts. This report uses a checked numeric snapshot of that evidence.

### Downloads and reuse

The **Output** tab contains `trial_metrics.csv` (all 120 training rows), `reviewed_evidence.json` (summary, selection, provenance and 60 confirmation histories), `figure_specs.json`, and `muon_yolo_results_explorer.html` (an offline interactive copy). Download the HTML and open it in a browser to explore the same controls without Kaggle or a live Python kernel. Expanding the hidden cells exposes the analysis code and numeric snapshot; running this report regenerates charts without training a model.

**Author:** Muchammad Yuda Tri Ananda · [yuda@myudak.com](mailto:yuda@myudak.com)
''')
    code("sections.append(('7. Interpretation and limits','<p>Existing recipes, three joint blocks, approximate unadjusted intervals, one tuning realization, boundary-selected LRs, short adaptation budgets, synthetic missing boxes, possible residual scene/pretraining overlap, and a single small detector. No universal superiority or isolated mechanism claim.</p><p>Original source data remain under upstream terms. This report embeds numeric evidence, not photographs or model weights.</p><h3>Provenance</h3><p>The checked numeric snapshot and trial CSV accompany this file. The original version 1 holds the full evidence and training source.</p>',None))\noutput=save_outputs(snapshot,sections)\ndisplay(HTML('<p><strong>Report complete.</strong> Five interactive charts, 120 trial rows, 60 confirmation histories and 70 verified summaries. Downloads are saved in the Output tab.</p>'))")
    notebook=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python'},'report_mode':'archived_evidence_cpu_only','evidence_version':1,
        'evidence_payload_sha256':hashlib.sha256(payload.encode()).hexdigest()})
    nbf.validate(notebook)
    try:NotebookClient(notebook,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    except Exception as error:raise RuntimeError(str(error)[-2500:]) from None
    assert not any(o.output_type=='error' for c in notebook.cells if c.cell_type=='code' for o in c.outputs)
    destination=ROOT/'kaggle/journal_public_report';destination.mkdir(parents=True,exist_ok=True)
    path=destination/'muon_yolo_results_explorer.ipynb'
    # Kaggle CLI 2.0.2 opens notebook source using the Windows locale encoding.
    # ASCII JSON escapes preserve every Unicode label across that boundary.
    path.write_text(json.dumps(notebook,ensure_ascii=True,indent=1)+'\n',encoding='ascii')
    metadata={'id':'myudak/muon-yolo-journal','id_no':140671190,'title':'Muon Yolo Journal','code_file':path.name,
        'language':'python','kernel_type':'notebook','is_private':False,'enable_gpu':False,'enable_internet':False,
        'dataset_sources':[],'competition_sources':[],'kernel_sources':[],'model_sources':[]}
    (destination/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    record={'status':'executed_locally','notebook':str(path.relative_to(ROOT)),'code_cells':sum(c.cell_type=='code' for c in cells),
        'interactive_charts':5,'training_rows':120,'confirmation_histories':60,'verified_summaries':70,
        'email':'yuda@myudak.com','original_evidence_url':ORIGINAL_URL,'gpu_enabled':False,'internet_enabled':False,
        'notebook_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'payload_sha256':hashlib.sha256(payload.encode()).hexdigest(),
        'chart_renderer':'isolated HTML frames with shared local plotly.min.js; offline HTML export also self-contained'}
    (ROOT/'research/INTERACTIVE_REPORT_STATUS.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record))


if __name__=='__main__':build()
