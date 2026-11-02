"""Fetch annual-report PDFs from Danish Business Authority public filings search.

Usage:
 python collect_cvr_reports.py --checklist Assignment5_CVR_139_Report_Collection_Checklist.csv

Only Danish 8-digit CVR numbers; looks for full-year 2025 reports.
Uses the public Erhvervsstyrelsen distribution search endpoint, NOT a paid API.
URLs and publication metadata are recorded; PDF bytes are validated.
No access-control bypass: HTTP failures, missing filings and unverified documents are logged.
Never commit CVR checklist, PDFs, or Orbis-linked research data to public GitHub.
"""
import argparse,csv,json,re,os,time,datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
import pymupdf

ROOT=Path(__file__).resolve().parent
BASE='https://distribution.virk.dk/offentliggoerelser/_search'
HEADERS={'User-Agent':'AcademicAnnualReportResearch/1.0 (student project; contact via institution)','Accept':'application/json'}
COLS=['company_name','bvd_id','cvr_number','status','period_start','period_end','published_at','document_type','document_url','pdf_pages','error']
def dig(obj,key):
    if isinstance(obj,dict):
        if key in obj and obj[key] not in (None,''):yield obj[key]
        for v in obj.values():yield from dig(v,key)
    elif isinstance(obj,list):
        for x in obj:yield from dig(x,key)

def dateonly(v):
    if isinstance(v,str) and re.match(r'^20\\d\\d-\\d\\d-\\d\\d',v):return v[:10]
    return ''

def pick_doc(hit):
    src=hit.get('_source',hit)
    # Common shape: offentliggoerelse with dokumenter (dokumentType + dokumentUrl).
    urlpairs=[]
    def walk(x):
        if isinstance(x,dict):
            url=x.get('dokumentUrl') or x.get('documentUrl') or x.get('pdf_url') or ''
            typ=str(x.get('dokumentType') or x.get('documentType') or '')
            if isinstance(url,str) and url:urlpairs.append((url,typ))
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(src)
    def rank(pair):
        u,t=pair
        lu=u.lower();lt=t.lower()
        return (int('pdf' in lt or urlparse(lu).path.endswith('.pdf')),int('regnskaber.virk.dk' in lu),int('xml' not in lt))
    urlpairs.sort(key=rank,reverse=True)
    return urlpairs[0] if urlpairs else ('','')

def search(session,cvr,timeout):
    # Public Elasticsearch query; query includes only CVR, no company financial fields.
    resp=session.get(BASE,params={'q':'cvrNummer:'+cvr,'size':'60'},headers=HEADERS,timeout=timeout)
    resp.raise_for_status()
    data=resp.json()
    return data.get('hits',{}).get('hits',[])

def choose(hits,year):
    eligible=[]
    for hit in hits:
        src=hit.get('_source',hit)
        start=next((dateonly(x) for x in dig(src,'startDato') if dateonly(x)),'')
        end=next((dateonly(x) for x in dig(src,'slutDato') if dateonly(x)),'')
        published=next((str(x) for x in dig(src,'offentliggoerelsesTidspunkt')),'')
        url,doctype=pick_doc(hit)
        if not end or not end.startswith(str(year)) or not url:continue
        if start:
            try:
                if (datetime.date.fromisoformat(end)-datetime.date.fromisoformat(start)).days<340:continue
            except ValueError:continue
        eligible.append({'period_start':start,'period_end':end,
                         'published_at':published,'document_type':doctype,'document_url':url})
    eligible.sort(key=lambda r:(r['period_end'],r['published_at']),reverse=True)
    return eligible[0] if eligible else None

def pdf_download(session,url,dest,timeout,limit_mb):
    if url.startswith('http://regnskaber.virk.dk/'):
        url='https://'+url[len('http://'):]
    p=urlparse(url)
    if p.scheme!='https' or p.hostname not in ('regnskaber.virk.dk','datacvr.virk.dk'):
        raise ValueError('Unexpected report document host: '+str(p.hostname))
    tmp=dest.with_suffix('.pdf.part')
    try:
        with session.get(url,headers=HEADERS,stream=True,timeout=timeout) as resp:
            resp.raise_for_status()
            size=0
            with tmp.open('wb') as f:
                for chunk in resp.iter_content(1024*256):
                    if not chunk:continue
                    size+=len(chunk)
                    if size>limit_mb*1024*1024:raise ValueError('File exceeds max size')
                    f.write(chunk)
        with tmp.open('rb') as f:
            if f.read(5)!=b'%PDF-':raise ValueError('Document is not PDF')
        with pymupdf.open(tmp) as pdf:
            pages=len(pdf)
            if pages<2:raise ValueError('Document fewer than 2 pages')
        os.replace(tmp,dest)
        return pages
    finally:
        if tmp.exists():tmp.unlink()

def write_log(rows,path):
    tmp=path.with_suffix('.csv.tmp')
    with tmp.open('w',encoding='utf-8',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=COLS,extrasaction='ignore')
        wr.writeheader();wr.writerows(rows)
    os.replace(tmp,path)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--checklist',required=True)
    p.add_argument('--out',default=str(ROOT/'cvr_download_log.csv'))
    p.add_argument('--year',type=int,default=2025)
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--timeout',type=int,default=30)
    p.add_argument('--max-mb',type=int,default=80)
    p.add_argument('--delay',type=float,default=1.0)
    args=p.parse_args()
    with open(args.checklist,encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)>0 and {'bvd_id','cvr_number','company_name'}.issubset(rows[0])
    reportdir=ROOT/'reports';reportdir.mkdir(exist_ok=True)
    results=[]
    with requests.Session() as sess:
        for i,row in enumerate(rows[:args.limit or len(rows)],1):
            cvr=(row.get('cvr_number') or '').strip()
            ident=re.sub(r'[^a-zA-Z0-9_-]','_',row['bvd_id'])
            target=reportdir/(ident+'.pdf')
            out={k:row.get(k,'') for k in COLS}
            try:
                if target.exists():
                    with pymupdf.open(target) as pdf:
                        out['pdf_pages']=len(pdf)
                    out['status']='already_present'
                elif not re.fullmatch(r'\\d{8}',cvr):
                    out['status']='not_danish_cvr'
                else:
                    hits=search(sess,cvr,args.timeout)
                    doc=choose(hits,args.year)
                    if not doc:
                        out['status']='no_matching_full_year_report'
                    else:
                        out.update(doc)
                        out['pdf_pages']=pdf_download(sess,doc['document_url'],target,args.timeout,args.max_mb)
                        out['status']='downloaded'
            except Exception as exc:
                out['status']='error'
                out['error']=str(exc)[:350]
            results.append(out)
            write_log(results,Path(args.out))
            print(f"[{i}/{min(len(rows),args.limit or len(rows))}] {row['company_name']}: {out['status']} {out.get('error','')}",flush=True)
            if out['status'] not in ('already_present','not_danish_cvr'):
                time.sleep(max(0,args.delay))
    print('Status totals:')
    from collections import Counter
    print(Counter(x['status'] for x in results))
    print('CVR report lookup log:',args.out)
    print('Check downloaded PDFs are the correct company and annual report BEFORE research scoring.')
if __name__=='__main__':main()
