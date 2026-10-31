"""Publish the reviewed CPU-only results report to the existing public notebook."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'kaggle/journal_public_report'
    metadata=json.loads((folder/'kernel-metadata.json').read_text())
    path=folder/metadata['code_file']
    assert path.read_bytes().isascii(),'Use ASCII JSON escapes to avoid Windows CLI source mojibake'
    notebook=json.loads(path.read_text())
    record_path=ROOT/'research/INTERACTIVE_REPORT_STATUS.json'
    record=json.loads(record_path.read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==record['notebook_sha256']
    assert metadata['id_no']==140671190 and metadata['id']=='myudak/muon-yolo-journal'
    assert metadata['is_private'] is False and metadata['enable_gpu'] is False and metadata['enable_internet'] is False
    assert record['status']=='executed_locally','Do not blindly resubmit an already published report'
    for cell in notebook['cells']:
        if cell['cell_type']!='code':continue
        source=''.join(cell['source'])
        assert cell['metadata']['_kg_hide-input'] is True
        assert not any(o.get('output_type')=='error' for o in cell['outputs'])
        tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):assert not any(a.name.split('.')[0] in {'torch','ultralytics','subprocess','kaggle','kagglehub'} for a in node.names)
            if isinstance(node,ast.ImportFrom):assert not node.module.startswith(('torch','ultralytics','src.','kaggle','subprocess'))
    # Record the intended mutation before the single request. An uncertain response needs readback, not retry.
    record.update(status='publication_request_started',publication_request_utc=datetime.now(timezone.utc).isoformat(),
        report_runtime_cap_seconds=180,report_compute='CPU only; charts and exports; no model training')
    record_path.write_text(json.dumps(record,indent=2)+'\n')
    from kaggle.api.kaggle_api_extended import KaggleApi
    api=KaggleApi();api.authenticate()
    response=api.kernels_push(str(folder),timeout='180')
    result={key:getattr(response,key) for key in ('ref','url','version_number','error','kernel_id')}
    record.update(publication_response=result,status='submitted' if not response.error and response.version_number else 'publication_response_requires_review')
    record_path.write_text(json.dumps(record,indent=2)+'\n')
    if response.error:raise RuntimeError(response.error)
    print(json.dumps(result))


if __name__=='__main__':main()
