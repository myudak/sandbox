"""Build private, self-contained Kaggle journal notebooks with atomic writes."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import zipfile

import nbformat as nbf
from build_notebook import atomic_text

ROOT=Path(__file__).resolve().parents[1]


def build(mode):
    plan=json.loads((ROOT/'research/JOURNAL_PLAN.json').read_text())
    cap=plan['preflight_cap_seconds' if mode=='preflight' else 'main_cap_seconds']
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        paths=sorted([*(ROOT/'src').glob('*.py'),*(ROOT/'configs').glob('*.yaml'),*(ROOT/'configs').glob('*.json'),
            *(ROOT/'tests').glob('test_*.py'),ROOT/'requirements.txt',ROOT/'research/JOURNAL_PLAN.json'])
        for path in paths:
            info=zipfile.ZipInfo(path.relative_to(ROOT).as_posix(),(2026,10,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,path.read_bytes())
    bundle=buffer.getvalue();encoded=base64.b64encode(bundle).decode()
    name='muon_yolo_journal_preflight' if mode=='preflight' else 'muon_yolo_journal'
    cells=[nbf.v4.new_markdown_cell(f'''# MuSGD × YOLO26 journal development: {mode}

Private research execution. Notebook cap: **{cap} seconds**, including installation and preparation. Training uses one Kaggle T4. No training runs on the user's laptop.

The frozen plan is embedded with inspectable source and tests. Primary comparisons use 1,280 updates and 20,480 image exposures for every condition. Validation-only tuning uses 10 exposure blocks; settings transfer to 20-block confirmation. Independent paired blocks vary training/subset/annotation seeds jointly. VOC2007 official splits are converted with all difficult objects included; scores are not official VOC AP.

Test metrics are opened only after the complete mandatory confirmation grid and a checkpoint freeze. Failures and budget shortfalls remain visible. A completed notebook is not a publication or novelty claim.
'''),nbf.v4.new_code_cell('%pip install -q "ultralytics==8.4.187" "PyYAML==6.0.3" "matplotlib>=3.8,<4" "Pillow>=10" "pytest>=8,<10"'),
    nbf.v4.new_code_cell(f'''from pathlib import Path
import base64, hashlib, io, json, os, subprocess, sys, traceback, zipfile
WORKING=Path('/kaggle/working')
PROJECT=WORKING/'journal_source'
PROJECT.mkdir(parents=True,exist_ok=True)
bundle=base64.b64decode({encoded!r})
assert hashlib.sha256(bundle).hexdigest()=={hashlib.sha256(bundle).hexdigest()!r}
with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
    assert all((PROJECT/member).resolve().is_relative_to(PROJECT.resolve()) for member in archive.namelist())
    archive.extractall(PROJECT)
sys.path.insert(0,str(PROJECT))
os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
subprocess.run([sys.executable,'-m','pytest','-q',str(PROJECT/'tests')],cwd=PROJECT,check=True)
plan=json.loads((PROJECT/'research/JOURNAL_PLAN.json').read_text())
print(json.dumps(plan,indent=2))
'''),nbf.v4.new_markdown_cell('## Execute the bounded plan\nImages and source annotations remain in temporary storage. Output contains manifests, histories, checkpoints, numeric results and a private duplicate-review sheet. Do not redistribute source photographs.'),
    nbf.v4.new_code_cell(f'''from src.journal import Campaign
OUTPUT=WORKING/{name!r}
try:
    campaign=Campaign(OUTPUT,plan,{cap-120},preflight={mode=='preflight'!r})
    campaign.run()
except Exception:
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'notebook_failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
    raise
'''),nbf.v4.new_code_cell('''print((OUTPUT/'CAMPAIGN_FINDINGS.md').read_text())
print(json.dumps(json.loads((OUTPUT/'manifest.json').read_text()),indent=2))
''')]
    notebook=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}})
    nbf.validate(notebook)
    path=ROOT/'notebooks'/f'{name}.ipynb';atomic_text(path,nbf.writes(notebook))
    folder=ROOT/'kaggle'/('journal_preflight' if mode=='preflight' else 'journal');folder.mkdir(parents=True,exist_ok=True)
    atomic_text(folder/path.name,nbf.writes(notebook))
    slug='muon-yolo-journal-preflight' if mode=='preflight' else 'muon-yolo-journal'
    atomic_text(folder/'kernel-metadata.json',json.dumps({'id':f'myudak/{slug}','title':slug.replace('-',' ').title(),
        'code_file':path.name,'language':'python','kernel_type':'notebook','is_private':True,'enable_gpu':True,
        'enable_internet':True,'machine_shape':'NvidiaTeslaT4','dataset_sources':[],'competition_sources':[],
        'kernel_sources':[],'model_sources':[]},indent=2)+'\n')
    print(json.dumps({'notebook':str(path),'bundle_sha256':hashlib.sha256(bundle).hexdigest(),'cap':cap}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['preflight','campaign'],required=True)
    build(parser.parse_args().mode)
