"""Freeze input identities after preflight review, before main submission."""
import json
from pathlib import Path
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.dataset_variants import digest,save_json
from src.journal_data import apply_review


def main():
    ledger=json.loads((ROOT/'research/JOURNAL_BUDGET_LEDGER.json').read_text())
    if any(j['kernel'].endswith('/muon-yolo-journal') for j in ledger['jobs']):
        raise RuntimeError('Do not refreeze inputs after campaign reservation/submission')
    output=ROOT/'outputs/kaggle_journal_preflight_v1/muon_yolo_journal_preflight'
    manifest=json.loads((output/'manifest.json').read_text())
    rows=json.loads((output/'results.json').read_text())
    assert manifest['status']=='completed' and len(rows)==6 and all(r['status']=='completed' for r in rows)
    review=json.loads((ROOT/'configs/journal_duplicate_exclusions.json').read_text())
    fingerprints={};datasets={}
    for name in ('wildlife','voc2007'):
        source=json.loads((output/'datasets'/name/'split_audit.json').read_text())
        identity={k:source[k] for k in ('schema','names','records','raw_source_fingerprint','base_fingerprint','near_rule','validation_limit','validation_seed')}
        assert digest(identity)==manifest['dataset_fingerprints'][name]
        if name=='wildlife':
            identity['records'],exclusions=apply_review(identity['records'],source['raw_source_fingerprint'],source['base_fingerprint'],review)
            identity['additional_visual_review_sha256']=digest(review)
        fingerprints[name]=digest(identity)
        datasets[name]={'fingerprint':digest(identity),'raw_source_fingerprint':source['raw_source_fingerprint'],
            'counts':{s:{'images':len(v),'objects':sum(r['objects'] for r in v)} for s,v in identity['records'].items()},
            'test_membership_unchanged':identity['records']['test']==source['records']['test']}
    freeze={'frozen_utc':datetime.now(timezone.utc).isoformat(),'preflight_version':1,'preflight_results_sha256':digest(rows),
        'review_basis':'Input-only candidate sheets, not model performance','wildlife_additional_review_sha256':digest(review),
        'datasets':datasets,'voc_candidate_review':'23 dHash candidates shown; no same-scene pair apparent in reviewed sheet; no extra visual exclusion. Screen is not exhaustive.',
        'preflight_to_main_code_changes':'GPU training/sampling logic unchanged. Added conservative source-bound training-image exclusion, per-run metadata persistence, evidence auditing and reporting.'}
    save_json(ROOT/'research/JOURNAL_DATA_FREEZE.json',freeze)
    plan_path=ROOT/'research/JOURNAL_PLAN.json';plan=json.loads(plan_path.read_text())
    plan['expected_dataset_fingerprints']=fingerprints
    plan['deduplication']['additional_visual_review_manifest']='configs/journal_duplicate_exclusions.json'
    plan['deduplication']['additional_visual_review_sha256']=digest(review)
    plan['deduplication']['review_chronology']='One additional likely same-scene wildlife training image excluded after preflight input review, before main submission; pilot remains unchanged.'
    save_json(plan_path,plan)
    ledger['jobs'][0].update(state='completed',completed_runs=6,reported_execution_seconds=manifest['elapsed_notebook_seconds'],
        evidence='outputs/kaggle_journal_preflight_v1',evidence_audit='passed')
    save_json(ROOT/'research/JOURNAL_BUDGET_LEDGER.json',ledger)
    print(json.dumps(freeze,indent=2))


if __name__=='__main__':main()
