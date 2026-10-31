"""Audit retrieved journal evidence without importing CUDA or opening test images."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.dataset_variants import digest,file_hash,save_json
from src.metrics import read_history


def audit(output):
    manifest=json.loads((output/'manifest.json').read_text())
    plan=json.loads((output/'frozen_plan_before_training.json').read_text())
    assert digest(plan)==manifest['identity']['plan_sha256']
    rows=json.loads((output/'results.json').read_text())
    assert len({r['run_id'] for r in rows})==len(rows)
    assert manifest['completed_runs']==sum(r['status']=='completed' for r in rows)
    variants={};code=manifest['identity']['code_sha256']
    for name,expected in manifest.get('dataset_fingerprints',{}).items():
        source=json.loads((output/'datasets'/name/'split_audit.json').read_text())
        identity={k:source[k] for k in ('schema','names','records','raw_source_fingerprint','base_fingerprint','near_rule','validation_limit','validation_seed')}
        if 'additional_visual_review_sha256' in source:identity['additional_visual_review_sha256']=source['additional_visual_review_sha256']
        assert digest(identity)==source['fingerprint']==expected
        if name in plan.get('expected_dataset_fingerprints',{}):assert expected==plan['expected_dataset_fingerprints'][name]
        assert source['test_membership_unchanged']
        assert len(source['records']['test'])==source['counts']['test']['images']
        for path in (output/'datasets'/name/'variants').glob('*/manifest.json'):
            variant=json.loads(path.read_text());assert digest({'config':variant['config'],'train':variant['records']['train']})==variant['fingerprint']
            variants[variant['fingerprint']]=variant
    orders={};initial={}
    for row in rows:
        attempt=output/'runs'/row['run_id']/f"attempt-{row['attempt']:03d}"
        spec=json.loads((attempt/'run_spec.json').read_text())
        assert digest(spec)==row['spec_sha256']
        assert spec['code_sha256']==code
        assert spec['variant_fingerprint']==row['variant_fingerprint']
        assert row['variant_fingerprint'] in variants
        assert row['train_images']==variants[row['variant_fingerprint']]['train_images']
        if row['status']!='completed':continue
        history=read_history(attempt/'train/results.csv')
        assert len(history)==row['epochs_completed']==row['epochs_budget']
        import math
        assert all(math.isfinite(v) for item in history for v in item.values())
        assert row['images_seen']==row['samples_per_epoch']*row['epochs_budget']
        assert row['optimizer_steps']==row['images_seen']//16
        assert row['actual_train_images']==row['train_images']
        assert row['optimizer_details']['class']==row['optimizer']
        assert 0<=row['val_map50_95']<=1
        key=(row['dataset'],row['seed'],row['variant_fingerprint'],digest(row['sampling']),row['epochs_budget'])
        assert orders.setdefault(key,row['exposure_order_sha256'])==row['exposure_order_sha256']
        init=(row['dataset'],row['seed'],row['variant_fingerprint'])
        assert initial.setdefault(init,row['initial_model_state_sha256'])==row['initial_model_state_sha256']
    tests=[]
    if (output/'final_test_results.json').exists():
        freeze=json.loads((output/'frozen_final_test_plan.json').read_text());assert freeze['plan_sha256']==digest(plan)
        assert freeze['code_sha256']==code
        by_id={r['run_id']:r for r in rows}
        checkpoints={r['run_id']:r for r in freeze['checkpoints']}
        assert len(checkpoints)==len(freeze['checkpoints'])
        tests=json.loads((output/'final_test_results.json').read_text())
        assert len({r['run_id'] for r in tests})==len(tests)
        for test in tests:
            assert test['freeze_sha256']==digest(freeze)
            row=by_id[test['run_id']];frozen=checkpoints[test['run_id']]
            assert row['best_weights_sha256']==frozen['best_weights_sha256']
            if test['status']=='completed':assert 0<=test['test_map50_95']<=1
    report={'status':'passed','checks':'Plan, code/spec, data/variant identities, finite histories, actual exposure/steps, optimizer identity, paired order/initialization and final-test freeze linkage',
        'manifest_status':manifest['status'],'training_rows':len(rows),'completed_training_rows':sum(r['status']=='completed' for r in rows),
        'test_rows':len(tests),'test_evaluated':manifest.get('test_evaluated',False),
        'results_file_sha256':file_hash(output/'results.json'),
        'limits':'Compact evidence audit verifies recorded hashes and internal consistency. Source image bytes and saved checkpoint bytes require separate retrieval to independently rehash.'}
    save_json(output/'local_evidence_audit.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    print(json.dumps(audit(parser.parse_args().output),indent=2))
