from pathlib import Path
import subprocess
import sys
import shutil

CHECKER=Path(__file__).resolve().parents[1]/'scripts/check_staged.py'

def stage(tmp_path,path,text,checker=CHECKER):
    subprocess.run(['git','init','-q'],cwd=tmp_path,check=True)
    file=tmp_path/path; file.parent.mkdir(parents=True,exist_ok=True); file.write_text(text)
    subprocess.run(['git','add',str(path)],cwd=tmp_path,check=True)
    return subprocess.run([sys.executable,str(checker)],cwd=tmp_path,text=True,capture_output=True)

def test_private_dataset_staging_rejected_without_printing_contents(tmp_path):
    result=stage(tmp_path,Path('private/raw.jsonl'),'synthetic content that must never be printed')
    assert result.returncode==1
    assert 'synthetic content' not in result.stdout

def test_key_pattern_rejected_without_printing_value(tmp_path):
    fake='sk-proj-'+'x'*25
    result=stage(tmp_path,Path('settings.txt'),'token='+fake)
    assert result.returncode==1
    assert fake not in result.stdout


def test_monorepo_synthetic_fixture_is_allowed(tmp_path):
    checker=tmp_path/'chatdna/scripts/check_staged.py'
    checker.parent.mkdir(parents=True)
    shutil.copyfile(CHECKER,checker)
    result=stage(tmp_path,Path('chatdna/data/synthetic/example.jsonl'),'{"text":"synthetic fixture"}',checker)
    assert result.returncode==0
