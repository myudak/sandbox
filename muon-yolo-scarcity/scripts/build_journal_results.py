"""Audit completed campaign evidence and build a portable CPU results companion."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import sys

import nbformat as nbf
from nbclient import NotebookClient
from nbconvert import HTMLExporter

from audit_journal_evidence import audit
from build_notebook import atomic_text

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.dataset_variants import digest


def build(output):
    verified=audit(output)
    rows=json.loads((output/'results.json').read_text())
    if not any(any('confirmation_' in role for role in r.get('roles',[])) for r in rows):
        raise ValueError('Preflight/tuning alone cannot be presented as journal confirmation')
    summary=json.loads((output/'campaign_summary.json').read_text())
    if summary['input_results_sha256']!=digest(rows):raise ValueError('Summary does not match trial ledger')
    images={p.name:base64.b64encode(p.read_bytes()).decode() for p in output.glob('journal_*.png')}
    snapshot={'results':rows,'summary':summary,'audit':verified,
        'selected_hyperparameters':json.loads((output/'selected_hyperparameters.json').read_text()) if (output/'selected_hyperparameters.json').exists() else None}
    payload=json.dumps(snapshot,allow_nan=False)
    cells=[nbf.v4.new_markdown_cell('''# Journal campaign: measured evidence review

This is a portable CPU-only companion to a retrieved Kaggle campaign. It embeds measured records, selection metadata and figure snapshots. It does not train a model, access the network or require Kaggle credentials. Validation and frozen test estimates stay separate. Partial campaigns and incomplete blocks remain explicit. The independent interval arithmetic below checks the reported approximate t intervals; this is not an image bootstrap or an adjusted significance analysis.
'''),nbf.v4.new_code_cell(f'''import base64, hashlib, json, math, statistics
from IPython.display import display, Markdown, Image, HTML
from html import escape
def table(records,columns=None):
    if not records: return Markdown('_No records._')
    columns=columns or list(dict.fromkeys(key for row in records for key in row))
    header=''.join('<th>'+escape(str(key))+'</th>' for key in columns)
    body=''.join('<tr>'+''.join('<td>'+escape(json.dumps(row.get(key)) if isinstance(row.get(key),(list,dict)) else str(row.get(key,'')))+'</td>' for key in columns)+'</tr>' for row in records)
    return HTML('<div style="overflow-x:auto"><table><thead><tr>'+header+'</tr></thead><tbody>'+body+'</tbody></table></div>')
payload={payload!r}
assert hashlib.sha256(payload.encode()).hexdigest()=={hashlib.sha256(payload.encode()).hexdigest()!r}
snapshot=json.loads(payload)
summary=snapshot['summary']
print('Campaign status:',summary['status'])
print('Frozen test status:',summary['test_status'])
print('Unique attempted runs:',summary['attempted_runs'])
print('Failure count:',len(summary['failed_runs']))
print('Incomplete confirmation blocks:',summary['incomplete_confirmation_blocks'])
print('Skipped stages:',summary['skipped'])
display(table(snapshot['results'],['dataset','roles','optimizer','seed','data_fraction','noise_probability','status','images_seen','optimizer_steps','val_map50_95']))
'''),nbf.v4.new_markdown_cell('## Selection and block estimates\nSettings were selected on wildlife validation anchors only, at a shorter tuning horizon. VOC settings were transferred without VOC tuning. Joint blocks vary training, subset and deletion seeds together.'),
    nbf.v4.new_code_cell('''print(json.dumps(snapshot['selected_hyperparameters'],indent=2))
# Independent small-sample interval arithmetic, using fixed two-sided t critical values.
critical={1:12.706204736432095,2:4.302652729696142,3:3.182446305284263,4:2.7764451051977987}
checked=0
for split in ('validation','frozen_test'):
    for dataset,group in summary[split].items():
        display(Markdown(f'### {dataset}: {split}; joint blocks {group["joint_blocks"]}'))
        for family in ('conditions','paired_optimizer_contrasts','three_way_interactions'):
            for item in group[family]:
                values=item['values']; n=len(values)
                assert n==item['n_joint_blocks']==len(group['joint_blocks'])
                assert math.isclose(statistics.mean(values),item['mean'],abs_tol=1e-10)
                if n==1:assert item['ci95'] is None
                else:
                    half=critical[n-1]*statistics.stdev(values)/n**.5
                    assert all(math.isclose(a,b,abs_tol=1e-6) for a,b in zip(item['ci95'],[item['mean']-half,item['mean']+half]))
                checked+=1
            display(table(group[family]))
print('Verified summary intervals/means:',checked)
display(table(summary['failed_runs']))
print('Limitations:')
for limitation in summary['limitations']: print('-',limitation)
'''),nbf.v4.new_markdown_cell('## Saved measured figures\nNative Matplotlib figures from the archived campaign. Bars/points and intervals must be interpreted with the reported block count and partial-stage status.'),
    nbf.v4.new_code_cell(f'''figures={images!r}
for name,encoded in figures.items():
    print(name)
    display(Image(data=base64.b64decode(encoded)))
''')]
    notebook=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'},'evidence_payload_sha256':hashlib.sha256(payload.encode()).hexdigest()})
    try:
        NotebookClient(notebook,timeout=180,kernel_name='python3',shutdown_kernel='immediate').execute()
    except Exception as error:
        # A failed cell can contain a large immutable snapshot; retain bounded diagnostics.
        raise RuntimeError(str(error)[-2000:]) from None
    assert not any(out.output_type=='error' for cell in notebook.cells if cell.cell_type=='code' for out in cell.outputs)
    path=ROOT/'notebooks/journal_results_review.ipynb';atomic_text(path,nbf.writes(notebook))
    html,_=HTMLExporter().from_notebook_node(notebook);atomic_text(path.with_suffix('.html'),html)
    report=output/'CAMPAIGN_FINDINGS.md'
    if report.exists():shutil.copy2(report,ROOT/'research/JOURNAL_FINDINGS.md')
    tex=[r'\noindent\textbf{Campaign status:} '+summary['status'].replace('_',r'\_')+r'. Frozen test status: '+summary['test_status'].replace('_',r'\_')+'.',
        r'\par All intervals below are approximate paired joint-block $t$ intervals in AP points. Cell comparisons are exploratory. Incomplete blocks and failures remain in the full ledger.']
    for split in ('validation','frozen_test'):
        for dataset,group in summary[split].items():
            tex += [r'\subsubsection{'+dataset.replace('_',r'\_')+': '+split.replace('_',' ')+r'}',
                'Completed joint blocks: '+', '.join(map(str,group['joint_blocks']))+'.',
                r'\begin{center}\begin{tabular}{llrrr}\toprule',
                r'Recipe difference & Images & Missing & Mean & 95\% interval\\\midrule']
            for row in group['paired_optimizer_contrasts']:
                ci=row['ci95'];ci_text='--' if ci is None else f"[{ci[0]:.2f}, {ci[1]:.2f}]"
                tex.append(f"{row['contrast']} & {row['fraction']:.0%} & {row['missing_probability']:.0%} & {row['mean']:+.2f} & {ci_text}".replace('%',r'\%')+r'\\')
            tex += [r'\bottomrule\end{tabular}\end{center}']
            for interaction in group['three_way_interactions']:
                ci=interaction['ci95'];ci_text='not estimated' if ci is None else f'[{ci[0]:.3f}, {ci[1]:.3f}]'
                tex.append(interaction['contrast'].replace(' x ',r' $\times$ ')+f": {interaction['mean']:+.3f} AP points; approximate 95\\% interval {ci_text}.")
    tex += [f"Unique attempted training runs: {summary['attempted_runs']}; unsuccessful/budget-stopped runs: {len(summary['failed_runs'])}.",
        r'\par These estimates retain the finite-search and three-block limitations. Submission readiness also requires authorship, venue selection and complete literature and image-rights statements.']
    atomic_text(ROOT/'paper/journal_results.tex','\n'.join(tex)+'\n')
    print(json.dumps({'notebook':str(path),'evidence_audit':'passed','status':summary['status'],'test_status':summary['test_status']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    build(parser.parse_args().output.resolve())
