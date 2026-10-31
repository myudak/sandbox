"""Inspect PDF text, metadata, links, fonts and page geometry; render every page."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from pypdf import PdfReader
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]


def verify(pdf,renderer):
    reader=PdfReader(pdf)
    assert reader.metadata.author=='Muchammad Yuda Tri Ananda'
    text='\n'.join(page.extract_text() or '' for page in reader.pages)
    assert 'Muchammad Yuda Tri Ananda' in text and 'yuda@myudak.com' in text
    for phrase in ('Working draft','results draft','Author information','TODO','??','being finalized'):
        assert phrase not in text,phrase
    assert '361947826' in text and '1,280' in text and '120' in text
    assert all(abs(float(page.mediabox.width)-595.276)<2 and abs(float(page.mediabox.height)-841.89)<2 for page in reader.pages)
    links=[];fonts={};page_stats=[]
    for i,page in enumerate(reader.pages,1):
        content=page.extract_text() or ''
        assert len(content)>80,f'Potential blank page {i}'
        page_stats.append({'page':i,'text_characters':len(content)})
        for reference in page.get('/Annots',[]):
            annotation=reference.get_object();action=annotation.get('/A',{})
            if action and action.get('/URI'):links.append(str(action['/URI']))
        for ref in page.get('/Resources',{}).get('/Font',{}).values():
            font=ref.get_object()
            for item in font.get('/DescendantFonts',[font]):
                obj=item.get_object();descriptor=obj.get('/FontDescriptor')
                if descriptor:
                    descriptor=descriptor.get_object()
                    fonts[str(obj.get('/BaseFont'))]=any(key in descriptor for key in ('/FontFile','/FontFile2','/FontFile3'))
    assert 'mailto:yuda@myudak.com' in links
    assert any('361947826' in uri for uri in links)
    assert fonts and all(fonts.values()),fonts
    pdf_hash=hashlib.sha256(pdf.read_bytes()).hexdigest()
    qa=ROOT/'tmp/pdfs/qa'/pdf_hash[:12];qa.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(renderer),'-r','110','-png',str(pdf),str(qa/'page')],check=True,capture_output=True)
    pages=sorted(qa.glob('page-*.png'),key=lambda p:int(p.stem.rsplit('-',1)[1]))
    assert len(pages)==len(reader.pages)
    width=360;height=530;columns=3
    canvas=Image.new('RGB',(columns*width,math.ceil(len(pages)/columns)*height),'#e7e9eb');draw=ImageDraw.Draw(canvas)
    for i,path in enumerate(pages):
        with Image.open(path) as image:
            image=image.convert('RGB');image.thumbnail((width-14,height-30))
            x=(i%columns)*width+(width-image.width)//2;y=(i//columns)*height+22
            canvas.paste(image,(x,y))
        draw.text(((i%columns)*width+12,(i//columns)*height+5),f'Page {i+1}',fill='black')
    canvas.save(qa/'contact_sheet.png')
    report={'status':'automated_checks_passed','pdf':str(pdf),'pdf_sha256':pdf_hash,'qa_directory':str(qa),
        'author':reader.metadata.author,'pages':len(reader.pages),'embedded_fonts':fonts,'uri_links':links,
        'page_statistics':page_stats,'source_sha256':hashlib.sha256((ROOT/'paper/main.tex').read_bytes()).hexdigest(),
        'rasterized_pages':len(pages),'visual_review':'pending manual inspection'}
    (ROOT/'research/PDF_RELEASE_QA.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pages':len(reader.pages),'fonts_embedded':len(fonts),'links':len(links),'contact_sheet':str(qa/'contact_sheet.png')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('pdf',type=Path);parser.add_argument('--renderer',type=Path,required=True)
    args=parser.parse_args();verify(args.pdf.resolve(),args.renderer.resolve())
