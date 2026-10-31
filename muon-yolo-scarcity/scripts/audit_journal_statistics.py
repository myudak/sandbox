"""Recalculate reported estimates directly from raw paired training/test rows."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.dataset_variants import digest,save_json


def audit(output):
    rows=json.loads((output/'results.json').read_text());tests=json.loads((output/'final_test_results.json').read_text())
    summary=json.loads((output/'campaign_summary.json').read_text());freeze=json.loads((output/'frozen_final_test_plan.json').read_text())
    assert len(rows)==120 and all(r['status']=='completed' for r in rows)
    assert len(tests)==60 and all(r['status']=='completed' for r in tests)
    assert digest(rows)==summary['input_results_sha256']
    by_id={r['run_id']:r for r in rows};frozen={r['run_id']:r for r in freeze['checkpoints']}
    assert {r['run_id'] for r in tests}==set(frozen)
    for test in tests:
        assert test['freeze_sha256']==digest(freeze)
        assert by_id[test['run_id']]['best_weights_sha256']==frozen[test['run_id']]['best_weights_sha256']
        assert all(math.isfinite(test[k]) and 0<=test[k]<=1 for k in ('test_map50_95','test_map50','test_precision','test_recall'))
    with (output/'results.csv').open(newline='',encoding='utf-8') as stream:
        csv_rows=list(csv.DictReader(stream))
    assert len(csv_rows)==len(rows)
    for record in csv_rows:
        for key in ('val_map50_95','run_call_seconds','images_seen','optimizer_steps'):
            assert float(record[key])==by_id[record['run_id']][key]
    checked=0
    for split in ('validation','frozen_test'):
        for dataset,group in summary[split].items():
            observed=[r for r in rows if r['dataset']==dataset and any(role.startswith(dataset+'_confirmation_') for role in r['roles'])]
            if split=='frozen_test':observed=[{**by_id[t['run_id']],**t} for t in tests if t['dataset']==dataset]
            metric='val_map50_95' if split=='validation' else 'test_map50_95'
            cells={(r['seed'],r['optimizer'],r['data_fraction'],r['noise_probability']):r for r in observed}
            assert group['joint_blocks']==[101,102,103]
            for item in group['conditions']:
                values=[100*cells[s,item['optimizer'],item['fraction'],item['missing_probability']][metric] for s in group['joint_blocks']]
                assert values==item['values'];checked+=1
            for item in group['paired_optimizer_contrasts']:
                optimizer=item['contrast'].split(' minus ')[0];fraction=item['fraction'];noise=item['missing_probability']
                values=[100*(cells[s,optimizer,fraction,noise][metric]-cells[s,'AdamW',fraction,noise][metric]) for s in group['joint_blocks']]
                assert values==item['values'];checked+=1
            for item in group['three_way_interactions']:
                optimizer=item['contrast'].split(' minus ')[0];values=[]
                for seed in group['joint_blocks']:
                    difference={(f,q):100*(cells[seed,optimizer,f,q][metric]-cells[seed,'AdamW',f,q][metric]) for f in (.2,1.) for q in (0.,.2)}
                    values.append(difference[.2,.2]-difference[.2,0.]-difference[1.,.2]+difference[1.,0.])
                assert all(math.isclose(a,b,abs_tol=1e-12) for a,b in zip(values,item['values']));checked+=1
            for family in ('conditions','paired_optimizer_contrasts','three_way_interactions'):
                for item in group[family]:
                    values=item['values'];mean=statistics.mean(values)
                    half=4.302652729696142*statistics.stdev(values)/math.sqrt(3)
                    assert math.isclose(mean,item['mean'],abs_tol=1e-12)
                    assert all(math.isclose(a,b,abs_tol=1e-7) for a,b in zip((mean-half,mean+half),item['ci95']))
    report={'status':'passed_numeric_recalculation','checked_summaries':checked,'training_rows':len(rows),'test_rows':len(tests),
        'freeze_plan_links':'passed','csv_json_agreement':'passed','t_interval_arithmetic':'passed',
        'results_sha256':digest(rows),'test_results_sha256':digest(tests),
        'scope':'Recorded metrics and three-block paired statistics; independent source-image/checkpoint byte rehashing is outside compact evidence audit.'}
    save_json(ROOT/'research/JOURNAL_NUMERIC_AUDIT.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path)
    print(json.dumps(audit(parser.parse_args().output),indent=2))
