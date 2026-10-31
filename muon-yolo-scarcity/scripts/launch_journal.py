"""Submit one journal notebook only after reserving its full runtime cap."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from build_notebook import atomic_text

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['preflight','campaign'],required=True)
    args=parser.parse_args()
    plan_path=ROOT/'research/JOURNAL_PLAN.json';ledger_path=ROOT/'research/JOURNAL_BUDGET_LEDGER.json'
    plan=json.loads(plan_path.read_text());ledger=json.loads(ledger_path.read_text())
    cap=plan['preflight_cap_seconds' if args.mode=='preflight' else 'main_cap_seconds']
    total=sum(job['cap_seconds'] for job in ledger['jobs'])
    if total+cap>min(plan['authorized_additional_notebook_seconds'],ledger['authorized_seconds']):
        raise ValueError(f"Runtime cap would exceed authorization: {total}+{cap} > 43200 seconds")
    subprocess.run([sys.executable,str(ROOT/'scripts/build_journal_notebook.py'),'--mode',args.mode],check=True,cwd=ROOT)
    folder=ROOT/'kaggle'/('journal_preflight' if args.mode=='preflight' else 'journal')
    metadata=json.loads((folder/'kernel-metadata.json').read_text())
    from src.dataset_variants import digest,file_hash
    from src.experiment import code_fingerprint
    job={'kernel':metadata['id'],'version':None,'cap_seconds':cap,'state':'reserved_before_submission',
        'reserved_utc':datetime.now(timezone.utc).isoformat(),'plan_sha256':digest(plan),
        'notebook_sha256':file_hash(folder/metadata['code_file']),'code_sha256':code_fingerprint()}
    ledger['jobs'].append(job)
    ledger.update(reserved_or_submitted_seconds=total+cap,remaining_unallocated_seconds=ledger['authorized_seconds']-total-cap)
    atomic_text(ledger_path,json.dumps(ledger,indent=2)+'\n')
    completed=subprocess.run(['kaggle','kernels','push','-p',str(folder),'-t',str(cap)],capture_output=True,text=True,encoding='utf-8',errors='replace',cwd=ROOT)
    print(completed.stdout);print(completed.stderr)
    job['submission_output']=completed.stdout+completed.stderr
    match=re.search(r'Kernel version (\d+) successfully pushed',completed.stdout)
    job['state']='submitted' if match else 'submission_unknown_reservation_retained'
    if match:job['version']=int(match.group(1))
    atomic_text(ledger_path,json.dumps(ledger,indent=2)+'\n')
    if completed.returncode:raise SystemExit(completed.returncode)
    if not match:raise RuntimeError('Submission response unclear; reconcile server state before any retry')


if __name__=='__main__':
    sys.path.insert(0,str(ROOT))
    main()
