"""Compare executed Kaggle report artifacts against the locally reviewed report."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main(remote):
    local=ROOT/'output/kaggle_report'
    expected=('paired-effects','absolute-scores','primary-interaction','validation-search','learning-curves')
    # This is a round-trip check, including encoding, chart controls and all plotted values.
    for name in ('reviewed_evidence.json','figure_specs.json'):
        assert json.loads((local/name).read_text(encoding='utf-8'))==json.loads((remote/name).read_text(encoding='utf-8')),name
    with (local/'trial_metrics.csv').open(newline='',encoding='utf-8') as a,(remote/'trial_metrics.csv').open(newline='',encoding='utf-8') as b:
        left=list(csv.DictReader(a));right=list(csv.DictReader(b))
        assert left==right and len(right)==120
    for name in expected:
        content=(remote/(name+'.html')).read_text(encoding='utf-8')
        assert 'plotly.min.js' in content and f'id="{name}"' in content
        assert 'Plotly.newPlot' in content
        assert not any(marker in content for marker in ('Ã—','Â·','âˆ’','\ufffd'))
    assert (remote/'plotly.min.js').stat().st_size>1000000
    offline=(remote/'muon_yolo_results_explorer.html').read_text(encoding='utf-8')
    assert 'yuda@myudak.com' in offline and '361947826' in offline
    assert 'plotly.js v' in offline and all(f'id="{name}"' in offline for name in expected)
    report={'status':'passed_remote_round_trip','source':str(remote.relative_to(ROOT)),
        'training_rows':len(right),'interactive_figures':len(expected),'chart_specs_and_controls_equal':True,
        'numeric_evidence_equal':True,'unicode_labels_equal':True,'self_contained_html':True,
        'artifact_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in remote.iterdir() if path.is_file()}}
    (ROOT/'research/INTERACTIVE_REPORT_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='artifact_sha256'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('remote',type=Path)
    main(parser.parse_args().remote.resolve())
