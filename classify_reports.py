"""Rate annual-report PDF design with a *local* Ollama vision model.
Classification does not access company profit data.
"""
import argparse, base64, csv, json, re, time
from pathlib import Path
from urllib.parse import urlparse
import fitz
import requests

ROOT=Path(__file__).resolve().parent
REPORTS=ROOT/'reports'
RUBRIC='''Judge only the visual design (typography, layout, photography,
visual storytelling, charts and brand consistency), not profits, company
size, industry, or report length. 1=plain text/tables; 2=basic design;
3=professional balanced design; 4=polished editorial graphics;
5=exceptional magazine-quality art direction. Use only sampled pages.'''

def chat(text, images=None):
    msg={'role':'user','content':text}
    if images: msg['images']=images
    r=requests.post('http://127.0.0.1:11434/api/chat',json={
      'model':'gemma3:4b','stream':False,'messages':[msg],
      'options':{'temperature':0}},timeout=360)
    r.raise_for_status()
    return r.json()['message']['content']

def approve():
    definition=chat('Describe YOUR definition of visual fanciness for annual reports on a 1–5 scale. Confirm you ignore profit and firm size. Compare with this rubric: '+RUBRIC)
    (ROOT/'fanciness_definition.txt').write_text(definition+'\n\nResearcher rubric:\n'+RUBRIC,encoding='utf-8')
    print('\nMODEL DEFINITION OF FANCY:\n'+definition)
    if input('\nRead and approve this definition? Type YES: ').strip()!='YES':
        raise SystemExit('Not approved; no reports scored.')

def download(url, path):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.netloc: raise ValueError('Direct HTTPS PDF URL required')
    path.parent.mkdir(exist_ok=True)
    with requests.get(url,stream=True,timeout=120,headers={'User-Agent':'Mozilla/5.0'}) as r:
        r.raise_for_status()
        data=bytearray()
        for chunk in r.iter_content(262144):
            data.extend(chunk)
            if len(data)>80_000_000: raise ValueError('PDF too large')
    if not data.startswith(b'%PDF'): raise ValueError('URL did not return PDF')
    path.write_bytes(data)

def score_pdf(path):
    with fitz.open(path) as doc:
        if not len(doc): raise ValueError('Empty PDF')
        ids=sorted(set(min(x,len(doc)-1) for x in [0,2,5,9]))
        imgs=[base64.b64encode(doc[i].get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).tobytes('png')).decode() for i in ids]
    reply=chat('Score this report using the rubric: '+RUBRIC+' Return ONLY JSON: {"fanciness": 1, "rationale": "design-based explanation"}. The integer must be between 1 and 5.',imgs)
    match=re.search(r'\{[\s\S]*\}',reply)
    if not match: raise ValueError('No JSON result: '+reply[:100])
    result=json.loads(match.group(0))
    val=result.get('fanciness')
    if type(val)!=int or not 1<=val<=5: raise ValueError('Invalid score')
    return val,str(result.get('rationale','')),','.join(str(i+1) for i in ids)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',default=str(ROOT/'report_manifest.csv'))
    ap.add_argument('--limit',type=int,default=0)
    args=ap.parse_args()
    with open(args.manifest,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    approve()
    output=[]; complete=0
    for row in rows:
        ident=row['bvd_id']; url=row.get('report_url','').strip()
        path=REPORTS/(re.sub(r'[^a-zA-Z0-9_-]','_',ident)+'.pdf')
        entry={**row,'fanciness':'','pages_reviewed':'','rationale':'','status':''}
        try:
            if not path.is_file():
                if not url: raise ValueError('Missing report URL and PDF')
                download(url,path)
            val,rationale,pages=score_pdf(path)
            entry.update(fanciness=val,rationale=rationale,pages_reviewed=pages,status='scored')
            complete+=1
            print(ident,row['company_name'],val,pages)
        except Exception as ex:
            entry['status']='error: '+str(ex)[:160]
            print(ident,entry['status'])
        output.append(entry)
        if args.limit and complete>=args.limit: break
        time.sleep(0.3)
    with (ROOT/'scores.csv').open('w',encoding='utf-8',newline='') as f:
        fields=list(dict.fromkeys([*rows[0].keys(),'fanciness','pages_reviewed','rationale','status'])) if rows else ['bvd_id','fanciness','status']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(output)
    print('Scored',complete,'reports. Results saved locally to scores.csv')

if __name__=='__main__':main()
