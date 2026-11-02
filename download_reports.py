"""Download approved annual-report PDF links at scale, preserving review metadata.

Inputs:
  report_manifest.csv with company_name,bvd_id,report_url,report_year
  Report URLs must first be reviewed against official issuer sources.
Outputs:
  reports/<bvd_id>.pdf (verified PDF bytes, where downloadable)
  download_log.csv (every company including errors and missing URLs)

No proxy bypass, guessed URLs, or automatic acceptance of search hits.
"""
import argparse, csv, os, re, time
from pathlib import Path
from urllib.parse import urlparse
import requests
import pymupdf

ROOT=Path(__file__).resolve().parent
FIELDS=['company_name','bvd_id','report_url','report_year','download_status','pdf_pages','pdf_filename','error']

def save(rows, filename):
    dest=Path(filename)
    tmp=dest.with_suffix(dest.suffix+'.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
    os.replace(tmp,dest)

def validate_pdf(path):
    with path.open('rb') as f:
        if f.read(5)!=b'%PDF-':
            raise ValueError('Response is not a PDF')
    with pymupdf.open(path) as pdf:
        if len(pdf)<2: raise ValueError('PDF has fewer than two pages')
        return len(pdf)

def download(url,target,timeout,max_bytes):
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.netloc:
        raise ValueError('Only reviewed HTTPS PDF URLs are accepted')
    temp=target.with_suffix('.pdf.part')
    try:
        with requests.get(url,stream=True,timeout=(15,timeout),headers={
            'User-Agent':'Mozilla/5.0 (compatible; academic report downloader)'
        }) as response:
            response.raise_for_status()
            total=0
            with temp.open('wb') as output:
                for chunk in response.iter_content(256*1024):
                    if not chunk: continue
                    total+=len(chunk)
                    if total>max_bytes: raise ValueError('PDF exceeds file size limit')
                    output.write(chunk)
        pages=validate_pdf(temp)
        os.replace(temp,target)
        return pages
    finally:
        if temp.exists(): temp.unlink()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',default=str(ROOT/'report_manifest.csv'))
    p.add_argument('--out',default=str(ROOT/'download_log.csv'))
    p.add_argument('--limit',type=int,default=0)
    p.add_argument('--timeout',type=int,default=45)
    p.add_argument('--max-mb',type=int,default=80)
    args=p.parse_args()
    with open(args.manifest,newline='',encoding='utf-8-sig') as f:
        entries=list(csv.DictReader(f))
    if not entries or not {'company_name','bvd_id','report_url','report_year'}.issubset(entries[0]):
        p.error('Manifest must have company_name,bvd_id,report_url,report_year')
    ids=[r['bvd_id'].strip() for r in entries]
    if len(ids)!=len(set(ids)) or not all(ids): p.error('Duplicate or missing BvD IDs')
    if args.limit<0: p.error('--limit must be nonnegative')
    if args.limit: entries=entries[:args.limit]
    report_dir=ROOT/'reports'
    report_dir.mkdir(exist_ok=True)
    results=[]
    for i,row in enumerate(entries,1):
        out={k:row.get(k,'') for k in FIELDS}
        ident=re.sub(r'[^a-zA-Z0-9_-]','_',row['bvd_id'].strip())
        filename=ident+'.pdf'
        target=report_dir/filename
        out['pdf_filename']=filename
        try:
            if target.exists():
                out['pdf_pages']=validate_pdf(target)
                out['download_status']='already_present'
            elif not row.get('report_url','').strip():
                out['download_status']='missing_approved_url'
            elif not re.fullmatch(r'20\d{2}(?:[/-](?:20)?\d{2})?',str(row.get('report_year','')).strip()):
                out['download_status']='missing_validated_year'
            else:
                out['pdf_pages']=download(row['report_url'].strip(),target,args.timeout,args.max_mb*1024*1024)
                out['download_status']='downloaded_pdf'
        except Exception as exc:
            out['download_status']='error'
            out['error']=str(exc)[:300]
        results.append(out)
        save(results,args.out)
        print(f"[{i}/{len(entries)}] {row['company_name']}: {out['download_status']} {out['error']}",flush=True)
        if out['download_status']=='downloaded_pdf': time.sleep(1)
    print('Downloaded:',sum(x['download_status']=='downloaded_pdf' for x in results),
          'Existing:',sum(x['download_status']=='already_present' for x in results),
          'Missing/blocked:',sum(x['download_status'] not in ('downloaded_pdf','already_present') for x in results))
    print('Audit log:',args.out)

if __name__=='__main__': main()
