"""Download compact evidence with pagination (CLI 2.0.2 output omits later pages)."""
import argparse
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from kaggle.api.kaggle_api_extended import KaggleApi, ApiListKernelSessionOutputRequest
from artifact_paths import comparable_path

parser = argparse.ArgumentParser()
parser.add_argument("--kernel", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument('--workers',type=int,default=4)
parser.add_argument('--include-predictions',action='store_true',help='Include potentially large per-image prediction JSON files')
parser.add_argument('--resume',action='store_true',help='Reuse atomically saved files from this same immutable notebook version; final identity audit is still required')
args = parser.parse_args()
pattern = r"^(?!.*(?:/images/|/labels/)).*(?:\.json|\.csv|\.png|\.svg|\.md|\.yaml|\.txt|\.log|\.ipynb)$"
if not 1<=args.workers<=8:raise ValueError('Use 1 to 8 bounded download workers')
owner, slug = args.kernel.split("/")
api = KaggleApi()
api.authenticate()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
token, pages, downloaded = None, 0, []
log_saved = False
def download(item):
    name,url=item
    if PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive or '..' in PurePosixPath(name.replace('\\','/')).parts:
        raise ValueError(f'Unsafe remote artifact name: {name!r}')
    root=Path(str(output)).resolve()
    destination = (root / name).resolve()
    if not Path(comparable_path(destination)).is_relative_to(Path(comparable_path(root))):raise ValueError(f'Output path escapes destination: {name!r}; resolved={str(destination)!r}; root={str(root)!r}')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if args.resume and destination.is_file() and destination.stat().st_size and destination.suffix!='.json':
        return name
    if args.resume and destination.is_file() and destination.suffix=='.json':
        try:
            json.loads(destination.read_text(encoding='utf-8'))
            return name
        except (ValueError,UnicodeError):pass
    temporary=destination.with_suffix(destination.suffix+'.download')
    for attempt in range(3):
        try:
            with requests.get(url,timeout=120,stream=True) as result:
                result.raise_for_status()
                with temporary.open('wb') as stream:
                    for chunk in result.iter_content(1024*1024):stream.write(chunk)
            break
        except requests.RequestException:
            if attempt==2:raise
            time.sleep(attempt+1)
    temporary.replace(destination)
    return name
with api.build_kaggle_client() as client:
    while True:
        request = ApiListKernelSessionOutputRequest()
        request.user_name, request.kernel_slug = owner, slug
        request.page_token = token
        request.page_size = 200
        response = client.kernels.kernels_api_client.list_kernel_session_output(request)
        pages += 1
        selected=[(str(item.file_name),str(item.url)) for item in response.files or [] if re.search(pattern,item.file_name) and (args.include_predictions or not item.file_name.endswith('/predictions.json'))]
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            downloaded.extend(executor.map(download,selected))
        print(f'Evidence page {pages}: {len(downloaded)} files retrieved/reused',flush=True)
        if response.log and not log_saved:
            (output / f"{slug}.log").write_text(response.log, encoding="utf-8")
            log_saved = True
        token = response.next_page_token
        if not token:
            break
(output / "retrieval.json").write_text(json.dumps({"kernel": args.kernel, "pages": pages,
    "downloaded": downloaded}, indent=2), encoding="utf-8")
print(f"Downloaded {len(downloaded)} evidence files over {pages} pages to {output}")
