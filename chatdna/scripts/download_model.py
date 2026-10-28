"""Download public, pinned model weights over resumable HTTPS; no private input."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

MODEL='Qwen/Qwen3-0.6B'
REVISION='c1899de289a04d12100db370d81485cdf75e47ca'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(f'https://huggingface.co/api/models/{MODEL}/tree/{REVISION}',timeout=30) as response:
        metadata=json.load(response)
    files={item['path']:item for item in metadata if item['type']=='file'}
    for name in ('config.json','generation_config.json','tokenizer.json','tokenizer_config.json','merges.txt','vocab.json','LICENSE','model.safetensors'):
        target=args.output/name
        info=files[name]
        expected_size=info['size']
        expected_hash=info.get('lfs',{}).get('oid')
        if target.exists() and target.stat().st_size==expected_size:
            if not expected_hash:
                continue
            with target.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()==expected_hash:
                    continue
        partial=target.with_suffix(target.suffix+'.partial')
        for attempt in range(8):
            offset=partial.stat().st_size if partial.exists() else 0
            if offset==expected_size:
                break
            # A fresh query avoids stale cached range responses at proxies.
            url=f'https://huggingface.co/{MODEL}/resolve/{REVISION}/{name}?download=true&part={offset}&attempt={attempt}'
            request=urllib.request.Request(url,headers={'Range':f'bytes={offset}-','Cache-Control':'no-cache'})
            try:
                with urllib.request.urlopen(request,timeout=45) as response:
                    if offset and response.status!=206:
                        raise ValueError('Server did not honor resume range')
                    written=offset
                    last_log=offset
                    with partial.open('ab' if offset else 'wb') as stream:
                        while chunk:=response.read(1024*1024):
                            stream.write(chunk)
                            written+=len(chunk)
                            if written-last_log>=64*1024*1024:
                                print(name,round(100*written/expected_size,1),'percent',flush=True)
                                last_log=written
                if partial.stat().st_size==expected_size:
                    break
            except Exception as error:
                print('Download retry',attempt+1,type(error).__name__,'(URL details withheld)',flush=True)
                time.sleep(min(5,attempt+1))
        if not partial.exists() or partial.stat().st_size!=expected_size:
            raise RuntimeError('Incomplete public weight download; partial preserved')
        if expected_hash:
            with partial.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=expected_hash:
                    raise ValueError('Model SHA-256 mismatch')
        partial.replace(target)
        print('Verified public file:',name,flush=True)
    (args.output/'download_manifest.json').write_text(json.dumps({'model':MODEL,'revision':REVISION,'license':'Apache-2.0','weights_sha256':files['model.safetensors']['lfs']['oid']},indent=2))

if __name__=='__main__':
    main()
