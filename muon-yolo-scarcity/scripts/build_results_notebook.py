"""Execute a self-contained review notebook from measured Kaggle artifacts.

This executes analysis/plotting locally; it never imports torch or trains a model.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from textwrap import dedent

import nbformat as nbf
from nbclient import NotebookClient
from nbconvert import HTMLExporter

from build_notebook import atomic_text

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--name", default="smoke_results_review")
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    rows = json.loads((evidence / "results.json").read_text(encoding="utf-8"))
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    split = json.loads((evidence / "split_audit.json").read_text(encoding="utf-8"))
    histories, hashes = {}, {}
    for name in ("results.json", "manifest.json", "split_audit.json", "checkpoint_lineage.json", "variant_audit.json"):
        hashes[name] = hashlib.sha256((evidence / name).read_bytes()).hexdigest()
    for row in rows:
        if row["status"] != "completed":
            continue
        path = evidence / "runs" / row["run_id"] / f"attempt-{row['attempt']:03d}" / "train/results.csv"
        with path.open(encoding="utf-8") as stream:
            histories[row["run_id"]] = [{k.strip(): float(v) for k, v in r.items()} for r in csv.DictReader(stream)]
        hashes[path.relative_to(evidence).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {"rows": rows, "manifest": manifest, "split_counts": split["counts"], "class_names": split["names"],
               "split_policy": split["split_policy"], "split_fingerprint": split["fingerprint"],
               "source_fingerprint": split["original_source_fingerprint"], "exclusions": split["excluded"],
               "variants": json.loads((evidence / "variant_audit.json").read_text(encoding="utf-8")),
               "checkpoint": json.loads((evidence / "checkpoint_lineage.json").read_text(encoding="utf-8")),
               "histories": histories, "artifact_sha256": hashes,
               "evidence_directory": str(evidence.relative_to(ROOT))}
    serialized = json.dumps(payload, sort_keys=True)
    snapshot_hash = hashlib.sha256(serialized.encode()).hexdigest()
    notebook = nbf.v4.new_notebook(metadata={"kernelspec": {"display_name": "Python 3", "name": "python3", "language": "python"}})
    md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
    notebook.cells = [
        md("# MuSGD × YOLO26: measured development review\n\n"
           "This companion contains an immutable snapshot of downloaded Kaggle measurements and runnable analysis code. "
           "It runs on CPU, uses no torch, and performs no training or test-set evaluation. "
           "The training notebooks are separate artifacts.\n\n"
           "**Status:** engineering development evidence, with provisional learning rates. "
           "No paper-level optimizer ranking or uncertainty claim follows from a one-seed run."),
        md("## 1. Restore and verify the measured snapshot\n"
           "Input JSON and per-epoch CSV hashes identify the source artifacts. "
           "The complete reviewed snapshot is embedded so the saved notebook remains usable without Kaggle credentials."),
        code(f"import json, hashlib, math\nfrom IPython.display import display, Markdown\n"
             f"DATA = json.loads({serialized!r})\n"
             f"assert hashlib.sha256(json.dumps(DATA, sort_keys=True).encode()).hexdigest() == {snapshot_hash!r}\n"
             "rows = DATA['rows']\n"
             "completed = [r for r in rows if r['status'] == 'completed']\n"
             "assert all(not r['test_evaluated'] for r in rows)\n"
             "assert all(math.isfinite(r['val_map50_95']) for r in completed)\n"
             "print('Snapshot verified; input artifact hashes:', len(DATA['artifact_sha256']))\n"),
        md("## 2. Execution and data integrity"),
        code(dedent('''\
            m = DATA['manifest']
            env = m['environment']
            counts = DATA['split_counts']
            display(Markdown(f"Completed **{len(completed)}/{m['planned_runs']}** planned runs. Manifest: **{m['status']}**. Test scored: **no**."))
            display(Markdown(f"Hardware: {env['gpu']} device {env['device_used']}; torch {env['torch']}; Ultralytics {env['ultralytics']}."))
            display(Markdown(f"Frozen image counts: **{counts['train']['images']} train / {counts['val']['images']} validation / {counts['test']['images']} test**. Policy: `{DATA['split_policy']}`; {len(DATA['exclusions'])} exclusions."))
            display(Markdown('All retained labels are unchanged. Test membership is preserved; validation/training membership differs from the raw official splits. Near-duplicate review is not exhaustive.'))
        ''')),
        md("## 3. Validation measurements\n"
           "mAP values below use the 0–1 scale. Runtime is the complete training call, including setup and validation; "
           "it is not a matched-time comparison. Peak allocated VRAM measures training allocations, not total GPU usage."),
        code(dedent('''\
            table = ['| Fraction | Missing-box probability | Optimizer | Seed | Val mAP50–95 | Epochs | Steps | Wall seconds |', '|---:|---:|---|---:|---:|---:|---:|---:|']
            for r in sorted(completed, key=lambda r:(r['data_fraction'],r['noise_probability'],r['optimizer'],r['seed'])):
                table.append(f"| {r['data_fraction']:.0%} | {r['noise_probability']:.0%} | {r['optimizer']} | {r['seed']} | {r['val_map50_95']:.5f} | {r['epochs_completed']} | {r['optimizer_steps']} | {r['training_seconds']:.2f} |")
            display(Markdown('\\n'.join(table)))
        ''')),
        md("## 4. Paired differences\n"
           "Pairing requires matching data fingerprints, initialized parameters, image exposure, steps and epochs. "
           "Differences are descriptive; repeated seeds and fair validation tuning are still required."),
        code("pairs=[]\n"
             "for a in completed:\n"
             "    if a['optimizer'] != 'AdamW': continue\n"
             "    b=next((r for r in completed if r['optimizer']=='MuSGD' and r['seed']==a['seed'] "
             "and r['variant_fingerprint']==a['variant_fingerprint']),None)\n"
             "    if b is None: continue\n"
             "    for k in ['initial_model_state_sha256','images_seen','optimizer_steps','epochs_completed']:\n"
             "        assert a[k]==b[k],k\n"
             "    pairs.append((a['data_fraction'],a['noise_probability'],a['seed'],100*(b['val_map50_95']-a['val_map50_95'])))\n"
             "display(Markdown('\\n'.join(['| Fraction | Missing boxes | Seed | MuSGD − AdamW (AP points) |',"
             "'|---:|---:|---:|---:|']+[f'| {f:.0%} | {n:.0%} | {s} | {d:+.3f} |' for f,n,s,d in pairs])))\n"
             "print('Verified pairs:',len(pairs),'; training seeds:',len({r['seed'] for r in completed}))\n"),
        md("## 5. Validation trajectories\n"
           "Per-epoch training-validation scores can differ slightly from independent validation of the saved best weights. "
           "All panels share an axis scale. Colors and line styles identify optimizers."),
        code("import matplotlib.pyplot as plt\n"
             "conditions=sorted({(r['data_fraction'],r['noise_probability']) for r in completed})\n"
             "cols=min(2,len(conditions)); height=3.5*math.ceil(len(conditions)/cols)\n"
             "fig,axes=plt.subplots(math.ceil(len(conditions)/cols),cols,figsize=(6*cols,height),squeeze=False,sharey=True)\n"
             "colors={'AdamW':'#2166ac','MuSGD':'#d95f02','SGD':'#1b9e77'}\n"
             "styles={'AdamW':'-','MuSGD':'--','SGD':':'}\n"
             "for ax,(fraction,noise) in zip(axes.flat,conditions):\n"
             "    for r in completed:\n"
             "        if (r['data_fraction'],r['noise_probability'])!=(fraction,noise):continue\n"
             "        h=DATA['histories'][r['run_id']]\n"
             "        ax.plot([e['epoch'] for e in h],[e['metrics/mAP50-95(B)'] for e in h],"
             "color=colors[r['optimizer']],linestyle=styles[r['optimizer']],label=f\"{r['optimizer']} seed {r['seed']}\")\n"
             "    ax.set(title=f'{fraction:.0%} training images · {noise:.0%} missing boxes',xlabel='Epoch',ylabel='Validation mAP50–95')\n"
             "    ax.grid(alpha=0.2);ax.legend()\n"
             "for ax in list(axes.flat)[len(conditions):]:ax.set_visible(False)\n"
             "upper=max((max(line.get_ydata()) for ax in axes.flat for line in ax.lines),default=0)*1.08\n"
             "for ax in axes.flat:ax.set_ylim(0,upper or 1)\n"
             "fig.suptitle('Development trajectories — untuned settings; no test evaluation')\n"
             "fig.tight_layout();plt.show()\n"),
        md("## 6. Corruption denominators and actual optimizer settings"),
        code(dedent('''\
            for v in DATA['variants']:
                display(Markdown(f"Variant `{v['variant_id']}`: **{v['train_images']}** images; **{v['removed_objects']}/{v['original_train_objects']}** objects removed (**{v['realized_noise_rate']:.2%}**); **{v['empty_train_labels']}** empty training label files."))
            group_table=['| Optimizer | Group | Parameters | Initial LR | Muon enabled |','|---|---|---:|---:|---|']
            seen=set()
            for r in completed:
                if r['optimizer'] in seen:continue
                seen.add(r['optimizer'])
                for g in r['optimizer_details']['groups']:
                    if not g['parameters']:continue
                    group_table.append(f"| {r['optimizer']} | {g.get('param_group','')} | {g['parameters']} | {g.get('initial_lr',g['lr']):.5f} | {g.get('use_muon',False)} |")
            display(Markdown('\\n'.join(group_table)))
        ''')),
        md("## 7. What this evidence supports\n\n"
           "Successful completion supports the experiment plumbing, deterministic variants and paired initialization checks. "
           "It does not establish a general optimizer advantage, a scarcity/noise interaction, a causal mechanism or significance. "
           "The implemented recipes differ in head LR multipliers and weight-decay behavior, and their LR defaults are untuned.\n\n"
           "Before a final paper: add equal-budget tuning, SGD, repeated training/corruption seeds, an audited external dataset, "
           "defined timing boundaries and a frozen one-shot test protocol. Source annotation quality, image provenance, "
           "pretraining overlap and residual scene overlap remain limitations.\n\n"
           "Source: measured Kaggle outputs identified by the embedded artifact hashes; methodological plans are in "
           "`research/PROTOCOL.md` and `research/RELATED_WORK.md`."),
    ]
    notebook.cells[2].metadata["jupyter"] = {"source_hidden": True}
    # Add class detail and native loss plots before the final limitations section.
    notebook.cells[-1:-1] = [
        md("## Class-specific validation AP\nEach value is the saved best checkpoint's validation AP for that class, on the 0–1 scale."),
        code(dedent('''\
            names=[DATA['class_names'][str(i)] for i in range(len(DATA['class_names']))]
            class_table=['| Fraction | Missing boxes | Optimizer | Seed | '+' | '.join(names)+' |', '|---:|---:|---|---:|'+'---:|'*len(names)]
            for r in completed:
                values=r['val_per_class_map50_95']
                assert len(values)==len(names) and all(0<=v<=1 for v in values)
                prefix=f"| {r['data_fraction']:.0%} | {r['noise_probability']:.0%} | {r['optimizer']} | {r['seed']} | "
                class_table.append(prefix+' | '.join(f'{v:.4f}' for v in values)+' |')
            display(Markdown('\\n'.join(class_table)))
        ''')),
        md("## Training-loss diagnostics\nBox and classification losses use separate panels/scales. Lower training loss alone does not establish generalization or explain an optimizer mechanism."),
        code(dedent('''\
            for field,ylabel in [('train/box_loss','Training box loss'),('train/cls_loss','Training classification loss')]:
                fig,axes=plt.subplots(math.ceil(len(conditions)/cols),cols,figsize=(6*cols,height),squeeze=False,sharey=True)
                for ax,(fraction,noise) in zip(axes.flat,conditions):
                    for r in completed:
                        if (r['data_fraction'],r['noise_probability'])!=(fraction,noise):continue
                        h=DATA['histories'][r['run_id']]
                        ax.plot([e['epoch'] for e in h],[e[field] for e in h],color=colors[r['optimizer']],linestyle=styles[r['optimizer']],label=f"{r['optimizer']} seed {r['seed']}")
                    ax.set(title=f'{fraction:.0%} training images · {noise:.0%} missing boxes',xlabel='Epoch',ylabel=ylabel)
                    ax.grid(alpha=0.2);ax.legend()
                for ax in list(axes.flat)[len(conditions):]:ax.set_visible(False)
                upper=max((max(line.get_ydata()) for ax in axes.flat for line in ax.lines),default=0)*1.08
                for ax in axes.flat:ax.set_ylim(0,upper or 1)
                fig.suptitle(ylabel+' — development settings')
                fig.tight_layout();plt.show()
        ''')),
    ]
    for cell in notebook.cells:
        if cell.cell_type == "code":
            compile(cell.source, "results_notebook_cell", "exec")
    nbf.validate(notebook)
    executed = NotebookClient(notebook, timeout=180, kernel_name="python3", shutdown_kernel="immediate",
                              resources={"metadata": {"path": str(ROOT)}}).execute()
    destination = ROOT / "notebooks" / f"{args.name}.ipynb"
    atomic_text(destination, nbf.writes(executed))
    exporter = HTMLExporter(exclude_input=True, exclude_input_prompt=True, exclude_output_prompt=True)
    html, _ = exporter.from_notebook_node(executed)
    atomic_text(destination.with_suffix(".html"), html)
    nbf.validate(executed)
    errors = [o for c in executed.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "error"]
    assert not errors
    print(f"Executed and saved: {destination}")


if __name__ == "__main__":
    main()
