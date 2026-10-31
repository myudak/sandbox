"""One-shot collection after completion; never polls or submits another job."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.dataset_variants import save_json


def main():
    publication_path=ROOT/'research/PUBLICATION_STATUS.json'
    if publication_path.exists():
        publication=json.loads(publication_path.read_text(encoding='utf-8'))
        if publication.get('publication_version')!=publication.get('training_result_version'):
            raise SystemExit(
                'The latest Kaggle version is a presentation save, not the frozen training version. '
                'Preserve outputs/kaggle_journal_v1; inspect the version-specific evidence_url in '
                'research/PUBLICATION_STATUS.json. Re-audit the existing evidence with '
                'python scripts/audit_journal_evidence.py outputs/kaggle_journal_v1/muon_yolo_journal. '
                'The publication manuscript includes are curated and must not be overwritten by this collector.'
            )
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi();api.authenticate()
    kernel='myudak/muon-yolo-journal'
    status=api.kernels_status(kernel)
    state=str(status.get('status','')) if isinstance(status,dict) else str(status.status)
    if any(word in state.lower() for word in ('running','queued')):
        raise SystemExit(f'Campaign is still {state}; no final evidence collected and no new notebook launched')
    destination=ROOT/'outputs/kaggle_journal_v1'
    subprocess.run([sys.executable,str(ROOT/'scripts/kaggle_evidence.py'),'--kernel',kernel,'--output',str(destination),'--resume'],check=True,cwd=ROOT)
    evidence=destination/'muon_yolo_journal'
    subprocess.run([sys.executable,str(ROOT/'scripts/audit_journal_evidence.py'),str(evidence)],check=True,cwd=ROOT)
    manifest=json.loads((evidence/'manifest.json').read_text())
    ledger_path=ROOT/'research/JOURNAL_BUDGET_LEDGER.json';ledger=json.loads(ledger_path.read_text())
    job=next(j for j in ledger['jobs'] if j['kernel']==kernel and j['version']==1)
    assert manifest['identity']['code_sha256']==job['code_sha256']
    assert manifest['identity']['plan_sha256']==job['plan_sha256']
    job.update(state=manifest['status'],reported_execution_seconds=manifest['elapsed_notebook_seconds'],
        evidence='outputs/kaggle_journal_v1',completed_runs=manifest['completed_runs'],evidence_audit='passed',test_evaluated=manifest.get('test_evaluated',False))
    save_json(ledger_path,ledger)
    rows=json.loads((evidence/'results.json').read_text())
    if any(any('confirmation_' in role for role in r.get('roles',[])) for r in rows):
        subprocess.run([sys.executable,str(ROOT/'scripts/build_journal_results.py'),str(evidence)],check=True,cwd=ROOT)
    else:print('No confirmation stage reached; preserve partial/failure evidence without a confirmatory report.')
    print(json.dumps({'manifest_status':manifest['status'],'evidence':str(evidence),'runtime_caps_reserved':sum(j['cap_seconds'] for j in ledger['jobs'])}))


if __name__=='__main__':main()
