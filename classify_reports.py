"""Rate annual-report PDF design with a *local* Ollama vision model.
Classification does not access company profit data.
"""
import argparse, base64, csv, json, re, time
from pathlib import Path
from urllib.parse import urlparse
import pymupdf
import requests

ROOT=Path(__file__).resolve().parent
REPORTS=ROOT/'reports'
RUBRIC='''Evaluate visual fanciness ONLY. Ignore company profit, size, brand prestige and industry.
Assess five design dimensions, each using integers 1 (plain) through 5 (exceptional):
graphic_design (25%): visual hierarchy, color, composition and graphic coherence;
typography (20%): readable, intentional typographic treatment (ordinary fonts can score highly);
photography_illustrations (20%): visual quality and integration, not a requirement for stock-vs-custom artwork;
charts_visualization (15%): clarity and thoughtful visual communication;
layout_storytelling (20%): cohesive layout, pacing and narrative.
Do not expect motion, interactivity, or animations in a static PDF.
An absent visual element should be judged by the quality and suitability of the actual design,
not automatically scored 1. Base all scores on the inspected pages, not assumptions.'''

def chat(text, images=None, timeout=180):
    msg={'role':'user','content':text}
    if images: msg['images']=images
    r=requests.post('http://127.0.0.1:11434/api/chat',json={
      'model':'gemma3:4b','stream':False,'messages':[msg],
      'options':{'temperature':0,'num_predict':450}},timeout=timeout)
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
    # Process only two lower-resolution pages per request to avoid oversized prompts.
    # The same page-selection rule is applied to every company.
    with pymupdf.open(path) as doc:
        if not len(doc): raise ValueError('Empty PDF')
        ids=sorted(set(min(x,len(doc)-1) for x in [0,5]))
        imgs=[]
        for i in ids:
            page=doc[i]
            pix=page.get_pixmap(matrix=pymupdf.Matrix(0.65,0.65),alpha=False)
            imgs.append(base64.b64encode(pix.tobytes('jpeg',jpg_quality=65)).decode('ascii'))
    prompt=('Evaluate these annual report page images using the rubric: '+RUBRIC+
        ' Respond as JSON only, with integer fields graphic_design, typography, '+
        'photography_illustrations, charts_visualization, layout_storytelling '+
        'from 1 to 5, and a short rationale. Do not compute a final score.')
    reply=chat(prompt,imgs,timeout=180)
    try:
        result=json.loads(reply)
    except json.JSONDecodeError:
        match=re.search(r'\{[\s\S]*?\}',reply)
        if not match: raise ValueError('Model returned no JSON: '+reply[:100])
        result=json.loads(match.group())
    weights={'graphic_design':.25,'typography':.20,'photography_illustrations':.20,
             'charts_visualization':.15,'layout_storytelling':.20}
    for key in weights:
        if type(result.get(key))!=int or not 1<=result[key]<=5:
            raise ValueError('Invalid dimension score for '+key)
    weighted=sum(result[k]*v for k,v in weights.items())
    score=max(1,min(5,int(weighted+0.5)))
    return score,round(weighted,3),str(result.get('rationale','')),','.join(str(i+1) for i in ids),{k:result[k] for k in weights}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',default=str(ROOT/'report_manifest.csv'))
    ap.add_argument('--limit',type=int,default=0)
    args=ap.parse_args()
    with open(args.manifest,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    if args.limit < 0: raise ValueError('--limit must be zero or positive')
    if args.limit: rows=rows[:args.limit]
    approve()
    output=[]; complete=0
    for row in rows:
        ident=row['bvd_id']; url=row.get('report_url','').strip()
        path=REPORTS/(re.sub(r'[^a-zA-Z0-9_-]','_',ident)+'.pdf')
        entry={**row,'fanciness':'','weighted_score':'','graphic_design':'','typography':'','photography_illustrations':'','charts_visualization':'','layout_storytelling':'','pages_reviewed':'','rationale':'','status':''}
        try:
            if not path.is_file():
                if not url: raise ValueError('Missing report URL and PDF')
                download(url,path)
            val,weighted,rationale,pages,dimensions=score_pdf(path)
            entry.update(fanciness=val,weighted_score=weighted,**dimensions,rationale=rationale,pages_reviewed=pages,status='scored')
            complete+=1
            print(ident,row['company_name'],val,pages)
        except Exception as ex:
            entry['status']='error: '+str(ex)[:160]
            print(ident,entry['status'])
        output.append(entry)
        # Write progress after every attempt, including failures.
        with (ROOT/'scores.csv').open('w',encoding='utf-8',newline='') as f:
            fields=list(dict.fromkeys([*rows[0].keys(),'fanciness','weighted_score','graphic_design','typography','photography_illustrations','charts_visualization','layout_storytelling','pages_reviewed','rationale','status']))
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(output)
        time.sleep(0.3)
    with (ROOT/'scores.csv').open('w',encoding='utf-8',newline='') as f:
        fields=list(dict.fromkeys([*rows[0].keys(),'fanciness','weighted_score','graphic_design','typography','photography_illustrations','charts_visualization','layout_storytelling','pages_reviewed','rationale','status'])) if rows else ['bvd_id','fanciness','status']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(output)
    print('Attempted',len(output),'companies; scored',complete,'reports. Results saved locally to scores.csv')

if __name__=='__main__':main()
