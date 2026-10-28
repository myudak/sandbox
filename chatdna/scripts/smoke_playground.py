"""Exercise local HTTP inference while printing aggregate results only."""
import argparse
import json
import re
import urllib.request
import urllib.error
from chatdna.runtime import save_json

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--url',default='http://127.0.0.1:8765'); parser.add_argument('--output',required=True); args=parser.parse_args()
    with urllib.request.urlopen(args.url,timeout=10) as response:
        page=response.read().decode()
        assert response.status==200 and 'ChatDNA' in page
    token=re.search(r"const token='([^']+)'",page).group(1)
    with urllib.request.urlopen(args.url+'/api/models',timeout=10) as response:
        registry=json.load(response)
    assert len(registry['models'])==3 and all(m['available'] for m in registry['models'])
    results={'html_status':200,'available_models':3,'generation':[]}
    for invalid_origin,session_token,expected in [(None,'invalid',403),('https://example.org',token,403)]:
        headers={'Content-Type':'application/json','X-Local-Token':session_token}
        if invalid_origin:headers['Origin']=invalid_origin
        request=urllib.request.Request(args.url+'/api/generate',data=json.dumps({'model':'baseline','prompt':'synthetic test'}).encode(),headers=headers)
        try:
            urllib.request.urlopen(request,timeout=10)
            raise AssertionError('Expected local-session rejection')
        except urllib.error.HTTPError as error:
            assert error.code==expected
    results['invalid_session_rejected']=True; results['foreign_origin_rejected']=True
    for name in ('baseline','lora','scratch'):
        payload={'model':name,'prompt':'Tulis satu kalimat pendek tentang belajar.','temperature':.7,'max_new_tokens':16}
        request=urllib.request.Request(args.url+'/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Local-Token':token})
        with urllib.request.urlopen(request,timeout=180) as response:
            result=json.load(response)
            assert response.status==200 and result['model']==name and isinstance(result['text'],str)
            results['generation'].append({'model':name,'status':200,'output_tokens':result['output_tokens'],'seconds':result['seconds'],'empty':result.get('empty_output',False),'privacy_suppressed':result['suppressed']})
    save_json(args.output,results)
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
