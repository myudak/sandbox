"""Isolated browser QA of the local app; screenshots contain no private samples."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--url',default='http://127.0.0.1:8765'); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--channel',default='msedge'); args=parser.parse_args()
    if urlparse(args.url).hostname not in {'127.0.0.1','localhost'}:
        raise ValueError('Only the local playground may be tested')
    args.output.mkdir(parents=True,exist_ok=True)
    results={}; errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel=args.channel,headless=True)
        try:
            desktop=browser.new_page(viewport={'width':1400,'height':1100},device_scale_factor=1)
            desktop.on('pageerror',lambda error:errors.append(type(error).__name__))
            desktop.goto(args.url,wait_until='networkidle')
            expect(desktop.locator('#model option')).to_have_count(3)
            labels=desktop.locator('#model').text_content()
            results['utf8_labels_correct']='\u00c2' not in labels and '\ufffd' not in labels
            results['desktop_no_horizontal_overflow']=desktop.evaluate('() => document.documentElement.scrollWidth<=window.innerWidth')
            desktop.screenshot(path=str(args.output/'playground-desktop.png'),full_page=True)
            mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
            mobile.goto(args.url,wait_until='networkidle')
            expect(mobile.locator('#model option')).to_have_count(3)
            results['mobile_no_horizontal_overflow']=mobile.evaluate('() => document.documentElement.scrollWidth<=window.innerWidth')
            mobile.screenshot(path=str(args.output/'playground-mobile.png'),full_page=True)
            desktop.locator('#prompt').fill('Jawab angka saja: 2 + 2 =')
            desktop.locator('#send').click()
            expect(desktop.locator('#state')).to_have_text('Complete',timeout=180000)
            body=desktop.locator('.bubble.model').last.evaluate("el=>Array.from(el.childNodes).filter(n=>n.nodeType===3).map(n=>n.textContent).join('')")
            results['baseline_ui_math_correct']=bool(re.search(r'\b4\b',body))
            desktop.goto(args.url+'/#scratch',wait_until='networkidle')
            desktop.reload(wait_until='networkidle')
            expect(desktop.locator('#mode')).to_have_text('SENTENCE FINISHER')
            expect(desktop.locator('#send')).to_have_text('Continue ↗')
            desktop.screenshot(path=str(args.output/'sentence-finisher-desktop.png'),full_page=True)
            mobile.goto(args.url+'/#scratch',wait_until='networkidle')
            expect(mobile.locator('#mode')).to_have_text('SENTENCE FINISHER')
            mobile.screenshot(path=str(args.output/'sentence-finisher-mobile.png'),full_page=True)
            results['scratch_sentence_mode']=True
            results['scratch_mobile_no_horizontal_overflow']=mobile.evaluate('() => document.documentElement.scrollWidth<=window.innerWidth')
            prefix='hari ini aku '
            desktop.locator('#prompt').fill(prefix)
            desktop.locator('#send').click()
            expect(desktop.locator('.completion')).to_have_count(1,timeout=180000)
            expect(desktop.locator('.completion .prefix')).to_have_text(prefix)
            expect(desktop.locator('#prompt')).to_have_value(prefix)
            results['scratch_live_completion_rendered']=desktop.locator('.completion .continuation,.completion .notice').count()==1
            # Synthetic deterministic response tests composition even if the real model emits EOS.
            suffix='<b>synthetic continuation</b>'
            desktop.route('**/api/generate',lambda route:route.fulfill(json={'model':'scratch','text':suffix,'empty_output':False,'suppressed':False,'output_tokens':4,'input_tokens':5,'seconds':.01}))
            desktop.locator('#send').click()
            expect(desktop.locator('.completion')).to_have_count(2)
            expect(desktop.locator('.completion').last.locator('.continuation')).to_have_text(suffix)
            results['scratch_text_rendered_safely']=desktop.locator('.continuation b').count()==0
            desktop.locator('.use-prefix').last.click()
            expect(desktop.locator('#prompt')).to_have_value(prefix+suffix)
            results['scratch_keep_writing_preserves_text']=True
            results['page_errors']=len(errors)
            assert all(value for key,value in results.items() if key!='page_errors')
            assert not errors
        finally:
            browser.close()
    (args.output.parent/'BROWSER_TEST.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results))

if __name__=='__main__':main()
