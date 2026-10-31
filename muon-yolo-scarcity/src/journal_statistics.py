"""Transparent paired-block summaries; validation and frozen test stay separate."""
from __future__ import annotations

import json
import math
from pathlib import Path
import statistics

from .dataset_variants import digest, save_json


def interval(values, critical=None):
    values = list(values)
    if not values or not all(math.isfinite(v) for v in values):
        raise ValueError("Finite nonempty sample required")
    n = len(values)
    mean = statistics.mean(values)
    if n == 1:
        return {"n_joint_blocks": 1, "mean": mean, "sd": None, "ci95": None, "values": values}
    if critical is None:
        from scipy.stats import t
        critical = float(t.ppf(0.975, n - 1))
    sd = statistics.stdev(values)
    half = critical * sd / math.sqrt(n)
    return {"n_joint_blocks": n, "mean": mean, "sd": sd, "ci95": [mean-half, mean+half], "values": values}


def paired_summary(rows, metric, optimizers):
    """Reject duplicate/unpaired cells; aggregate only complete 2x2 blocks."""
    cells = {}
    for row in rows:
        if row.get("status") != "completed":
            raise ValueError("Failed rows cannot enter paired summaries")
        key = (row["seed"], row["optimizer"], row["data_fraction"], row["noise_probability"])
        if key in cells:
            raise ValueError("Duplicate paired cell")
        value = row[metric]
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid AP")
        cells[key] = row
    seeds = sorted({key[0] for key in cells})
    expected = {(o,f,q) for o in optimizers for f in (0.2,1.0) for q in (0.0,0.2)}
    for seed in seeds:
        if {(o,f,q) for s,o,f,q in cells if s==seed} != expected:
            raise ValueError("Incomplete joint seed block")
        for f in (0.2,1.0):
            for q in (0.0,0.2):
                identities = {cells[seed,o,f,q].get("variant_fingerprint") for o in optimizers}
                if len(identities) != 1:
                    raise ValueError("Unpaired annotation/subset realization")
    condition_means = []
    contrasts = []
    for f in (0.2,1.0):
        for q in (0.0,0.2):
            for optimizer in optimizers:
                condition_means.append({"optimizer":optimizer,"fraction":f,"missing_probability":q,
                    **interval([100*cells[s,optimizer,f,q][metric] for s in seeds])})
            for optimizer in optimizers:
                if optimizer == "AdamW": continue
                contrasts.append({"contrast":f"{optimizer} minus AdamW","fraction":f,"missing_probability":q,
                    **interval([100*(cells[s,optimizer,f,q][metric]-cells[s,'AdamW',f,q][metric]) for s in seeds])})
    interactions = []
    for optimizer in optimizers:
        if optimizer == "AdamW": continue
        values = []
        for seed in seeds:
            def difference(f,q): return cells[seed,optimizer,f,q][metric]-cells[seed,'AdamW',f,q][metric]
            values.append(100*((difference(0.2,0.2)-difference(0.2,0.0))-(difference(1.0,0.2)-difference(1.0,0.0))))
        interactions.append({"contrast":f"{optimizer} minus AdamW: scarcity x missing-box interaction",**interval(values)})
    return {"metric":metric,"units":"AP points (100 times mAP)","joint_blocks":seeds,
        "interval_method":"Student t interval across independent paired joint training/subset/corruption blocks; approximate at small n; no multiplicity adjustment",
        "conditions":condition_means,"paired_optimizer_contrasts":contrasts,"three_way_interactions":interactions}


def summarize_campaign(output: Path):
    from .journal import select_confirmatory_rows
    rows = json.loads((output/'results.json').read_text())
    manifest = json.loads((output/'manifest.json').read_text())
    selected, incomplete = select_confirmatory_rows(rows)
    report = {"input_results_sha256":digest(rows),"status":manifest['status'],
        "attempted_runs":len(rows),"failed_runs":[{"run_id":r['run_id'],"status":r['status'],"error":r.get('error')} for r in rows if r['status']!='completed'],
        "incomplete_confirmation_blocks":incomplete,"skipped":manifest.get('skipped',[]),
        "validation":{},"frozen_test":{},"test_status":manifest.get('final_test_status','not_opened'),
        "limitations":["Short-budget fine-tuning recipes, not isolated orthogonalization effects or convergence results.",
            "Joint blocks vary training, subset and annotation deletion seeds together; intervals do not isolate these variance sources.",
            "Approximate t intervals at n=3 are unstable. Cell contrasts are exploratory; no multiple-comparison claims.",
            "One checkpoint lineage, uncertain pretrained-image overlap, and unresolved source-image rights limit generalization.",
            "VOC-derived all-object mAP50-95 is not official VOC AP; validation uses a frozen 512-image sample.",
            "Hyperparameters selected at 10 exposure blocks and transferred to 20/60-block schedules; tuning is not convergence-based."]}
    for dataset,optimizers in (("wildlife",('AdamW','MuSGD','SGD')),("voc2007",('AdamW','MuSGD'))):
        group=[r for r in selected if r['dataset']==dataset]
        if group: report['validation'][dataset]=paired_summary(group,'val_map50_95',optimizers)
    test_path=output/'final_test_results.json'
    if test_path.exists():
        tests=json.loads(test_path.read_text()); by_id={r['run_id']:r for r in selected}
        # A test block is summarized only when its complete prespecified grid finished.
        for dataset,optimizers in (("wildlife",('AdamW','MuSGD','SGD')),("voc2007",('AdamW','MuSGD'))):
            merged=[{**by_id[t['run_id']],**t} for t in tests if t['status']=='completed' and t['run_id'] in by_id and t['dataset']==dataset]
            complete=[];missing=[]
            for seed in sorted({r['seed'] for r in selected if r['dataset']==dataset}):
                block=[r for r in merged if r['seed']==seed]
                if len(block)==len(optimizers)*4: complete.extend(block)
                else: missing.append(seed)
            if complete: report['frozen_test'][dataset]=paired_summary(complete,'test_map50_95',optimizers)
            report.setdefault('incomplete_test_blocks',{})[dataset]=missing
    save_json(output/'campaign_summary.json',report)
    lines=['# Bounded journal campaign evidence','',f"Status: **{report['status']}**. Attempted runs: {len(rows)}. Failed/budget-stopped runs: {len(report['failed_runs'])}.",
        '',f"Frozen test status: `{report['test_status']}`. Validation and test summaries are separate.",'',
        'All intervals describe variation across joint randomization blocks. They are not image-bootstrap confidence intervals or evidence of optimizer causality.','']
    for split in ('validation','frozen_test'):
        for dataset,summary in report[split].items():
            lines += [f'## {dataset}: {split}', '',f"Joint blocks: {summary['joint_blocks']}. Units: AP points.",'',
                '| Contrast | Images | Missing boxes | Mean paired difference | Approximate 95% interval |','|---|---:|---:|---:|---|']
            for row in summary['paired_optimizer_contrasts']:
                bounds=row['ci95'];ci='Unavailable (one block)' if bounds is None else f"[{bounds[0]:.3f}, {bounds[1]:.3f}]"
                lines.append(f"| {row['contrast']} | {row['fraction']:.0%} | {row['missing_probability']:.0%} | {row['mean']:+.3f} | {ci} |")
            lines+=['']
    lines+=['## Limits','']+[f'- {item}' for item in report['limitations']]
    (output/'CAMPAIGN_FINDINGS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if report['validation']: plot_summary(output,report)
    return report


def plot_summary(output, report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'AdamW':'#2166ac','MuSGD':'#d95f02','SGD':'#1b9e77'}
    for split in ('validation','frozen_test'):
        datasets=report[split]
        if not datasets: continue
        fig,axes=plt.subplots(1,len(datasets),figsize=(7*len(datasets),4.7),squeeze=False,sharey=True)
        for ax,(dataset,summary) in zip(axes[0],datasets.items()):
            optimizers=list(dict.fromkeys(r['optimizer'] for r in summary['conditions']))
            for i,optimizer in enumerate(optimizers):
                data=[r for r in summary['conditions'] if r['optimizer']==optimizer]
                x=[j+(i-(len(optimizers)-1)/2)*.16 for j in range(4)]
                y=[r['mean'] for r in data]
                error=[0 if r['ci95'] is None else r['ci95'][1]-r['mean'] for r in data]
                ax.errorbar(x,y,yerr=error,fmt='o-',capsize=3,label=optimizer,color=colors[optimizer])
            ax.set_xticks(range(4),['20% / 0%','20% / 20%','100% / 0%','100% / 20%'])
            ax.set_xlabel('Available images / missing-box probability')
            ax.set_title(f"{dataset}; {len(summary['joint_blocks'])} joint blocks")
            ax.grid(axis='y',alpha=.2);ax.legend()
        axes[0,0].set_ylabel('mAP50–95 × 100 (approximate 95% t intervals)')
        bounds=[v for summary in datasets.values() for r in summary['conditions'] for v in (r['ci95'] or [r['mean']])]
        axes[0,0].set_ylim(min(0,min(bounds)-2),max(100,max(bounds)+2))
        fig.suptitle(f"Fixed exposure: {split.replace('_',' ')}; short-budget recipes")
        fig.tight_layout()
        for suffix in ('png','svg'):fig.savefig(output/f'journal_{split}.{suffix}',dpi=180)
        plt.close(fig)
